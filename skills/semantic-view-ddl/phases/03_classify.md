---
name: sv-ddl-phase3-classify
description: Classify each column as FACT, DIMENSION, TIME_DIMENSION, METRIC, or SKIP based on data type and business context
---

# Phase 3: Column Classification

## Purpose
Decide which columns become FACTS, DIMENSIONS, METRICS, or are skipped.
This is the most important design decision — wrong classification causes bad SQL generation from Cortex Analyst.

---

## Step 3.0: Governance pre-pass (runs before heuristics)

### 3.0-A: Lock tenant columns (IS_MTT = true only)

If `IS_MTT = true`, immediately mark every column in `TENANT_COLUMNS` as **DIMENSION — LOCKED**.
These columns are never overridable to SKIP, FACT, or PRIVATE — they must be visible dimensions so
Cortex Analyst can filter by tenant. Skip them in all heuristic checks below.

```
Locked tenant dimensions: <TENANT_COLUMNS>
Reason: MTT schema — tenant boundary columns must be DIMENSION in every SV.
```

### 3.0-B: PII scan

Branch on `PII_SCAN_MODE`:

**Mode: `"patterns"` (default)**
Flag any column whose name matches:
`EMAIL`, `E_MAIL`, `SSN`, `TAX_ID`, `PHONE`, `MOBILE`, `FAX`, `DOB`, `BIRTH_DATE`, `BIRTHDAY`,
`ADDRESS`, `STREET`, `ZIPCODE`, `ZIP_CODE`, `POSTAL`, `FIRST_NAME`, `LAST_NAME`, `FULL_NAME`,
`GENDER`, `IP_ADDRESS`, `CREDIT_CARD`, `PASSPORT`, `LICENSE`, `NPI`, `MRN`, `PATIENT_ID`

Store matched columns as `PII_FLAGGED`.

**Mode: `"classify"` (SYSTEM$CLASSIFY)**
Run Snowflake's built-in classifier on each source table. Requires `APPLY DATA PRIVACY CLASSIFICATION` privilege.

```sql
-- Run per source table:
SELECT SYSTEM$CLASSIFY('<DB>.<SCHEMA>.<TABLE>', {'auto_tag': false});
```

Parse the JSON result: collect all columns where `privacy_category` is `'IDENTIFIER'` or `'QUASI_IDENTIFIER'`
or `semantic_category` is non-null. Merge with name-pattern results.
Store as `PII_FLAGGED` (deduplicated).

⚠️ If SYSTEM$CLASSIFY returns an access error, fall back to name patterns and note the fallback as a warning.

**Mode: `"skip"`**
Set `PII_FLAGGED = []`. Skip all PII checks. A governance follow-up note will appear at the end of Phase 3.

---

## Step 3.1: Auto-classify using heuristics

Apply these rules to every column in `TABLE_PROFILES`. Start with the heuristic classification, then refine with business context.

### Classification rules (apply in order)

| Priority | Condition | Classification |
|----------|-----------|---------------|
| 0 | Column is in `PII_FLAGGED` (from Step 3.0-B) | **⚠️ PII — flag for governance check** (default: SKIP; keep as DIMENSION only with user approval; NEVER reclassify as FACT to use PRIVATE modifier) |
| 1 | `DATE`, `TIMESTAMP`, `DATETIME`, `TIMESTAMP_NTZ`, `TIMESTAMP_LTZ` | **TIME_DIMENSION** |
| 2 | Column name ends with `_ID`, `_KEY`, `_CODE`, `_NBR`, `_NUM`, `_SK` | **DIMENSION** (even if numeric — it's an identifier, not a measure) |
| 3 | Column name starts with or contains `IS_`, `HAS_`, `FLAG` | **DIMENSION** (boolean/flag) |
| 4 | `BOOLEAN` type | **DIMENSION** |
| 5 | `VARCHAR`, `TEXT`, `CHAR` | **DIMENSION** |
| 6 | `NUMBER`, `INTEGER`, `FLOAT`, `DECIMAL` with distinct_count / total_rows > 0.5 (high cardinality ratio → likely a measure) | **FACT** |
| 7 | `NUMBER`, `INTEGER`, `FLOAT` with low cardinality (< 20 distinct values) | **DIMENSION** (categorical numeric — e.g. STATUS_CODE, RATING) |
| 8 | Column name contains `AMOUNT`, `PRICE`, `REVENUE`, `COST`, `TOTAL`, `SUM`, `COUNT`, `QTY`, `QUANTITY` | **FACT** |
| 9 | Internal/ETL columns: `_CREATED_AT`, `_UPDATED_AT`, `_ETL`, `_LOAD_`, `_BATCH_`, `_DW_` | **SKIP** (exclude from SV) |
| 10 | All other numeric columns | **FACT** (default) |

### Aggregate/computed metrics

Metrics are NOT raw columns — they are aggregate expressions you define:
- `COUNT(*)` → total row count
- `SUM(revenue_col)` → total revenue
- `AVG(price_col)` → average price
- `COUNT(DISTINCT id_col)` → unique count

Propose sensible metrics based on `BUSINESS_CONTEXT` and the available FACT columns.

---

## Step 3.2: Present classification table for review

Format the output as a table grouped by table name. Show auto-classification + user can override:

```
Column Classification for <TABLE_NAME>
(Edit classifications before proceeding)

Column                  | Type      | Classification    | Reason
------------------------|-----------|-------------------|--------------------------------
DEALER_ID               | VARCHAR   | DIMENSION         | ID-like name
DEALER_NAME             | VARCHAR   | DIMENSION         | text
DAYS_IN_INVENTORY       | NUMBER    | FACT              | numeric measure
LISTING_STATUS          | VARCHAR   | DIMENSION         | categorical text
LIST_PRICE              | NUMBER    | FACT              | contains PRICE
ACQUISITION_DATE        | DATE      | TIME_DIMENSION    | date type
LAST_MODIFIED_AT        | TIMESTAMP | SKIP              | ETL/audit column
LOAD_BATCH_ID           | VARCHAR   | SKIP              | ETL column pattern

Proposed METRICS (aggregate expressions):
  • total_vehicles     AS COUNT(*)                          — total vehicle count
  • avg_days_on_lot    AS AVG(DAYS_IN_INVENTORY)            — average days on lot
  • avg_list_price     AS AVG(LIST_PRICE)                   — average listing price
  • total_list_value   AS SUM(LIST_PRICE)                   — total inventory value

Override any classification? (type column name and new type, or 'ok' to proceed)
```

⚠️ **STOPPING POINT** — Wait for user to confirm or override classifications.

---

## Step 3.3: Apply user overrides

Accept overrides in any format:
- `DAYS_IN_INVENTORY → DIMENSION` (user knows it's capped at 0-365, categorical)
- `LISTING_STATUS → SKIP` (not relevant for this SV)
- Add a new metric: `active_count AS COUNT_IF(LISTING_STATUS = 'ACTIVE')`

Store the final classification as `COLUMN_CLASSES`:
```json
{
  "VEHICLES_TABLE": {
    "DEALER_ID":          { "class": "DIMENSION", "description": "...", "synonyms": [...] },
    "DAYS_IN_INVENTORY":  { "class": "FACT",      "description": "...", "synonyms": [...] },
    "ACQUISITION_DATE":   { "class": "TIME_DIMENSION", ... },
    "LAST_MODIFIED_AT":   { "class": "SKIP" }
  },
  "metrics": [
    { "table": "VEHICLES_TABLE", "name": "total_vehicles",  "expr": "COUNT(*)" },
    { "table": "VEHICLES_TABLE", "name": "avg_days_on_lot", "expr": "AVG(DAYS_IN_INVENTORY)" }
  ]
}
```

---

## Step 3.3.5: Cortex Search eligibility (fix 3)

After user overrides are accepted, scan `COLUMN_CLASSES` for dimensions with type `VARCHAR` / `TEXT` that
have high cardinality (distinct_count > 1000 or distinct_count / total_rows > 0.3). These are candidates
for Cortex Search Service — full-text fuzzy search on that dimension column.

If any candidates exist, ask:

```
Free-text search candidates detected:
  • <table_alias>.<col_name>  (<N> distinct values — e.g. "incident notes", "product description")
  [...]

Do any of these columns contain free-form text that users might search with natural language?
(e.g. support notes, descriptions, comments — NOT structured categories or IDs)

For each: should I attach a Cortex Search Service?
  → Yes: provide the fully qualified CSS name: DB.SCHEMA.CSS_NAME
         (or type "create" and I'll generate the DDL to create one)
  → No: leave as standard dimension (keyword filter only)
  → Skip all: no CSS attachments
```

Store results as `CSS_ATTACHMENTS`: list of `{ table_alias, col_name, css_fqn }`.

In Phase 5 Step 5.4, each entry in `CSS_ATTACHMENTS` gets:
```sql
<table_alias>.<dim_name> AS <physical_col>
  WITH SYNONYMS = ( ... )
  COMMENT = '<description>'
  WITH CORTEX SEARCH SERVICE <css_fqn>
```

⚠️ **No `AS` on the `WITH CORTEX SEARCH SERVICE` line** — it is not an expression, it is a clause modifier.
⚠️ **Order is enforced**: `WITH SYNONYMS` → `COMMENT` → `WITH CORTEX SEARCH SERVICE` (last).

If no candidates exist, skip this step silently.

---

## Step 3.3.6: PRIVATE modifier check (fix 4)

After CSS check, ask about visibility of facts and metrics:

```
Visibility check — facts and metrics are PUBLIC by default (visible in Snowflake Intelligence UI).

Mark any as PRIVATE if they should be queryable by Cortex Analyst but hidden from the UI browser:

Facts:    <list all FACT column names>
Metrics:  <list all proposed metric names>

Any to mark PRIVATE? (e.g. "cost_basis, margin_pct" — or "none")
```

For each column/metric the user marks PRIVATE, prepend `PRIVATE` in Phase 5 generation:
```sql
PRIVATE <table_alias>.<fact_name> AS <physical_col>
```
```sql
PRIVATE <table_alias>.<metric_name> AS <aggregate_expr>
```

⚠️ `PRIVATE` is valid on FACTS and METRICS only — **not on dimensions**. If user tries to mark a
dimension PRIVATE, explain this and offer to SKIP it instead.

Store as `PRIVATE_COLUMNS`: set of `{ table_alias, col_name }`.

---

## Step 3.4: Governance notes (non-blocking)

Run this step **after** user overrides are accepted (Step 3.3 complete).

**Regulated mode override**: If `REGULATED_MODE = true`, treat every advisory note below as a hard
⚠️ **STOPPING POINT** — require explicit user confirmation before proceeding to Phase 4. This
restores the original blocking behavior for HIPAA/GDPR/PCI/SOX environments.

**Short-circuit conditions** (vary by case):

- `PII_SCAN_MODE = "skip"` → show only the ℹ️ skip note at the bottom of this section, then continue
- `PII_FLAGGED` is empty AND `IS_MTT = false` → continue silently (no panel)
- `PII_FLAGGED` non-empty but `PII_KEPT_AS_DIMENSION` is empty AND `IS_MTT = false`:
  → show the **PII auto-SKIP notice** below (not the full panel), then continue

**Full panel** — present when `PII_KEPT_AS_DIMENSION` is non-empty OR `IS_MTT = true`.
Continue automatically unless the user types "mask", "rap", or "stop":

```
─── Governance Notes ───────────────────────────────────────────
PII columns kept as DIMENSION: <table.column list, or "none">
  → Masking policies recommended (type "mask" to set up now)

MTT: <TENANT_COLUMNS> locked as DIMENSION ✓   [only if IS_MTT=true]
  → Row access policy recommended (type "rap" to set up now)
────────────────────────────────────────────────────────────────
Type "mask", "rap", or press Enter / "ok" to continue to Phase 4.
```

Only render the MTT line if `IS_MTT = true`.
Only render the PII line if `PII_KEPT_AS_DIMENSION` is non-empty.

**PII auto-SKIP notice** — show when `PII_FLAGGED` non-empty but none kept as DIMENSION:

```
ℹ️  <N> PII column(s) detected and auto-classified as SKIP: <column list>.
    They will not appear in the semantic view.
    Type "mask" to include them with a masking policy, or press Enter to continue.
```

Wait for user input here (default: continue on Enter/"ok").

**If user types "mask"**: note "load data-governance skill → data-policy workflow" and pause.
Resume semantic-view-ddl from Phase 4 when masking setup is complete.

**If user types "rap"**: note "load data-governance skill → data-policy workflow (row access
policy track)" and pause. Resume from Phase 4 when done.

**Any other input (Enter, "ok", "continue")**: proceed immediately to Phase 4.

### PII scan was skipped (PII_SCAN_MODE = "skip")

Append a single informational note and continue without waiting:

```
ℹ️  PII scanning was skipped. If these tables contain personal data, consider
    running SYSTEM$CLASSIFY or reviewing string columns manually before deploying
    this SV to production.
```

---

## Output variables

| Variable | Contents |
|----------|----------|
| `COLUMN_CLASSES` | Per-table, per-column classification dict |
| `PROPOSED_METRICS` | List of {table, name, expr, description} |
| `PII_FLAGGED` | Columns identified as PII (any scan mode) |
| `PII_KEPT_AS_DIMENSION` | Subset of PII_FLAGGED with final class = DIMENSION |
| `CSS_ATTACHMENTS` | List of {table_alias, col_name, css_fqn} — dimensions with Cortex Search attached |
| `PRIVATE_COLUMNS` | Set of {table_alias, col_name} — facts/metrics to render with PRIVATE modifier |
