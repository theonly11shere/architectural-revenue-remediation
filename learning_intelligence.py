"""Trilloka V7.4 adaptive knowledge memory.

The learning layer is deliberately *outside* the scoring engine.  It can remember
classification corrections, emerging business archetypes, Architect decisions and
remediation outcomes, but it cannot directly create a finding or alter score weights.
Only bounded, validated recognition hints are allowed back into business inference.

Production persistence
----------------------
Set TRILLOKA_LEARNING_DB_PATH to a persistent Render disk path, e.g.
/var/data/trilloka_learning.db.  SQLite is used so the feature is self-contained and
requires no new hosted service.  If the configured path cannot be opened the engine
falls back to /tmp and exposes persistent=False in its status.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import threading
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

_VERSION = "v7.5.2-learning-v2"
_LOCK = threading.RLock()

# Deliberately compact.  We learn discriminating commercial language, not full page text.
_STOPWORDS = {
    "the","and","for","with","from","that","this","your","you","our","are","was","were","have","has","had",
    "will","can","all","more","about","home","page","learn","read","view","click","get","new","best","into","out",
    "not","but","use","using","how","what","why","when","where","who","their","they","them","its","it's","we",
    "a","an","of","to","in","on","at","by","or","as","is","be","it","us","my","i","me","up","now",
    "services","service",  # too broad to learn safely as a type signal
}

_SAFE_TYPES = {
    "ecommerce","marketplace","local_service","professional_service","healthcare","medspa","legal",
    "financial_services","real_estate","restaurant","hospitality_event","saas","b2b","agency",
    "membership_creator","education","nonprofit","automotive",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _domain_hash(domain: str) -> str:
    salt = os.environ.get("TRILLOKA_LEARNING_HASH_SALT", "trilloka-learning-v1")
    raw = (salt + "|" + str(domain or "").strip().lower()).encode("utf-8", "ignore")
    return hashlib.sha256(raw).hexdigest()


def _clean_type(value: Any) -> str:
    value = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    return value if value in _SAFE_TYPES else "general"


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)


def _loads(value: Any, default: Any) -> Any:
    try:
        return json.loads(value) if value not in (None, "") else default
    except Exception:
        return default


def _bool_env(name: str, default: bool) -> bool:
    raw = str(os.environ.get(name, "1" if default else "0")).strip().lower()
    return raw not in {"0", "false", "no", "off"}


def _int_env(name: str, default: int, minimum: int = 1) -> int:
    try:
        return max(minimum, int(os.environ.get(name, str(default))))
    except Exception:
        return default


def _float_env(name: str, default: float, minimum: float = 0.0, maximum: float = 10.0) -> float:
    try:
        return max(minimum, min(maximum, float(os.environ.get(name, str(default)))))
    except Exception:
        return default


def _meaningful_terms(text: str, limit: int = 30) -> List[str]:
    """Extract privacy-safe candidate vocabulary from public title/H1/meta evidence.

    We avoid storing whole sentences and exclude numbers, emails, URLs and obvious PII-like
    strings.  Both single tokens and compact two-token phrases are retained.
    """
    text = re.sub(r"https?://\S+|www\.\S+|\b\S+@\S+\b", " ", str(text or "").lower())
    words = [w for w in re.findall(r"[a-z][a-z0-9+&'-]{2,30}", text) if w not in _STOPWORDS]
    words = [w.strip("-'&") for w in words if not any(ch.isdigit() for ch in w)]
    counts = Counter(w for w in words if len(w) >= 3)
    ranked = [w for w, _ in counts.most_common(limit)]
    bigrams: List[str] = []
    for a, b in zip(words, words[1:]):
        if a in _STOPWORDS or b in _STOPWORDS or a == b:
            continue
        phrase = f"{a} {b}"
        if 7 <= len(phrase) <= 45 and phrase not in bigrams:
            bigrams.append(phrase)
        if len(bigrams) >= 12:
            break
    return list(dict.fromkeys(ranked + bigrams))[:limit]


def build_learning_signature(scan: Mapping[str, Any]) -> Dict[str, Any]:
    """Build a compact semantic fingerprint from already-public scanner evidence."""
    profile = scan.get("architecture_profile") if isinstance(scan.get("architecture_profile"), Mapping) else {}
    deep = scan.get("business_deep_dive") if isinstance(scan.get("business_deep_dive"), Mapping) else {}
    observations = deep.get("concept_observations") if isinstance(deep.get("concept_observations"), Mapping) else {}
    concept_names: List[str] = []
    concepts = observations.get("concepts") if isinstance(observations.get("concepts"), Mapping) else {}
    for name, detail in concepts.items():
        if isinstance(detail, Mapping) and detail.get("observed"):
            concept_names.append(str(name))

    action_types = [str(x) for x in (scan.get("mobile_cta_types") or []) if x]
    schema = [str(x).lower() for x in (scan.get("schema_types") or []) if x]
    contexts = [str(x) for x in (profile.get("context_tags") or []) if x]

    structural: List[str] = []
    for key in (
        "add_to_cart_visible","checkout_context_detected","reservation_present","order_online_present",
        "phone_number_visible","address_location_visible","form_present","analytics_present",
        "mobile_primary_cta_present","pricing_signal_present","reviews_present","credentials_present",
    ):
        if scan.get(key) is True:
            structural.append("has:" + key)

    text = " ".join([
        str(scan.get("title") or ""),
        " ".join(str(x) for x in (scan.get("h1_tags") or [])[:4]),
        str(scan.get("meta_description") or ""),
    ])
    terms = _meaningful_terms(text, 32)
    fingerprint = sorted(set(
        ["schema:" + x for x in schema[:12]]
        + ["action:" + x for x in action_types[:12]]
        + ["context:" + x for x in contexts[:10]]
        + ["concept:" + x for x in concept_names[:20]]
        + structural
        + ["term:" + x for x in terms]
    ))
    return {
        "fingerprint": fingerprint[:80],
        "candidate_terms": terms[:32],
        "journey_model": str(profile.get("journey_model") or "general"),
        "context_tags": contexts[:10],
        "observed_concepts": concept_names[:20],
    }


class LearningMemory:
    def __init__(self) -> None:
        self.enabled = _bool_env("TRILLOKA_LEARNING_ENABLED", True)
        self.auto_activate = _bool_env("TRILLOKA_LEARNING_AUTO_ACTIVATE_CLASSIFICATION", True)
        self.min_support = _int_env("TRILLOKA_LEARNING_AUTO_ACTIVATE_MIN_DOMAINS", 12, 3)
        self.max_conflict_rate = _float_env("TRILLOKA_LEARNING_MAX_CONFLICT_RATE", 0.10, 0.0, 0.49)
        self.max_inference_boost = _float_env("TRILLOKA_LEARNING_MAX_INFERENCE_BOOST", 4.0, 0.0, 6.0)
        requested = os.environ.get("TRILLOKA_LEARNING_DB_PATH", "trilloka_learning.db").strip() or "trilloka_learning.db"
        self.db_path, self.persistent = self._resolve_db_path(requested)
        self._init_db()

    def _resolve_db_path(self, requested: str) -> Tuple[str, bool]:
        path = Path(requested).expanduser()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            test = path.parent / ".trilloka_write_test"
            test.write_text("ok", encoding="utf-8")
            test.unlink(missing_ok=True)
            # /tmp is explicitly treated as ephemeral.
            return str(path), not str(path).startswith("/tmp/")
        except Exception:
            fallback = Path("/tmp/trilloka_learning.db")
            fallback.parent.mkdir(parents=True, exist_ok=True)
            return str(fallback), False

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=8000")
        return conn

    def _init_db(self) -> None:
        # Initialize the shared operational store even when adaptive learning is disabled;
        # Architect review/report delivery must remain available independently.
        with _LOCK, self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS learning_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    domain_hash TEXT,
                    business_type TEXT,
                    subtype TEXT,
                    journey_model TEXT,
                    confidence REAL,
                    source TEXT,
                    status TEXT,
                    payload_json TEXT NOT NULL DEFAULT '{}'
                );
                CREATE INDEX IF NOT EXISTS idx_learning_events_type ON learning_events(event_type, created_at);
                CREATE INDEX IF NOT EXISTS idx_learning_events_domain ON learning_events(domain_hash, created_at);

                CREATE TABLE IF NOT EXISTS learned_terms (
                    business_type TEXT NOT NULL,
                    term TEXT NOT NULL,
                    support_domains_json TEXT NOT NULL DEFAULT '[]',
                    conflict_domains_json TEXT NOT NULL DEFAULT '[]',
                    status TEXT NOT NULL DEFAULT 'candidate',
                    architect_approved INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (business_type, term)
                );
                CREATE INDEX IF NOT EXISTS idx_terms_status ON learned_terms(status, business_type);

                CREATE TABLE IF NOT EXISTS archetypes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    broad_type TEXT NOT NULL,
                    subtype_label TEXT NOT NULL,
                    signature_json TEXT NOT NULL DEFAULT '[]',
                    support_domains_json TEXT NOT NULL DEFAULT '[]',
                    status TEXT NOT NULL DEFAULT 'candidate',
                    architect_approved INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_archetypes_type ON archetypes(broad_type, status);

                CREATE TABLE IF NOT EXISTS architect_reviews (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    vault_id TEXT,
                    domain_hash TEXT,
                    severity TEXT NOT NULL,
                    category TEXT NOT NULL,
                    title TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    evidence_json TEXT NOT NULL DEFAULT '{}',
                    inspect_json TEXT NOT NULL DEFAULT '{}',
                    status TEXT NOT NULL DEFAULT 'open',
                    resolution TEXT,
                    resolution_priority TEXT,
                    resolution_notes TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_architect_status ON architect_reviews(status, severity, created_at);

                CREATE TABLE IF NOT EXISTS remediation_outcomes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    business_type TEXT NOT NULL,
                    journey_model TEXT NOT NULL,
                    rule_key TEXT NOT NULL,
                    outcome_status TEXT NOT NULL,
                    technical_note TEXT,
                    cro_note TEXT,
                    systems_note TEXT,
                    verification_note TEXT,
                    support_count INTEGER NOT NULL DEFAULT 1,
                    architect_approved INTEGER NOT NULL DEFAULT 1
                );
                CREATE INDEX IF NOT EXISTS idx_outcome_lookup ON remediation_outcomes(business_type, journey_model, rule_key, outcome_status);

                CREATE TABLE IF NOT EXISTS pending_reports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    vault_id TEXT NOT NULL UNIQUE,
                    domain_hash TEXT NOT NULL,
                    customer_email TEXT NOT NULL,
                    report_json TEXT NOT NULL,
                    review_ids_json TEXT NOT NULL DEFAULT '[]',
                    status TEXT NOT NULL DEFAULT 'awaiting_architect',
                    delivered_at TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_pending_status ON pending_reports(status, created_at);
                """
            )

    # ---------- bounded classification learning ----------
    def record_classification_confirmation(
        self,
        *,
        domain: str,
        selected_business_type: str,
        scan: Mapping[str, Any],
        previous_candidates: Optional[Mapping[str, Any]] = None,
        source: str = "user_confirmation",
        subtype_label: str = "",
    ) -> Dict[str, Any]:
        if not self.enabled:
            return {"recorded": False, "reason": "learning_disabled"}
        btype = _clean_type(selected_business_type)
        if btype == "general":
            return {"recorded": False, "reason": "unsupported_business_type"}
        sig = build_learning_signature(scan)
        dh = _domain_hash(domain)
        payload = {
            "signature": sig,
            "previous_candidates": dict(previous_candidates or {}),
            "policy": "Classification corrections train bounded recognition memory only; they never change scoring weights automatically.",
        }
        with _LOCK, self._connect() as conn:
            conn.execute(
                "INSERT INTO learning_events(created_at,event_type,domain_hash,business_type,subtype,journey_model,confidence,source,status,payload_json) VALUES(?,?,?,?,?,?,?,?,?,?)",
                (_utc_now(), "classification_confirmation", dh, btype, subtype_label or None, sig.get("journey_model"), 1.0, source, "candidate", _json(payload)),
            )
            self._update_terms(conn, btype, dh, sig.get("candidate_terms") or [])
            archetype = self._update_archetype(conn, btype, dh, sig.get("fingerprint") or [], subtype_label)
            conn.commit()
        return {"recorded": True, "business_type": btype, "archetype": archetype, "term_count": len(sig.get("candidate_terms") or [])}

    def _update_terms(self, conn: sqlite3.Connection, selected_type: str, domain_hash: str, terms: Sequence[str]) -> None:
        now = _utc_now()
        for term in list(dict.fromkeys(str(x).strip().lower() for x in terms if x))[:32]:
            if len(term) < 3 or len(term) > 48:
                continue
            # selected type support
            row = conn.execute("SELECT * FROM learned_terms WHERE business_type=? AND term=?", (selected_type, term)).fetchone()
            supports = set(_loads(row["support_domains_json"], [])) if row else set()
            conflicts = set(_loads(row["conflict_domains_json"], [])) if row else set()
            supports.add(domain_hash)
            status = str(row["status"]) if row else "candidate"
            approved = int(row["architect_approved"]) if row else 0
            if approved:
                status = "active"
            elif self.auto_activate and len(supports) >= self.min_support:
                denom = max(1, len(supports) + len(conflicts))
                if len(conflicts) / denom <= self.max_conflict_rate:
                    status = "active"
                else:
                    status = "validated"
            elif len(supports) >= max(3, self.min_support // 2):
                status = "validated"
            conn.execute(
                "INSERT INTO learned_terms(business_type,term,support_domains_json,conflict_domains_json,status,architect_approved,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?) "
                "ON CONFLICT(business_type,term) DO UPDATE SET support_domains_json=excluded.support_domains_json,status=excluded.status,updated_at=excluded.updated_at",
                (selected_type, term, _json(sorted(supports)), _json(sorted(conflicts)), status, approved, row["created_at"] if row else now, now),
            )
            # The same confirmed term becomes conflict evidence for active candidates in other categories.
            other_rows = conn.execute("SELECT * FROM learned_terms WHERE term=? AND business_type<>?", (term, selected_type)).fetchall()
            for other in other_rows:
                o_conf = set(_loads(other["conflict_domains_json"], [])); o_conf.add(domain_hash)
                o_sup = set(_loads(other["support_domains_json"], []))
                o_status = str(other["status"])
                if not int(other["architect_approved"]):
                    rate = len(o_conf) / max(1, len(o_conf) + len(o_sup))
                    if rate > self.max_conflict_rate:
                        o_status = "validated" if len(o_sup) >= max(3, self.min_support // 2) else "candidate"
                conn.execute(
                    "UPDATE learned_terms SET conflict_domains_json=?, status=?, updated_at=? WHERE business_type=? AND term=?",
                    (_json(sorted(o_conf)), o_status, now, other["business_type"], term),
                )

    @staticmethod
    def _jaccard(a: Iterable[str], b: Iterable[str]) -> float:
        aa, bb = set(a), set(b)
        if not aa or not bb:
            return 0.0
        return len(aa & bb) / max(1, len(aa | bb))

    def _update_archetype(self, conn: sqlite3.Connection, btype: str, domain_hash: str, fingerprint: Sequence[str], subtype_label: str) -> Dict[str, Any]:
        rows = conn.execute("SELECT * FROM archetypes WHERE broad_type=?", (btype,)).fetchall()
        best = None; best_sim = 0.0
        for row in rows:
            sim = self._jaccard(fingerprint, _loads(row["signature_json"], []))
            if sim > best_sim:
                best, best_sim = row, sim
        now = _utc_now()
        if best is not None and best_sim >= 0.38:
            supports = set(_loads(best["support_domains_json"], [])); supports.add(domain_hash)
            merged = Counter(_loads(best["signature_json"], []) + list(fingerprint))
            signature = [term for term, _ in merged.most_common(60)]
            label = subtype_label.strip() or str(best["subtype_label"])
            status = str(best["status"])
            if int(best["architect_approved"]):
                status = "active"
            elif len(supports) >= self.min_support:
                status = "validated"  # subtype promotion remains Architect-controlled.
            conn.execute(
                "UPDATE archetypes SET subtype_label=?, signature_json=?, support_domains_json=?, status=?, updated_at=? WHERE id=?",
                (label, _json(signature), _json(sorted(supports)), status, now, best["id"]),
            )
            return {"id": best["id"], "label": label, "similarity": round(best_sim, 3), "support": len(supports), "status": status}
        digest = hashlib.sha1((btype + "|" + "|".join(sorted(fingerprint)[:30])).encode()).hexdigest()[:6].upper()
        label = subtype_label.strip() or f"Emerging {btype.replace('_',' ').title()} Pattern {digest}"
        cur = conn.execute(
            "INSERT INTO archetypes(broad_type,subtype_label,signature_json,support_domains_json,status,architect_approved,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)",
            (btype, label, _json(list(fingerprint)[:60]), _json([domain_hash]), "candidate", 0, now, now),
        )
        return {"id": cur.lastrowid, "label": label, "similarity": 1.0, "support": 1, "status": "candidate"}

    def inference_overlay(self, scan: Mapping[str, Any]) -> Dict[str, Any]:
        """Return bounded recognition-only hints from ACTIVE learned knowledge."""
        if not self.enabled:
            return {"scores": {}, "matched_terms": {}, "archetype": None, "version": _VERSION}
        sig = build_learning_signature(scan)
        terms = set(sig.get("candidate_terms") or [])
        scores: Dict[str, float] = {}
        matched: Dict[str, List[str]] = {}
        archetype_hint = None
        with _LOCK, self._connect() as conn:
            if terms:
                placeholders = ",".join("?" for _ in terms)
                rows = conn.execute(
                    f"SELECT * FROM learned_terms WHERE status='active' AND term IN ({placeholders})", tuple(sorted(terms))
                ).fetchall()
                for row in rows:
                    btype = str(row["business_type"])
                    support = len(_loads(row["support_domains_json"], []))
                    conflict = len(_loads(row["conflict_domains_json"], []))
                    reliability = support / max(1, support + conflict)
                    # One learned term is never allowed to dominate core evidence.
                    increment = min(0.75, 0.25 + 0.04 * support) * reliability
                    scores[btype] = scores.get(btype, 0.0) + increment
                    matched.setdefault(btype, []).append(str(row["term"]))
            # Active subtype fingerprints are advisory; they do not alter broad scoring.
            rows = conn.execute("SELECT * FROM archetypes WHERE status='active'").fetchall()
            best_sim = 0.0
            for row in rows:
                sim = self._jaccard(sig.get("fingerprint") or [], _loads(row["signature_json"], []))
                if sim > best_sim and sim >= 0.34:
                    best_sim = sim
                    archetype_hint = {
                        "id": int(row["id"]), "broad_type": row["broad_type"], "label": row["subtype_label"],
                        "similarity": round(sim, 3), "support": len(_loads(row["support_domains_json"], [])),
                    }
        # Bound the total learned influence for every category.
        scores = {k: round(min(self.max_inference_boost, v), 3) for k, v in scores.items() if k in _SAFE_TYPES}
        return {
            "scores": scores,
            "matched_terms": {k: v[:8] for k, v in matched.items()},
            "archetype": archetype_hint,
            "version": _VERSION,
            "policy": "Only validated classification memory contributes a bounded recognition hint. It cannot create findings or modify scoring weights.",
        }

    def pathway_routing_overlay(self, business_type: str, subtype: str = "") -> Dict[str, Any]:
        """Learn only crawl priorities from previously strong path resolutions.

        This never returns evidence, confidence, findings or score changes. A learned journey can
        move its URLs/markers earlier in the bounded crawl, but the current site must prove its own path.
        """
        btype = _clean_type(business_type)
        if not self.enabled or btype == "general":
            return {"journey_priorities": [], "support": {}, "version": _VERSION, "policy": "routing_only"}
        counts: Counter[str] = Counter()
        domains: Dict[str, set] = {}
        subtype_counts: Counter[str] = Counter()
        with _LOCK, self._connect() as conn:
            rows = conn.execute(
                "SELECT domain_hash,payload_json FROM learning_events WHERE event_type='completed_scan' AND business_type=? ORDER BY id DESC LIMIT 1200",
                (btype,),
            ).fetchall()
        for row in rows:
            payload = _loads(row["payload_json"], {})
            resolution = payload.get("journey_resolution") if isinstance(payload, Mapping) else {}
            if not isinstance(resolution, Mapping) or int(resolution.get("authority") or 0) < 4:
                continue
            journey = str(resolution.get("journey_model") or "general")
            if journey == "general":
                continue
            dh = str(row["domain_hash"] or "")
            domains.setdefault(journey, set()).add(dh)
            counts[journey] += 1
            if subtype and str(payload.get("business_subtype") or "") == str(subtype):
                subtype_counts[journey] += 1
        # Distinct-domain support prevents one repeatedly rescanned site from dominating routing.
        ranked=[]
        for journey, seen in domains.items():
            support=len(seen)
            if support < 3:
                continue
            ranked.append((-(support*10 + min(9, subtype_counts.get(journey,0))), journey, support))
        ranked.sort()
        return {
            "journey_priorities": [j for _,j,_ in ranked[:6]],
            "support": {j:support for _,j,support in ranked[:6]},
            "version": _VERSION,
            "policy": "Validated historical paths prioritize discovery only; current-site evidence remains authoritative.",
        }

    # ---------- scan / review / outcome memory ----------
    def record_completed_scan(self, *, domain: str, scan: Mapping[str, Any], audit: Mapping[str, Any]) -> None:
        if not self.enabled:
            return
        profile = scan.get("architecture_profile") if isinstance(scan.get("architecture_profile"), Mapping) else {}
        resolution = profile.get("journey_marker_resolution") if isinstance(profile.get("journey_marker_resolution"), Mapping) else {}
        payload = {
            "signature": build_learning_signature(scan),
            "score": audit.get("overall_score", audit.get("overall_health_score")),
            "verified_rules": [str(x.get("rule_key")) for x in (audit.get("scoring_ledger") or []) if isinstance(x, Mapping) and x.get("rule_key")][:40],
            "architect_review_count": len(audit.get("architect_review_queue") or []),
            # Routing memory is deliberately evidence-gated. Future scans may learn what to LOOK FOR,
            # never what conclusion to force. Old completed_scan rows without this block are ignored.
            "journey_resolution": {
                "journey_model": str(resolution.get("journey_model") or profile.get("journey_model") or "general"),
                "authority": int(resolution.get("authority") or 0),
                "status": str(resolution.get("status") or "UNVERIFIED"),
                "path_completeness": str(resolution.get("path_completeness") or "0/3"),
            },
            "business_subtype": str(profile.get("business_subtype") or ""),
        }
        with _LOCK, self._connect() as conn:
            conn.execute(
                "INSERT INTO learning_events(created_at,event_type,domain_hash,business_type,subtype,journey_model,confidence,source,status,payload_json) VALUES(?,?,?,?,?,?,?,?,?,?)",
                (_utc_now(), "completed_scan", _domain_hash(domain), _clean_type(profile.get("business_type")), None,
                 str(profile.get("journey_model") or "general"), float(profile.get("business_type_confidence") or 0.0),
                 "scanner", "observed", _json(payload)),
            )
            conn.commit()

    def add_architect_reviews(self, *, domain: str, vault_id: str, reviews: Sequence[Mapping[str, Any]]) -> List[int]:
        # Human review is an operational quality gate and remains available even when adaptive learning is disabled.
        ids: List[int] = []
        now = _utc_now(); dh = _domain_hash(domain)
        with _LOCK, self._connect() as conn:
            for review in reviews:
                # Avoid duplicate open queue items for the same vault/category/title.
                existing = conn.execute(
                    "SELECT id FROM architect_reviews WHERE vault_id=? AND category=? AND title=? AND status='open'",
                    (vault_id, str(review.get("category") or "judgment"), str(review.get("title") or "Architect review")),
                ).fetchone()
                if existing:
                    ids.append(int(existing["id"])); continue
                cur = conn.execute(
                    "INSERT INTO architect_reviews(created_at,updated_at,vault_id,domain_hash,severity,category,title,reason,evidence_json,inspect_json,status) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                    (now, now, vault_id, dh, str(review.get("severity") or "IMPORTANT"), str(review.get("category") or "judgment"),
                     str(review.get("title") or "Architect review"), str(review.get("reason") or ""), _json(review.get("evidence") or {}),
                     _json(review.get("architect_should_inspect") or {}), "open"),
                )
                ids.append(int(cur.lastrowid))
            conn.commit()
        return ids

    def list_architect_reviews(self, status: str = "open", limit: int = 100) -> List[Dict[str, Any]]:
        # Review workflow is independent of whether recognition learning is enabled.
        status = str(status or "open").lower()
        with _LOCK, self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM architect_reviews WHERE status=? ORDER BY CASE severity WHEN 'CRITICAL' THEN 0 WHEN 'IMPORTANT' THEN 1 ELSE 2 END, created_at DESC LIMIT ?",
                (status, max(1, min(500, int(limit)))),
            ).fetchall()
        return [self._review_row(row) for row in rows]

    @staticmethod
    def _review_row(row: sqlite3.Row) -> Dict[str, Any]:
        return {
            "id": int(row["id"]), "created_at": row["created_at"], "updated_at": row["updated_at"], "vault_id": row["vault_id"],
            "severity": row["severity"], "category": row["category"], "title": row["title"], "reason": row["reason"],
            "evidence": _loads(row["evidence_json"], {}), "architect_should_inspect": _loads(row["inspect_json"], {}),
            "status": row["status"], "resolution": row["resolution"], "resolution_priority": row["resolution_priority"],
            "resolution_notes": row["resolution_notes"],
        }

    def resolve_architect_review(self, review_id: int, resolution: str, priority: str = "", notes: str = "") -> Dict[str, Any]:
        resolution = str(resolution or "").strip().lower()
        allowed = {"confirmed_problem", "not_a_problem", "optimization", "insufficient_evidence", "resolved"}
        if resolution not in allowed:
            raise ValueError(f"resolution must be one of: {', '.join(sorted(allowed))}")
        with _LOCK, self._connect() as conn:
            row = conn.execute("SELECT * FROM architect_reviews WHERE id=?", (int(review_id),)).fetchone()
            if not row:
                raise ValueError("Architect review not found")
            now = _utc_now()
            conn.execute(
                "UPDATE architect_reviews SET status='resolved',resolution=?,resolution_priority=?,resolution_notes=?,updated_at=? WHERE id=?",
                (resolution, str(priority or "").upper(), str(notes or "")[:2000], now, int(review_id)),
            )
            conn.execute(
                "INSERT INTO learning_events(created_at,event_type,domain_hash,business_type,subtype,journey_model,confidence,source,status,payload_json) VALUES(?,?,?,?,?,?,?,?,?,?)",
                (now, "architect_review_resolution", row["domain_hash"], None, None, None, 1.0, "architect", "validated",
                 _json({"review_id": int(review_id), "category": row["category"], "title": row["title"], "resolution": resolution, "priority": priority, "notes": str(notes or "")[:2000]})),
            )
            conn.commit()
            updated = conn.execute("SELECT * FROM architect_reviews WHERE id=?", (int(review_id),)).fetchone()
        return self._review_row(updated)

    def record_missed_finding(self, payload: Mapping[str, Any]) -> Dict[str, Any]:
        btype = _clean_type(payload.get("business_type"))
        with _LOCK, self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO learning_events(created_at,event_type,domain_hash,business_type,subtype,journey_model,confidence,source,status,payload_json) VALUES(?,?,?,?,?,?,?,?,?,?)",
                (_utc_now(), "architect_missed_finding", _domain_hash(str(payload.get("domain") or "")), btype,
                 str(payload.get("subtype") or "")[:120] or None, str(payload.get("journey_model") or "general"), 1.0,
                 "architect", "validated", _json({k: v for k, v in dict(payload).items() if k != "domain"})),
            )
            conn.commit()
        return {"recorded": True, "event_id": int(cur.lastrowid), "status": "validated_training_example"}

    def record_remediation_outcome(self, payload: Mapping[str, Any]) -> Dict[str, Any]:
        btype = _clean_type(payload.get("business_type"))
        journey = str(payload.get("journey_model") or "general")
        rule = str(payload.get("rule_key") or "").strip()
        outcome = str(payload.get("outcome_status") or "").strip().lower()
        if btype == "general" or not rule or outcome not in {"improved","resolved","no_change","worse","not_applicable"}:
            raise ValueError("business_type, rule_key and a valid outcome_status are required")
        now = _utc_now()
        notes = {
            "technical": str(payload.get("technical_note") or "")[:1600],
            "cro": str(payload.get("cro_note") or "")[:1600],
            "systems": str(payload.get("systems_note") or "")[:1600],
            "verification": str(payload.get("verification_note") or "")[:1600],
        }
        with _LOCK, self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO remediation_outcomes(created_at,updated_at,business_type,journey_model,rule_key,outcome_status,technical_note,cro_note,systems_note,verification_note,support_count,architect_approved) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                (now, now, btype, journey, rule, outcome, notes["technical"], notes["cro"], notes["systems"], notes["verification"], 1, 1),
            )
            conn.execute(
                "INSERT INTO learning_events(created_at,event_type,domain_hash,business_type,subtype,journey_model,confidence,source,status,payload_json) VALUES(?,?,?,?,?,?,?,?,?,?)",
                (now, "remediation_outcome", _domain_hash(str(payload.get("domain") or "")), btype, None, journey, 1.0, "architect", "validated", _json({"rule_key": rule, "outcome_status": outcome, **notes})),
            )
            conn.commit()
        return {"recorded": True, "outcome_id": int(cur.lastrowid)}

    def outcome_guidance(self, business_type: str, journey_model: str, rule_key: str) -> Dict[str, Any]:
        """Return only Architect-recorded successful outcomes; never an autonomous rewrite."""
        btype = _clean_type(business_type); journey = str(journey_model or "general"); rule = str(rule_key or "")
        if not self.enabled or btype == "general" or not rule:
            return {}
        with _LOCK, self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM remediation_outcomes WHERE business_type=? AND rule_key=? AND outcome_status IN ('improved','resolved') AND architect_approved=1 ORDER BY created_at DESC LIMIT 20",
                (btype, rule),
            ).fetchall()
        if not rows:
            return {}
        # Prefer same journey, then aggregate only repeated wording by keeping latest vetted example.
        same = [r for r in rows if str(r["journey_model"]) == journey]
        chosen = same[0] if same else rows[0]
        support = len(same) if same else len(rows)
        return {
            "supporting_outcomes": support,
            "technical_note": chosen["technical_note"] or "",
            "cro_note": chosen["cro_note"] or "",
            "systems_note": chosen["systems_note"] or "",
            "verification_note": chosen["verification_note"] or "",
            "policy": "Architect-confirmed historical outcome guidance; website-specific evidence remains authoritative.",
        }

    def queue_pending_report(self, *, vault_id: str, domain: str, customer_email: str, report: Mapping[str, Any], review_ids: Sequence[int]) -> Dict[str, Any]:
        # Customer report hold/release is operational and must not disappear when adaptive learning is disabled.
        if not vault_id or not customer_email:
            return {"queued": False}
        now = _utc_now()
        with _LOCK, self._connect() as conn:
            conn.execute(
                "INSERT INTO pending_reports(created_at,updated_at,vault_id,domain_hash,customer_email,report_json,review_ids_json,status) VALUES(?,?,?,?,?,?,?,?) "
                "ON CONFLICT(vault_id) DO UPDATE SET updated_at=excluded.updated_at,customer_email=excluded.customer_email,report_json=excluded.report_json,review_ids_json=excluded.review_ids_json,status='awaiting_architect'",
                (now, now, str(vault_id), _domain_hash(domain), str(customer_email), _json(dict(report)), _json(list(review_ids)), "awaiting_architect"),
            )
            conn.commit()
        return {"queued": True, "vault_id": str(vault_id), "review_count": len(review_ids)}

    def list_pending_reports(self, status: str = "awaiting_architect", limit: int = 100) -> List[Dict[str, Any]]:
        with _LOCK, self._connect() as conn:
            rows = conn.execute(
                "SELECT id,created_at,updated_at,vault_id,review_ids_json,status,delivered_at FROM pending_reports WHERE status=? ORDER BY created_at DESC LIMIT ?",
                (str(status), max(1, min(500, int(limit)))),
            ).fetchall()
        return [{
            "id": int(r["id"]), "created_at": r["created_at"], "updated_at": r["updated_at"], "vault_id": r["vault_id"],
            "review_ids": _loads(r["review_ids_json"], []), "status": r["status"], "delivered_at": r["delivered_at"],
        } for r in rows]

    def reviews_for_vault(self, vault_id: str) -> List[Dict[str, Any]]:
        with _LOCK, self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM architect_reviews WHERE vault_id=? ORDER BY CASE severity WHEN 'CRITICAL' THEN 0 WHEN 'IMPORTANT' THEN 1 ELSE 2 END, created_at",
                (str(vault_id),),
            ).fetchall()
        return [self._review_row(r) for r in rows]

    def prepare_pending_report_delivery(self, vault_id: str) -> Dict[str, Any]:
        with _LOCK, self._connect() as conn:
            row = conn.execute("SELECT * FROM pending_reports WHERE vault_id=?", (str(vault_id),)).fetchone()
            if not row:
                raise ValueError("Pending report not found")
            open_count = conn.execute("SELECT COUNT(*) c FROM architect_reviews WHERE vault_id=? AND status='open'", (str(vault_id),)).fetchone()["c"]
            if open_count:
                raise ValueError(f"{open_count} Architect review item(s) are still open")
            report = _loads(row["report_json"], {})
            reviews = conn.execute("SELECT * FROM architect_reviews WHERE vault_id=? ORDER BY created_at", (str(vault_id),)).fetchall()
            review_summary = [{
                "severity": r["severity"], "category": r["category"], "title": r["title"], "resolution": r["resolution"],
                "priority": r["resolution_priority"], "architect_note": r["resolution_notes"],
            } for r in reviews]
            report["architect_review"] = {
                "status": "completed", "reviewed_at": _utc_now(), "items": review_summary,
                "note": "Human Architect review is shown separately from the automated result; automated evidence/scoring is retained for reproducibility.",
            }
            return {"vault_id": row["vault_id"], "customer_email": row["customer_email"], "report": report, "reviews": review_summary}

    def mark_pending_report_delivered(self, vault_id: str) -> None:
        now = _utc_now()
        with _LOCK, self._connect() as conn:
            conn.execute("UPDATE pending_reports SET status='delivered',delivered_at=?,updated_at=? WHERE vault_id=?", (now, now, str(vault_id)))
            conn.commit()

    # ---------- owner controls ----------
    def list_candidates(self, limit: int = 100) -> Dict[str, Any]:
        with _LOCK, self._connect() as conn:
            terms = conn.execute(
                "SELECT * FROM learned_terms WHERE status<>'active' ORDER BY updated_at DESC LIMIT ?", (max(1, min(500, int(limit))),)
            ).fetchall()
            archetypes = conn.execute(
                "SELECT * FROM archetypes WHERE status<>'active' ORDER BY updated_at DESC LIMIT ?", (max(1, min(500, int(limit))),)
            ).fetchall()
        return {
            "terms": [{
                "business_type": r["business_type"], "term": r["term"], "status": r["status"],
                "support": len(_loads(r["support_domains_json"], [])), "conflicts": len(_loads(r["conflict_domains_json"], [])),
            } for r in terms],
            "archetypes": [{
                "id": int(r["id"]), "broad_type": r["broad_type"], "subtype_label": r["subtype_label"], "status": r["status"],
                "support": len(_loads(r["support_domains_json"], [])), "architect_approved": bool(r["architect_approved"]),
            } for r in archetypes],
        }

    def promote(self, *, kind: str, identifier: Any, label: str = "") -> Dict[str, Any]:
        kind = str(kind or "").lower()
        now = _utc_now()
        with _LOCK, self._connect() as conn:
            if kind == "archetype":
                row = conn.execute("SELECT * FROM archetypes WHERE id=?", (int(identifier),)).fetchone()
                if not row: raise ValueError("Archetype not found")
                new_label = str(label or row["subtype_label"]).strip()[:160]
                conn.execute("UPDATE archetypes SET status='active',architect_approved=1,subtype_label=?,updated_at=? WHERE id=?", (new_label, now, int(identifier)))
                conn.commit()
                return {"promoted": True, "kind": kind, "id": int(identifier), "label": new_label}
            if kind == "term":
                if not isinstance(identifier, Mapping): raise ValueError("Term promotion requires {business_type, term}")
                btype = _clean_type(identifier.get("business_type")); term = str(identifier.get("term") or "").strip().lower()
                row = conn.execute("SELECT * FROM learned_terms WHERE business_type=? AND term=?", (btype, term)).fetchone()
                if not row: raise ValueError("Learned term not found")
                conn.execute("UPDATE learned_terms SET status='active',architect_approved=1,updated_at=? WHERE business_type=? AND term=?", (now, btype, term))
                conn.commit()
                return {"promoted": True, "kind": kind, "business_type": btype, "term": term}
        raise ValueError("kind must be archetype or term")

    def stats(self) -> Dict[str, Any]:
        with _LOCK, self._connect() as conn:
            event_count = conn.execute("SELECT COUNT(*) c FROM learning_events").fetchone()["c"]
            term_rows = conn.execute("SELECT status,COUNT(*) c FROM learned_terms GROUP BY status").fetchall()
            archetype_rows = conn.execute("SELECT status,COUNT(*) c FROM archetypes GROUP BY status").fetchall()
            open_reviews = conn.execute("SELECT COUNT(*) c FROM architect_reviews WHERE status='open'").fetchone()["c"]
            outcomes = conn.execute("SELECT COUNT(*) c FROM remediation_outcomes").fetchone()["c"]
            pending_reports = conn.execute("SELECT COUNT(*) c FROM pending_reports WHERE status='awaiting_architect'").fetchone()["c"]
        return {
            "enabled": bool(self.enabled),
            "version": _VERSION,
            "database_path": self.db_path,
            "persistent": self.persistent,
            "events": int(event_count),
            "learned_terms": {str(r["status"]): int(r["c"]) for r in term_rows},
            "archetypes": {str(r["status"]): int(r["c"]) for r in archetype_rows},
            "open_architect_reviews": int(open_reviews),
            "remediation_outcomes": int(outcomes),
            "pending_architect_reports": int(pending_reports),
            "auto_activation_min_domains": self.min_support,
            "max_inference_boost": self.max_inference_boost,
            "policy": "Knowledge may grow continuously; scoring logic and verified-evidence rules do not self-modify.",
        }


learning_memory = LearningMemory()
