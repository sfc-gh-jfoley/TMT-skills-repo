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
