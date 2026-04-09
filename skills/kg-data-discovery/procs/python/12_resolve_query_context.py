import hashlib
import json
import re
from typing import Any, Dict, List, Optional

from snowflake.snowpark import Session


def normalize_question(question: str) -> str:
    return re.sub(r"\s+", " ", question.strip().lower())


def hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def extract_question_intent(question: str) -> Dict[str, Any]:
    normalized = normalize_question(question)
    aggregation_words = ["sum", "total", "count", "average", "avg", "how many"]
    compare_words = ["compare", "versus", "vs", "difference"]
    if any(k in normalized for k in compare_words):
        detected_intent = "compare"
    elif any(k in normalized for k in aggregation_words):
        detected_intent = "aggregation"
    else:
        detected_intent = "lookup"

    detected_time_scope = {"raw": None}
    if any(k in normalized for k in ["today", "yesterday", "last week", "last month", "last quarter", "last year"]):
        detected_time_scope = {"raw": normalized}

    return {
        "normalized_question": normalized,
        "detected_intent": detected_intent,
        "detected_entities": [],
        "detected_metrics": [],
        "detected_filters": {},
        "detected_time_scope": detected_time_scope,
        "detected_grain": None,
    }


def fetch_domain_candidates(session: Session, domain_hint: Optional[str], max_routes: int) -> List[str]:
    if domain_hint:
        return [domain_hint.upper()]
    rows = session.sql("""
        SELECT domain_name
        FROM KG_CONTROL.PUBLIC.DOMAIN_REGISTRY
        WHERE status IN ('ENRICHED', 'ACTIVE', 'GRADUATED')
        ORDER BY CASE status WHEN 'GRADUATED' THEN 1 WHEN 'ACTIVE' THEN 2 WHEN 'ENRICHED' THEN 3 ELSE 9 END,
                 updated_at DESC
        LIMIT ?
    """, [max(1, max_routes)]).collect()
    return [r["DOMAIN_NAME"] for r in rows]


def load_domain_registry(session: Session, domain_name: str) -> Optional[Dict[str, Any]]:
    rows = session.sql("""
        SELECT domain_name, meta_database, status, css_name, source_databases, ontology_agent
        FROM KG_CONTROL.PUBLIC.DOMAIN_REGISTRY
        WHERE domain_name = ?
    """, [domain_name]).collect()
    if not rows:
        return None
    r = rows[0]
    return {
        "domain_name": r["DOMAIN_NAME"],
        "meta_database": r["META_DATABASE"],
        "status": r["STATUS"],
        "css_name": r["CSS_NAME"],
        "source_databases": r["SOURCE_DATABASES"],
        "ontology_agent": r["ONTOLOGY_AGENT"],
    }


def load_domain_config(session: Session, meta_db: str) -> Dict[str, Any]:
    rows = session.sql(f"SELECT config_key, config_value FROM {meta_db}.META.DOMAIN_CONFIG").collect()
    out = {}
    for r in rows:
        out[r["CONFIG_KEY"]] = r["CONFIG_VALUE"]
    return out


def count_open_blocking_conflicts(session: Session, meta_db: str) -> int:
    if not session.sql("""
        SELECT COUNT(*) AS cnt
        FROM information_schema.tables
        WHERE table_schema = 'META' AND table_name = 'SEMANTIC_PLAN'
    """).collect():
        return 0
    return 0


def estimate_transient_quality(domain_row: Dict[str, Any], plan: Dict[str, Any]) -> float:
    base = 0.60
    status = domain_row.get("status")
    if status == "ACTIVE":
        base += 0.15
    elif status == "ENRICHED":
        base += 0.05
    if plan.get("detected_intent") == "aggregation":
        base += 0.05
    if plan.get("detected_time_scope", {}).get("raw"):
        base += 0.05
    return min(base, 0.95)


def choose_route(domain_row: Dict[str, Any], domain_config: Dict[str, Any], plan: Dict[str, Any], strict_mode: bool) -> Dict[str, Any]:
    ontology_agent = domain_config.get("ontology_agent") or domain_row.get("ontology_agent")
    css_name = domain_row.get("css_name")
    status = domain_row.get("status")

    if ontology_agent not in (None, "null") and status == "GRADUATED":
        return {
            "route": "ONTOLOGY_AGENT",
            "confidence": 0.95,
            "target": {
                "domain": domain_row["domain_name"],
                "semantic_view": None,
                "ontology_agent": ontology_agent,
            },
            "warnings": [],
            "blocking_conflicts": [],
        }

    if status == "ACTIVE" and css_name:
        return {
            "route": "TRANSIENT_CONTRACT",
            "confidence": estimate_transient_quality(domain_row, plan),
            "target": {
                "domain": domain_row["domain_name"],
                "semantic_view": None,
                "ontology_agent": None,
            },
            "warnings": [],
            "blocking_conflicts": [],
        }

    if status == "ENRICHED":
        return {
            "route": "TRANSIENT_CONTRACT",
            "confidence": estimate_transient_quality(domain_row, plan) - 0.05,
            "target": {
                "domain": domain_row["domain_name"],
                "semantic_view": None,
                "ontology_agent": None,
            },
            "warnings": ["Domain is enriched but CSS is not marked ACTIVE yet"],
            "blocking_conflicts": [],
        }

    route = "BLOCKED" if strict_mode else "AMBIGUOUS"
    return {
        "route": route,
        "confidence": 0.20,
        "target": {
            "domain": domain_row["domain_name"],
            "semantic_view": None,
            "ontology_agent": None,
        },
        "warnings": [f"Domain {domain_row['domain_name']} is not ready for transient execution"],
        "blocking_conflicts": [],
    }


def persist_question_plan(session: Session, meta_db: str, plan: Dict[str, Any], user_question: str, domain_candidates: List[str], confidence: float) -> str:
    plan_id = hash_text(user_question + "::" + "|".join(domain_candidates))
    session.sql(f"""
        INSERT INTO {meta_db}.META.QUESTION_PLAN (
            plan_id, user_question, normalized_question, detected_intent,
            detected_entities, detected_metrics, detected_filters,
            detected_time_scope, detected_grain, domain_candidates, confidence
        )
        SELECT ?, ?, ?, ?, PARSE_JSON(?), PARSE_JSON(?), PARSE_JSON(?), PARSE_JSON(?), ?, PARSE_JSON(?), ?
    """, [
        plan_id,
        user_question,
        plan["normalized_question"],
        plan["detected_intent"],
        json.dumps(plan["detected_entities"]),
        json.dumps(plan["detected_metrics"]),
        json.dumps(plan["detected_filters"]),
        json.dumps(plan["detected_time_scope"]),
        plan["detected_grain"],
        json.dumps(domain_candidates),
        confidence,
    ]).collect()
    return plan_id


def persist_semantic_plan(session: Session, meta_db: str, plan_id: str, route_info: Dict[str, Any]) -> str:
    route = route_info["route"]
    semantic_plan_id = hash_text(plan_id + "::" + route)
    session.sql(f"""
        INSERT INTO {meta_db}.META.SEMANTIC_PLAN (
            semantic_plan_id, plan_id, chosen_route, chosen_semantic_view, chosen_ontology_agent,
            use_transient_contract, route_confidence, ambiguity_reason, blocking_conflicts
        )
        SELECT ?, ?, ?, ?, ?, ?, ?, PARSE_JSON(?), PARSE_JSON(?)
    """, [
        semantic_plan_id,
        plan_id,
        route,
        route_info.get("target", {}).get("semantic_view"),
        route_info.get("target", {}).get("ontology_agent"),
        route == "TRANSIENT_CONTRACT",
        route_info.get("confidence"),
        json.dumps({"warnings": route_info.get("warnings", [])}),
        json.dumps(route_info.get("blocking_conflicts", [])),
    ]).collect()
    return semantic_plan_id


def main(session: Session, user_question: str, domain_hint: Optional[str], max_routes: int, strict_mode: bool) -> Dict[str, Any]:
    if not user_question or not user_question.strip():
        return {"status": "error", "code": "EMPTY_QUESTION", "message": "user_question is required"}

    domain_candidates = fetch_domain_candidates(session, domain_hint, max_routes)
    if not domain_candidates:
        return {"status": "error", "code": "NO_DOMAINS", "message": "No eligible domains found in DOMAIN_REGISTRY"}

    chosen_domain = domain_candidates[0]
    domain_row = load_domain_registry(session, chosen_domain)
    if not domain_row:
        return {"status": "error", "code": "UNKNOWN_DOMAIN", "message": f"Domain {chosen_domain} not found"}

    meta_db = domain_row["meta_database"]
    domain_config = load_domain_config(session, meta_db)
    plan = extract_question_intent(user_question)
    route_info = choose_route(domain_row, domain_config, plan, strict_mode)

    plan_id = persist_question_plan(session, meta_db, plan, user_question, domain_candidates[:max(1, max_routes)], route_info["confidence"])
    semantic_plan_id = persist_semantic_plan(session, meta_db, plan_id, route_info)

    return {
        "status": "ok",
        "question_plan_id": plan_id,
        "semantic_plan_id": semantic_plan_id,
        "route": route_info["route"],
        "target": route_info["target"],
        "resolved_entities": [],
        "canonical_metrics": [],
        "join_graph": [],
        "confidence": route_info["confidence"],
        "warnings": route_info.get("warnings", []),
        "blocking_conflicts": route_info.get("blocking_conflicts", []),
        "execution_contract": {},
    }
