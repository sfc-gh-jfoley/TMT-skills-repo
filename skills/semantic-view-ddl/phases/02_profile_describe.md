---
name: sv-ddl-phase2-profile-describe
description: Profile source tables and use CORTEX.COMPLETE to auto-generate column descriptions, synonyms, and sample values
---

# Phase 2: Profile & Auto-Describe

## Purpose
Profile each source table's data and use `SNOWFLAKE.CORTEX.COMPLETE` to generate:
- Column descriptions (1-2 sentences, business-readable)
- Synonyms (2-3 natural language aliases)
- Sample values (5 representative values for categorical columns)

This is the programmatic equivalent of what Snowsight does manually when you describe a semantic view column.

---

## Step 2.1: Profile each source table

For **each table** in `SOURCE_TABLES`, run this profiling query. Replace `<TABLE>` with the fully qualified name.

```sql
SELECT
    c.COLUMN_NAME,
    c.DATA_TYPE,
    c.COMMENT,
    c.IS_NULLABLE,
    c.CHARACTER_MAXIMUM_LENGTH,
    COUNT_IF(t.<col> IS NOT NULL)            AS non_null_count,
    COUNT_IF(t.<col> IS NULL)                AS null_count,
    COUNT(DISTINCT t.<col>)                  AS distinct_count,
    COUNT(*)                                 AS total_rows
FROM INFORMATION_SCHEMA.COLUMNS c
WHERE c.TABLE_CATALOG = '<db>'
  AND c.TABLE_SCHEMA  = '<schema>'
  AND c.TABLE_NAME    = '<table>'
ORDER BY c.ORDINAL_POSITION;
```

**Note**: The `non_null_count`/`null_count`/`distinct_count` columns above are illustrative — run a separate count query per column for tables with wide schemas. For most tables, use the simplified profiling query below:

```sql
-- Simplified profiling: row count + column catalog
SELECT
    COLUMN_NAME,
    DATA_TYPE,
    COMMENT,
    IS_NULLABLE
FROM <db>.INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA = '<schema>'
  AND TABLE_NAME   = '<table>'
ORDER BY ORDINAL_POSITION;

-- Row count
SELECT COUNT(*) AS total_rows FROM <db>.<schema>.<table>;
```

Then for **categorical columns** (VARCHAR, BOOLEAN, DATE) with manageable cardinality — get sample values:

```sql
SELECT ARRAY_AGG(DISTINCT <col>::VARCHAR) WITHIN GROUP (ORDER BY <col>::VARCHAR)
FROM (SELECT <col> FROM <db>.<schema>.<table> LIMIT 500) t
WHERE <col> IS NOT NULL;
```

Store results as `TABLE_PROFILES` — a per-table dict of column metadata.

---

## Step 2.1.5: Non-standard identifier scan

After collecting column names from DESCRIBE / INFORMATION_SCHEMA, scan **every column name** across all source tables for characters that require double-quote wrapping.

**A column name is non-standard if it:**
- Contains any character outside `A-Z`, `0-9`, `_` (after uppercasing)
- Starts with a digit
- Contains SQL-significant chars: `@`, `.`, `-`, `:`, `|`, `"`, `(`, `)`, space, or tab
- Matches patterns suggesting auto-generation: contains `||`, `current_timestamp`, `::`, numeric suffix after special char

**Detection query** (run once per table):

```sql
SELECT
    COLUMN_NAME,
    CASE
        WHEN COLUMN_NAME != UPPER(REGEXP_REPLACE(COLUMN_NAME, '[^A-Z0-9_]', ''))
             OR REGEXP_LIKE(COLUMN_NAME, '^[0-9].*')
        THEN TRUE
        ELSE FALSE
    END AS needs_quoting,
    '"' || REPLACE(COLUMN_NAME, '"', '""') || '"' AS safe_quoted_form
FROM <db>.INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA = '<schema>'
  AND TABLE_NAME   = '<table>'
  AND (
      COLUMN_NAME != UPPER(REGEXP_REPLACE(COLUMN_NAME, '[^A-Z0-9_]', ''))
      OR REGEXP_LIKE(COLUMN_NAME, '^[0-9].*')
  )
ORDER BY ORDINAL_POSITION;
```

**If any non-standard columns are found:**

1. Store them in `NON_STANDARD_COLUMNS` as a dict: `{original_name: safe_quoted_form}`
2. Print a warning block before the description preview:

```
⚠️  NON-STANDARD COLUMN IDENTIFIERS DETECTED

These column names require double-quote wrapping in all DDL expressions.
They will be quoted automatically in the generated semantic view.

  Table: <TABLE>
  ┌─────────────────────────────────────┬──────────────────────────────────────────┐
  │ Column name (raw)                   │ Safe quoted form                         │
  ├─────────────────────────────────────┼──────────────────────────────────────────┤
  │ user@email.com                      │ "user@email.com"                         │
  │ dev_||@_||timestamp:_:_._old        │ "dev_||@_||timestamp:_:_._old"           │
  │ 2023_revenue                        │ "2023_revenue"                           │
  └─────────────────────────────────────┴──────────────────────────────────────────┘

  These columns will be classified normally in Phase 3 but will be
  excluded from FACTS/DIMENSIONS/METRICS unless you explicitly include them.
  Recommendation: SKIP non-standard columns in classification unless they
  carry essential business value — they create fragile DDL.
```

3. In Phase 3 classification, **default non-standard columns to SKIP** with the note `[non-standard identifier — skipped by default]`. The user can override to DIMENSION/FACT if needed.
4. If a non-standard column IS kept (user overrides to DIMENSION/FACT), flag it in Phase 5 so Rule 9 wraps it in double-quotes everywhere it appears in the DDL — including inside computed expressions.

---

## Step 2.2: Auto-describe with CORTEX.COMPLETE

For each column, build and execute a CORTEX.COMPLETE prompt.

**Prompt template** (use `mistral-7b` for speed, `llama3.1-70b` for quality):

```sql
SELECT SNOWFLAKE.CORTEX.COMPLETE(
  'mistral-7b',
  CONCAT(
    'You are a data documentation expert. Generate metadata for a database column.\n',
    'Respond ONLY with a JSON object — no explanation, no markdown fences.\n\n',
    'Table: ', '<table_name>', '\n',
    'Column: ', '<col_name>', '\n',
    'Data type: ', '<data_type>', '\n',
    'Nullable: ', '<is_nullable>', '\n',
    'Distinct values (approx): ', '<distinct_count>', '\n',
    'Sample values: ', '<sample_values_csv>', '\n',
    'Existing comment: ', '<existing_comment_or_none>', '\n',
    'Business context: ', '<BUSINESS_CONTEXT>', '\n',
    CASE WHEN '<DOC_CONTEXT>' != 'null'
         THEN CONCAT('Documentation context:\n', '<DOC_CONTEXT>', '\n')
         ELSE '' END,
    '\n',
    'Return exactly this JSON structure:\n',
    '{"description": "1-2 sentence business description",',
    '"synonyms": ["alias1","alias2","alias3"],',
    '"sample_values": ["val1","val2","val3","val4","val5"]',
    '}'
  )
) AS col_metadata;
```

**Batch strategy**: For tables with many columns (>20), batch 5 columns per CORTEX.COMPLETE call to reduce latency:

```sql
SELECT SNOWFLAKE.CORTEX.COMPLETE(
  'mistral-7b',
  CONCAT(
    'Generate JSON metadata for these ', <N>, ' columns from table <table_name>.\n',
    'Business context: <BUSINESS_CONTEXT>\n',
    'Return a JSON array, one object per column with keys: column_name, description, synonyms, sample_values.\n\n',
    'Columns:\n',
    '1. <col1> (<type1>) sample values: <samples1>\n',
    '2. <col2> (<type2>) sample values: <samples2>\n',
    ...
  )
) AS batch_metadata;
```

Parse the JSON result and store as `COLUMN_DESCRIPTIONS` — a dict keyed by `table.column`.

---

## Step 2.3: Apply descriptions as COMMENT ON COLUMN

After generating descriptions, apply them to Snowflake so FastGen or DESCRIBE will pick them up:

```sql
-- Apply table comment
COMMENT ON TABLE <db>.<schema>.<table>
  IS '<generated table description>';

-- Apply per-column comments (repeat for each column)
ALTER TABLE <db>.<schema>.<table>
  ALTER COLUMN <col_name> COMMENT '<generated description>';
```

**Note**: This modifies the source tables. If that's not acceptable, set `APPLY_COMMENTS = false` and skip this step — descriptions will be injected directly into the DDL COMMENT clauses in Phase 5.

Ask user: "Apply descriptions as COMMENT ON COLUMN in Snowflake? (yes = updates source tables, no = inject into DDL only)"

---

## Step 2.4: Present description preview

Show a sample of 3-5 generated descriptions for user review:

```
Auto-description preview (3 of N columns):

  DEALER_ID (VARCHAR)
    → Description: "Unique identifier for each dealership in the network."
    → Synonyms: dealer id, dealership id, dealer code
    → Sample values: DLR-001, DLR-042, DLR-118

  DAYS_IN_INVENTORY (NUMBER)
    → Description: "Number of days a vehicle has been on the lot since acquisition."
    → Synonyms: lot age, days on lot, inventory age
    → Sample values: 3, 14, 47, 62, 89

  LISTING_STATUS (VARCHAR)
    → Description: "Current listing status of the vehicle on the marketplace."
    → Synonyms: status, availability, listing state
    → Sample values: ACTIVE, SOLD, EXPIRED, PENDING

Proceed with these descriptions? (yes / regenerate / skip descriptions)
```

⚠️ **STOPPING POINT** — Wait for user approval before continuing to Phase 3.

---

## Output variables

| Variable | Contents |
|----------|----------|
| `TABLE_PROFILES` | Per-table dict: column name → {data_type, nullable, distinct_count, sample_values} |
| `COLUMN_DESCRIPTIONS` | Per-column dict: table.col → {description, synonyms, sample_values} |
| `APPLY_COMMENTS` | Boolean — whether COMMENTs were written to source tables |
| `NON_STANDARD_COLUMNS` | Dict of flagged columns: `{original_name: safe_quoted_form}` — empty if all names are clean |
