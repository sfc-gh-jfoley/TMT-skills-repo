# Phase 03 — Build

Execute all DDL and file generation in order. Self-validate before declaring completion.

---

## Step 1 — Database and Schema Setup

```sql
-- Create ontology database and schema
CREATE DATABASE IF NOT EXISTS {SLUG_UPPER}_ONTOLOGY_DEMO;
CREATE SCHEMA IF NOT EXISTS {SLUG_UPPER}_ONTOLOGY_DEMO.{SLUG_UPPER}_KG;
USE SCHEMA {SLUG_UPPER}_ONTOLOGY_DEMO.{SLUG_UPPER}_KG;
```

---

## Step 2 — Physical Layer

### KG Path (BUILD_PATH = KG)

```sql
CREATE OR REPLACE TABLE KG_NODE (
    node_id       VARCHAR        NOT NULL,
    node_type     VARCHAR        NOT NULL,
    domain        VARCHAR        NOT NULL,
    label         VARCHAR,
    properties    VARIANT,
    source_system VARCHAR,
    created_at    TIMESTAMP_NTZ  DEFAULT CURRENT_TIMESTAMP()
);

CREATE OR REPLACE TABLE KG_EDGE (
    edge_id       VARCHAR        NOT NULL,
    domain        VARCHAR        NOT NULL,
    source_id     VARCHAR        NOT NULL,
    target_id     VARCHAR        NOT NULL,
    relation_type VARCHAR        NOT NULL,
    properties    VARIANT,
    weight        NUMBER(5,4)    DEFAULT 1.0,
    created_at    TIMESTAMP_NTZ  DEFAULT CURRENT_TIMESTAMP()
);
```

Seed data requirements:
- ≥ 60 KG_NODE rows — drawn from the WOW question graph traversals; rows must tell the business narrative
- ≥ 40 KG_EDGE rows — at least one edge per HIGH-confidence relationship in `relations.json`
- All 3 WOW question traversal paths must be fully represented in seed data
- `domain` column must match the domain name from Phase 01

### DIRECT_TABLE Path (BUILD_PATH = DIRECT_TABLE)

```sql
-- Deploy demo_tables.sql verbatim as the physical foundation
-- Source: {demo_tables_sql_path}
-- Do NOT generate KG_NODE or KG_EDGE
```

Verify at least one table from `demo_tables.sql` is queryable before continuing.

---

## Step 3 — Typed Concrete Views

One view per concrete class in `classes.json`:

```sql
CREATE OR REPLACE VIEW V_{CLASS_ID_UPPER} AS
SELECT
    {pk_column}  AS node_id,
    '{class_id}' AS node_type,
    -- key_columns aliased without duplicate names
    {key_columns_with_aliases}
FROM {source_table};
```

Rules:
- No duplicate column names across the view's SELECT list
- Alias any column that would conflict with `node_id` or `node_type`
- One view per concrete class — skip abstract classes here

---

## Step 4 — HIGH-Priority Relationship Views

One view per HIGH-confidence entry in `relations.json`:

```sql
CREATE OR REPLACE VIEW V_{RELATION_ID_UPPER} AS
SELECT
    a.node_id       AS source_id,
    b.node_id       AS target_id,
    '{relation_id}' AS relation_type,
    -- additional context columns as needed, aliased to avoid duplicates
FROM V_{SOURCE_CLASS_UPPER} a
JOIN V_{TARGET_CLASS_UPPER} b ON {join_sql};
```

---

## Step 5 — ONT_* Metadata Tables

```sql
CREATE OR REPLACE TABLE ONT_CLASS (
    class_id        VARCHAR NOT NULL,
    label           VARCHAR NOT NULL,
    is_abstract     BOOLEAN NOT NULL DEFAULT FALSE,
    parent_class_id VARCHAR,
    source_table    VARCHAR,
    description     VARCHAR,
    created_at      TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);

CREATE OR REPLACE TABLE ONT_PROPERTY (
    property_id  VARCHAR NOT NULL,
    class_id     VARCHAR NOT NULL,
    label        VARCHAR NOT NULL,
    data_type    VARCHAR,
    is_key       BOOLEAN DEFAULT FALSE,
    description  VARCHAR
);

CREATE OR REPLACE TABLE ONT_RELATION (
    relation_id    VARCHAR NOT NULL,
    label          VARCHAR NOT NULL,
    source_class   VARCHAR NOT NULL,
    target_class   VARCHAR NOT NULL,
    cardinality    VARCHAR,
    confidence     VARCHAR,
    join_sql       VARCHAR
);

CREATE OR REPLACE TABLE ONT_NAMESPACE (
    namespace_id  VARCHAR NOT NULL,
    prefix        VARCHAR NOT NULL,
    uri           VARCHAR NOT NULL,
    description   VARCHAR
);

CREATE OR REPLACE TABLE ONT_MAPPING (
    mapping_id      VARCHAR NOT NULL,
    source_system   VARCHAR NOT NULL,
    source_table    VARCHAR,
    target_class_id VARCHAR NOT NULL,
    mapping_type    VARCHAR DEFAULT 'DIRECT'
);

CREATE OR REPLACE TABLE ONT_CATALOG (
    object_fqn   VARCHAR NOT NULL,
    object_type  VARCHAR NOT NULL,
    class_id     VARCHAR,
    description  VARCHAR,
    created_at   TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);

CREATE OR REPLACE TABLE ONT_GRAPH_STATS (
    stat_key    VARCHAR NOT NULL,
    stat_value  VARIANT NOT NULL,
    computed_at TIMESTAMP_NTZ NOT NULL DEFAULT CURRENT_TIMESTAMP()
);
```

Seed all tables from `classes.json`, `relations.json`, and `system_mapping.json`.

---

## Step 6 — Abstract Ontology Views

One view per abstract class in `classes.json`:

```sql
CREATE OR REPLACE VIEW VW_ONT_{ABSTRACT_CLASS_UPPER} AS
    SELECT *, '{abstract_class_id}' AS ont_class FROM V_{CONCRETE_SUBCLASS_1}
    UNION ALL
    SELECT *, '{abstract_class_id}' AS ont_class FROM V_{CONCRETE_SUBCLASS_2}
    -- one UNION ALL block per concrete subclass
    ;
```

---

## Step 7 — Stored Procedure

```sql
CREATE OR REPLACE PROCEDURE SP_GENERATE_{SLUG_UPPER}_ONTOLOGY_VIEWS()
RETURNS TABLE(view_name VARCHAR, node_type VARCHAR, row_count NUMBER)
LANGUAGE SQL
AS
BEGIN
    -- Health check: return view name, node_type, and row count for all V_* views
    RETURN TABLE(
        SELECT 'V_' || class_id AS view_name,
               class_id         AS node_type,
               (SELECT COUNT(*) FROM IDENTIFIER('V_' || class_id)) AS row_count
        FROM ONT_CLASS
        WHERE is_abstract = FALSE
    );
END;
```

---

## Step 8 — Populate ONT_GRAPH_STATS

```sql
INSERT INTO ONT_GRAPH_STATS (stat_key, stat_value) VALUES
    ('total_nodes',     (SELECT PARSE_JSON(COUNT(*)) FROM KG_NODE)),
    ('total_edges',     (SELECT PARSE_JSON(COUNT(*)) FROM KG_EDGE)),
    ('class_count',     (SELECT PARSE_JSON(COUNT(*)) FROM ONT_CLASS)),
    ('relation_count',  (SELECT PARSE_JSON(COUNT(*)) FROM ONT_RELATION));
-- Add 3 WOW-question business metrics — one aggregate per WOW question
```

---

## Step 9 — 10 Demo Queries

Write 10 SQL queries directly in `{slug}_ontology.sql`. Requirements:
- Queries 1–3: the 3 WOW questions (must return non-empty results from seed data)
- Queries 4–10: supporting analytics (aggregations, trends, cross-system joins)
- Each query preceded by a comment block: `-- DEMO QUERY {n}: {business question}`

---

## Step 10 — Output Files

Write to `{output_dir}`:

### `{slug}_agent_config.yaml`

```yaml
name: {SLUG_UPPER}_AGENT
database: {SLUG_UPPER}_ONTOLOGY_DEMO
schema: {SLUG_UPPER}_KG
warehouse: COMPUTE_WH
comment: "Ontology agent for {company_name}"
sample_questions:
  - "{wow_question_1}"
  - "{wow_question_2}"
  - "{wow_question_3}"
tools:
  - tool_type: cortex_search
    name: kg_search
    service_name: {css_service_fqn}
    max_results: 5
  - tool_type: cortex_analyst_text_to_sql
    name: ontology_analyst
    semantic_model: "{SLUG_UPPER}_ONTOLOGY_DEMO.{SLUG_UPPER}_KG.{domain}_360_SV"
tool_resources:
  kg_search:
    columns: [search_content, table_fqn, description]
```

No placeholders in `sample_questions` — use the actual WOW question text.

### `{slug}_demo_walkthrough.md`

5-act live demo script (~25–30 min):
- Act 1: Business context — the cross-system problem
- Act 2: Show the raw data (the siloed before state)
- Act 3: The ontology layer (ONT_* views, class hierarchy)
- Act 4: Agent demo — ask the 3 WOW questions live
- Act 5: "What's next" — production graduation, CSS refresh cadence

### `streamlit/streamlit_app.py`

Streamlit-in-Snowflake compatible app. **Critical rules:**
- Use `SNOWFLAKE.CORTEX.COMPLETE()` via SQL session — NOT the Cortex Agent REST API (blocked inside SiS)
- Use `get_active_session()` for the Snowflake session
- Include a sidebar with the 3 WOW question shortcuts
- Display results in `st.dataframe()` with `st.snow()` on first WOW answer

### `streamlit/pyproject.toml` and `streamlit/secrets.toml.example`

Standard Streamlit project config and connection template.

### `eval_dataset.sql`

```sql
CREATE OR REPLACE TABLE {SLUG_UPPER}_AGENT_EVAL (
    input_query  VARCHAR NOT NULL,
    expected_tools VARCHAR NOT NULL
);

INSERT INTO {SLUG_UPPER}_AGENT_EVAL VALUES
    ('{wow_question_1}', 'ontology_analyst'),
    -- 25-40 total rows
    -- Mix of: ontology_analyst only, kg_search only, both tools
    ;
```

---

## STOPPING POINT — Self-Validation Loop

Before declaring Phase 03 complete, run validation checks:

**File completeness:**
- `classes.json` exists and has ≥ 25 entries
- `relations.json` exists and has ≥ 12 entries, ≥ 3 HIGH
- `{slug}_ontology.sql` exists and has ≥ 10 query blocks
- `{slug}_agent_config.yaml` has no placeholder text in `sample_questions`
- `streamlit_app.py` contains `get_active_session()` and `SNOWFLAKE.CORTEX.COMPLETE`
- `eval_dataset.sql` has ≥ 25 INSERT rows

**SQL correctness checks:**
- No duplicate column names in any V_* view SELECT list
- All WOW query traversal paths have corresponding seed data rows in KG_NODE/KG_EDGE
- ONT_* tables are seeded (non-empty INSERT blocks present)

On any failure: fix the specific issue and re-check. Do not emit completion until all checks pass.

---

## Phase 03 Outputs

```
Phase 03 complete:
  DDL file:         {output_dir}/{slug}_ontology.sql ({n} lines)
  Agent config:     {output_dir}/{slug}_agent_config.yaml
  Demo walkthrough: {output_dir}/{slug}_demo_walkthrough.md
  Streamlit app:    {output_dir}/streamlit/streamlit_app.py
  Eval dataset:     {output_dir}/eval_dataset.sql ({n} rows)
  KG_NODE seed:     {n} rows
  KG_EDGE seed:     {n} rows
  Views generated:  {n} V_* + {n} VW_ONT_*

Proceeding to Phase 04 — Validate.
```
