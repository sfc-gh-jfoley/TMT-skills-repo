import json
from typing import Any, Dict, Optional

from snowflake.snowpark import Session


def write_query_log(session: Session, question: str, route: str, quality: Optional[float], cache_hit: bool, status: str, error_message: Optional[str] = None):
    session.sql("""
        INSERT INTO KG_CONTROL.PUBLIC.QUERY_LOG (
            query_id, question, resolution_route, assembly_quality_score, cache_hit, execution_status, error_message, timestamp
        )
        SELECT UUID_STRING(), ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP()
    """, [question, route, quality, cache_hit, status, error_message]).collect()


def main(session: Session, user_question: str, domain_hint: Optional[str], max_routes: int, strict_mode: bool) -> Dict[str, Any]:
    resolution = session.call("KG_CONTROL.PUBLIC.RESOLVE_QUERY_CONTEXT", user_question, domain_hint, max_routes, strict_mode)
    route = resolution.get("route") if isinstance(resolution, dict) else None
    quality = resolution.get("confidence") if isinstance(resolution, dict) else None

    if not isinstance(resolution, dict) or resolution.get("status") != "ok":
        write_query_log(session, user_question, route or "ERROR", quality, False, "error", json.dumps(resolution))
        return {"status": "error", "resolution": resolution}

    if route == "ONTOLOGY_AGENT":
        write_query_log(session, user_question, route, quality, False, "handoff", None)
        return {
            "status": "ok",
            "route": route,
            "handoff": resolution.get("target", {}),
            "message": "Route to ontology-backed agent",
        }

    if route == "TRANSIENT_CONTRACT":
        meta_db = resolution.get("target", {}).get("domain", "") + "_META"
        plan_id = resolution.get("question_plan_id")
        semantic_plan_id = resolution.get("semantic_plan_id")
        build_result = session.call("KG_CONTROL.PUBLIC.BUILD_TRANSIENT_CONTRACT", meta_db, plan_id, semantic_plan_id, resolution.get("target", {}).get("domain"))
        validate_result = session.call("KG_CONTROL.PUBLIC.VALIDATE_TRANSIENT_CONTRACT", meta_db, semantic_plan_id)
        write_query_log(session, user_question, route, quality, False, "validated", None)
        return {
            "status": "ok",
            "route": route,
            "resolution": resolution,
            "build_result": build_result,
            "validate_result": validate_result,
        }

    write_query_log(session, user_question, route or "UNKNOWN", quality, False, "no_route", None)
    return {"status": "ok", "resolution": resolution}
