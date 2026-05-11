# Phase 01 — Intake

Confirm all inputs, validate required Snowflake objects exist, resolve the build path, and assemble enrichment context before any design or DDL work begins.

---

## Step 1 — Consume the EMIT MANIFEST

Ask the user to paste the `EMIT MANIFEST — kg-data-discovery` JSON block, or provide:
- Domain name
- Source databases/schemas
- CSS service FQN
- stability_score and table_count

If no manifest is available, prompt:

```
No EMIT MANIFEST found. Please either:
  1) Paste the EMIT MANIFEST block from kg-data-discovery, or
  2) Run kg-data-discovery ONBOARD for your domain first
```

Hard stop if neither is provided.

---

## Step 2 — Validate Manifest Fields

Check these fields are present and valid:

| Field | Validation |
|-------|-----------|
| `domain` | non-empty string |
| `stability_score` | float 0.0–1.0 |
| `table_count` | integer |
| `css_service` | non-empty FQN string |
| `fk_map` | object (may be empty `{}`) |
| `enrichment_path` | one of: `tier_0`, `tier_1`, `tier_2`, `mixed` |

**STOPPING POINT — stability gate:**
- If `stability_score < 0.7` → warn clearly, require explicit user confirmation ("yes, proceed anyway") before continuing
- If `table_count < 3` → hard stop: "Domain has fewer than 3 tables. Run kg-data-discovery ENRICH first."

---

## Step 3 — Validate Snowflake Prerequisites

Run these checks. If any fail, hard stop with the specific failure and remediation step.

```sql
-- 1. CONCEPTS table has enough table-level entries
SELECT COUNT(*) AS cnt
FROM {DOMAIN}_META.META.CONCEPTS
WHERE concept_level = 'table'
AND is_active = TRUE;
-- FAIL if cnt < 3
```

```sql
-- 2. RELATIONSHIPS table exists (empty is OK)
SELECT COUNT(*) AS cnt
FROM {DOMAIN}_META.META.RELATIONSHIPS
WHERE domain = '{domain_name}';
-- FAIL if table does not exist (catch exception)
```

```sql
-- 3. DOMAIN_CONFIG has domain_name set
SELECT config_value
FROM {DOMAIN}_META.META.DOMAIN_CONFIG
WHERE config_key = 'domain_name';
-- FAIL if no row returned
```

```sql
-- 4. CSS service active
SELECT status
FROM {DOMAIN}_META.META.DOMAIN_CONFIG
WHERE config_key = 'css_service_fqn';
-- FAIL if null or if CSS status != ACTIVE
```

```sql
-- 5. DOMAIN_REGISTRY row exists and is in valid status
SELECT status
FROM KG_CONTROL.PUBLIC.DOMAIN_REGISTRY
WHERE domain_name = '{domain_name}';
-- FAIL if status NOT IN ('ENRICHED', 'ACTIVE')
```

If all pass, print a green-check summary of what was validated.

---

## Step 4 — Resolve Build Path

Check whether the user has provided a `demo_tables.sql` path:

- **If `demo_tables.sql` exists at a user-provided path:** set `BUILD_PATH = DIRECT_TABLE`
  - Physical base tables must be deployed before proceeding (verify by querying one table)
  - Skip KG_NODE / KG_EDGE generation in Phase 03
- **If absent:** set `BUILD_PATH = KG`
  - Phase 03 will generate KG_NODE + KG_EDGE seed data

This is a **NON-NEGOTIABLE gate** — do not proceed with a mismatched build path.

---

## Step 5 — Query KG for Enrichment Context

```sql
-- Top 20 table-level concepts by query frequency
SELECT
    c.table_fqn,
    c.description,
    c.keywords,          -- VARIANT column (actual DDL column name)
    c.tables_yaml,
    c.join_keys_yaml,
    c.metrics_yaml,
    c.sample_values,
    c.query_count,
    c.enrichment_quality_score
FROM {DOMAIN}_META.META.CONCEPTS c
WHERE c.concept_level = 'table'
AND c.is_active = TRUE
ORDER BY c.query_count DESC NULLS LAST
LIMIT 20;
```

```sql
-- All relationships for the domain
SELECT
    r.source_table,
    r.source_column,
    r.target_table,
    r.target_column,
    r.relationship_type,
    r.confidence,
    r.detection_method
FROM {DOMAIN}_META.META.RELATIONSHIPS r
WHERE r.domain = '{domain_name}'
AND r.is_active = TRUE
ORDER BY r.confidence DESC;
```

> NOTE: The `keywords` column is VARIANT (array of strings). Use
> `LATERAL FLATTEN(input => keywords)` — NOT `keywords_yaml`
> (that name is incorrect and will fail).

---

## Step 6 — Synthesize Business Questions

From the top concept keywords and FK map, synthesize 5–8 candidate natural-language business questions. These will become WOW questions in Phase 02.

Criteria:
- At least 3 must span 2+ source systems (cross-system = highest value)
- At least 1 must involve aggregation (count, sum, average)
- At least 1 must involve a time dimension if any timestamp column exists

Present the list to the user and ask them to confirm, add, or replace before Phase 02.

---

## Step 7 — Collect Remaining Inputs

Ask for any not yet provided:

| Input | Prompt |
|-------|--------|
| `company_slug` | "What slug should I use for output files? (lowercase, hyphenated, e.g. `att`)" |
| `company_name` | "Display name for the company? (e.g. `AT&T`)" |
| `output_dir` | "Where should I write output files? (e.g. `~/demos/att/`)" |
| `schema_summary.md` path | "Do you have a schema_summary.md with real table/column names? (optional)" |
| `join_graph.md` path | "Do you have a join_graph.md with pre-confirmed join pairs? (optional)" |

---

## Phase 01 Outputs

On successful completion, confirm:

```
Phase 01 complete:
  domain:         {domain_name}
  build_path:     KG | DIRECT_TABLE
  table_count:    {n}
  relationship_count: {n}
  css_service:    {fqn}
  company_slug:   {slug}
  output_dir:     {path}
  business_questions: [list of 5-8]

Proceeding to Phase 02 — Design.
```
