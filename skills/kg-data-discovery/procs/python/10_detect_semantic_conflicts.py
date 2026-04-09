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
