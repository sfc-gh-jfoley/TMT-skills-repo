---
name: sv-ddl-phase1-context
description: Context gathering for DDL-based semantic view creation — tables, business intent, and optional documentation
---

# Phase 1: Context Gathering

## Purpose
Collect everything needed before touching Snowflake: tables, business context, and optional data dictionary.
This phase has **one mandatory stopping point** — wait for user input before proceeding to Phase 2.

---

## Step 1.0: New or existing semantic view?

Before anything else, ask:

```
Are you creating a new semantic view or improving an existing one?

  A) New — build from source tables (continue through all phases)
  B) Existing — load a deployed SV and edit it (skip Phases 2-4, go to Phase 5)
```

### If B (existing SV):

Ask for the fully qualified SV name, then fetch its current DDL:

```sql
SELECT GET_DDL('SEMANTIC VIEW', '<DB>.<SCHEMA>.<SV_NAME>');
```

Store the result as `EXISTING_DDL`. Then ask:

```
Loaded existing SV: <SV_NAME>
  Tables:      <N>
  Facts:       <N>
  Dimensions:  <N>
  Metrics:     <N>

What would you like to change?
Examples:
  - Add a new metric
  - Add AI_QUESTION_CATEGORIZATION
  - Attach a Cortex Search Service to a dimension
  - Mark a fact as PRIVATE
  - Add AI_VERIFIED_QUERIES
  - Fix a broken alias
  - Add a missing relationship

Describe your changes and I'll update the DDL directly in Phase 5.
```

Set `MODE = "existing"`. Skip Phases 2, 3, and 4 entirely. Load Phase 5 with `EXISTING_DDL`
pre-populated as the starting DDL. Run the self-check (Step 5.8) against it before presenting.

### If A (new SV):

Set `MODE = "new"`. Continue to Step 1.1 below.

---

## Step 1.1: Get semantic view target

Ask for three things in a single message:

1. **Semantic view name** — valid SQL identifier, uppercase recommended: `DEALER_360_SV`
2. **Target database + schema** — where the SV will be created: `MY_DB.PUBLIC`
3. **Snowflake connection** — which connection to use (or "default")

Store as:
- `SV_NAME`
- `SV_DB`, `SV_SCHEMA`
- `SV_CONNECTION`

---

## Step 1.2: Get source tables

Ask: "Which tables should this semantic view cover? Provide fully qualified names: `DB.SCHEMA.TABLE`"

Accept any of:
- A list of table names (one per line or comma-separated)
- A SQL query you want modeled (extract tables from it)
- A description of the domain (e.g. "our dealer management tables in AUTOTRADER_DB.PROD")

Extract fully qualified table names. Store as `SOURCE_TABLES` list.

For each table, immediately verify access:
```sql
SELECT * FROM <db>.<schema>.<table> LIMIT 1;
```

If any table is inaccessible, **stop and report** which tables failed before proceeding.

---

## Step 1.3: Get business context

Ask: "What business questions should this semantic view answer? What are the key metrics and dimensions users care about?"

Accept free-form text. This feeds directly into:
- AI_SQL_GENERATION instructions
- Description generation prompts in Phase 2
- Metric/dimension classification in Phase 3

Store as `BUSINESS_CONTEXT`.

---

## Step 1.4: Optional — documentation context

Ask: "Do you have any documentation that describes these tables? Provide a file path or paste the content directly."

Accept:
- **File paths**: `.md`, `.txt`, `.csv` (data dictionary), `.yaml`
- **Pasted text**: column descriptions, ERD notes, data dictionary table
- **Nothing** — skip and proceed

If a file path is provided:
```bash
cat <file_path>
```
Read the file and store as `DOC_CONTEXT`.

If CSV format (data dictionary), parse for: `table_name`, `column_name`, `description` columns.

If nothing provided, set `DOC_CONTEXT = null`.

---

## Step 1.5: MTT and PII governance intake

Ask all questions together in a single message — do not split into multiple rounds.

If the user types **`s`** (or "skip") at any point in this step, immediately set
`IS_MTT=false`, `TENANT_COLUMNS=[]`, `PII_SCAN_MODE="skip"`, `REGULATED_MODE=false`
and proceed directly to Phase 2 — skip the rest of Step 1.5.

```
(Type 's' to skip governance questions and proceed directly to Phase 2)

Three quick governance questions before we profile the tables:

1. Multi-tenancy: Is this schema shared across multiple customers, orgs, or tenants?
   (e.g., a SaaS product where each customer's data lives in the same tables)
   → Yes / No
   If yes: which column(s) define the tenant boundary?
   (e.g., ACCOUNT_ID, ORG_ID, TENANT_ID, CLIENT_ID — one column is typical)

2. PII scanning: How thorough should PII detection be?
   A) Name patterns only  — fast; flags columns named EMAIL, SSN, PHONE, DOB, ADDRESS, etc.
   B) Name patterns + SYSTEM$CLASSIFY  — thorough; runs Snowflake's built-in classifier
      on each source table (~10-30s per table, requires APPLY DATA PRIVACY CLASSIFICATION privilege)
   C) Skip PII scanning  — I'll handle governance separately

3. Regulated environment: Is this SV for HIPAA, GDPR, PCI, or SOX compliance?
   → Yes / No  (if yes, governance warnings become hard stops rather than advisory notes)
```

Store responses as:
- `IS_MTT` — `true` / `false`
- `TENANT_COLUMNS` — list of tenant discriminator column names (empty if IS_MTT=false)
- `PII_SCAN_MODE` — `"patterns"` | `"classify"` | `"skip"`
- `REGULATED_MODE` — `true` / `false`

**If IS_MTT = true**: note that tenant columns will be forced to DIMENSION in Phase 3 and a row access policy will be recommended at the end of Phase 3.

**If PII_SCAN_MODE = "classify"**: SYSTEM$CLASSIFY will be run per table in Phase 3 Step 3.1 before any column-name pattern checks.

**If REGULATED_MODE = true**: governance notes in Phase 3 Step 3.4 become hard stopping points.

---

## ⚠️ MANDATORY STOP

Present this summary before proceeding:

```
Context collected:
  SV name:        <SV_NAME>
  Target:         <SV_DB>.<SV_SCHEMA>
  Tables:         <N> tables — <list>
  Connection:     <SV_CONNECTION>
  Doc context:    <"yes - N chars" | "none">
  Multi-tenant:   <"yes — tenant col: <TENANT_COLUMNS>" | "no">
  PII scan mode:  <"name patterns" | "SYSTEM$CLASSIFY" | "skip">
  Regulated mode: <"yes (HIPAA/GDPR/PCI/SOX)" | "no">

Proceeding to Phase 2: Profile & Auto-Describe.
```

Wait for user to confirm or correct before loading Phase 2.

---

## Output variables passed to next phases

| Variable | Contents |
|----------|----------|
| `SV_NAME` | Semantic view identifier |
| `SV_DB`, `SV_SCHEMA` | Target location |
| `SV_CONNECTION` | Active Snowflake connection name |
| `SOURCE_TABLES` | List of fully qualified table names |
| `BUSINESS_CONTEXT` | Free-form business description |
| `DOC_CONTEXT` | Documentation text or null |
| `IS_MTT` | true/false — multi-tenant schema |
| `TENANT_COLUMNS` | List of tenant discriminator column names |
| `PII_SCAN_MODE` | "patterns" \| "classify" \| "skip" |
| `REGULATED_MODE` | true/false — regulated compliance environment (HIPAA/GDPR/PCI/SOX) |
