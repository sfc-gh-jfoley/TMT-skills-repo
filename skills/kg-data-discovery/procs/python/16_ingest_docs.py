import json

# DDL for DOC_CONTEXT — created lazily on first ingest
_DOC_CONTEXT_DDL = """
CREATE TABLE IF NOT EXISTS {meta_db}.META.DOC_CONTEXT (
    doc_id              VARCHAR         NOT NULL DEFAULT UUID_STRING(),
    domain              VARCHAR         NOT NULL,
    doc_type            VARCHAR         NOT NULL,
    -- Accepted types: schema_doc | data_dict | readme | er_diagram |
    --                 dbt_schema | manual | other
    doc_text            VARCHAR         NOT NULL,
    extracted_tables    VARIANT,        -- [{table_name, description, columns: [{name, description}]}]
    coverage_tables     VARIANT,        -- array of table names mentioned
    extraction_model    VARCHAR,
    extracted_at        TIMESTAMP_NTZ,
    is_active           BOOLEAN         NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMP_NTZ   NOT NULL DEFAULT CURRENT_TIMESTAMP(),
    PRIMARY KEY (doc_id)
)
"""

_EXTRACTION_PROMPT = """\
You are a data dictionary parser. Given the documentation text below, extract every table
mentioned and its column descriptions.

Return a JSON array with this exact structure (no markdown, no explanation):
[
  {{
    "table_name": "ORDERS",
    "description": "One-to-two sentence business description of the table.",
    "columns": [
      {{"name": "ORDER_ID",  "description": "Unique order identifier"}},
      {{"name": "STATUS",    "description": "Fulfillment status: PENDING, SHIPPED, DELIVERED"}}
    ]
  }}
]

Documentation text:
{doc_text}
"""


def _get_llm_model(session, meta_db: str) -> str:
    """Read llm_model from DOMAIN_CONFIG; fall back to claude-sonnet-4."""
    try:
        rows = session.sql(f"""
            SELECT config_value::VARCHAR AS v
            FROM {meta_db}.META.DOMAIN_CONFIG
            WHERE config_key = 'llm_model'
        """).collect()
        if rows and rows[0]['V']:
            return rows[0]['V'].strip('"')
    except Exception:
        pass
    return 'claude-sonnet-4'


def _ensure_doc_context(session, meta_db: str):
    """Create DOC_CONTEXT if it doesn't exist."""
    try:
        session.sql(_DOC_CONTEXT_DDL.format(meta_db=meta_db)).collect()
    except Exception:
        pass


def _extract_via_complete(session, doc_text: str, llm_model: str) -> list:
    """Call CORTEX.COMPLETE to extract table/column descriptions."""
    max_chars = 12000
    if len(doc_text) > max_chars:
        doc_text = doc_text[:max_chars] + '\n[... truncated ...]'

    prompt = _EXTRACTION_PROMPT.format(doc_text=doc_text)

    try:
        rows = session.sql("""
            SELECT SNOWFLAKE.CORTEX.COMPLETE(
                ?,
                ARRAY_CONSTRUCT(OBJECT_CONSTRUCT('role', 'user', 'content', ?))
            ):choices[0]:message:content::VARCHAR AS result
        """, [llm_model, prompt]).collect()

        if not rows or not rows[0]['RESULT']:
            return []

        raw = rows[0]['RESULT'].strip()
        # Strip markdown code fences if model wrapped them
        if raw.startswith('```'):
            lines = raw.split('\n')
            raw = '\n'.join(lines[1:])
        if raw.endswith('```'):
            raw = raw[:-3].strip()

        parsed = json.loads(raw)
        return parsed if isinstance(parsed, list) else []
    except Exception:
        return []


def _upsert_doc_row(session, meta_db: str, domain_name: str,
                    doc_type: str, doc_text: str,
                    extracted: list, llm_model: str):
    """Insert a DOC_CONTEXT row for this ingestion."""
    coverage = [e['table_name'] for e in extracted if e.get('table_name')]
    session.sql(f"""
        INSERT INTO {meta_db}.META.DOC_CONTEXT
            (domain, doc_type, doc_text,
             extracted_tables, coverage_tables,
             extraction_model, extracted_at, is_active)
        VALUES (?, ?, ?,
                PARSE_JSON(?), PARSE_JSON(?),
                ?, CURRENT_TIMESTAMP(), TRUE)
    """, [
        domain_name.upper(), doc_type, doc_text[:32000],
        json.dumps(extracted), json.dumps(coverage),
        llm_model
    ]).collect()


def _apply_to_concepts(session, meta_db: str, extracted: list) -> int:
    """
    Update CONCEPTS with doc-derived descriptions where they beat current quality.
    Quality threshold: 0.82 (doc-derived beats heuristic/AI_CLASSIFY but yields to AI_EXTRACT+).
    """
    updated = 0
    for entry in extracted:
        tbl_name = (entry.get('table_name') or '').strip().upper()
        description = (entry.get('description') or '').strip()
        columns = entry.get('columns') or []

        if not tbl_name or not description:
            continue

        rows = session.sql(f"""
            SELECT concept_id, enrichment_quality_score
            FROM {meta_db}.META.CONCEPTS
            WHERE UPPER(source_table) = ?
              AND concept_level = 'table'
              AND is_active = TRUE
        """, [tbl_name]).collect()

        for row in rows:
            if (row['ENRICHMENT_QUALITY_SCORE'] or 0) < 0.82:
                col_hints = ' '.join([
                    f"{c['name']}: {c['description']}"
                    for c in columns
                    if c.get('name') and c.get('description')
                ])
                search_suffix = f' {col_hints}' if col_hints else ''
                session.sql(f"""
                    UPDATE {meta_db}.META.CONCEPTS
                    SET description                = ?,
                        search_content             = search_content || ?,
                        enrichment_source          = 'DOC_CONTEXT',
                        enrichment_tier            = 0,
                        enrichment_quality_score   = 0.82,
                        enrichment_timestamp       = CURRENT_TIMESTAMP(),
                        updated_at                 = CURRENT_TIMESTAMP()
                    WHERE concept_id = ?
                """, [description, search_suffix, row['CONCEPT_ID']]).collect()
                updated += 1

    return updated


def main(session, domain_name: str, doc_text: str, doc_type: str) -> str:
    """
    Ingest a documentation artifact and apply extracted descriptions to CONCEPTS.

    Args:
        domain_name:  Domain to enrich (e.g. 'SALESFORCE').
        doc_text:     Raw text of the documentation (schema doc, README, data dict, etc.).
        doc_type:     One of: schema_doc | data_dict | readme | er_diagram |
                              dbt_schema | manual | other
    """
    meta_db = domain_name.upper() + '_META'
    llm_model = _get_llm_model(session, meta_db)

    _ensure_doc_context(session, meta_db)

    extracted = _extract_via_complete(session, doc_text, llm_model)

    if not extracted:
        # Store even if extraction failed — the raw text may be useful later
        _upsert_doc_row(session, meta_db, domain_name, doc_type, doc_text, [], llm_model)
        return (
            f"INGEST_DOCS: {domain_name.upper()} — doc ingested ({doc_type}) "
            f"but no tables extracted. Raw text stored in DOC_CONTEXT."
        )

    _upsert_doc_row(session, meta_db, domain_name, doc_type, doc_text, extracted, llm_model)
    updated_count = _apply_to_concepts(session, meta_db, extracted)

    return (
        f"INGEST_DOCS: {domain_name.upper()} — "
        f"{len(extracted)} tables extracted from {doc_type}, "
        f"{updated_count} CONCEPTS updated (quality >= 0.82 threshold). "
        f"Model: {llm_model}."
    )
