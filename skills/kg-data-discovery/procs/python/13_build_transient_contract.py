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
        "detected_entities": r["DETECTED_ENTITIES"] or [],
        "detected_metrics": r["DETECTED_METRICS"] or [],
        "detected_filters": r["DETECTED_FILTERS"] or {},
        "detected_time_scope": r["DETECTED_TIME_SCOPE"] or {},
        "detected_grain": r["DETECTED_GRAIN"],
    }


def load_candidate_concepts(session: Session, meta_db: str, limit_rows: int = 5) -> List[Dict[str, Any]]:
    rows = session.sql(f"""
        SELECT concept_id, table_fqn, tables_yaml, metrics_yaml, enrichment_quality_score
        FROM {meta_db}.META.CONCEPTS
        WHERE is_active = TRUE
        ORDER BY query_count DESC, enrichment_quality_score DESC NULLS LAST
        LIMIT ?
    """, [limit_rows]).collect()
    return [
        {
            "concept_id": r["CONCEPT_ID"],
            "table_fqn": r["TABLE_FQN"],
            "tables_yaml": r["TABLES_YAML"],
            "metrics_yaml": r["METRICS_YAML"],
            "quality": r["ENRICHMENT_QUALITY_SCORE"],
        }
        for r in rows
    ]


def load_candidate_relationships(session: Session, meta_db: str, limit_rows: int = 10) -> List[Dict[str, Any]]:
    rows = session.sql(f"""
        SELECT source_table, target_table, source_column, target_column, relationship_type, confidence, detection_method
        FROM {meta_db}.META.RELATIONSHIPS
        WHERE is_active = TRUE
        ORDER BY confidence DESC, created_at DESC
        LIMIT ?
    """, [limit_rows]).collect()
    return [
        {
            "source_table": r["SOURCE_TABLE"],
            "target_table": r["TARGET_TABLE"],
            "source_column": r["SOURCE_COLUMN"],
            "target_column": r["TARGET_COLUMN"],
            "relationship_type": r["RELATIONSHIP_TYPE"],
            "confidence": r["CONFIDENCE"],
            "detection_method": r["DETECTION_METHOD"],
        }
        for r in rows
    ]


def parse_metric_candidates(concepts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for c in concepts:
        if c.get("metrics_yaml"):
            out.append({
                "metric_name": c["table_fqn"].split('.')[-1] + "_metric",
                "canonical_metric_name": None,
                "sql_expression": None,
                "grain": None,
                "source": c["table_fqn"],
                "confidence": c.get("quality") or 0.5,
                "chosen": False,
            })
    return out


def insert_join_graph(session: Session, meta_db: str, semantic_plan_id: str, joins: List[Dict[str, Any]]) -> None:
    for idx, j in enumerate(joins, start=1):
        session.sql(f"""
            INSERT INTO {meta_db}.META.TRANSIENT_JOIN_GRAPH (
                semantic_plan_id, edge_order, source_object, target_object,
                source_key, target_key, relationship_type, confidence, provenance
            )
            SELECT ?, ?, ?, ?, ?, ?, ?, ?, ?
        """, [
            semantic_plan_id,
            idx,
            j["source_table"],
            j["target_table"],
            j["source_column"],
            j["target_column"],
            j["relationship_type"],
            j["confidence"],
            j["detection_method"],
        ]).collect()


def insert_metric_bindings(session: Session, meta_db: str, semantic_plan_id: str, metrics: List[Dict[str, Any]]) -> None:
    for idx, m in enumerate(metrics):
        session.sql(f"""
            INSERT INTO {meta_db}.META.TRANSIENT_METRIC_BINDINGS (
                semantic_plan_id, metric_name, canonical_metric_name,
                sql_expression, grain, source, confidence, chosen
            )
            SELECT ?, ?, ?, ?, ?, ?, ?, ?
        """, [
            semantic_plan_id,
            m["metric_name"],
            m["canonical_metric_name"],
            m["sql_expression"],
            m["grain"],
            m["source"],
            m["confidence"],
            idx == 0,
        ]).collect()


def write_transient_semantic_spec(session: Session, meta_db: str, semantic_plan_id: str, semantic_spec: Dict[str, Any]) -> None:
    session.sql(f"""
        INSERT INTO {meta_db}.META.TRANSIENT_SEMANTIC_SPEC (
            semantic_plan_id, semantic_spec, generated_sql_preview, compile_status, compile_error
        )
        SELECT ?, PARSE_JSON(?), ?, ?, ?
    """, [
        semantic_plan_id,
        json.dumps(semantic_spec),
        semantic_spec.get("generated_sql_preview"),
        'PENDING',
        None,
    ]).collect()


def main(session: Session, meta_db: str, plan_id: str, semantic_plan_id: str, domain_name: str) -> Dict[str, Any]:
    qp = load_question_plan(session, meta_db, plan_id)
    concepts = load_candidate_concepts(session, meta_db)
    joins = load_candidate_relationships(session, meta_db)
    metrics = parse_metric_candidates(concepts)

    insert_join_graph(session, meta_db, semantic_plan_id, joins)
    insert_metric_bindings(session, meta_db, semantic_plan_id, metrics)

    tables = [c["table_fqn"] for c in concepts]
    generated_sql_preview = None
    if tables:
        generated_sql_preview = f"SELECT * FROM {tables[0]} LIMIT 100"

    semantic_spec = {
        "domain": domain_name,
        "intent": qp["detected_intent"],
        "entities": qp["detected_entities"],
        "metrics": qp["detected_metrics"],
        "filters": qp["detected_filters"],
        "time_scope": qp["detected_time_scope"],
        "grain": qp["detected_grain"],
        "tables": tables,
        "joins": joins,
        "metric_candidates": metrics,
        "generated_sql_preview": generated_sql_preview,
    }

    write_transient_semantic_spec(session, meta_db, semantic_plan_id, semantic_spec)

    return {
        "status": "ok",
        "semantic_plan_id": semantic_plan_id,
        "tables": tables,
        "join_count": len(joins),
        "metric_count": len(metrics),
        "generated_sql_preview": generated_sql_preview,
    }
