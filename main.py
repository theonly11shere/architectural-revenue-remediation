"""Trilloka Architect Engine V6 API gateway with tiered paid-plan entitlements.

Scanner compatibility
---------------------
* Public scan routes remain POST /api/audit and POST /api/scan.
* Existing request fields remain accepted.
* Existing successful-response keys remain present.
* New purchase/pass/report-access fields are additive.

Commercial access
-----------------
* Free preview: one successful scan per IP/device per rolling 24h.
* $350 Essential: Top 3 remediation, full 50-check data, 2 scans/day for 30 days.
* $550 Advanced: Top 6 remediation, full 50-check data, 3 scans/day for 30 days,
  one 15-minute guidance call.
* $850 Architect: Top 10 remediation, full 50-check data, 4 scans/day for 30 days,
  two 15-minute guidance calls and a 15-hour email-support response target.
* Paid access is bound to email + purchased domain + a secure purchase access pass.
"""

from __future__ import annotations

import asyncio
import copy
import hmac
import json
import os
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import uvicorn
from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Request as FastAPIRequest, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr

from hybrid_scanner import HybridScanner
from scan_access import AccessDenied, AccessTicket, PLAN_CATALOG, ScanAccessManager
from scorer import RevenueScorer

try:
    from report_engine import ReportGenerator

    reporter = ReportGenerator()
    REPORT_ENGINE_AVAILABLE = True
except Exception as exc:
    print(f"[Report Engine] Import failed: {exc}")
    reporter = None
    REPORT_ENGINE_AVAILABLE = False


app = FastAPI(
    title="Trilloka Architect Engine API",
    description="Evidence-weighted Revenue Readiness Diagnostic & Tiered Report Gateway",
    version="6.3.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

scanner = HybridScanner()
scorer = RevenueScorer()
access_manager = ScanAccessManager()


class AuditRequest(BaseModel):
    domain: str
    business_name: Optional[str] = ""
    business_type: str = "auto"
    competitor_has_feature: Optional[bool] = None
    email: Optional[EmailStr] = None
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


def _admin_key_valid(value: Optional[str]) -> bool:
    configured = os.environ.get("TRILLOKA_ADMIN_API_KEY", "").strip()
    return bool(configured and value and hmac.compare_digest(value.strip(), configured))


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


def handle_trilloka_guardrail(target_domain: str) -> Optional[Dict[str, Any]]:
    clean_url = target_domain if target_domain.startswith(("http://", "https://")) else f"https://{target_domain}"
    domain = urlparse(clean_url).netloc.lower() or target_domain.lower()
    if "trilloka" not in domain:
        return None

    snapshot_file = "trilloka_30day_audit_snapshot.json"
    snapshot_data: Dict[str, Any] = {}
    if os.path.exists(snapshot_file):
        try:
            with open(snapshot_file, "r", encoding="utf-8") as handle:
                snapshot_data = json.load(handle)
        except Exception as exc:
            print(f"[Guardrail] Error reading snapshot JSON: {exc}")

    score = float(snapshot_data.get("overall_score", 75.0))
    return {
        "success": True,
        "is_guarded": True,
        "target_domain": target_domain,
        "status": "INTERCEPTED",
        "guardrail": {
            "heading": "Nice try!!!",
            "message": "Did you really think we didn't know some of you wouldn't be able to resist yourselves. Well, The Architect has commanded us to scan his own website every 30 days and check its ongoing state of strength...",
            "note": "While external public scans are barred on core infrastructure, below are the latest stored Trilloka self-diagnostic results.",
        },
        "overall_score": score,
        "surface_metrics": {
            "mobile_performance_score": snapshot_data.get("mobile_performance_score", score),
            "seo_health_index": snapshot_data.get("seo_health_index", score),
            "ai_spectrum_pct": snapshot_data.get("ai_spectrum_pct", 0.0),
            "online_presence_index": snapshot_data.get("online_presence_index", score),
            "conversion_efficiency": snapshot_data.get("conversion_efficiency", score),
            "competitor_gap_score": 0,
            "classification": "Architect Core Platform",
        },
        "key_friction_insight": {
            "passed_count": snapshot_data.get("passed_count", 3),
            "failed_count": snapshot_data.get("failed_count", 1),
            "load_time_seconds": snapshot_data.get("load_time_seconds", 0.97),
        },
        "revenue_leak": snapshot_data.get(
            "revenue_leak", {"est_annual_revenue_leak": "Self-scan exposure stored in latest snapshot"}
        ),
        "cms_platform": snapshot_data.get("cms_detected", "Trilloka Engine"),
        "audit_snapshot": snapshot_data,
        "message": "Trilloka infrastructure self-scan intercepted. Displaying stored diagnostic snapshot.",
    }


@app.get("/health")
def health_check() -> Dict[str, Any]:
    return {
        "status": "online",
        "system": "Trilloka Architect Engine v6.3",
        "google_api_configured": bool(os.environ.get("PAGESPEED_API_KEY") or os.environ.get("GOOGLE_API_KEY")),
        "report_engine": REPORT_ENGINE_AVAILABLE,
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
    x_trilloka_admin_key: Optional[str] = Header(default=None, alias="X-Trilloka-Admin-Key"),
) -> Dict[str, Any]:
    """Called only after your payment backend has independently verified a successful purchase.

    The plaintext purchase pass is returned once. Store/deliver it through the payment success
    flow; only its HMAC hash is retained by Trilloka.
    """
    if not _admin_key_valid(x_trilloka_admin_key):
        raise HTTPException(status_code=403, detail="Admin authorization required")
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
    x_trilloka_admin_key: Optional[str] = Header(default=None, alias="X-Trilloka-Admin-Key"),
) -> Dict[str, Any]:
    """Backward-compatible endpoint name. It now activates one of the three 30-day plans."""
    if not _admin_key_valid(x_trilloka_admin_key):
        raise HTTPException(status_code=403, detail="Admin authorization required")
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


@app.get("/api/admin/scan-usage")
def scan_usage(
    x_trilloka_admin_key: Optional[str] = Header(default=None, alias="X-Trilloka-Admin-Key"),
) -> Dict[str, Any]:
    if not _admin_key_valid(x_trilloka_admin_key):
        raise HTTPException(status_code=403, detail="Admin authorization required")
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
    active_only: bool = False,
    limit: int = 100,
    x_trilloka_admin_key: Optional[str] = Header(default=None, alias="X-Trilloka-Admin-Key"),
) -> Dict[str, Any]:
    if not _admin_key_valid(x_trilloka_admin_key):
        raise HTTPException(status_code=403, detail="Admin authorization required")
    return {"success": True, **access_manager.list_entitlements(active_only=active_only, limit=limit)}


@app.post("/api/admin/entitlement/status")
def admin_entitlement_lookup(
    payload: EntitlementAdminRef,
    x_trilloka_admin_key: Optional[str] = Header(default=None, alias="X-Trilloka-Admin-Key"),
) -> Dict[str, Any]:
    """Owner lookup uses a POST body so customer email/domain are not placed in the URL."""
    if not _admin_key_valid(x_trilloka_admin_key):
        raise HTTPException(status_code=403, detail="Admin authorization required")
    status = access_manager.entitlement_status(str(payload.email), payload.domain)
    if not status.get("exists"):
        raise HTTPException(status_code=404, detail="No entitlement exists for this email/domain")
    return {"success": True, **status}


@app.post("/api/admin/entitlement/update")
def admin_update_entitlement(
    payload: EntitlementUpdateRequest,
    x_trilloka_admin_key: Optional[str] = Header(default=None, alias="X-Trilloka-Admin-Key"),
) -> Dict[str, Any]:
    """Upgrade/downgrade, extend/shorten expiry, or change payment reference without changing the pass."""
    if not _admin_key_valid(x_trilloka_admin_key):
        raise HTTPException(status_code=403, detail="Admin authorization required")
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
    x_trilloka_admin_key: Optional[str] = Header(default=None, alias="X-Trilloka-Admin-Key"),
) -> Dict[str, Any]:
    if not _admin_key_valid(x_trilloka_admin_key):
        raise HTTPException(status_code=403, detail="Admin authorization required")
    try:
        result = access_manager.revoke_entitlement(email=str(payload.email), domain=payload.domain)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, "revoked": True, **result}


@app.post("/api/admin/entitlement/restore")
def admin_restore_entitlement(
    payload: EntitlementAdminRef,
    x_trilloka_admin_key: Optional[str] = Header(default=None, alias="X-Trilloka-Admin-Key"),
) -> Dict[str, Any]:
    if not _admin_key_valid(x_trilloka_admin_key):
        raise HTTPException(status_code=403, detail="Admin authorization required")
    try:
        result = access_manager.restore_entitlement(email=str(payload.email), domain=payload.domain)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, "restored": True, **result}


@app.post("/api/admin/entitlement/rotate-pass")
def admin_rotate_pass(
    payload: EntitlementAdminRef,
    x_trilloka_admin_key: Optional[str] = Header(default=None, alias="X-Trilloka-Admin-Key"),
) -> Dict[str, Any]:
    """Issue a replacement pass. The old pass stops working immediately."""
    if not _admin_key_valid(x_trilloka_admin_key):
        raise HTTPException(status_code=403, detail="Admin authorization required")
    try:
        result = access_manager.rotate_access_pass(email=str(payload.email), domain=payload.domain)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, "pass_rotated": True, **result}


@app.post("/api/admin/entitlement/change-domain")
def admin_change_domain(
    payload: EntitlementDomainChangeRequest,
    x_trilloka_admin_key: Optional[str] = Header(default=None, alias="X-Trilloka-Admin-Key"),
) -> Dict[str, Any]:
    if not _admin_key_valid(x_trilloka_admin_key):
        raise HTTPException(status_code=403, detail="Admin authorization required")
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
    x_trilloka_admin_key: Optional[str] = Header(default=None, alias="X-Trilloka-Admin-Key"),
) -> Dict[str, Any]:
    if not _admin_key_valid(x_trilloka_admin_key):
        raise HTTPException(status_code=403, detail="Admin authorization required")
    try:
        result = access_manager.reset_daily_usage(email=str(payload.email), domain=payload.domain)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, "daily_usage_reset": True, **result}


@app.post("/api/admin/entitlement/guidance-call")
def admin_record_guidance_call(
    payload: GuidanceCallAdminRequest,
    x_trilloka_admin_key: Optional[str] = Header(default=None, alias="X-Trilloka-Admin-Key"),
) -> Dict[str, Any]:
    if not _admin_key_valid(x_trilloka_admin_key):
        raise HTTPException(status_code=403, detail="Admin authorization required")
    try:
        result = access_manager.record_guidance_call(
            email=str(payload.email), domain=payload.domain, delta=payload.delta
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, "guidance_usage_updated": True, **result}


async def _run_scan_async(domain: str, business_name: str = "") -> Dict[str, Any]:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None, lambda: asyncio.run(scanner.execute_hybrid_scan(domain, business_name))
    )


def _base_success_payload(
    *,
    requested_domain: str,
    scan_data: Dict[str, Any],
    audit_results: Dict[str, Any],
    admin_master_report: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    all_leaks = (audit_results.get("tiered_remediation_packages") or {}).get("tier_10_arch10", [])
    return {
        "success": True,
        "status": "complete",
        "target_domain": requested_domain,
        "overall_score": audit_results.get("overall_score"),
        "surface_metrics": audit_results.get("surface_metrics", {}),
        "key_friction_insight": audit_results.get("key_friction_insight", {}),
        "revenue_leak": audit_results.get("revenue_leak", {}),
        "cms_platform": audit_results.get("cms_platform", "Not confidently identified"),
        "dev_handoff_kit": audit_results.get("dev_handoff_kit", ""),
        "top_5_seo_leaks": all_leaks[:5],
        "top_10_financial_leaks": all_leaks[:10],
        "message": "Scan complete.",
        "business_profile": audit_results.get("business_profile", {}),
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
        "scanner_engine_version": scan_data.get("scanner_engine_version", "v6"),
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
            "remediation_findings_unlocked": limit,
            "guidance_calls": plan["guidance_calls"],
            "guidance_call_minutes": plan["guidance_call_minutes"],
            "email_support_response_hours": plan["email_support_response_hours"],
            "purchased_domain": ticket.domain_key,
        }
        return result

    if ticket.mode in {"admin", "unmetered"}:
        result["report_access"] = {
            "plan_id": "internal_full",
            "full_50_checkpoint_data": True,
            "remediation_findings_unlocked": 10,
        }
        return result

    previews = [_preview_leak(item) for item in all_leaks[:3]]
    result["top_10_financial_leaks"] = previews
    result["top_5_seo_leaks"] = previews
    result.pop("full_50_checkpoint_basis", None)
    result.pop("scoring_ledger", None)
    result.pop("overlap_adjustments", None)
    result.pop("score_formula", None)
    result["report_access"] = {
        "plan_id": "free_preview",
        "plan_name": "Free Preview",
        "full_50_checkpoint_data": False,
        "remediation_findings_unlocked": 0,
        "preview_findings_shown": len(previews),
        "upgrade_required_for_patch_plan": True,
    }
    return result


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
            f"Detailed remediation is unlocked for the Top {plan.get('remediation_limit', ticket.remediation_limit or 0)} findings."
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
    report["top_6_financial_leaks"] = findings[:6]
    report["customer_plan"] = dict(plan)
    report["remediation_limit"] = limit
    report["purchased_domain"] = ticket.domain_key
    return report


async def _run_audit_impl(
    payload: AuditRequest,
    background_tasks: BackgroundTasks,
    http_request: FastAPIRequest,
    response: Response,
    x_trilloka_admin_key: Optional[str],
) -> Dict[str, Any]:
    guardrail_response = handle_trilloka_guardrail(payload.domain)
    if guardrail_response:
        return guardrail_response

    domain_key = access_manager.normalize_domain(payload.domain)
    if not domain_key:
        raise HTTPException(status_code=400, detail="A valid target domain is required")

    device_id, device_created = access_manager.ensure_device_id(http_request.cookies.get("trilloka_scan_device"))
    if device_created:
        _set_device_cookie(response, device_id)
    client_ip = access_manager.client_ip(http_request)
    email = str(payload.email) if payload.email else None
    access_pass = str(payload.access_pass or "").strip() or None
    admin_bypass = _admin_key_valid(x_trilloka_admin_key)

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

    try:
        scan_data = await _run_scan_async(payload.domain, payload.business_name or "")
        if not scan_data.get("is_reachable"):
            raise HTTPException(
                status_code=400,
                detail=f"Domain '{payload.domain}' is offline, unreachable, or blocking both HTTP and browser inspection.",
            )

        try:
            audit_results = scorer.audit_and_score(
                scan_data=scan_data,
                business_type=payload.business_type,
                competitor_data_present=payload.competitor_has_feature,
            )
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
                    background_tasks.add_task(
                        reporter.send_customer_report_email,
                        customer_email=email,
                        customer_report=customer_report,
                    )
            except Exception as exc:
                print(f"[Report Engine] Delivery/archive skipped — {exc}")

        base_payload = _base_success_payload(
            requested_domain=payload.domain,
            scan_data=scan_data,
            audit_results=audit_results,
            admin_master_report=admin_master_report,
        )
        # Cache only the complete generic engine result. Visibility is applied per requester later.
        access_manager.cache_put(domain_key, base_payload)
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


@app.post("/api/audit")
async def run_audit(
    payload: AuditRequest,
    background_tasks: BackgroundTasks,
    http_request: FastAPIRequest,
    response: Response,
    x_trilloka_admin_key: Optional[str] = Header(default=None, alias="X-Trilloka-Admin-Key"),
) -> Dict[str, Any]:
    return await _run_audit_impl(payload, background_tasks, http_request, response, x_trilloka_admin_key)


@app.post("/api/scan")
async def run_scan(
    payload: AuditRequest,
    background_tasks: BackgroundTasks,
    http_request: FastAPIRequest,
    response: Response,
    x_trilloka_admin_key: Optional[str] = Header(default=None, alias="X-Trilloka-Admin-Key"),
) -> Dict[str, Any]:
    return await _run_audit_impl(payload, background_tasks, http_request, response, x_trilloka_admin_key)


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
