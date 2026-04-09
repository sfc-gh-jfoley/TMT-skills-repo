from typing import Any, Dict

from snowflake.snowpark import Session


def load_transient_spec(session: Session, meta_db: str, semantic_plan_id: str):
    rows = session.sql(f"""
        SELECT semantic_spec, generated_sql_preview
        FROM {meta_db}.META.TRANSIENT_SEMANTIC_SPEC
        WHERE semantic_plan_id = ?
        ORDER BY created_at DESC
        LIMIT 1
    """, [semantic_plan_id]).collect()
    if not rows:
        raise ValueError(f"TRANSIENT_SEMANTIC_SPEC not found for {semantic_plan_id}")
    return rows[0][0], rows[0][1]


def update_compile_status(session: Session, meta_db: str, semantic_plan_id: str, status: str, error: str = None):
    session.sql(f"""
        UPDATE {meta_db}.META.TRANSIENT_SEMANTIC_SPEC
        SET compile_status = ?, compile_error = ?
        WHERE semantic_plan_id = ?
    """, [status, error, semantic_plan_id]).collect()


def compile_preview_sql(session: Session, sql_text: str) -> Dict[str, Any]:
    if not sql_text:
        return {"ok": False, "error": "No generated_sql_preview provided"}
    try:
        preview_sql = f"EXPLAIN USING TEXT {sql_text}"
        session.sql(preview_sql).collect()
        return {"ok": True, "error": None}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def main(session: Session, meta_db: str, semantic_plan_id: str) -> Dict[str, Any]:
    spec, sql_preview = load_transient_spec(session, meta_db, semantic_plan_id)

    tables = spec.get("tables") if isinstance(spec, dict) else []
    joins = spec.get("joins") if isinstance(spec, dict) else []
    compile_result = compile_preview_sql(session, sql_preview)

    checks = {
        "spec_exists": True,
        "tables_present": bool(tables),
        "joins_present": bool(joins),
        "blocking_conflicts": False,
        "compile_ok": compile_result["ok"],
    }

    status = "VALID" if checks["spec_exists"] and checks["compile_ok"] else "INVALID"
    update_compile_status(session, meta_db, semantic_plan_id, status, compile_result["error"])

    return {
        "status": "ok",
        "semantic_plan_id": semantic_plan_id,
        "checks": checks,
        "validation_status": status,
        "compile_error": compile_result["error"],
    }
