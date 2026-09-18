"""Trilloka Architect Engine V7 API gateway with Business Type + Journey + Context scoring and tiered paid-plan entitlements.

Scanner compatibility
---------------------
* Public scan routes remain POST /api/audit and POST /api/scan.
* Existing request fields remain accepted.
* Existing successful-response keys remain present.
* New purchase/pass/report-access fields are additive.

Commercial access
-----------------
* Free preview: one successful scan per IP/device per rolling 24h. Public score,
  SEO/performance surface metrics, modeled competitor-gap proxy, and revenue-exposure
  estimate remain visible; detailed leak identities and remediation are locked.
* $350 Essential: up to Top 4 verified revenue findings + 3-angle fixes, full 50-check data,
  2 scans/day for 30 days.
* $550 Advanced: up to Top 8 verified revenue findings + 3-angle fixes + 14-day roadmap,
  full 50-check data, 3 scans/day for 30 days, one 15-minute guidance call.
* $850 Architect: up to Top 10 verified revenue findings + 3-angle fixes + 30-day roadmap,
  full 50-check data, 4 scans/day for 30 days, two 15-minute guidance calls and a
  15-hour email-support response target.
* Paid access is bound to email + purchased domain + a secure purchase access pass.
"""

from __future__ import annotations

import asyncio
import copy
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import uvicorn
from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Request as FastAPIRequest, Response
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr

from admin_auth import AdminAuthError, AdminAuthManager
from hybrid_scanner import HybridScanner
from network_security import NetworkTargetError, validate_public_http_url
from scan_access import AccessDenied, AccessTicket, PLAN_CATALOG, ScanAccessManager
from scorer import RevenueScorer
from architect_review import build_architect_review_queue
from learning_intelligence import learning_memory

try:
    from report_engine import ReportGenerator

    reporter = ReportGenerator()
    REPORT_ENGINE_AVAILABLE = True
except Exception as exc:
    print(f"[Report Engine] Import failed: {exc}")
    reporter = None
    REPORT_ENGINE_AVAILABLE = False


def _configure_plan_catalog() -> None:
    """Align report depth/roadmap access with the current three paid tiers.

    scan_access owns entitlement validation and quota accounting; this gateway only
    adjusts additive report-delivery metadata on the shared catalog object. Existing
    plan IDs, prices, scan quotas, expiry behavior and guidance-call fields remain intact.
    """
    overrides = {
        "essential_350": {"remediation_limit": 4, "roadmap_days": 0},
        "advanced_550": {"remediation_limit": 8, "roadmap_days": 14},
        "architect_850": {"remediation_limit": 10, "roadmap_days": 30},
    }
    for plan_id, values in overrides.items():
        plan = PLAN_CATALOG.get(plan_id)
        if isinstance(plan, dict):
            plan.update(values)


_configure_plan_catalog()


_ALLOWED_ORIGINS = [
    item.strip() for item in os.environ.get(
        "TRILLOKA_ALLOWED_ORIGINS", "https://trilloka.com,https://www.trilloka.com"
    ).split(",") if item.strip()
]


def _env_int(name: str, default: int, minimum: int = 1) -> int:
    try:
        return max(minimum, int(os.environ.get(name, str(default))))
    except Exception:
        return default


_SELF_SCAN_URL = os.environ.get("TRILLOKA_SELF_SCAN_URL", "https://trilloka.com/").strip() or "https://trilloka.com/"
_SELF_SNAPSHOT_FILE = os.environ.get("TRILLOKA_SELF_SNAPSHOT_FILE", "trilloka_30day_audit_snapshot.json").strip() or "trilloka_30day_audit_snapshot.json"
_SELF_SNAPSHOT_MAX_AGE_DAYS = _env_int("TRILLOKA_SELF_SNAPSHOT_MAX_AGE_DAYS", 30)
_PROTECTED_DOMAIN_ROOTS = tuple(
    sorted({
        item.strip().lower().rstrip(".")
        for item in os.environ.get("TRILLOKA_PROTECTED_DOMAINS", "trilloka.com").split(",")
        if item.strip()
    })
) or ("trilloka.com",)

app = FastAPI(
    title="Trilloka Architect Engine API",
    description="Evidence-weighted Revenue Readiness Diagnostic, local competitor benchmark & tiered report gateway",
    version="7.5.3",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-Trilloka-System-Key", "X-Trilloka-Admin-Session", "X-Trilloka-Device-ID"],
    expose_headers=["X-Trilloka-Access-Reason", "Retry-After"],
)

scanner = HybridScanner()
scorer = RevenueScorer()
access_manager = ScanAccessManager()
admin_auth = AdminAuthManager()


# ---------------------------------------------------------------------------
# V7.3.1 methodology-boundary helpers
# ---------------------------------------------------------------------------
# Customer reports should explain *what* Trilloka verified and *why* it matters
# without shipping the private weighting matrix, calibration anchors, inference
# signals or tie-break logic.  Admin/Vault data remains complete for debugging,
# reproducibility and Architect review.  Public API keys stay backward-compatible.

def _public_architecture_profile(profile: Dict[str, Any] | None) -> Dict[str, Any]:
    src = profile if isinstance(profile, dict) else {}
    safe_secondary = []
    for item in src.get("secondary_journeys") or []:
        if isinstance(item, dict):
            safe_secondary.append({
                "journey_model": item.get("journey_model"),
                "journey_label": item.get("journey_label"),
                "relative_strength": item.get("relative_strength"),
            })
        elif item:
            safe_secondary.append(item)
    return {
        "model_basis": "business_type_journey_context",
        "business_type": src.get("business_type") or src.get("vertical") or "general",
        "business_type_label": src.get("business_type_label") or "General / Unresolved Business",
        "business_type_confidence": src.get("business_type_confidence"),
        "business_type_source": src.get("business_type_source"),
        "business_subtype": src.get("business_subtype"),
        "business_subtype_label": src.get("business_subtype_label"),
        "business_subtype_confidence": src.get("business_subtype_confidence"),
        "business_subtype_role": "inspection_modifier",
        "journey_model": src.get("journey_model") or "general",
        "journey_label": src.get("journey_label") or "General / Unresolved Journey",
        "confidence": src.get("confidence"),
        "provisional": bool(src.get("provisional")),
        "journey_resolved": bool(src.get("journey_resolved")) if src.get("journey_resolved") is not None else not bool(src.get("provisional")),
        "primary_conversion": src.get("primary_conversion"),
        "secondary_conversions": list(src.get("secondary_conversions") or []),
        "secondary_journeys": safe_secondary,
        "context_tags": list(src.get("context_tags") or []),
        "context_labels": list(src.get("context_labels") or []),
        # Explicitly disclose the visibility boundary instead of silently removing data.
        "methodology_detail": "public_summary",
        "private_inference_signals_withheld": True,
    }


def _public_score_formula(formula: Dict[str, Any] | None) -> Dict[str, Any]:
    src = formula if isinstance(formula, dict) else {}
    # Keep customer-level score transparency (the three earned banks and final
    # public scale) without exposing rule multipliers, blueprint anchors or the
    # exact calibration function.  Internal/Vault reports still retain all fields.
    return {
        "method": "Trilloka Commercial Architecture Methodology",
        "foundation_layer_score": src.get("foundation_layer_score"),
        "foundation_layer_max": src.get("foundation_layer_max"),
        "revenue_user_architecture_score": src.get("revenue_user_architecture_score"),
        "revenue_user_architecture_max": src.get("revenue_user_architecture_max"),
        "elite_architecture_score": src.get("elite_architecture_score"),
        "elite_architecture_max": src.get("elite_architecture_max"),
        "canonical_three_layer_score": src.get("canonical_three_layer_score"),
        "unknown_policy": src.get("unknown_policy") or "UNKNOWN is never treated as a failure.",
        "weighting_policy": "Business type, customer journey, context, evidence strength and commercial relevance influence importance; exact proprietary weights and calibration constants are not published.",
        "proprietary_calibration_withheld": True,
    }


def _public_scoring_ledger(rows: List[Dict[str, Any]] | None) -> List[Dict[str, Any]]:
    safe: List[Dict[str, Any]] = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        safe.append({
            "rule_key": row.get("rule_key"),
            "finding": row.get("leak_name") or row.get("checkpoint_name") or row.get("finding"),
            "family": row.get("family"),
            "confidence": row.get("confidence"),
            "finding_type": row.get("finding_type") or "VERIFIED_FINDING",
            "priority": row.get("priority"),
            "methodology_detail": "customer_safe",
        })
    return safe


def _public_checkpoint_basis(rows: List[Dict[str, Any]] | None) -> List[Dict[str, Any]]:
    safe: List[Dict[str, Any]] = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        safe.append({
            "id": row.get("id"),
            "check": row.get("check"),
            "status": row.get("status"),
            "category": row.get("category"),
            "evidence": copy.deepcopy(row.get("evidence")),
            "reason": row.get("reason"),
            "customer_note": row.get("customer_note"),
            "business_type": row.get("business_type"),
            "journey_model": row.get("journey_model"),
            "context_tags": list(row.get("context_tags") or []),
            "analysis_layer": row.get("analysis_layer"),
            "unknown_reason_code": row.get("unknown_reason_code"),
            "methodology_detail": "customer_safe",
        })
    return safe


def _public_analysis_layers(layers: Dict[str, Any] | None) -> Dict[str, Any]:
    src = layers if isinstance(layers, dict) else {}
    safe: Dict[str, Any] = {}
    for key, value in src.items():
        if not isinstance(value, dict):
            continue
        safe[key] = {
            "layer_score": value.get("layer_score"),
            "layer_max": value.get("layer_max"),
            "status": value.get("status"),
            "summary": value.get("summary") or value.get("note"),
        }
    return safe


def _public_finding(item: Dict[str, Any]) -> Dict[str, Any]:
    # Preserve everything required to understand and implement a finding while withholding
    # private numeric weighting/multiplier fields that are useful mainly for reverse engineering.
    allowed = {
        "rule_key", "checkpoint_id", "checkpoint_name", "leak_name", "title",
        "impact_summary", "finding_type", "report_class", "severity_label", "category",
        "confidence", "priority", "plain_problem", "what_we_found", "where_it_happens",
        "why_it_matters", "financial_effect", "what_should_be_done", "solutions_3_angles",
        "evidence_receipt", "source", "implementation_effort", "financial_mechanism",
        "journey_stage", "family", "customer_note",
    }
    return {key: copy.deepcopy(value) for key, value in item.items() if key in allowed}


def _public_methodology_summary() -> Dict[str, Any]:
    return {
        "name": "Trilloka Commercial Architecture Methodology",
        "principles": [
            "Business-type aware",
            "Customer-journey based",
            "Evidence first",
            "Commercially prioritized",
            "Architect reviewed",
        ],
        "public_explanation": (
            "Trilloka reconstructs the public customer path, checks the decision points and technical evidence around that path, "
            "then prioritizes verified weaknesses according to the business and the outcome the website is trying to create."
        ),
        "private_boundary": (
            "Exact weights, calibration constants, inference signals, ranking equations and recommendation-selection rules are proprietary and remain server-side."
        ),
    }


def _protect_methodology_for_customer(payload: Dict[str, Any]) -> Dict[str, Any]:
    result = copy.deepcopy(payload)
    profile = result.get("architecture_profile") or result.get("business_profile") or {}
    safe_profile = _public_architecture_profile(profile)
    result["architecture_profile"] = safe_profile
    result["business_profile"] = copy.deepcopy(safe_profile)
    if "score_formula" in result:
        result["score_formula"] = _public_score_formula(result.get("score_formula"))
    if "scoring_ledger" in result:
        result["scoring_ledger"] = _public_scoring_ledger(result.get("scoring_ledger"))
    if "full_50_checkpoint_basis" in result:
        result["full_50_checkpoint_basis"] = _public_checkpoint_basis(result.get("full_50_checkpoint_basis"))
    if "analysis_layers" in result:
        result["analysis_layers"] = _public_analysis_layers(result.get("analysis_layers"))
    for key in ("top_10_financial_leaks", "top_8_financial_leaks", "top_6_financial_leaks", "top_5_seo_leaks", "verified_revenue_findings"):
        if isinstance(result.get(key), list):
            result[key] = [_public_finding(item) for item in result.get(key) if isinstance(item, dict)]
    # Internal overlap/cap mechanics are not needed to understand or implement a customer finding.
    if "overlap_adjustments" in result:
        result["overlap_adjustments"] = []
    result["methodology"] = _public_methodology_summary()
    result["methodology_visibility"] = "customer_safe_summary"
    return result


class BusinessClassificationRequest(BaseModel):
    domain: str
    business_name: Optional[str] = ""


class AuditRequest(BaseModel):
    domain: str
    business_name: Optional[str] = ""
    business_type: str = "auto"
    competitor_has_feature: Optional[bool] = None
    email: Optional[EmailStr] = None
    # V7.4 additive learning context. Set by the frontend only when the user is answering
    # Trilloka's own category-confirmation request. It does not alter scoring directly.
    classification_confirmation: bool = False
    classification_previous_candidates: Optional[Dict[str, Any]] = None
    business_subtype: Optional[str] = ""
    # Additive V6.3 field. Free scans do not require it. Paid scans require the pass issued after
    # the verified purchase was activated for this email + domain.
    access_pass: Optional[str] = None
    # Additive. Lets a paid customer intentionally bypass the short accidental-double-submit cache.
    force_refresh: bool = False


class PlanActivationRequest(BaseModel):
    email: EmailStr
    domain: str
    plan_id: str
    purchase_ref: Optional[str] = ""
    # Owner-only options for complimentary/custom-duration grants.
    duration_days_override: Optional[int] = None
    complimentary: bool = False


class PackageGrantRequest(BaseModel):
    """Backward-compatible admin payload name; now grants a domain-specific plan, not 5 credits."""

    email: EmailStr
    domain: str
    plan_id: str = "essential_350"
    purchase_ref: Optional[str] = ""


class CustomerPlanStatusRequest(BaseModel):
    email: EmailStr
    domain: str
    access_pass: str


class EntitlementAdminRef(BaseModel):
    email: EmailStr
    domain: str


class EntitlementUpdateRequest(BaseModel):
    email: EmailStr
    domain: str
    plan_id: Optional[str] = None
    # Positive extends, negative shortens. Keeps the original access pass valid.
    extend_days: Optional[int] = None
    # Unix timestamp. Use instead of extend_days when an exact expiry is desired.
    expires_at: Optional[int] = None
    purchase_ref: Optional[str] = None


class EntitlementDomainChangeRequest(BaseModel):
    email: EmailStr
    domain: str
    new_domain: str


class GuidanceCallAdminRequest(BaseModel):
    email: EmailStr
    domain: str
    # +1 marks a call used; -1 undoes one if needed.
    delta: int = 1


class AdminOtpVerifyRequest(BaseModel):
    code: str


class SelfSnapshotRefreshRequest(BaseModel):
    # Owner-only. False reuses a still-fresh stored snapshot; True forces a real controlled self-scan.
    force: bool = False


class ArchitectReviewResolveRequest(BaseModel):
    review_id: int
    resolution: str
    priority: Optional[str] = ""
    notes: Optional[str] = ""


class LearningPromoteRequest(BaseModel):
    kind: str
    identifier: Any
    label: Optional[str] = ""


class LearningMissRequest(BaseModel):
    domain: str
    business_type: str
    subtype: Optional[str] = ""
    journey_model: Optional[str] = "general"
    finding_type: str
    evidence_page: Optional[str] = ""
    why_it_matters: str
    priority: Optional[str] = ""
    recommended_remedy: Optional[str] = ""


class LearningOutcomeRequest(BaseModel):
    domain: str
    business_type: str
    journey_model: Optional[str] = "general"
    rule_key: str
    outcome_status: str
    technical_note: Optional[str] = ""
    cro_note: Optional[str] = ""
    systems_note: Optional[str] = ""
    verification_note: Optional[str] = ""


class PendingReportFinalizeRequest(BaseModel):
    vault_id: str


def _legacy_admin_key_valid(value: Optional[str]) -> bool:
    """Emergency compatibility only. Disabled by default so human admin access requires emailed OTP."""
    enabled = os.environ.get("TRILLOKA_ALLOW_LEGACY_ADMIN_KEY", "false").strip().lower() in {"1", "true", "yes", "on"}
    if not enabled:
        return False
    configured = os.environ.get("TRILLOKA_ADMIN_API_KEY", "").strip()
    if not configured or not value:
        return False
    import hmac as _hmac
    return _hmac.compare_digest(value.strip(), configured)


def _system_key_valid(value: Optional[str]) -> bool:
    """Machine-to-machine key for a verified payment backend; never used by the owner browser."""
    configured = os.environ.get("TRILLOKA_PLAN_ACTIVATION_KEY", "").strip()
    if not configured or not value:
        return False
    import hmac as _hmac
    return _hmac.compare_digest(value.strip(), configured)


def _admin_session_token(request: FastAPIRequest, header_value: Optional[str] = None) -> Optional[str]:
    return (header_value or request.cookies.get(admin_auth.cookie_name) or "").strip() or None


def _is_admin_session(request: FastAPIRequest, header_value: Optional[str] = None, legacy_key: Optional[str] = None) -> bool:
    token = _admin_session_token(request, header_value)
    return admin_auth.validate_session(token) or _legacy_admin_key_valid(legacy_key)


def _require_admin_session(request: FastAPIRequest, header_value: Optional[str] = None, legacy_key: Optional[str] = None) -> None:
    if _is_admin_session(request, header_value, legacy_key):
        return
    raise HTTPException(status_code=401, detail="Fresh Trilloka owner sign-in required")


def _require_admin_or_system(
    request: FastAPIRequest,
    admin_session: Optional[str] = None,
    system_key: Optional[str] = None,
    legacy_key: Optional[str] = None,
) -> None:
    if _system_key_valid(system_key):
        return
    _require_admin_session(request, admin_session, legacy_key)


def _set_device_cookie(response: Response, device_id: str) -> None:
    secure = os.environ.get("SCAN_COOKIE_SECURE", "true").strip().lower() in {"1", "true", "yes", "on"}
    samesite = os.environ.get("SCAN_COOKIE_SAMESITE", "lax").strip().lower()
    if samesite not in {"lax", "strict", "none"}:
        samesite = "lax"
    response.set_cookie(
        key="trilloka_scan_device",
        value=device_id,
        max_age=60 * 60 * 24 * 365,
        httponly=True,
        secure=secure,
        samesite=samesite,
    )


def _resolve_scan_device_id(http_request: FastAPIRequest, response: Response) -> str:
    """Resolve a stable browser device token for quota/replay ownership.

    The public frontend is hosted on trilloka.com while the API is on onrender.com, so a
    SameSite cookie alone is not sufficiently reliable across browsers. The frontend also
    sends a random X-Trilloka-Device-ID stored locally. IP limits remain in force, so this
    token is an additive continuity mechanism rather than a quota bypass.
    """
    supplied = str(http_request.headers.get("X-Trilloka-Device-ID") or "").strip()
    cookie_value = http_request.cookies.get("trilloka_scan_device")
    candidate = supplied or cookie_value
    device_id, device_created = access_manager.ensure_device_id(candidate)
    if device_created or cookie_value != device_id:
        _set_device_cookie(response, device_id)
    return device_id


def _access_error(exc: AccessDenied) -> HTTPException:
    if exc.reason in {"PAID_PASS_REQUIRED", "PAID_PLAN_REVOKED"}:
        status_code = 403
    elif exc.reason == "PAID_PLAN_EXPIRED":
        status_code = 402
    else:
        status_code = 429
    headers = {"X-Trilloka-Access-Reason": exc.reason}
    if exc.retry_after:
        headers["Retry-After"] = str(int(exc.retry_after))
    return HTTPException(status_code=status_code, detail=str(exc), headers=headers)


def _normalized_host(target_domain: str) -> str:
    raw = str(target_domain or "").strip()
    if not raw:
        return ""
    clean_url = raw if raw.startswith(("http://", "https://")) else f"https://{raw}"
    try:
        host = (urlparse(clean_url).hostname or "").lower().rstrip(".")
    except Exception:
        host = ""
    return host


def _is_protected_trilloka_domain(target_domain: str) -> bool:
    host = _normalized_host(target_domain)
    if not host:
        return False
    return any(host == root or host.endswith("." + root) for root in _PROTECTED_DOMAIN_ROOTS)


def _parse_snapshot_time(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except Exception:
        return None


def _load_self_snapshot() -> Dict[str, Any]:
    path = Path(_SELF_SNAPSHOT_FILE)
    if not path.exists() or not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception as exc:
        print(f"[Guardrail] Error reading snapshot JSON: {exc}")
        return {}


def _snapshot_freshness(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    generated = _parse_snapshot_time(
        snapshot.get("generated_at")
        or snapshot.get("scan_timestamp")
        or snapshot.get("timestamp")
        or snapshot.get("scanned_at")
    )
    if generated is None:
        try:
            generated = datetime.fromtimestamp(Path(_SELF_SNAPSHOT_FILE).stat().st_mtime, tz=timezone.utc)
        except Exception:
            generated = None
    if generated is None:
        return {"generated_at": None, "age_days": None, "stale": True}
    age_days = max(0.0, (datetime.now(timezone.utc) - generated).total_seconds() / 86400.0)
    return {
        "generated_at": generated.isoformat(),
        "age_days": round(age_days, 2),
        "stale": age_days > float(_SELF_SNAPSHOT_MAX_AGE_DAYS),
    }


def _atomic_write_self_snapshot(snapshot: Dict[str, Any]) -> None:
    path = Path(_SELF_SNAPSHOT_FILE)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(path.name + ".tmp")
    temp_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(str(temp_path), str(path))


def _public_self_snapshot(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(snapshot, dict) or not snapshot:
        return {}
    allowed = {
        "snapshot_version", "snapshot_source", "generated_at", "target_domain",
        "scanner_engine_version", "overall_score", "score_rating", "score_scope",
        "journey_model", "journey_label", "journey_confidence", "context_tags",
        "mobile_performance_score", "seo_health_index", "ai_spectrum_pct",
        "online_presence_index", "conversion_efficiency", "conversion_path_readiness", "conversion_metric_status", "common_foundation_index",
        "adaptive_architecture_index", "evidence_confidence_level", "evidence_confidence_score",
        "verified_checkpoints", "applicable_checkpoints", "passed_count", "failed_count",
        "unknown_count", "not_applicable_count", "cms_detected", "load_time_seconds",
        "confirmed_major_leak_count", "corroborated_major_leak_count", "revenue_leak",
        "previous_snapshot_score", "score_delta_since_previous", "comparison_confidence",
    }
    return {key: copy.deepcopy(value) for key, value in snapshot.items() if key in allowed}


def _build_self_snapshot(
    *,
    target_domain: str,
    scan_data: Dict[str, Any],
    audit_results: Dict[str, Any],
    previous_snapshot: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    surface = audit_results.get("surface_metrics") if isinstance(audit_results.get("surface_metrics"), dict) else {}
    architecture = audit_results.get("architecture_profile") or audit_results.get("business_profile") or {}
    evidence = audit_results.get("evidence_confidence") if isinstance(audit_results.get("evidence_confidence"), dict) else {}
    checkpoints = [x for x in (audit_results.get("full_50_checkpoint_basis") or []) if isinstance(x, dict)]
    counts = {"PASS": 0, "FAIL": 0, "UNKNOWN": 0, "NOT_APPLICABLE": 0}
    for item in checkpoints:
        status = str(item.get("status") or "").upper()
        if status in counts:
            counts[status] += 1

    high = audit_results.get("high_impact_confirmation") if isinstance(audit_results.get("high_impact_confirmation"), dict) else {}
    high_results = high.get("results") if isinstance(high.get("results"), dict) else {}
    confirmed = sum(1 for item in high_results.values() if isinstance(item, dict) and str(item.get("status") or "").upper() == "CONFIRMED")
    corroborated = sum(1 for item in high_results.values() if isinstance(item, dict) and str(item.get("status") or "").upper() == "CORROBORATED")

    score = audit_results.get("overall_score")
    if score is None:
        score = audit_results.get("overall_health_score")
    prev_score = previous_snapshot.get("overall_score") if isinstance(previous_snapshot, dict) else None
    delta = None
    try:
        if score is not None and prev_score is not None:
            delta = round(float(score) - float(prev_score), 1)
    except Exception:
        delta = None

    scan_quality = scan_data.get("scan_quality") if isinstance(scan_data.get("scan_quality"), dict) else {}
    load_time = scan_data.get("load_time_seconds")
    if load_time is None:
        load_time = scan_quality.get("load_time_seconds")

    return {
        "snapshot_version": 2,
        "snapshot_source": "owner_controlled_v7_self_scan",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "target_domain": target_domain,
        "scanner_engine_version": scan_data.get("scanner_engine_version", "v7.2.2"),
        "overall_score": score,
        "score_rating": audit_results.get("score_rating", ""),
        "score_scope": audit_results.get("score_scope", "Observable website Revenue Readiness only."),
        "journey_model": architecture.get("journey_model", "general"),
        "journey_label": architecture.get("journey_label", "General / Unresolved Journey"),
        "journey_confidence": architecture.get("confidence"),
        "context_tags": list(architecture.get("context_tags") or []),
        "mobile_performance_score": surface.get("mobile_performance_score"),
        "seo_health_index": surface.get("seo_health_index"),
        "ai_spectrum_pct": surface.get("ai_spectrum_pct"),
        "online_presence_index": surface.get("online_presence_index"),
        "conversion_efficiency": surface.get("conversion_efficiency"),
        "conversion_path_readiness": surface.get("conversion_path_readiness", surface.get("conversion_efficiency")),
        "conversion_metric_status": surface.get("conversion_metric_status"),
        "common_foundation_index": surface.get("common_foundation_index"),
        "adaptive_architecture_index": surface.get("adaptive_architecture_index"),
        "evidence_confidence_level": evidence.get("level"),
        "evidence_confidence_score": evidence.get("score"),
        "verified_checkpoints": evidence.get("verified_checkpoints"),
        "applicable_checkpoints": evidence.get("applicable_checkpoints"),
        "passed_count": counts["PASS"],
        "failed_count": counts["FAIL"],
        "unknown_count": counts["UNKNOWN"],
        "not_applicable_count": counts["NOT_APPLICABLE"],
        "cms_detected": audit_results.get("cms_platform", scan_data.get("cms_platform", "Trilloka Engine")),
        "load_time_seconds": load_time,
        "confirmed_major_leak_count": confirmed,
        "corroborated_major_leak_count": corroborated,
        "revenue_leak": copy.deepcopy(audit_results.get("revenue_leak") or {}),
        "previous_snapshot_score": prev_score,
        "score_delta_since_previous": delta,
        "comparison_confidence": (
            "same_engine_comparison"
            if previous_snapshot and previous_snapshot.get("scanner_engine_version") == scan_data.get("scanner_engine_version")
            else ("directional_only" if previous_snapshot else "baseline_created")
        ),
        # Minimal internal state for future owner-only before/after snapshot comparisons.
        "finding_rule_keys": sorted({
            str(x.get("rule_key"))
            for x in (audit_results.get("scoring_ledger") or [])
            if isinstance(x, dict) and x.get("rule_key")
        }),
        "checkpoint_statuses": {
            str(x.get("id")): str(x.get("status"))
            for x in checkpoints if x.get("id") is not None
        },
    }


def handle_trilloka_guardrail(target_domain: str) -> Optional[Dict[str, Any]]:
    if not _is_protected_trilloka_domain(target_domain):
        return None

    snapshot_data = _load_self_snapshot()
    public_snapshot = _public_self_snapshot(snapshot_data)
    freshness = _snapshot_freshness(snapshot_data) if snapshot_data else {"generated_at": None, "age_days": None, "stale": True}
    has_snapshot = bool(public_snapshot)
    score = public_snapshot.get("overall_score") if has_snapshot else None

    return {
        "success": True,
        "is_guarded": True,
        "target_domain": target_domain,
        "status": "INTERCEPTED",
        "guardrail": {
            "heading": "Nice try!!!",
            "message": "Did you really think we didn't know some of you wouldn't be able to resist yourselves. Well, The Architect has commanded us to scan his own website every 30 days and check its ongoing state of strength...",
            "note": "External public scans are blocked on protected Trilloka domains. Only a stored owner-controlled self-diagnostic snapshot may be displayed.",
            "snapshot_available": has_snapshot,
            "snapshot_generated_at": freshness.get("generated_at"),
            "snapshot_age_days": freshness.get("age_days"),
            "snapshot_stale": freshness.get("stale"),
            "snapshot_max_age_days": _SELF_SNAPSHOT_MAX_AGE_DAYS,
        },
        # Never fabricate self-scan values when the snapshot file is absent.
        "overall_score": score,
        "surface_metrics": {
            "mobile_performance_score": public_snapshot.get("mobile_performance_score") if has_snapshot else None,
            "seo_health_index": public_snapshot.get("seo_health_index") if has_snapshot else None,
            "ai_spectrum_pct": public_snapshot.get("ai_spectrum_pct") if has_snapshot else None,
            "online_presence_index": public_snapshot.get("online_presence_index") if has_snapshot else None,
            "conversion_path_readiness": public_snapshot.get("conversion_path_readiness", public_snapshot.get("conversion_efficiency")) if has_snapshot else None,
            "conversion_efficiency": public_snapshot.get("conversion_efficiency") if has_snapshot else None,
            "common_foundation_index": public_snapshot.get("common_foundation_index") if has_snapshot else None,
            "adaptive_architecture_index": public_snapshot.get("adaptive_architecture_index") if has_snapshot else None,
            "competitor_gap_score": None,
            "competitor_data_available": False,
            "classification": "Architect Core Platform",
        },
        "competitor_benchmark": {
            "available": False,
            "status": "protected_self_scan",
            "sample_count": 0,
            "reason": "Local competitor benchmarking is intentionally disabled for the protected Trilloka self-diagnostic.",
            "does_not_directly_change_readiness_score": True,
        },
        "key_friction_insight": {
            "passed_count": public_snapshot.get("passed_count") if has_snapshot else None,
            "failed_count": public_snapshot.get("failed_count") if has_snapshot else None,
            "load_time_seconds": public_snapshot.get("load_time_seconds") if has_snapshot else None,
        },
        "revenue_leak": public_snapshot.get("revenue_leak", {}) if has_snapshot else {},
        "cms_platform": public_snapshot.get("cms_detected", "Trilloka Engine") if has_snapshot else "Trilloka Engine",
        "audit_snapshot": public_snapshot,
        "message": (
            "Trilloka infrastructure self-scan intercepted. Displaying the latest stored owner-controlled diagnostic snapshot."
            if has_snapshot
            else "Trilloka infrastructure self-scan intercepted. No stored self-diagnostic snapshot is currently available; no fallback score was fabricated."
        ),
    }


@app.get("/health")
def health_check() -> Dict[str, Any]:
    return {
        "status": "online",
        "system": "Trilloka Architect Engine v7.5.2",
        "google_api_configured": bool(os.environ.get("PAGESPEED_API_KEY") or os.environ.get("GOOGLE_API_KEY")),
        "places_api_configured": bool(os.environ.get("GOOGLE_PLACES_API_KEY") or os.environ.get("GOOGLE_API_KEY") or os.environ.get("PAGESPEED_API_KEY")),
        "report_engine": REPORT_ENGINE_AVAILABLE,
        "adaptive_learning": learning_memory.stats(),
        "owner_otp_auth": {
            "enabled": admin_auth.configured,
            "locked_owner_email": True,
            "session_minutes": round(admin_auth.session_ttl_seconds / 60, 1),
            "authenticated_scan_bypass": True,
        },
        "scan_access_control": {
            "enabled": access_manager.enabled,
            "free_limit": access_manager.free_limit,
            "free_window_hours": round(access_manager.free_window_seconds / 3600, 2),
            "plan_timezone": access_manager.plan_timezone_name,
            "plans": access_manager.public_plans(),
        },
    }


@app.get("/api/plans")
def public_plans() -> Dict[str, Any]:
    """Additive public plan catalogue for pricing cards/checkout."""
    return {
        "success": True,
        "free_preview": {
            "price": 0,
            "currency": "CAD",
            "scans": "1 successful preview scan per rolling 24 hours per IP/device",
            "checkpoint_access": "summary_only",
            "remediation_limit": 0,
        },
        "plans": access_manager.public_plans(),
    }



def _admin_console_html() -> str:
    # Private owner console. Authentication is enforced by HttpOnly OTP session cookie on every API call.
    return r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Trilloka Owner Console</title>
<style>
:root{color-scheme:dark}body{margin:0;background:#071018;color:#eef3f4;font:15px/1.45 system-ui,-apple-system,Segoe UI,Arial,sans-serif}main{max-width:1080px;margin:0 auto;padding:36px 20px}.card{background:#0d1821;border:1px solid #263743;border-radius:16px;padding:20px;margin:14px 0;box-shadow:0 12px 36px #0005}h1,h2{margin:0 0 12px}.muted{color:#aebdc6}.ok{color:#a5e7bf}.err{color:#ffb4ab}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:12px}input,select,button,textarea{width:100%;box-sizing:border-box;border-radius:10px;border:1px solid #354b58;background:#09141c;color:#eef3f4;padding:11px 12px;margin:6px 0}button{cursor:pointer;background:#d8c29b;color:#111;border:none;font-weight:700}button.secondary{background:#18303e;color:#eef3f4}.actions{display:flex;gap:8px;flex-wrap:wrap}.actions button{width:auto}pre{white-space:pre-wrap;word-break:break-word;background:#071018;padding:14px;border-radius:10px;max-height:420px;overflow:auto}.hidden{display:none}.code{font-size:25px;letter-spacing:4px;text-align:center}.danger{background:#7f1d1d;color:white}
</style>
</head>
<body><main>
<h1>Trilloka Owner Console</h1>
<p class="muted">Private administration. Every new owner session requires a one-time code sent only to the configured owner email.</p>
<div id="login" class="card">
  <h2>Owner sign-in</h2>
  <p id="loginMsg" class="muted">Request a one-time code. No email address can be entered or changed here.</p>
  <button id="sendCode">Email my code</button>
  <input id="otp" class="code" inputmode="numeric" maxlength="6" autocomplete="one-time-code" placeholder="000000">
  <button id="verifyCode" class="secondary">Verify code</button>
</div>
<div id="console" class="hidden">
  <div class="card"><div class="actions"><button id="refresh">Refresh usage</button><button id="listEnt" class="secondary">List entitlements</button><button id="logout" class="danger">Log out</button></div><pre id="output">Authenticated.</pre></div>

  <div class="card">
    <h2>Owner Internal Scanner</h2>
    <p class="muted">Authenticated owner scans bypass the public free-scan quota and run fresh proof-backed analysis, including severe-finding confirmation and before/after comparison when a prior domain snapshot exists.</p>
    <div class="grid">
      <input id="ownerScanDomain" placeholder="example.com" autocomplete="off">
      <select id="ownerScanType">
        <option value="auto" selected>Auto-detect business type (recommended)</option>
        <option value="ecommerce">E-commerce / Retail</option><option value="marketplace">Marketplace</option>
        <option value="local_service">Local Service</option><option value="professional_service">Professional Service</option>
        <option value="healthcare">Healthcare</option><option value="medspa">MedSpa</option><option value="legal">Legal</option>
        <option value="financial_services">Financial Services</option><option value="real_estate">Real Estate</option>
        <option value="restaurant">Restaurant / Food Service</option><option value="hospitality_event">Hospitality / Events</option>
        <option value="saas">SaaS</option><option value="b2b">B2B / Industrial</option><option value="agency">Agency</option>
        <option value="membership_creator">Membership / Creator</option><option value="education">Education / Training</option>
        <option value="automotive">Automotive</option>
      </select>
    </div>
    <button id="ownerScan">Your Architectural Analysis</button>
    <pre id="ownerScanOutput">Enter a domain to run an owner-only fresh analysis.</pre>
  </div>

  <div class="card">
    <h2>Protected Trilloka Snapshot</h2>
    <p class="muted">Runs the real V7 engine directly against the configured Trilloka public site, bypassing only the public self-scan intercept, then atomically replaces the stored 30-day snapshot. The stored public guardrail snapshot intentionally excludes local competitor benchmarking.</p>
    <div class="actions"><button id="selfSnapshot">Update Trilloka Snapshot Now</button></div>
    <pre id="selfSnapshotOutput">No update requested in this owner session.</pre>
  </div>

  <div class="card">
    <h2>Architect Review Queue</h2>
    <p class="muted">Human-only judgments are separated from automated scoring. Resolve them before a paid customer report can be delivered.</p>
    <div class="actions"><button id="loadReviews">Load open reviews</button><button id="loadPending" class="secondary">Pending reports</button><button id="loadLearning" class="secondary">Learning status</button></div>
    <div class="grid"><input id="reviewId" type="number" placeholder="Review ID"><select id="reviewResolution"><option value="confirmed_problem">Confirmed problem</option><option value="not_a_problem">Not a problem</option><option value="optimization">Optimization only</option><option value="insufficient_evidence">Still insufficient evidence</option></select><select id="reviewPriority"><option value="">Keep / no priority</option><option>CRITICAL</option><option>HIGH</option><option>MEDIUM</option><option>LOW</option></select><input id="reviewNotes" placeholder="Architect note"></div>
    <div class="actions"><button id="resolveReview">Resolve review</button></div>
    <pre id="architectOutput">Load open reviews to begin.</pre>
  </div>
  <div class="card">
    <h2>Knowledge Vault Teaching</h2>
    <p class="muted">Teach Trilloka from confirmed misses and outcomes without changing its scoring formula. Candidate recognition stays separate until validated.</p>
    <div class="actions"><button id="loadCandidates">Load learning candidates</button></div>
    <div class="grid">
      <select id="promoteKind"><option value="archetype">Promote / name archetype</option><option value="term">Promote recognition term</option></select>
      <input id="promoteId" placeholder="Archetype ID or term">
      <input id="promoteType" placeholder="Business type for term only">
      <input id="promoteLabel" placeholder="Subtype label (archetype only)">
    </div>
    <button id="promoteKnowledge">Approve candidate knowledge</button>
    <hr style="border:0;border-top:1px solid #263743;margin:18px 0">
    <h3>Scanner missed a finding</h3>
    <div class="grid"><input id="missDomain" placeholder="domain"><input id="missType" placeholder="business type e.g. ecommerce"><input id="missJourney" placeholder="journey e.g. direct_purchase"><input id="missFinding" placeholder="finding type"><input id="missPriority" placeholder="priority"><input id="missPage" placeholder="evidence page"></div>
    <textarea id="missWhy" placeholder="Why this matters"></textarea><textarea id="missRemedy" placeholder="Recommended remedy"></textarea>
    <button id="recordMiss">Record supervised learning example</button>
    <hr style="border:0;border-top:1px solid #263743;margin:18px 0">
    <h3>Record remediation outcome</h3>
    <div class="grid"><input id="outcomeDomain" placeholder="domain"><input id="outcomeType" placeholder="business type"><input id="outcomeJourney" placeholder="journey"><input id="outcomeRule" placeholder="rule key"><select id="outcomeStatus"><option value="improved">Improved</option><option value="resolved">Resolved</option><option value="no_change">No change</option><option value="worse">Worse</option><option value="not_applicable">Not applicable</option></select></div>
    <textarea id="outcomeCro" placeholder="What UX/CRO change was made / learned"></textarea><textarea id="outcomeTech" placeholder="Technical note"></textarea><textarea id="outcomeSystems" placeholder="Systems/process note"></textarea><textarea id="outcomeVerify" placeholder="How the outcome was verified"></textarea>
    <button id="recordOutcome">Record Architect-confirmed outcome</button>
    <pre id="learningOutput">Knowledge teaching actions will appear here.</pre>
  </div>

  <div class="card">
    <h2>Finalize Architect-Reviewed Report</h2>
    <p class="muted">Customer delivery is blocked while any Architect review item for the Vault is open.</p>
    <div class="grid"><input id="finalizeVault" placeholder="Vault ID"></div>
    <button id="finalizeReport">Finalize &amp; email customer report</button>
    <pre id="finalizeOutput">Enter a Vault ID after all review items are resolved.</pre>
  </div>

  <div class="card"><h2>Activate / complimentary plan</h2><div class="grid"><input id="aEmail" placeholder="customer@email.com"><input id="aDomain" placeholder="example.com"><select id="aPlan"><option value="essential_350">$350 Essential</option><option value="advanced_550">$550 Advanced</option><option value="architect_850">$850 Architect</option></select><input id="aRef" placeholder="purchase reference"></div><button id="activate">Activate plan</button></div>
  <div class="card"><h2>Manage customer</h2><div class="grid"><input id="mEmail" placeholder="customer@email.com"><input id="mDomain" placeholder="example.com"><select id="mPlan"><option value="">Keep current plan</option><option value="essential_350">$350 Essential</option><option value="advanced_550">$550 Advanced</option><option value="architect_850">$850 Architect</option></select><input id="extendDays" type="number" placeholder="extend days (+/-)"><input id="newDomain" placeholder="new domain if changing"></div><div class="actions"><button data-act="status">Status</button><button data-act="update">Update plan/expiry</button><button data-act="reset">Reset daily scans</button><button data-act="callplus">Call +1</button><button data-act="callminus">Call -1</button><button data-act="rotate">Rotate pass</button><button data-act="domain">Change domain</button><button data-act="restore">Restore</button><button data-act="revoke" class="danger">Revoke</button></div></div>
</div>
<script>
const $=id=>document.getElementById(id), out=$('output');
async function api(path,opts={}){opts.credentials='same-origin';opts.headers={'Content-Type':'application/json',...(opts.headers||{})};const r=await fetch(path,opts);let j={};try{j=await r.json()}catch{}if(!r.ok)throw new Error(j.detail||('HTTP '+r.status));return j}
function showConsole(on){$('login').classList.toggle('hidden',on);$('console').classList.toggle('hidden',!on)}
async function status(){try{const j=await api('/api/admin/auth/status');showConsole(!!j.authenticated);if(j.authenticated)out.textContent='Owner session active. Expires in '+Math.ceil(j.expires_in_seconds/60)+' min.'}catch{showConsole(false)}}
$('sendCode').onclick=async()=>{try{const j=await api('/api/admin/auth/request-code',{method:'POST'});$('loginMsg').className='ok';$('loginMsg').textContent='Code sent to '+j.destination+'. It expires in '+Math.ceil(j.expires_in_seconds/60)+' minutes.'}catch(e){$('loginMsg').className='err';$('loginMsg').textContent=e.message}};
$('verifyCode').onclick=async()=>{try{await api('/api/admin/auth/verify-code',{method:'POST',body:JSON.stringify({code:$('otp').value})});$('otp').value='';await status()}catch(e){$('loginMsg').className='err';$('loginMsg').textContent=e.message}};
$('logout').onclick=async()=>{await api('/api/admin/auth/logout',{method:'POST'});showConsole(false)};
function print(j){out.textContent=JSON.stringify(j,null,2)}
$('refresh').onclick=async()=>{try{print(await api('/api/admin/scan-usage'))}catch(e){out.textContent=e.message}};
$('listEnt').onclick=async()=>{try{print(await api('/api/admin/entitlements?limit=100'))}catch(e){out.textContent=e.message}};
$('ownerScan').onclick=async()=>{
  const domain=$('ownerScanDomain').value.trim();
  const scanOut=$('ownerScanOutput');
  if(!domain){scanOut.textContent='Enter a domain first.';return}
  $('ownerScan').disabled=true;
  scanOut.textContent='Running your Architectural Analysis...';
  try{
    const result=await api('/api/scan',{
      method:'POST',
      body:JSON.stringify({
        domain:domain,
        business_type:$('ownerScanType').value,
        force_refresh:true
      })
    });
    scanOut.textContent=JSON.stringify(result,null,2);
  }catch(e){
    scanOut.textContent=e.message;
  }finally{
    $('ownerScan').disabled=false;
  }
};
$('selfSnapshot').onclick=async()=>{
  const scanOut=$('selfSnapshotOutput');
  $('selfSnapshot').disabled=true;
  scanOut.textContent='Running controlled Trilloka self-diagnostic and updating snapshot...';
  try{
    const result=await api('/api/admin/self-scan-snapshot',{method:'POST',body:JSON.stringify({force:true})});
    scanOut.textContent=JSON.stringify(result,null,2);
  }catch(e){
    scanOut.textContent=e.message;
  }finally{
    $('selfSnapshot').disabled=false;
  }
};
$('loadCandidates').onclick=async()=>{try{const j=await api('/api/admin/learning/candidates?limit=100');$('learningOutput').textContent=JSON.stringify(j,null,2)}catch(e){$('learningOutput').textContent=e.message}};
$('promoteKnowledge').onclick=async()=>{try{const kind=$('promoteKind').value;let identifier=$('promoteId').value.trim();if(kind==='archetype')identifier=Number(identifier);else identifier={business_type:$('promoteType').value.trim(),term:identifier};const j=await api('/api/admin/learning/promote',{method:'POST',body:JSON.stringify({kind:kind,identifier:identifier,label:$('promoteLabel').value.trim()})});$('learningOutput').textContent=JSON.stringify(j,null,2)}catch(e){$('learningOutput').textContent=e.message}};
$('recordMiss').onclick=async()=>{try{const j=await api('/api/admin/learning/missed-finding',{method:'POST',body:JSON.stringify({domain:$('missDomain').value,business_type:$('missType').value,journey_model:$('missJourney').value||'general',finding_type:$('missFinding').value,evidence_page:$('missPage').value,why_it_matters:$('missWhy').value,priority:$('missPriority').value,recommended_remedy:$('missRemedy').value})});$('learningOutput').textContent=JSON.stringify(j,null,2)}catch(e){$('learningOutput').textContent=e.message}};
$('recordOutcome').onclick=async()=>{try{const j=await api('/api/admin/learning/outcome',{method:'POST',body:JSON.stringify({domain:$('outcomeDomain').value,business_type:$('outcomeType').value,journey_model:$('outcomeJourney').value||'general',rule_key:$('outcomeRule').value,outcome_status:$('outcomeStatus').value,technical_note:$('outcomeTech').value,cro_note:$('outcomeCro').value,systems_note:$('outcomeSystems').value,verification_note:$('outcomeVerify').value})});$('learningOutput').textContent=JSON.stringify(j,null,2)}catch(e){$('learningOutput').textContent=e.message}};
$('loadReviews').onclick=async()=>{try{const j=await api('/api/admin/architect-reviews?status=open');$('architectOutput').textContent=JSON.stringify(j,null,2)}catch(e){$('architectOutput').textContent=e.message}};
$('loadPending').onclick=async()=>{try{const j=await api('/api/admin/pending-reports?status=awaiting_architect');$('architectOutput').textContent=JSON.stringify(j,null,2)}catch(e){$('architectOutput').textContent=e.message}};
$('loadLearning').onclick=async()=>{try{const j=await api('/api/admin/learning/status');$('architectOutput').textContent=JSON.stringify(j,null,2)}catch(e){$('architectOutput').textContent=e.message}};
$('resolveReview').onclick=async()=>{try{const id=Number($('reviewId').value);if(!id)throw new Error('Enter a Review ID');const j=await api('/api/admin/architect-review/resolve',{method:'POST',body:JSON.stringify({review_id:id,resolution:$('reviewResolution').value,priority:$('reviewPriority').value,notes:$('reviewNotes').value})});$('architectOutput').textContent=JSON.stringify(j,null,2)}catch(e){$('architectOutput').textContent=e.message}};
$('finalizeReport').onclick=async()=>{const vault=$('finalizeVault').value.trim();if(!vault){$('finalizeOutput').textContent='Enter a Vault ID first.';return}try{$('finalizeReport').disabled=true;$('finalizeOutput').textContent='Checking Architect review and delivering report...';const j=await api('/api/admin/report/finalize',{method:'POST',body:JSON.stringify({vault_id:vault})});$('finalizeOutput').textContent=JSON.stringify(j,null,2)}catch(e){$('finalizeOutput').textContent=e.message}finally{$('finalizeReport').disabled=false}};
$('activate').onclick=async()=>{try{print(await api('/api/admin/activate-plan',{method:'POST',body:JSON.stringify({email:$('aEmail').value,domain:$('aDomain').value,plan_id:$('aPlan').value,purchase_ref:$('aRef').value})}))}catch(e){out.textContent=e.message}};
document.querySelectorAll('[data-act]').forEach(b=>b.onclick=async()=>{const email=$('mEmail').value,domain=$('mDomain').value,ref={email,domain};let path='',body=ref;switch(b.dataset.act){case'status':path='/api/admin/entitlement/status';break;case'update':path='/api/admin/entitlement/update';body={...ref,plan_id:$('mPlan').value||null,extend_days:$('extendDays').value?Number($('extendDays').value):null};break;case'reset':path='/api/admin/entitlement/reset-daily-usage';break;case'callplus':path='/api/admin/entitlement/guidance-call';body={...ref,delta:1};break;case'callminus':path='/api/admin/entitlement/guidance-call';body={...ref,delta:-1};break;case'rotate':path='/api/admin/entitlement/rotate-pass';break;case'domain':path='/api/admin/entitlement/change-domain';body={...ref,new_domain:$('newDomain').value};break;case'restore':path='/api/admin/entitlement/restore';break;case'revoke':path='/api/admin/entitlement/revoke';break}try{print(await api(path,{method:'POST',body:JSON.stringify(body)}))}catch(e){out.textContent=e.message}});
status();
</script>
</main></body></html>"""


def _admin_auth_error(exc: AdminAuthError) -> HTTPException:
    headers = {"X-Trilloka-Admin-Auth-Reason": exc.reason}
    if exc.retry_after:
        headers["Retry-After"] = str(int(exc.retry_after))
    status = 429 if exc.reason in {"OTP_COOLDOWN", "OTP_RATE_LIMIT"} else 401
    if exc.reason in {"ADMIN_EMAIL_NOT_CONFIGURED", "OTP_EMAIL_NOT_CONFIGURED", "OTP_EMAIL_DELIVERY_FAILED"}:
        status = 503
    return HTTPException(status_code=status, detail=str(exc), headers=headers)


@app.get("/admin", response_class=HTMLResponse, include_in_schema=False)
def admin_console() -> str:
    return _admin_console_html()


@app.post("/api/admin/auth/request-code", include_in_schema=False)
def admin_request_code(http_request: FastAPIRequest, response: Response) -> Dict[str, Any]:
    try:
        challenge = admin_auth.request_code(access_manager.client_ip(http_request))
    except AdminAuthError as exc:
        raise _admin_auth_error(exc) from exc
    response.set_cookie(
        key=admin_auth.challenge_cookie_name,
        value=challenge.token,
        max_age=admin_auth.otp_ttl_seconds,
        httponly=True,
        secure=admin_auth.cookie_secure,
        samesite="strict",
        path="/",
    )
    return {
        "success": True,
        "sent": True,
        "destination": challenge.destination,
        "expires_in_seconds": admin_auth.otp_ttl_seconds,
    }


@app.post("/api/admin/auth/verify-code", include_in_schema=False)
def admin_verify_code(payload: AdminOtpVerifyRequest, http_request: FastAPIRequest, response: Response) -> Dict[str, Any]:
    try:
        session = admin_auth.verify_code(
            payload.code,
            http_request.cookies.get(admin_auth.challenge_cookie_name),
            access_manager.client_ip(http_request),
        )
    except AdminAuthError as exc:
        raise _admin_auth_error(exc) from exc
    response.delete_cookie(admin_auth.challenge_cookie_name, path="/", samesite="strict")
    response.set_cookie(
        key=admin_auth.cookie_name,
        value=session.token,
        max_age=admin_auth.session_ttl_seconds,
        httponly=True,
        secure=admin_auth.cookie_secure,
        samesite="strict",
        path="/",
    )
    return {"success": True, "authenticated": True, "expires_at": session.expires_at}


@app.get("/api/admin/auth/status", include_in_schema=False)
def admin_auth_status(
    http_request: FastAPIRequest,
    x_trilloka_admin_session: Optional[str] = Header(default=None, alias="X-Trilloka-Admin-Session"),
) -> Dict[str, Any]:
    return admin_auth.session_status(_admin_session_token(http_request, x_trilloka_admin_session))


@app.post("/api/admin/auth/logout", include_in_schema=False)
def admin_logout(
    http_request: FastAPIRequest,
    response: Response,
    x_trilloka_admin_session: Optional[str] = Header(default=None, alias="X-Trilloka-Admin-Session"),
) -> Dict[str, Any]:
    admin_auth.revoke_session(_admin_session_token(http_request, x_trilloka_admin_session))
    response.delete_cookie(admin_auth.cookie_name, path="/", samesite="strict")
    response.delete_cookie(admin_auth.challenge_cookie_name, path="/", samesite="strict")
    return {"success": True, "authenticated": False}


@app.get("/api/admin/learning/status", include_in_schema=False)
def admin_learning_status(
    http_request: FastAPIRequest,
    x_trilloka_admin_session: Optional[str] = Header(default=None, alias="X-Trilloka-Admin-Session"),
    x_trilloka_admin_key: Optional[str] = Header(default=None, alias="X-Trilloka-Admin-Key"),
) -> Dict[str, Any]:
    _require_admin_session(http_request, x_trilloka_admin_session, x_trilloka_admin_key)
    return {"success": True, "learning": learning_memory.stats()}


@app.get("/api/admin/learning/candidates", include_in_schema=False)
def admin_learning_candidates(
    http_request: FastAPIRequest,
    limit: int = 100,
    x_trilloka_admin_session: Optional[str] = Header(default=None, alias="X-Trilloka-Admin-Session"),
    x_trilloka_admin_key: Optional[str] = Header(default=None, alias="X-Trilloka-Admin-Key"),
) -> Dict[str, Any]:
    _require_admin_session(http_request, x_trilloka_admin_session, x_trilloka_admin_key)
    return {"success": True, **learning_memory.list_candidates(limit)}


@app.post("/api/admin/learning/promote", include_in_schema=False)
def admin_learning_promote(
    payload: LearningPromoteRequest,
    http_request: FastAPIRequest,
    x_trilloka_admin_session: Optional[str] = Header(default=None, alias="X-Trilloka-Admin-Session"),
    x_trilloka_admin_key: Optional[str] = Header(default=None, alias="X-Trilloka-Admin-Key"),
) -> Dict[str, Any]:
    _require_admin_session(http_request, x_trilloka_admin_session, x_trilloka_admin_key)
    try:
        return {"success": True, **learning_memory.promote(kind=payload.kind, identifier=payload.identifier, label=payload.label or "")}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/admin/learning/missed-finding", include_in_schema=False)
def admin_learning_missed_finding(
    payload: LearningMissRequest,
    http_request: FastAPIRequest,
    x_trilloka_admin_session: Optional[str] = Header(default=None, alias="X-Trilloka-Admin-Session"),
    x_trilloka_admin_key: Optional[str] = Header(default=None, alias="X-Trilloka-Admin-Key"),
) -> Dict[str, Any]:
    _require_admin_session(http_request, x_trilloka_admin_session, x_trilloka_admin_key)
    return learning_memory.record_missed_finding(payload.model_dump())


@app.post("/api/admin/learning/outcome", include_in_schema=False)
def admin_learning_outcome(
    payload: LearningOutcomeRequest,
    http_request: FastAPIRequest,
    x_trilloka_admin_session: Optional[str] = Header(default=None, alias="X-Trilloka-Admin-Session"),
    x_trilloka_admin_key: Optional[str] = Header(default=None, alias="X-Trilloka-Admin-Key"),
) -> Dict[str, Any]:
    _require_admin_session(http_request, x_trilloka_admin_session, x_trilloka_admin_key)
    try:
        return {"success": True, **learning_memory.record_remediation_outcome(payload.model_dump())}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/admin/architect-reviews", include_in_schema=False)
def admin_architect_reviews(
    http_request: FastAPIRequest,
    status: str = "open",
    limit: int = 100,
    x_trilloka_admin_session: Optional[str] = Header(default=None, alias="X-Trilloka-Admin-Session"),
    x_trilloka_admin_key: Optional[str] = Header(default=None, alias="X-Trilloka-Admin-Key"),
) -> Dict[str, Any]:
    _require_admin_session(http_request, x_trilloka_admin_session, x_trilloka_admin_key)
    rows = learning_memory.list_architect_reviews(status=status, limit=limit)
    return {"success": True, "status": status, "count": len(rows), "reviews": rows}


@app.post("/api/admin/architect-review/resolve", include_in_schema=False)
def admin_architect_review_resolve(
    payload: ArchitectReviewResolveRequest,
    http_request: FastAPIRequest,
    x_trilloka_admin_session: Optional[str] = Header(default=None, alias="X-Trilloka-Admin-Session"),
    x_trilloka_admin_key: Optional[str] = Header(default=None, alias="X-Trilloka-Admin-Key"),
) -> Dict[str, Any]:
    _require_admin_session(http_request, x_trilloka_admin_session, x_trilloka_admin_key)
    try:
        return {"success": True, "review": learning_memory.resolve_architect_review(payload.review_id, payload.resolution, payload.priority or "", payload.notes or "")}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/admin/self-scan-snapshot", include_in_schema=False)
async def admin_refresh_self_scan_snapshot(
    payload: SelfSnapshotRefreshRequest,
    http_request: FastAPIRequest,
    x_trilloka_admin_session: Optional[str] = Header(default=None, alias="X-Trilloka-Admin-Session"),
    x_trilloka_admin_key: Optional[str] = Header(default=None, alias="X-Trilloka-Admin-Key"),
) -> Dict[str, Any]:
    """Owner-only controlled self-scan that updates the public guardrail snapshot.

    The public /api/scan guardrail remains intact. This route calls the scanner directly only
    after fresh owner authentication, so the protected site can maintain a real snapshot
    without exposing a public bypass.
    """
    _require_admin_session(http_request, x_trilloka_admin_session, x_trilloka_admin_key)

    previous_snapshot = _load_self_snapshot()
    freshness = _snapshot_freshness(previous_snapshot) if previous_snapshot else {"stale": True}
    if previous_snapshot and not payload.force and not freshness.get("stale", True):
        return {
            "success": True,
            "updated": False,
            "reason": "STORED_SNAPSHOT_STILL_FRESH",
            "snapshot": _public_self_snapshot(previous_snapshot),
            "freshness": freshness,
        }

    target = _SELF_SCAN_URL
    scan_data = await _run_scan_async(target, "Trilloka", "auto")
    if not scan_data.get("is_reachable"):
        raise HTTPException(status_code=502, detail="Configured Trilloka self-scan target is unreachable or blocking inspection")

    try:
        preliminary = scorer.audit_and_score(
            scan_data=scan_data,
            business_type="auto",
            competitor_data_present=None,
        )
        try:
            threshold = float(os.environ.get("TRILLOKA_CONFIRMATION_THRESHOLD_POINTS", "3.5"))
        except Exception:
            threshold = 3.5
        if hasattr(scanner, "confirm_high_impact_findings"):
            try:
                confirmation = await scanner.confirm_high_impact_findings(
                    scan_data, preliminary, "auto", threshold
                )
            except Exception as confirm_exc:
                print(f"[Self Snapshot] High-impact confirmation failed closed — {confirm_exc}")
                confirmation = {
                    "completed": True,
                    "threshold_points": threshold,
                    "candidate_count": None,
                    "results": {},
                    "error": str(confirm_exc),
                    "policy": "Confirmation failed during protected self-scan; severe first-pass candidates remain unscored.",
                }
        else:
            confirmation = {
                "completed": True,
                "threshold_points": threshold,
                "candidate_count": None,
                "results": {},
                "policy": "Confirmation method unavailable during protected self-scan; severe first-pass candidates remain unscored.",
            }
        scan_data["high_impact_confirmation"] = confirmation

        audit_results = scorer.audit_and_score(
            scan_data=scan_data,
            business_type="auto",
            competitor_data_present=None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        import traceback
        print(f"[Self Snapshot] Scoring failed — {exc}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Protected self-scan scoring failed; previous snapshot was left unchanged") from exc

    snapshot = _build_self_snapshot(
        target_domain=target,
        scan_data=scan_data,
        audit_results=audit_results,
        previous_snapshot=previous_snapshot,
    )
    try:
        _atomic_write_self_snapshot(snapshot)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Self-scan completed but snapshot storage failed: {str(exc)[:160]}") from exc

    return {
        "success": True,
        "updated": True,
        "target_domain": target,
        "snapshot": _public_self_snapshot(snapshot),
        "freshness": _snapshot_freshness(snapshot),
        "storage": {
            "configured_path": _SELF_SNAPSHOT_FILE,
            "note": "For 30-day persistence across Render restarts/deploys, point TRILLOKA_SELF_SNAPSHOT_FILE at a persistent-disk path when one is configured.",
        },
    }


@app.get("/diagnostic")
def diagnostic() -> Dict[str, Any]:
    results: Dict[str, Any] = {"status": "running", "checks": {}}
    results["checks"]["env_google_api_key"] = bool(
        os.environ.get("PAGESPEED_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    )
    try:
        local_scanner = HybridScanner()
        results["checks"]["scanner_init"] = "OK"
        preflight = local_scanner._fast_http_preflight("https://example.com")
        results["checks"]["http_preflight"] = "OK" if preflight.get("is_reachable") else "UNAVAILABLE"
        psi = local_scanner._fetch_google_pagespeed("https://example.com")
        results["checks"]["pagespeed_api"] = psi.get("pagespeed_api_status", "unknown")
    except Exception as exc:
        results["checks"]["scanner_init"] = f"FAIL: {exc}"
    try:
        RevenueScorer()
        results["checks"]["scorer_init"] = "OK"
    except Exception as exc:
        results["checks"]["scorer_init"] = f"FAIL: {exc}"
    results["checks"]["report_engine"] = "OK" if REPORT_ENGINE_AVAILABLE else "NOT LOADED"
    results["checks"]["scan_access"] = "OK" if access_manager.enabled else "DISABLED"
    return results


@app.post("/api/admin/activate-plan")
def activate_plan(
    payload: PlanActivationRequest,
    http_request: FastAPIRequest,
    x_trilloka_admin_session: Optional[str] = Header(default=None, alias="X-Trilloka-Admin-Session"),
    x_trilloka_system_key: Optional[str] = Header(default=None, alias="X-Trilloka-System-Key"),
    x_trilloka_admin_key: Optional[str] = Header(default=None, alias="X-Trilloka-Admin-Key"),
) -> Dict[str, Any]:
    """Called only after your payment backend has independently verified a successful purchase.

    The plaintext purchase pass is returned once. Store/deliver it through the payment success
    flow; only its HMAC hash is retained by Trilloka.
    """
    _require_admin_or_system(http_request, x_trilloka_admin_session, x_trilloka_system_key, x_trilloka_admin_key)
    try:
        result = access_manager.activate_plan(
            email=str(payload.email),
            domain=payload.domain,
            plan_id=payload.plan_id,
            purchase_ref=payload.purchase_ref or "",
            duration_days_override=payload.duration_days_override,
            complimentary=bool(payload.complimentary),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, "entitlement_created": True, **result}


@app.post("/api/admin/grant-scan-package")
def grant_scan_package(
    payload: PackageGrantRequest,
    http_request: FastAPIRequest,
    x_trilloka_admin_session: Optional[str] = Header(default=None, alias="X-Trilloka-Admin-Session"),
    x_trilloka_system_key: Optional[str] = Header(default=None, alias="X-Trilloka-System-Key"),
    x_trilloka_admin_key: Optional[str] = Header(default=None, alias="X-Trilloka-Admin-Key"),
) -> Dict[str, Any]:
    """Backward-compatible endpoint name. It now activates one of the three 30-day plans."""
    _require_admin_or_system(http_request, x_trilloka_admin_session, x_trilloka_system_key, x_trilloka_admin_key)
    try:
        result = access_manager.grant_package(
            email=str(payload.email),
            domain=payload.domain,
            plan_id=payload.plan_id,
            purchase_ref=payload.purchase_ref or "",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, "entitlement_created": True, **result}


@app.get("/api/admin/pending-reports", include_in_schema=False)
def admin_pending_reports(
    http_request: FastAPIRequest,
    status: str = "awaiting_architect",
    x_trilloka_admin_session: Optional[str] = Header(default=None, alias="X-Trilloka-Admin-Session"),
    x_trilloka_admin_key: Optional[str] = Header(default=None, alias="X-Trilloka-Admin-Key"),
) -> Dict[str, Any]:
    _require_admin_session(http_request, x_trilloka_admin_session, x_trilloka_admin_key)
    return {"success": True, "reports": learning_memory.list_pending_reports(status=status, limit=100)}


@app.post("/api/admin/report/finalize", include_in_schema=False)
def admin_finalize_customer_report(
    payload: PendingReportFinalizeRequest,
    http_request: FastAPIRequest,
    x_trilloka_admin_session: Optional[str] = Header(default=None, alias="X-Trilloka-Admin-Session"),
    x_trilloka_admin_key: Optional[str] = Header(default=None, alias="X-Trilloka-Admin-Key"),
) -> Dict[str, Any]:
    _require_admin_session(http_request, x_trilloka_admin_session, x_trilloka_admin_key)
    if not REPORT_ENGINE_AVAILABLE or reporter is None or not hasattr(reporter, "send_customer_report_email"):
        raise HTTPException(status_code=503, detail="Customer report delivery is not configured")
    try:
        prepared = learning_memory.prepare_pending_report_delivery(payload.vault_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    sent = reporter.send_customer_report_email(prepared["customer_email"], prepared["report"])
    if not sent:
        raise HTTPException(status_code=502, detail="Customer report email could not be delivered; pending report was retained")
    learning_memory.mark_pending_report_delivered(payload.vault_id)
    return {
        "success": True, "vault_id": payload.vault_id, "delivered": True,
        "architect_review_count": len(prepared.get("reviews") or []),
    }


@app.get("/api/admin/scan-usage")
def scan_usage(
    http_request: FastAPIRequest,
    x_trilloka_admin_session: Optional[str] = Header(default=None, alias="X-Trilloka-Admin-Session"),
    x_trilloka_admin_key: Optional[str] = Header(default=None, alias="X-Trilloka-Admin-Key"),
) -> Dict[str, Any]:
    _require_admin_session(http_request, x_trilloka_admin_session, x_trilloka_admin_key)
    return {"success": True, **access_manager.admin_metrics()}


@app.post("/api/plan/status")
def customer_plan_status(payload: CustomerPlanStatusRequest) -> Dict[str, Any]:
    """Customer-safe plan status. The pass is sent in the POST body so it is not exposed in URL logs."""
    status = access_manager.entitlement_status(
        str(payload.email), payload.domain, payload.access_pass, require_pass=True
    )
    if not status.get("exists"):
        raise HTTPException(status_code=404, detail="No paid plan exists for this email/domain")
    if not status.get("pass_valid"):
        raise HTTPException(status_code=403, detail="Valid purchase access pass required")
    # purchase_ref is an internal/payment reconciliation field and is not needed in customer UI.
    status.pop("purchase_ref", None)
    return {"success": True, **status}


@app.get("/api/admin/entitlements")
def admin_list_entitlements(
    http_request: FastAPIRequest,
    active_only: bool = False,
    limit: int = 100,
    x_trilloka_admin_session: Optional[str] = Header(default=None, alias="X-Trilloka-Admin-Session"),
    x_trilloka_admin_key: Optional[str] = Header(default=None, alias="X-Trilloka-Admin-Key"),
) -> Dict[str, Any]:
    _require_admin_session(http_request, x_trilloka_admin_session, x_trilloka_admin_key)
    return {"success": True, **access_manager.list_entitlements(active_only=active_only, limit=limit)}


@app.post("/api/admin/entitlement/status")
def admin_entitlement_lookup(
    payload: EntitlementAdminRef,
    http_request: FastAPIRequest,
    x_trilloka_admin_session: Optional[str] = Header(default=None, alias="X-Trilloka-Admin-Session"),
    x_trilloka_admin_key: Optional[str] = Header(default=None, alias="X-Trilloka-Admin-Key"),
) -> Dict[str, Any]:
    """Owner lookup uses a POST body so customer email/domain are not placed in the URL."""
    _require_admin_session(http_request, x_trilloka_admin_session, x_trilloka_admin_key)
    status = access_manager.entitlement_status(str(payload.email), payload.domain)
    if not status.get("exists"):
        raise HTTPException(status_code=404, detail="No entitlement exists for this email/domain")
    return {"success": True, **status}


@app.post("/api/admin/entitlement/update")
def admin_update_entitlement(
    payload: EntitlementUpdateRequest,
    http_request: FastAPIRequest,
    x_trilloka_admin_session: Optional[str] = Header(default=None, alias="X-Trilloka-Admin-Session"),
    x_trilloka_admin_key: Optional[str] = Header(default=None, alias="X-Trilloka-Admin-Key"),
) -> Dict[str, Any]:
    """Upgrade/downgrade, extend/shorten expiry, or change payment reference without changing the pass."""
    _require_admin_session(http_request, x_trilloka_admin_session, x_trilloka_admin_key)
    try:
        result = access_manager.update_entitlement(
            email=str(payload.email),
            domain=payload.domain,
            plan_id=payload.plan_id,
            extend_days=payload.extend_days,
            expires_at=payload.expires_at,
            purchase_ref=payload.purchase_ref,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, "entitlement_updated": True, **result}


@app.post("/api/admin/entitlement/revoke")
def admin_revoke_entitlement(
    payload: EntitlementAdminRef,
    http_request: FastAPIRequest,
    x_trilloka_admin_session: Optional[str] = Header(default=None, alias="X-Trilloka-Admin-Session"),
    x_trilloka_admin_key: Optional[str] = Header(default=None, alias="X-Trilloka-Admin-Key"),
) -> Dict[str, Any]:
    _require_admin_session(http_request, x_trilloka_admin_session, x_trilloka_admin_key)
    try:
        result = access_manager.revoke_entitlement(email=str(payload.email), domain=payload.domain)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, "revoked": True, **result}


@app.post("/api/admin/entitlement/restore")
def admin_restore_entitlement(
    payload: EntitlementAdminRef,
    http_request: FastAPIRequest,
    x_trilloka_admin_session: Optional[str] = Header(default=None, alias="X-Trilloka-Admin-Session"),
    x_trilloka_admin_key: Optional[str] = Header(default=None, alias="X-Trilloka-Admin-Key"),
) -> Dict[str, Any]:
    _require_admin_session(http_request, x_trilloka_admin_session, x_trilloka_admin_key)
    try:
        result = access_manager.restore_entitlement(email=str(payload.email), domain=payload.domain)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, "restored": True, **result}


@app.post("/api/admin/entitlement/rotate-pass")
def admin_rotate_pass(
    payload: EntitlementAdminRef,
    http_request: FastAPIRequest,
    x_trilloka_admin_session: Optional[str] = Header(default=None, alias="X-Trilloka-Admin-Session"),
    x_trilloka_admin_key: Optional[str] = Header(default=None, alias="X-Trilloka-Admin-Key"),
) -> Dict[str, Any]:
    """Issue a replacement pass. The old pass stops working immediately."""
    _require_admin_session(http_request, x_trilloka_admin_session, x_trilloka_admin_key)
    try:
        result = access_manager.rotate_access_pass(email=str(payload.email), domain=payload.domain)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, "pass_rotated": True, **result}


@app.post("/api/admin/entitlement/change-domain")
def admin_change_domain(
    payload: EntitlementDomainChangeRequest,
    http_request: FastAPIRequest,
    x_trilloka_admin_session: Optional[str] = Header(default=None, alias="X-Trilloka-Admin-Session"),
    x_trilloka_admin_key: Optional[str] = Header(default=None, alias="X-Trilloka-Admin-Key"),
) -> Dict[str, Any]:
    _require_admin_session(http_request, x_trilloka_admin_session, x_trilloka_admin_key)
    try:
        result = access_manager.change_entitlement_domain(
            email=str(payload.email), domain=payload.domain, new_domain=payload.new_domain
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, "domain_changed": True, **result}


@app.post("/api/admin/entitlement/reset-daily-usage")
def admin_reset_daily_usage(
    payload: EntitlementAdminRef,
    http_request: FastAPIRequest,
    x_trilloka_admin_session: Optional[str] = Header(default=None, alias="X-Trilloka-Admin-Session"),
    x_trilloka_admin_key: Optional[str] = Header(default=None, alias="X-Trilloka-Admin-Key"),
) -> Dict[str, Any]:
    _require_admin_session(http_request, x_trilloka_admin_session, x_trilloka_admin_key)
    try:
        result = access_manager.reset_daily_usage(email=str(payload.email), domain=payload.domain)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, "daily_usage_reset": True, **result}


@app.post("/api/admin/entitlement/guidance-call")
def admin_record_guidance_call(
    payload: GuidanceCallAdminRequest,
    http_request: FastAPIRequest,
    x_trilloka_admin_session: Optional[str] = Header(default=None, alias="X-Trilloka-Admin-Session"),
    x_trilloka_admin_key: Optional[str] = Header(default=None, alias="X-Trilloka-Admin-Key"),
) -> Dict[str, Any]:
    _require_admin_session(http_request, x_trilloka_admin_session, x_trilloka_admin_key)
    try:
        result = access_manager.record_guidance_call(
            email=str(payload.email), domain=payload.domain, delta=payload.delta
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, "guidance_usage_updated": True, **result}


async def _run_scan_async(
    domain: str,
    business_name: str = "",
    business_type: str = "auto",
) -> Dict[str, Any]:
    # HybridScanner is already async; keep Playwright on the active event loop.
    # V7.3 keeps business_type as a first-class scoring input. Auto-detect resolves business type
    # from public evidence; an explicit recognized type is respected. Journey + context remain
    # separately inferred from the observed website so scoring adapts without forcing one funnel.
    return await scanner.execute_hybrid_scan(domain, business_name, business_type)


def _base_success_payload(
    *,
    requested_domain: str,
    scan_data: Dict[str, Any],
    audit_results: Dict[str, Any],
    admin_master_report: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    all_leaks = (audit_results.get("tiered_remediation_packages") or {}).get("tier_10_arch10", [])
    overall_score = audit_results.get("overall_score")
    if overall_score is None:
        overall_score = audit_results.get("overall_health_score")

    return {
        "success": True,
        "status": "complete",
        "target_domain": requested_domain,
        "overall_score": overall_score,
        "score_rating": audit_results.get("score_rating", ""),
        "score_scope": audit_results.get("score_scope", ""),
        "evidence_confidence": audit_results.get("evidence_confidence", {}),
        "maturity_gate": audit_results.get("maturity_gate", {}),
        # Public modal receives only the existence/count/priority signal, never the omission identities.
        "foundation_omission_signal": {
            key: (audit_results.get("foundation_omission_signal") or {}).get(key)
            for key in ("triggered", "count", "highest_level", "density", "modal_title", "modal_message", "report_section_available")
        },
        "surface_metrics": audit_results.get("surface_metrics", {}),
        "competitor_benchmark": audit_results.get("competitor_benchmark", {}),
        # Backward-compatible public diagnostic lane. This contains only surface/search/
        # peer measurements and no proprietary commercial finding identities.
        "public_free_diagnostics": {
            "seo_health_index": (audit_results.get("surface_metrics") or {}).get("seo_health_index"),
            "seo_health_available": (audit_results.get("surface_metrics") or {}).get("seo_health_available"),
            "common_foundation_index": (audit_results.get("surface_metrics") or {}).get("common_foundation_index"),
            "performance_index": (audit_results.get("surface_metrics") or {}).get("performance_index"),
            "mobile_index": (audit_results.get("surface_metrics") or {}).get("mobile_index"),
            "competitor_benchmark": audit_results.get("competitor_benchmark", {}),
            "competitor_data_available": (audit_results.get("surface_metrics") or {}).get("competitor_data_available"),
            "competitor_gap_score": (audit_results.get("surface_metrics") or {}).get("competitor_gap_score"),
            "policy": "Public/free diagnostics show foundation, search and relevance-gated competitor context. Verified commercial leak identities, evidence receipts, causal scoring and remediation remain protected.",
        },
        "key_friction_insight": audit_results.get("key_friction_insight", {}),
        "revenue_leak": audit_results.get("revenue_leak", {}),
        "cms_platform": audit_results.get("cms_platform", "Not confidently identified"),
        "dev_handoff_kit": audit_results.get("dev_handoff_kit", ""),
        "top_5_seo_leaks": all_leaks[:5],
        "top_10_financial_leaks": all_leaks[:10],
        "message": "Scan complete.",
        "architecture_profile": audit_results.get("architecture_profile", audit_results.get("business_profile", {})),
        "business_type": audit_results.get("business_type", (audit_results.get("architecture_profile") or {}).get("business_type", "general")),
        "business_type_label": audit_results.get("business_type_label", (audit_results.get("architecture_profile") or {}).get("business_type_label", "General / Unresolved Business")),
        "business_type_confidence": audit_results.get("business_type_confidence", (audit_results.get("architecture_profile") or {}).get("business_type_confidence")),
        "business_subtype": audit_results.get("business_subtype", (audit_results.get("architecture_profile") or audit_results.get("business_profile") or {}).get("business_subtype")),
        "business_subtype_label": audit_results.get("business_subtype_label", (audit_results.get("architecture_profile") or audit_results.get("business_profile") or {}).get("business_subtype_label")),
        "business_subtype_confidence": audit_results.get("business_subtype_confidence", (audit_results.get("architecture_profile") or audit_results.get("business_profile") or {}).get("business_subtype_confidence")),
        "business_subtype_role": "inspection_modifier",
        "journey_model": (audit_results.get("architecture_profile") or audit_results.get("business_profile") or {}).get("journey_model", "general"),
        "journey_label": (audit_results.get("architecture_profile") or audit_results.get("business_profile") or {}).get("journey_label", "General / Unresolved Journey"),
        "secondary_journeys": (audit_results.get("architecture_profile") or audit_results.get("business_profile") or {}).get("secondary_journeys", []),
        "context_tags": (audit_results.get("architecture_profile") or audit_results.get("business_profile") or {}).get("context_tags", []),
        "commercial_architecture_diagnostics": scan_data.get("commercial_architecture_diagnostics", {}),
        # Keep full TCEA metadata available to paid/internal consumers. The free access
        # branch removes it before returning the public response.
        "commercial_evidence_architecture": audit_results.get("commercial_evidence_architecture", {}),
        "public_content_hygiene": scan_data.get("public_content_hygiene", {}),
        "commercial_eligibility": scan_data.get("commercial_eligibility", {}),
        "architect_review_queue": audit_results.get("architect_review_queue", []),
        "architect_review_summary": {
            "count": len(audit_results.get("architect_review_queue") or []),
            "critical": sum(1 for x in (audit_results.get("architect_review_queue") or []) if isinstance(x, dict) and str(x.get("severity")) == "CRITICAL"),
            "important": sum(1 for x in (audit_results.get("architect_review_queue") or []) if isinstance(x, dict) and str(x.get("severity")) == "IMPORTANT"),
            "status": "awaiting_architect" if (audit_results.get("architect_review_queue") or []) else "none",
        },
        "analysis_layers": audit_results.get("analysis_layers", {}),
        # Legacy alias retained for existing consumers.
        "business_profile": audit_results.get("business_profile", audit_results.get("architecture_profile", {})),
        "scan_quality": scan_data.get("scan_quality", {}),
        "evidence_coverage": scan_data.get("evidence_coverage", {}),
        "scoring_ledger": audit_results.get("scoring_ledger", []),
        "overlap_adjustments": audit_results.get("overlap_adjustments", []),
        "score_formula": audit_results.get("score_formula", {}),
        "ai_spectrum_status": audit_results.get("ai_spectrum_status", "unknown"),
        "cms_confidence": scan_data.get("cms_confidence", "low"),
        "report_checkpoint_summary": (admin_master_report or {}).get("checkpoint_summary", {}),
        "verification_coverage_note": (admin_master_report or {}).get("verification_coverage_note", ""),
        # Kept in protected server cache. Free responses strip this; paid responses expose all 50.
        "full_50_checkpoint_basis": audit_results.get("full_50_checkpoint_basis", []),
        "scanner_engine_version": scan_data.get("scanner_engine_version", "v7.2.2"),
        "evidence_receipts": audit_results.get("evidence_receipts", []),
        "high_impact_confirmation": audit_results.get("high_impact_confirmation", {}),
        "unconfirmed_high_impact_observations": audit_results.get("unconfirmed_high_impact_observations", []),
        "rescan_comparison": audit_results.get("rescan_comparison", {}),
        "customer_report_delivery": audit_results.get("customer_report_delivery", {}),
        "learning_memory": audit_results.get("learning_memory", {}),
    }


def _build_rescan_comparison(
    previous_payload: Optional[Dict[str, Any]],
    current_audit: Dict[str, Any],
    current_scan: Dict[str, Any],
) -> Dict[str, Any]:
    previous = previous_payload if isinstance(previous_payload, dict) else {}
    current = current_audit if isinstance(current_audit, dict) else {}
    current_score = current.get("overall_score")
    if current_score is None:
        current_score = current.get("overall_health_score")
    if not previous:
        return {
            "status": "BASELINE_CREATED",
            "has_previous_snapshot": False,
            "score_before": None,
            "score_after": current_score,
            "score_delta": None,
            "fixed_findings": [],
            "new_findings": [],
            "persistent_findings": [],
            "checkpoint_improvements": [],
            "checkpoint_regressions": [],
            "current_engine_version": current_scan.get("scanner_engine_version"),
            "note": "This scan establishes the baseline. A later forced re-scan can show verified architectural changes against this public-domain snapshot.",
        }

    previous_score = previous.get("overall_score")
    previous_findings = [x for x in (previous.get("top_10_financial_leaks") or []) if isinstance(x, dict)]
    current_packages = current.get("tiered_remediation_packages") or {}
    current_findings = [x for x in (current_packages.get("tier_10_arch10") or []) if isinstance(x, dict)]
    previous_ledger = [x for x in (previous.get("scoring_ledger") or []) if isinstance(x, dict)]
    current_ledger = [x for x in (current.get("scoring_ledger") or []) if isinstance(x, dict)]
    prev_source = previous_ledger or previous_findings
    curr_source = current_ledger or current_findings
    prev_rules = {str(x.get("rule_key") or "") for x in prev_source if x.get("rule_key")}
    curr_rules = {str(x.get("rule_key") or "") for x in curr_source if x.get("rule_key")}

    prev_cp = {
        int(x.get("id")): str(x.get("status"))
        for x in (previous.get("full_50_checkpoint_basis") or [])
        if isinstance(x, dict) and x.get("id") is not None
    }
    curr_cp = {
        int(x.get("id")): str(x.get("status"))
        for x in (current.get("full_50_checkpoint_basis") or [])
        if isinstance(x, dict) and x.get("id") is not None
    }
    improvements = []
    regressions = []
    for cp_id, before in prev_cp.items():
        after = curr_cp.get(cp_id)
        if after is None or after == before:
            continue
        if before == "FAIL" and after == "PASS":
            improvements.append({"checkpoint_id": cp_id, "before": before, "after": after})
        elif before == "PASS" and after == "FAIL":
            regressions.append({"checkpoint_id": cp_id, "before": before, "after": after})

    delta = None
    try:
        if previous_score is not None and current_score is not None:
            delta = round(float(current_score) - float(previous_score), 1)
    except Exception:
        delta = None

    previous_engine = previous.get("scanner_engine_version")
    current_engine = current_scan.get("scanner_engine_version")
    methodology_changed = bool(previous_engine and current_engine and previous_engine != current_engine)
    return {
        "status": "COMPARISON_AVAILABLE",
        "has_previous_snapshot": True,
        "score_before": previous_score,
        "score_after": current_score,
        "score_delta": delta,
        "fixed_findings": sorted(prev_rules - curr_rules),
        "new_findings": sorted(curr_rules - prev_rules),
        "persistent_findings": sorted(prev_rules & curr_rules),
        "checkpoint_improvements": improvements,
        "checkpoint_regressions": regressions,
        "previous_engine_version": previous_engine,
        "current_engine_version": current_engine,
        "methodology_changed": methodology_changed,
        "comparison_confidence": "directional_only" if methodology_changed else "same_engine_comparison",
        "comparison_basis": (
            "The scanner version changed between snapshots, so score/finding deltas may reflect both methodology and website changes; use this comparison directionally until a same-engine baseline exists."
            if methodology_changed
            else "Previous protected domain snapshot vs fresh scan using the same engine generation; the delta shows observed public architecture/evidence changed, not that revenue changed by the same amount."
        ),
    }


def _public_leak_class(leak: Dict[str, Any]) -> str:
    """Map a protected finding into a broad public class without exposing the finding identity."""
    raw = " ".join(str(leak.get(k) or "") for k in ("leak_class", "category", "family", "rule_key")).lower()
    if any(token in raw for token in ("trust", "proof", "review", "identity", "provider", "credib", "authority")):
        return "TRUST"
    if any(token in raw for token in ("delivery", "shipping", "return", "refund", "pricing", "expectation", "policy", "terms")):
        return "EXPECTATION"
    if any(token in raw for token in ("checkout", "cart", "conversion", "form", "booking", "reservation", "payment", "application", "completion", "primary_conversion", "continuity", "action")):
        return "COMPLETION"
    if any(token in raw for token in ("consistency", "contradict", "mismatch")):
        return "CONSISTENCY"
    if any(token in raw for token in ("measurement", "analytics", "tracking", "attribution")):
        return "MEASUREMENT"
    if any(token in raw for token in ("clarity", "message", "content", "heading", "h1")):
        return "CLARITY"
    if any(token in raw for token in ("speed", "performance", "mobile", "interaction")):
        return "PERFORMANCE"
    return "CUSTOMER PATH"


def _public_commercial_diagnosis(leaks: List[Dict[str, Any]]) -> Dict[str, Any]:
    classes: List[str] = []
    for leak in leaks:
        cls = _public_leak_class(leak)
        if cls not in classes:
            classes.append(cls)
        if len(classes) >= 4:
            break
    return {
        "priority_gap_count": len(leaks),
        "leak_classes": classes,
        "detail_boundary": "exact_evidence_financial_mechanism_commercial_minimums_and_remediation_protected",
    }


def _preview_leak(leak: Dict[str, Any]) -> Dict[str, Any]:
    """Free preview may show the problem, not the paid patch plan."""
    allowed = {
        "rule_key",
        "leak_name",
        "impact_summary",
        "finding_type",
        "severity_label",
        "severity_factor",
        "severity_score",
        "final_score_loss",
        "category",
        "confidence",
    }
    return {key: copy.deepcopy(value) for key, value in leak.items() if key in allowed}


def _apply_report_access(base_payload: Dict[str, Any], ticket: AccessTicket) -> Dict[str, Any]:
    result = copy.deepcopy(base_payload)
    all_leaks: List[Dict[str, Any]] = [
        item for item in (base_payload.get("top_10_financial_leaks") or []) if isinstance(item, dict)
    ]

    if ticket.mode == "paid" and ticket.plan_id in PLAN_CATALOG:
        plan = PLAN_CATALOG[ticket.plan_id]
        limit = int(plan["remediation_limit"])
        unlocked = copy.deepcopy(all_leaks[:limit])
        result["top_10_financial_leaks"] = unlocked
        result["top_5_seo_leaks"] = copy.deepcopy(unlocked[: min(5, limit)])
        result["report_access"] = {
            "plan_id": plan["plan_id"],
            "plan_name": plan["name"],
            "full_50_checkpoint_data": True,
            "remediation_findings_unlocked": len(unlocked),
            "remediation_limit": limit,
            "roadmap_days": int(plan.get("roadmap_days") or 0),
            "guidance_calls": plan["guidance_calls"],
            "guidance_call_minutes": plan["guidance_call_minutes"],
            "email_support_response_hours": plan["email_support_response_hours"],
            "purchased_domain": ticket.domain_key,
        }
        return _protect_methodology_for_customer(result)

    if ticket.mode in {"admin", "unmetered"}:
        result["report_access"] = {
            "plan_id": "internal_full",
            "full_50_checkpoint_data": True,
            "remediation_findings_unlocked": 10,
        }
        return result

    # Free keeps only public surface diagnostics + Google/local competitor context.
    # Exact commercial findings, Commercial Minimum gaps, causal/financial mechanisms,
    # detailed scoring evidence and remediation remain protected in the Vault/paid report.
    result["public_commercial_diagnosis"] = _public_commercial_diagnosis(all_leaks)
    result["verified_financial_leak_count"] = len(all_leaks)
    result["top_10_financial_leaks"] = []
    result["top_5_seo_leaks"] = []
    result.pop("key_friction_insight", None)
    result.pop("revenue_leak", None)
    result.pop("financial_exposure", None)
    result.pop("dev_handoff_kit", None)
    result.pop("commercial_architecture_diagnostics", None)
    result.pop("commercial_evidence_architecture", None)
    result.pop("architect_review_summary", None)
    result.pop("rescan_comparison", None)
    result.pop("learning_memory", None)
    result.pop("full_50_checkpoint_basis", None)
    result.pop("scoring_ledger", None)
    result.pop("overlap_adjustments", None)
    result.pop("score_formula", None)
    result.pop("evidence_receipts", None)
    result.pop("high_impact_confirmation", None)
    result.pop("unconfirmed_high_impact_observations", None)
    result.pop("architect_review_queue", None)
    result["report_access"] = {
        "plan_id": "free_preview",
        "plan_name": "Free Preview",
        "full_50_checkpoint_data": False,
        "remediation_findings_unlocked": 0,
        "preview_findings_shown": 0,
        "public_gap_count_shown": len(all_leaks),
        "locked_findings_count": len(all_leaks),
        "upgrade_required_for_patch_plan": True,
    }
    return _protect_methodology_for_customer(result)


def _attach_access_metadata(
    payload: Dict[str, Any],
    ticket: AccessTicket,
    *,
    cached: bool,
    cache_age_seconds: Optional[int] = None,
    email: Optional[str] = None,
    access_pass: Optional[str] = None,
) -> Dict[str, Any]:
    result = _apply_report_access(payload, ticket)
    result["scan_access"] = access_manager.access_summary(
        ticket,
        cached=cached,
        cache_age_seconds=cache_age_seconds,
        email=email,
        access_pass=access_pass,
    )
    if cached:
        result["message"] = "Recent verified result returned from protected cache; no new external scan/API work was performed."
    elif ticket.mode == "paid":
        plan = PLAN_CATALOG.get(ticket.plan_id or "", {})
        result["message"] = (
            f"Paid {plan.get('name','audit')} scan complete. "
            f"Detailed remediation is unlocked for up to the Top {plan.get('remediation_limit', ticket.remediation_limit or 0)} verified findings."
        )
    elif ticket.mode == "free":
        result["message"] = "Free preview complete. Detailed patch plans and full 50-checkpoint data unlock with a paid audit plan."
    return result


def _customer_report_for_ticket(admin_report: Dict[str, Any], ticket: AccessTicket) -> Optional[Dict[str, Any]]:
    if ticket.mode != "paid" or ticket.plan_id not in PLAN_CATALOG:
        return None
    plan = PLAN_CATALOG[ticket.plan_id]
    report = copy.deepcopy(admin_report)
    limit = int(plan["remediation_limit"])
    findings = [x for x in (report.get("top_10_financial_leaks") or []) if isinstance(x, dict)][:limit]
    report["top_10_financial_leaks"] = findings
    report["verified_revenue_findings"] = copy.deepcopy(findings)
    # Backward-compatible aliases plus the current 8-finding middle tier.
    report["top_6_financial_leaks"] = findings[:6]
    report["top_8_financial_leaks"] = findings[:8]
    # Do not let the summary table reveal locked finding identities from a higher plan.
    if reporter is not None and hasattr(reporter, "_build_at_a_glance"):
        report["at_a_glance"] = reporter._build_at_a_glance(
            report.get("verified_revenue_findings") or [],
            report.get("verification_priorities") or [],
            report.get("verified_strengths") or [],
            report.get("future_optimizations") or [],
        )
    report["customer_plan"] = dict(plan)
    report["remediation_limit"] = limit
    report["purchased_domain"] = ticket.domain_key

    roadmap_days = int(plan.get("roadmap_days") or 0)
    report["roadmap_days"] = roadmap_days
    if reporter is not None and hasattr(reporter, "build_implementation_roadmap"):
        report["implementation_roadmap"] = reporter.build_implementation_roadmap(
            findings, roadmap_days
        )
    else:
        report["implementation_roadmap"] = []

    # Customer-facing reports remain fully actionable but do not expose the private
    # inference signals, exact weighting matrix or public-score calibration constants.
    report = _protect_methodology_for_customer(report)
    return report


async def _execute_reserved_scan(
    payload: AuditRequest,
    background_tasks: BackgroundTasks,
    ticket: AccessTicket,
    validated_target: Any,
    previous_snapshot: Optional[Dict[str, Any]],
    email: Optional[str],
    access_pass: Optional[str],
) -> Dict[str, Any]:
    """Execute one already-authorized scan and settle its reservation exactly once."""
    try:
        scan_data = await _run_scan_async(validated_target.url, payload.business_name or "", payload.business_type)
        if not scan_data.get("is_reachable"):
            raise HTTPException(
                status_code=400,
                detail=f"Domain '{payload.domain}' is offline, unreachable, or blocking both HTTP and browser inspection.",
            )

        eligibility = scan_data.get("commercial_eligibility") if isinstance(scan_data.get("commercial_eligibility"), dict) else {}
        if eligibility and not eligibility.get("allow_scan", True):
            # Product-fit decline: do not consume allowance or fabricate a commercial score.
            access_manager.finish(ticket, success=False)
            return {
                "success": False,
                "status": "not_commercial_target",
                "target_domain": payload.domain,
                "commercial_eligibility": eligibility,
                "scanner_engine_version": scan_data.get("scanner_engine_version", "v7.5.3"),
                "message": eligibility.get("reason") or "This site does not expose a sufficiently strong commercial/revenue journey for Trilloka Revenue Readiness scoring.",
            }

        if scan_data.get("requires_business_type_confirmation"):
            # This is not a failed website scan and must not consume the user's scan allowance.
            # The scanner deliberately stops before scoring because category-specific importance
            # would otherwise be based on an unresolved business model.
            access_manager.finish(ticket, success=False)
            confirmation = dict(scan_data.get("business_type_confirmation") or {})
            profile = scan_data.get("architecture_profile") or scan_data.get("business_profile") or {}
            return {
                "success": False,
                "status": "business_type_confirmation_required",
                "target_domain": payload.domain,
                "requires_business_type_confirmation": True,
                "business_type": profile.get("business_type", "general"),
                "business_type_label": profile.get("business_type_label", "General / Unresolved Business"),
                "business_type_confidence": profile.get("business_type_confidence"),
                "business_type_confirmation": confirmation,
                "scanner_engine_version": scan_data.get("scanner_engine_version", "v7.5.3"),
                "message": "Trilloka could not resolve the business category confidently enough for the category deep dive. Choose the closest business type and run the scan again; no score was generated and this attempt was released rather than counted as a completed scan.",
            }

        try:
            # Pass 1 identifies candidates. It is not the final commercial score when a finding can
            # create a large deduction; proof-backed candidates must survive an independent passive recheck.
            preliminary_audit = scorer.audit_and_score(
                scan_data=scan_data,
                business_type=payload.business_type,
                competitor_data_present=payload.competitor_has_feature,
            )
            try:
                threshold = float(os.environ.get("TRILLOKA_CONFIRMATION_THRESHOLD_POINTS", "3.5"))
            except Exception:
                threshold = 3.5
            if hasattr(scanner, "confirm_high_impact_findings"):
                try:
                    confirmation = await scanner.confirm_high_impact_findings(
                        scan_data, preliminary_audit, payload.business_type, threshold
                    )
                except Exception as confirm_exc:
                    print(f"[Confirmation] High-impact confirmation failed closed — {confirm_exc}")
                    confirmation = {
                        "completed": True,
                        "threshold_points": threshold,
                        "candidate_count": None,
                        "results": {},
                        "error": str(confirm_exc),
                        "policy": "Confirmation phase failed; severe first-pass candidates are unscored rather than treated as verified failures.",
                    }
                scan_data["high_impact_confirmation"] = confirmation
            else:
                scan_data["high_impact_confirmation"] = {
                    "completed": True,
                    "threshold_points": threshold,
                    "candidate_count": None,
                    "results": {},
                    "policy": "Confirmation method unavailable; severe first-pass candidates are unscored.",
                }

            # Pass 2 is authoritative. Confirmed severe findings score fully, corroborated findings
            # score conservatively, and disputed/unconfirmed findings remain unscored observations.
            audit_results = scorer.audit_and_score(
                scan_data=scan_data,
                business_type=payload.business_type,
                competitor_data_present=payload.competitor_has_feature,
            )
            rescan_comparison = _build_rescan_comparison(
                previous_snapshot, audit_results, scan_data
            )
            if (
                not rescan_comparison.get("has_previous_snapshot")
                and REPORT_ENGINE_AVAILABLE and reporter is not None
                and hasattr(reporter, "build_vault_rescan_comparison")
            ):
                try:
                    vault_comparison = reporter.build_vault_rescan_comparison(payload.domain, audit_results)
                    if isinstance(vault_comparison, dict) and vault_comparison.get("has_previous_snapshot"):
                        rescan_comparison = vault_comparison
                except Exception as compare_exc:
                    print(f"[Rescan] Vault comparison skipped — {compare_exc}")
            audit_results["rescan_comparison"] = rescan_comparison

            # V7.4 human-escalation layer: difficult visual/interactive/external judgments are
            # surfaced to the Architect instead of being converted into automatic failures.
            architect_queue = build_architect_review_queue(scan_data, audit_results, require_final_proof=(ticket.mode == "paid"))
            audit_results["architect_review_queue"] = architect_queue
            scan_data["architect_review_queue"] = architect_queue
            try:
                review_ids = []
                # Free previews may disclose that human judgment is advisable, but they do not
                # create operational owner workload. Paid reports and owner/internal scans can.
                if ticket.mode in {"paid", "admin"}:
                    review_ids = learning_memory.add_architect_reviews(
                        domain=payload.domain,
                        vault_id=str(audit_results.get("vault_id") or ""),
                        reviews=architect_queue,
                    )
                audit_results["architect_review_ids"] = review_ids
            except Exception as review_exc:
                print(f"[Architect Review] Queue persistence skipped — {review_exc}")

            # User category corrections become bounded recognition knowledge. Candidate knowledge
            # never changes production scoring automatically.
            if payload.classification_confirmation and str(payload.business_type or "auto").lower() not in {"", "auto", "general"}:
                try:
                    learning_memory.record_classification_confirmation(
                        domain=payload.domain, selected_business_type=payload.business_type, scan=scan_data,
                        previous_candidates=payload.classification_previous_candidates or {},
                        source="user_category_confirmation", subtype_label=str(payload.business_subtype or ""),
                    )
                except Exception as learn_exc:
                    print(f"[Learning] Classification correction skipped — {learn_exc}")

            try:
                learning_memory.record_completed_scan(domain=payload.domain, scan=scan_data, audit=audit_results)
                audit_results["learning_memory"] = learning_memory.stats()
            except Exception as learn_exc:
                print(f"[Learning] Completed-scan memory skipped — {learn_exc}")
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except Exception as exc:
            import traceback

            print(f"[Scorer] Crash — {exc}")
            traceback.print_exc()
            raise HTTPException(
                status_code=500,
                detail="Scoring engine failed. No substitute or fallback score was generated.",
            ) from exc

        resolved_score = audit_results.get("overall_score")
        if resolved_score is None:
            resolved_score = audit_results.get("overall_health_score")
        if resolved_score is None:
            raise HTTPException(
                status_code=500,
                detail="Scoring engine completed without an overall score. No synthetic zero was returned.",
            )

        admin_master_report: Optional[Dict[str, Any]] = None
        customer_report: Optional[Dict[str, Any]] = None
        if REPORT_ENGINE_AVAILABLE and reporter is not None:
            try:
                admin_master_report = reporter.generate_admin_master_report(audit_results, scan_data)
                customer_report = _customer_report_for_ticket(admin_master_report, ticket)
                background_tasks.add_task(
                    reporter.archive_to_vault,
                    target_domain=payload.domain,
                    admin_report=admin_master_report,
                    raw_scan_data=scan_data,
                )
                background_tasks.add_task(reporter.send_admin_alert_email, admin_report=admin_master_report)
                if customer_report is not None and email and hasattr(reporter, "send_customer_report_email"):
                    # V7.4 holds the paid customer email until the human Architect resolves the
                    # review queue. This makes "Architect-reviewed" an operational truth rather
                    # than marketing copy. The automated scan result remains available immediately.
                    review_ids = list(audit_results.get("architect_review_ids") or [])
                    try:
                        queued = learning_memory.queue_pending_report(
                            vault_id=str(admin_master_report.get("vault_id") or audit_results.get("vault_id") or ""),
                            domain=payload.domain, customer_email=str(email), report=customer_report, review_ids=review_ids
                        )
                        audit_results["customer_report_delivery"] = {
                            "status": "awaiting_architect_review" if queued.get("queued") else "not_queued",
                            "review_count": len(review_ids),
                        }
                    except Exception as pending_exc:
                        print(f"[Report Engine] Pending Architect delivery queue failed — {pending_exc}")
            except Exception as exc:
                print(f"[Report Engine] Delivery/archive skipped — {exc}")

        base_payload = _base_success_payload(
            requested_domain=payload.domain,
            scan_data=scan_data,
            audit_results=audit_results,
            admin_master_report=admin_master_report,
        )
        # Cache only the complete generic engine result. Visibility is applied per requester later.
        access_manager.cache_put(ticket.domain_key, base_payload)
        access_manager.finish(ticket, success=True)
        return _attach_access_metadata(
            base_payload,
            ticket,
            cached=False,
            email=email,
            access_pass=access_pass,
        )

    except HTTPException:
        access_manager.finish(ticket, success=False)
        raise
    except Exception as exc:
        access_manager.finish(ticket, success=False)
        print(f"[Scanner] Fatal scan error: {exc}")
        raise HTTPException(
            status_code=500,
            detail="Scanner execution failed before a defensible diagnostic could be produced",
        ) from exc


async def _run_audit_impl(
    payload: AuditRequest,
    background_tasks: BackgroundTasks,
    http_request: FastAPIRequest,
    response: Response,
    x_trilloka_admin_session: Optional[str],
    x_trilloka_admin_key: Optional[str],
) -> Dict[str, Any]:
    guardrail_response = handle_trilloka_guardrail(payload.domain)
    if guardrail_response:
        return guardrail_response

    # Reject SSRF/internal-network targets before quota reservation, cache lookup, Google
    # API usage, HTTP probing or Chromium launch. DNS is resolved here for an early 400;
    # the scanner revalidates and pins every actual server-side connection independently.
    try:
        validated_target = await asyncio.to_thread(validate_public_http_url, payload.domain)
    except NetworkTargetError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Unsafe or invalid scan target ({exc.reason}): {exc}",
        ) from exc

    domain_key = access_manager.normalize_domain(validated_target.url)
    if not domain_key:
        raise HTTPException(status_code=400, detail="A valid target domain is required")

    previous_snapshot: Optional[Dict[str, Any]] = None
    try:
        previous_cached = access_manager.cache_get(domain_key, 365 * 24 * 60 * 60)
        if previous_cached:
            previous_snapshot = copy.deepcopy(previous_cached[0])
    except Exception as exc:
        print(f"[Rescan] Previous snapshot lookup skipped — {exc}")

    device_id = _resolve_scan_device_id(http_request, response)
    client_ip = access_manager.client_ip(http_request)
    email = str(payload.email) if payload.email else None
    access_pass = str(payload.access_pass or "").strip() or None
    # Bypass is available only to a verified owner/admin session.
    admin_bypass = _is_admin_session(
        http_request, x_trilloka_admin_session, x_trilloka_admin_key
    )

    # Only a valid paid pass can invoke paid duplicate protection.
    try:
        is_duplicate = access_manager.recent_paid_duplicate(
            email,
            domain_key,
            access_pass,
            force_refresh=bool(payload.force_refresh),
        )
    except AccessDenied as exc:
        raise _access_error(exc) from exc

    if is_duplicate:
        cached = access_manager.cache_get(domain_key, access_manager.paid_duplicate_grace_seconds)
        if cached:
            cached_payload, age = cached
            access_manager.note_cache_hit("paid_duplicate")
            status = access_manager.entitlement_status(email, domain_key, access_pass)
            plan = status.get("plan") or {}
            ticket = AccessTicket(
                mode="paid",
                usage_id=None,
                subject_hash=access_manager.email_subject(email),
                domain_key=domain_key,
                plan_id=plan.get("plan_id"),
                scans_per_day=plan.get("scans_per_day"),
                scans_remaining_today=status.get("scans_remaining_today"),
                remediation_limit=plan.get("remediation_limit"),
                expires_at=status.get("expires_at"),
                reservation_consumes_quota=False,
            )
            return _attach_access_metadata(
                cached_payload,
                ticket,
                cached=True,
                cache_age_seconds=age,
                email=email,
                access_pass=access_pass,
            )

    try:
        ticket = access_manager.reserve(
            ip=client_ip,
            device_id=device_id,
            email=email,
            domain_key=domain_key,
            access_pass=access_pass,
            admin_bypass=admin_bypass,
        )
    except AccessDenied as exc:
        raise _access_error(exc) from exc

    # Free preview requests may reuse a 24-hour domain result while still consuming the one free
    # preview allowance, protecting PageSpeed/Places/Chromium cost.
    if ticket.mode == "free":
        cached = access_manager.cache_get(domain_key, access_manager.free_cache_seconds)
        if cached:
            cached_payload, age = cached
            access_manager.finish(ticket, success=True)
            access_manager.note_cache_hit("free")
            return _attach_access_metadata(
                cached_payload,
                ticket,
                cached=True,
                cache_age_seconds=age,
                email=email,
                access_pass=access_pass,
            )

    return await _execute_reserved_scan(
        payload=payload,
        background_tasks=background_tasks,
        ticket=ticket,
        validated_target=validated_target,
        previous_snapshot=previous_snapshot,
        email=email,
        access_pass=access_pass,
    )

def _scan_job_public_meta(job: Dict[str, Any]) -> Dict[str, Any]:
    now = int(time.time())
    return {
        "job_id": str(job.get("job_id") or ""),
        "status": str(job.get("status") or "processing"),
        "domain": str(job.get("domain_key") or ""),
        "created_at": int(job.get("created_at") or 0),
        "completed_at": int(job.get("completed_at") or 0) or None,
        "expires_at": int(job.get("expires_at") or 0),
        "expires_in_seconds": max(0, int(job.get("expires_at") or 0) - now),
    }


def _replay_existing_result(job: Dict[str, Any]) -> Dict[str, Any]:
    result = copy.deepcopy(job.get("result") or {})
    completed_at = int(job.get("completed_at") or job.get("updated_at") or 0)
    age = max(0, int(time.time()) - completed_at) if completed_at else 0
    result["scan_replay"] = {
        "replayed": True,
        "fresh_scan_run": False,
        "replay_reason": "SAME_DEVICE_DOMAIN_24H_REVIEW",
        "original_job_id": str(job.get("job_id") or ""),
        "original_completed_at": completed_at or None,
        "age_seconds": age,
        "review_window_hours": round(access_manager.free_cache_seconds / 3600, 2),
    }
    access = result.get("scan_access") if isinstance(result.get("scan_access"), dict) else {}
    access.update({
        "cached": True,
        "replayed_existing_scan": True,
        "fresh_scan_run": False,
        "cache_age_seconds": age,
    })
    result["scan_access"] = access
    result["message"] = (
        "24-hour scan review: this is your previously completed result for this domain. "
        "No new scan was run and no additional scan allowance was used."
    )
    return result


async def _process_scan_job(
    *,
    job_id: str,
    payload_data: Dict[str, Any],
    ticket: AccessTicket,
    validated_target: Any,
    previous_snapshot: Optional[Dict[str, Any]],
    email: Optional[str],
    access_pass: Optional[str],
) -> None:
    # This runs after the 202 response is returned. The durable SQLite job row lets the
    # browser reconnect or refresh while the expensive scan continues server-side.
    job_background = BackgroundTasks()
    try:
        payload = AuditRequest(**payload_data)
        result = await _execute_reserved_scan(
            payload=payload,
            background_tasks=job_background,
            ticket=ticket,
            validated_target=validated_target,
            previous_snapshot=previous_snapshot,
            email=email,
            access_pass=access_pass,
        )
        access_manager.complete_scan_job(job_id, result)
        try:
            await job_background()
        except Exception as delivery_exc:
            print(f"[Scan Job] Report delivery/archive task failed after result completion — {delivery_exc}")
    except HTTPException as exc:
        reason = str((exc.headers or {}).get("X-Trilloka-Access-Reason") or "SCAN_FAILED")
        access_manager.fail_scan_job(
            job_id,
            status_code=int(exc.status_code or 500),
            reason=reason,
            detail=str(exc.detail or "Scan failed"),
        )
    except Exception as exc:
        access_manager.fail_scan_job(
            job_id,
            status_code=500,
            reason="SCAN_FAILED",
            detail="Scanner execution failed before a defensible diagnostic could be produced",
        )
        print(f"[Scan Job] Fatal worker error — {exc}")


@app.post("/api/scan/classify")
async def classify_scan_business(payload: BusinessClassificationRequest) -> Dict[str, Any]:
    """Preflight business-category inference before quota reservation or full scoring.

    Frontends may call this first. If the category is ambiguous, show the returned options and
    resubmit the full scan with the user's chosen business_type.
    """
    guardrail_response = handle_trilloka_guardrail(payload.domain)
    if guardrail_response:
        return {
            "success": True,
            "status": "protected_domain",
            "target_domain": payload.domain,
            "requires_business_type_confirmation": False,
            "message": "Protected Trilloka domain; public category preflight was not run.",
        }
    try:
        validated_target = await asyncio.to_thread(validate_public_http_url, payload.domain)
    except NetworkTargetError as exc:
        raise HTTPException(status_code=400, detail=f"Unsafe or invalid scan target ({exc.reason}): {exc}") from exc
    try:
        return await scanner.classify_business_type(validated_target.url, payload.business_name or "")
    except Exception as exc:
        print(f"[Classification] Preflight failed — {exc}")
        raise HTTPException(status_code=500, detail="Business-category preflight failed before a category could be resolved.") from exc


@app.post("/api/scan/start")
async def start_scan_job(
    payload: AuditRequest,
    background_tasks: BackgroundTasks,
    http_request: FastAPIRequest,
    response: Response,
    x_trilloka_admin_session: Optional[str] = Header(default=None, alias="X-Trilloka-Admin-Session"),
    x_trilloka_admin_key: Optional[str] = Header(default=None, alias="X-Trilloka-Admin-Key"),
) -> Dict[str, Any]:
    """Start or resume a long-running scan without tying completion to one browser request."""
    guardrail_response = handle_trilloka_guardrail(payload.domain)
    if guardrail_response:
        return {
            "state": "complete",
            "replayed": False,
            "fresh_scan_run": False,
            "result": guardrail_response,
            "message": "Protected self-diagnostic returned without launching a public scan job.",
        }

    try:
        validated_target = await asyncio.to_thread(validate_public_http_url, payload.domain)
    except NetworkTargetError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Unsafe or invalid scan target ({exc.reason}): {exc}",
        ) from exc

    domain_key = access_manager.normalize_domain(validated_target.url)
    if not domain_key:
        raise HTTPException(status_code=400, detail="A valid target domain is required")

    device_id = _resolve_scan_device_id(http_request, response)
    email = str(payload.email) if payload.email else None
    access_pass = str(payload.access_pass or "").strip() or None
    admin_bypass = _is_admin_session(http_request, x_trilloka_admin_session, x_trilloka_admin_key)

    # First, recover the same browser's own job/result. This occurs BEFORE quota reservation,
    # so reviewing the same free URL for 24 hours cannot consume a second free scan.
    existing = access_manager.find_device_domain_job(
        device_id=device_id,
        domain_key=domain_key,
        max_age_seconds=access_manager.free_cache_seconds,
    )
    if existing:
        state = str(existing.get("status") or "")
        existing_mode = str(existing.get("mode") or "")
        if state == "processing":
            response.status_code = 202
            return {
                "state": "processing",
                "resumed": True,
                "replayed": False,
                "fresh_scan_run": False,
                "job": _scan_job_public_meta(existing),
                "message": "Your existing scan is still processing. No second scan was started.",
            }
        existing_result = existing.get("result") if isinstance(existing.get("result"), dict) else {}
        allow_replay = (
            state == "complete"
            and isinstance(existing.get("result"), dict)
            and str(existing_result.get("status") or "") != "business_type_confirmation_required"
            and not (existing_mode == "free" and access_pass)
            and not (existing_mode == "paid" and bool(payload.force_refresh))
        )
        if allow_replay:
            access_manager.note_cache_hit("same_device_24h_review")
            return {
                "state": "complete",
                "resumed": True,
                "replayed": True,
                "fresh_scan_run": False,
                "job": _scan_job_public_meta(existing),
                "result": _replay_existing_result(existing),
                "message": "Showing the scan already completed for this URL within your 24-hour review window. No new scan was run.",
            }

    # Preserve the existing paid accidental-double-submit protection for jobs created before
    # this resumable-job release or by older clients.
    try:
        is_paid_duplicate = access_manager.recent_paid_duplicate(
            email,
            domain_key,
            access_pass,
            force_refresh=bool(payload.force_refresh),
        )
    except AccessDenied as exc:
        raise _access_error(exc) from exc

    if is_paid_duplicate:
        cached = access_manager.cache_get(domain_key, access_manager.paid_duplicate_grace_seconds)
        if cached:
            cached_payload, age = cached
            status = access_manager.entitlement_status(email, domain_key, access_pass)
            plan = status.get("plan") or {}
            ticket = AccessTicket(
                mode="paid",
                usage_id=None,
                subject_hash=access_manager.email_subject(email),
                domain_key=domain_key,
                plan_id=plan.get("plan_id"),
                scans_per_day=plan.get("scans_per_day"),
                scans_remaining_today=status.get("scans_remaining_today"),
                remediation_limit=plan.get("remediation_limit"),
                expires_at=status.get("expires_at"),
                reservation_consumes_quota=False,
            )
            result = _attach_access_metadata(
                cached_payload,
                ticket,
                cached=True,
                cache_age_seconds=age,
                email=email,
                access_pass=access_pass,
            )
            result["message"] = "Recent paid result returned; no duplicate scan was run."
            return {"state": "complete", "replayed": True, "fresh_scan_run": False, "result": result}

    client_ip = access_manager.client_ip(http_request)
    try:
        ticket = access_manager.reserve(
            ip=client_ip,
            device_id=device_id,
            email=email,
            domain_key=domain_key,
            access_pass=access_pass,
            admin_bypass=admin_bypass,
        )
    except AccessDenied as exc:
        raise _access_error(exc) from exc

    previous_snapshot: Optional[Dict[str, Any]] = None
    try:
        previous_cached = access_manager.cache_get(domain_key, 365 * 24 * 60 * 60)
        if previous_cached:
            previous_snapshot = copy.deepcopy(previous_cached[0])
    except Exception as exc:
        print(f"[Scan Job] Previous snapshot lookup skipped — {exc}")

    try:
        job_id = access_manager.create_scan_job(ticket, device_id=device_id)
    except Exception:
        # Do not consume an allowance if durable job creation itself fails.
        access_manager.finish(ticket, success=False)
        raise HTTPException(status_code=503, detail="Could not create a resumable scan job. Please try again.")

    background_tasks.add_task(
        _process_scan_job,
        job_id=job_id,
        payload_data=payload.model_dump(mode="json"),
        ticket=ticket,
        validated_target=validated_target,
        previous_snapshot=previous_snapshot,
        email=email,
        access_pass=access_pass,
    )
    response.status_code = 202
    job = access_manager.get_scan_job(job_id, device_id=device_id) or {
        "job_id": job_id, "status": "processing", "domain_key": domain_key,
        "created_at": int(time.time()), "expires_at": int(time.time()) + access_manager.free_cache_seconds,
    }
    return {
        "state": "processing",
        "resumed": False,
        "replayed": False,
        "fresh_scan_run": True,
        "job": _scan_job_public_meta(job),
        "message": "Scan started. You can refresh or reconnect; this job will continue server-side and the completed result can be reviewed again for 24 hours.",
    }


@app.get("/api/scan/status/{job_id}")
async def get_scan_job_status(
    job_id: str,
    http_request: FastAPIRequest,
    response: Response,
) -> Dict[str, Any]:
    device_id = _resolve_scan_device_id(http_request, response)
    job = access_manager.get_scan_job(job_id, device_id=device_id)
    if not job:
        raise HTTPException(status_code=404, detail="Scan job was not found for this browser or its review window has expired.")

    meta = _scan_job_public_meta(job)
    state = str(job.get("status") or "processing")
    if state == "complete":
        return {
            "state": "complete",
            "replayed": False,
            "fresh_scan_run": True,
            "job": meta,
            "result": job.get("result") or {},
            "message": "Scan complete.",
        }
    if state == "failed":
        return {
            "state": "failed",
            "job": meta,
            "error": {
                "status": int(job.get("error_status") or 500),
                "reason": str(job.get("error_reason") or "SCAN_FAILED"),
                "detail": str(job.get("error_detail") or "The scan did not complete."),
            },
        }
    return {
        "state": "processing",
        "job": meta,
        "message": "Architectural Analysis is still processing. No second scan is required.",
    }


@app.post("/api/audit")
async def run_audit(
    payload: AuditRequest,
    background_tasks: BackgroundTasks,
    http_request: FastAPIRequest,
    response: Response,
    x_trilloka_admin_session: Optional[str] = Header(default=None, alias="X-Trilloka-Admin-Session"),
    x_trilloka_admin_key: Optional[str] = Header(default=None, alias="X-Trilloka-Admin-Key"),
) -> Dict[str, Any]:
    return await _run_audit_impl(
        payload, background_tasks, http_request, response, x_trilloka_admin_session, x_trilloka_admin_key
    )


@app.post("/api/scan")
async def run_scan(
    payload: AuditRequest,
    background_tasks: BackgroundTasks,
    http_request: FastAPIRequest,
    response: Response,
    x_trilloka_admin_session: Optional[str] = Header(default=None, alias="X-Trilloka-Admin-Session"),
    x_trilloka_admin_key: Optional[str] = Header(default=None, alias="X-Trilloka-Admin-Key"),
) -> Dict[str, Any]:
    return await _run_audit_impl(
        payload, background_tasks, http_request, response, x_trilloka_admin_session, x_trilloka_admin_key
    )


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)