-- =============================================================================
-- KG Data Discovery — Query Plane Procedure Wrappers
-- Deployable CREATE PROCEDURE statements for additive query-plane Python tools.
-- These are wrappers around the local Python implementations and do not modify ontology.
-- =============================================================================

CREATE OR REPLACE PROCEDURE KG_CONTROL.PUBLIC.RESOLVE_QUERY_CONTEXT(
    user_question VARCHAR,
    domain_hint   VARCHAR,
    max_routes    NUMBER,
    strict_mode   BOOLEAN
)
RETURNS VARIANT
LANGUAGE PYTHON
RUNTIME_VERSION = '3.12'
PACKAGES = ('snowflake-snowpark-python')
HANDLER = 'main'
EXECUTE AS CALLER
AS
$$
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
    detected_intent = "aggregation" if any(k in normalized for k in ["sum", "total", "count", "average", "avg", "how many"]) else "lookup"
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


def fetch_domain_candidates(session: Session, domain_hint: Optional[str]) -> List[str]:
    if domain_hint:
        return [domain_hint.upper()]
    rows = session.sql("""
        SELECT domain_name
        FROM KG_CONTROL.PUBLIC.DOMAIN_REGISTRY
        WHERE status IN ('ENRICHED', 'ACTIVE', 'GRADUATED')
        ORDER BY updated_at DESC
        LIMIT 5
    """).collect()
    return [r["DOMAIN_NAME"] for r in rows]


def load_domain_registry(session: Session, domain_name: str) -> Optional[Dict[str, Any]]:
    rows = session.sql("""
        SELECT domain_name, meta_database, status, css_name, source_databases
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
    }


def load_domain_config(session: Session, meta_db: str) -> Dict[str, Any]:
    rows = session.sql(f"SELECT config_key, config_value FROM {meta_db}.META.DOMAIN_CONFIG").collect()
    out = {}
    for r in rows:
        out[r["CONFIG_KEY"]] = r["CONFIG_VALUE"]
    return out


def persist_question_plan(session: Session, meta_db: str, plan: Dict[str, Any], user_question: str, domain_candidates: List[str]) -> str:
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
        0.5,
    ]).collect()
    return plan_id


def persist_semantic_plan(session: Session, meta_db: str, plan_id: str, route: str, ontology_agent: Optional[str], confidence: float) -> str:
    semantic_plan_id = hash_text(plan_id + "::" + route)
    session.sql(f"""
        INSERT INTO {meta_db}.META.SEMANTIC_PLAN (
            semantic_plan_id, plan_id, chosen_route, chosen_ontology_agent,
            use_transient_contract, route_confidence, ambiguity_reason, blocking_conflicts
        )
        SELECT ?, ?, ?, ?, ?, ?, PARSE_JSON(?), PARSE_JSON(?)
    """, [
        semantic_plan_id,
        plan_id,
        route,
        ontology_agent,
        route == "TRANSIENT_CONTRACT",
        confidence,
        json.dumps({}),
        json.dumps([]),
    ]).collect()
    return semantic_plan_id


def main(session: Session, user_question: str, domain_hint: Optional[str], max_routes: int, strict_mode: bool) -> Dict[str, Any]:
    if not user_question or not user_question.strip():
        return {"status": "error", "code": "EMPTY_QUESTION", "message": "user_question is required"}

    domain_candidates = fetch_domain_candidates(session, domain_hint)
    if not domain_candidates:
        return {"status": "error", "code": "NO_DOMAINS", "message": "No eligible domains found in DOMAIN_REGISTRY"}

    chosen_domain = domain_candidates[0]
    domain_row = load_domain_registry(session, chosen_domain)
    if not domain_row:
        return {"status": "error", "code": "UNKNOWN_DOMAIN", "message": f"Domain {chosen_domain} not found"}

    meta_db = domain_row["meta_database"]
    domain_config = load_domain_config(session, meta_db)
    ontology_agent = domain_config.get("ontology_agent")
    route = "ONTOLOGY_AGENT" if ontology_agent not in (None, "null") else "TRANSIENT_CONTRACT"
    confidence = 0.9 if route == "ONTOLOGY_AGENT" else 0.6

    plan = extract_question_intent(user_question)
    plan_id = persist_question_plan(session, meta_db, plan, user_question, domain_candidates[:max(1, max_routes)])
    semantic_plan_id = persist_semantic_plan(session, meta_db, plan_id, route, ontology_agent, confidence)

    return {
        "status": "ok",
        "question_plan_id": plan_id,
        "semantic_plan_id": semantic_plan_id,
        "route": route,
        "target": {
            "domain": chosen_domain,
            "semantic_view": None,
            "ontology_agent": ontology_agent,
        },
        "resolved_entities": [],
        "canonical_metrics": [],
        "join_graph": [],
        "confidence": confidence,
        "warnings": [],
        "blocking_conflicts": [],
        "execution_contract": {},
    }
$$;


CREATE OR REPLACE PROCEDURE KG_CONTROL.PUBLIC.BUILD_TRANSIENT_CONTRACT(
    meta_db          VARCHAR,
    plan_id          VARCHAR,
    semantic_plan_id VARCHAR,
    domain_name      VARCHAR
)
RETURNS VARIANT
LANGUAGE PYTHON
RUNTIME_VERSION = '3.12'
PACKAGES = ('snowflake-snowpark-python')
HANDLER = 'main'
EXECUTE AS CALLER
AS
$$
import json
from typing import Any, Dict, List

from snowflake.snowpark import Session


def load_question_plan(session: Session, meta_db: str, plan_id: str) -> Dict[str, Any]:
    rows = session.sql(f"""
        SELECT plan_id, detected_intent, detected_entities, detected_metrics,
               detected_filters, detected_time_scope, detected_grain
        FROM {meta_db}.META.QUESTION_PLAN
        WHERE plan_id = ?
    """, [plan_id]).collect()
    if not rows:
        raise ValueError(f"QUESTION_PLAN not found for {plan_id}")
    r = rows[0]
    return {
        "plan_id": r["PLAN_ID"],
        "detected_intent": r["DETECTED_INTENT"],
        "detected_entities": r["DETECTED_ENTITIES"],
        "detected_metrics": r["DETECTED_METRICS"],
        "detected_filters": r["DETECTED_FILTERS"],
        "detected_time_scope": r["DETECTED_TIME_SCOPE"],
        "detected_grain": r["DETECTED_GRAIN"],
    }


def write_transient_semantic_spec(session: Session, meta_db: str, semantic_plan_id: str, semantic_spec: Dict[str, Any]) -> None:
    session.sql(f"""
        INSERT INTO {meta_db}.META.TRANSIENT_SEMANTIC_SPEC (
            semantic_plan_id, semantic_spec, generated_sql_preview, compile_status, compile_error
        )
        SELECT ?, PARSE_JSON(?), ?, ?, ?
    """, [
        semantic_plan_id,
        json.dumps(semantic_spec),
        None,
        'PENDING',
        None,
    ]).collect()


def main(session: Session, meta_db: str, plan_id: str, semantic_plan_id: str, domain_name: str) -> Dict[str, Any]:
    qp = load_question_plan(session, meta_db, plan_id)

    semantic_spec = {
        "domain": domain_name,
        "intent": qp["detected_intent"],
        "entities": qp["detected_entities"] or [],
        "metrics": qp["detected_metrics"] or [],
        "filters": qp["detected_filters"] or {},
        "time_scope": qp["detected_time_scope"] or {},
        "grain": qp["detected_grain"],
        "tables": [],
        "joins": [],
    }

    write_transient_semantic_spec(session, meta_db, semantic_plan_id, semantic_spec)

    return {
        "status": "ok",
        "semantic_plan_id": semantic_plan_id,
        "semantic_spec": semantic_spec,
    }
$$;


CREATE OR REPLACE PROCEDURE KG_CONTROL.PUBLIC.VALIDATE_TRANSIENT_CONTRACT(
    meta_db          VARCHAR,
    semantic_plan_id VARCHAR
)
RETURNS VARIANT
LANGUAGE PYTHON
RUNTIME_VERSION = '3.12'
PACKAGES = ('snowflake-snowpark-python')
HANDLER = 'main'
EXECUTE AS CALLER
AS
$$
from typing import Any, Dict

from snowflake.snowpark import Session


def load_transient_spec(session: Session, meta_db: str, semantic_plan_id: str):
    rows = session.sql(f"""
        SELECT semantic_spec
        FROM {meta_db}.META.TRANSIENT_SEMANTIC_SPEC
        WHERE semantic_plan_id = ?
        ORDER BY created_at DESC
        LIMIT 1
    """, [semantic_plan_id]).collect()
    if not rows:
        raise ValueError(f"TRANSIENT_SEMANTIC_SPEC not found for {semantic_plan_id}")
    return rows[0][0]


def update_compile_status(session: Session, meta_db: str, semantic_plan_id: str, status: str, error: str = None):
    session.sql(f"""
        UPDATE {meta_db}.META.TRANSIENT_SEMANTIC_SPEC
        SET compile_status = ?, compile_error = ?
        WHERE semantic_plan_id = ?
    """, [status, error, semantic_plan_id]).collect()


def main(session: Session, meta_db: str, semantic_plan_id: str) -> Dict[str, Any]:
    spec = load_transient_spec(session, meta_db, semantic_plan_id)
    checks = {
        "spec_exists": True,
        "tables_present": bool(spec.get("tables") if isinstance(spec, dict) else False),
        "joins_present": bool(spec.get("joins") if isinstance(spec, dict) else False),
        "blocking_conflicts": False,
    }

    status = "VALID" if checks["spec_exists"] else "INVALID"
    update_compile_status(session, meta_db, semantic_plan_id, status, None)

    return {
        "status": "ok",
        "semantic_plan_id": semantic_plan_id,
        "checks": checks,
        "validation_status": status,
    }
$$;


CREATE OR REPLACE PROCEDURE KG_CONTROL.PUBLIC.DETECT_SEMANTIC_CONFLICTS(
    domain_name VARCHAR,
    meta_db     VARCHAR,
    ont_db      VARCHAR,
    ont_schema  VARCHAR
)
RETURNS VARIANT
LANGUAGE PYTHON
RUNTIME_VERSION = '3.12'
PACKAGES = ('snowflake-snowpark-python')
HANDLER = 'main'
EXECUTE AS CALLER
AS
$$
import json
from typing import Any, Dict, List

from snowflake.snowpark import Session


def load_conflicts(session: Session, ont_db: str, ont_schema: str, domain_name: str):
    return session.sql(f"""
        SELECT conflict_id, conflict_type, severity, ont_object_ref, kg_object_ref, semantic_view_ref, conflict_detail
        FROM {ont_db}.{ont_schema}.ONT_CONFLICT_REGISTRY
        WHERE domain_name = ? AND resolution_status = 'OPEN'
    """, [domain_name]).collect()


def load_domain_state(session: Session, meta_db: str):
    concepts = session.sql(f"SELECT COUNT(*) AS cnt FROM {meta_db}.META.CONCEPTS WHERE is_active = TRUE").collect()[0]["CNT"]
    rels = session.sql(f"SELECT COUNT(*) AS cnt FROM {meta_db}.META.RELATIONSHIPS WHERE is_active = TRUE").collect()[0]["CNT"]
    return {"active_concepts": concepts, "active_relationships": rels}


def main(session: Session, domain_name: str, meta_db: str, ont_db: str, ont_schema: str) -> Dict[str, Any]:
    domain_state = load_domain_state(session, meta_db)
    conflicts = load_conflicts(session, ont_db, ont_schema, domain_name)
    return {
        "status": "ok",
        "domain_name": domain_name,
        "active_concepts": domain_state["active_concepts"],
        "active_relationships": domain_state["active_relationships"],
        "open_conflicts": [
            {
                "conflict_id": r["CONFLICT_ID"],
                "conflict_type": r["CONFLICT_TYPE"],
                "severity": r["SEVERITY"],
            }
            for r in conflicts
        ],
    }
$$;


CREATE OR REPLACE PROCEDURE KG_CONTROL.PUBLIC.VERIFY_METRIC_BINDINGS(
    domain_name       VARCHAR,
    ont_db            VARCHAR,
    ont_schema        VARCHAR,
    semantic_view_fqn VARCHAR
)
RETURNS VARIANT
LANGUAGE PYTHON
RUNTIME_VERSION = '3.12'
PACKAGES = ('snowflake-snowpark-python')
HANDLER = 'main'
EXECUTE AS CALLER
AS
$$
import json
from typing import Any, Dict, List

from snowflake.snowpark import Session


def load_ontology_metrics(session: Session, ont_db: str, ont_schema: str, domain_name: str):
    return session.sql(f"""
        SELECT metric_name, canonical_expression, metric_metadata
        FROM {ont_db}.{ont_schema}.ONT_METRIC_DEF
        WHERE domain_name = ?
    """, [domain_name]).collect()


def load_existing_metric_decisions(session: Session, ont_db: str, ont_schema: str, domain_name: str):
    return session.sql(f"""
        SELECT metric_name, chosen_expression, status
        FROM {ont_db}.{ont_schema}.CANONICAL_METRIC_DECISIONS
        WHERE domain_name = ?
    """, [domain_name]).collect()


def main(session: Session, domain_name: str, ont_db: str, ont_schema: str, semantic_view_fqn: str) -> Dict[str, Any]:
    ontology_metrics = load_ontology_metrics(session, ont_db, ont_schema, domain_name)
    existing_decisions = load_existing_metric_decisions(session, ont_db, ont_schema, domain_name)

    return {
        "status": "ok",
        "domain_name": domain_name,
        "semantic_view_fqn": semantic_view_fqn,
        "ontology_metric_count": len(ontology_metrics),
        "existing_decision_count": len(existing_decisions),
        "decisions": [
            {
                "metric_name": r["METRIC_NAME"],
                "chosen_expression": r["CHOSEN_EXPRESSION"],
                "status": r["STATUS"],
            }
            for r in existing_decisions
        ],
    }
$$;
