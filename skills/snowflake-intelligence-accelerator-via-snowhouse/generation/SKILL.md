---
name: snowflake-intelligence-generation
description: "Generation phase for SI Accelerator. Cluster domains and generate deployment scripts."
parent_skill: snowflake-intelligence-accelerator-via-snowhouse
---

# Generation Phase

Cluster discovered tables into business domains and generate 9 deployment scripts.

## When to Load

- After completing discovery phase
- User says "create scripts", "generate setup", or "now generate"

## Prerequisites

- Discovery phase completed with:
  - Customer account ID and deployment
  - BI warehouse(s) identified
  - High-value tables discovered
  - Column metadata extracted

## Workflow

### Step 1: Domain Clustering

**Goal:** Group discovered tables into business domains

**Clustering Patterns:**
| Pattern | Domain | Example Tables |
|---------|--------|----------------|
| `FACT_`, `ORDER`, `DELIVERY`, `TRANSACTION` | Operations | FACT_ORDERS, MAINDBLOCAL_DELIVERY |
| `DIM_`, `DIMENSION_`, `MASTER_` | Dimensions | DIMENSION_STORE, DIM_DATE |
| `USER`, `CUSTOMER`, `CONSUMER`, `MEMBER` | Users | DIMENSION_CONSUMERS, USER_PROFILE |
| `PRODUCT`, `CATALOG`, `ITEM`, `SKU` | Products | CATALOG_UMP, PRODUCT_MASTER |
| `CAMPAIGN`, `AD_`, `PROMOTION` | Marketing | DIM_CAMPAIGN_HISTORY |
| `REVENUE`, `COST`, `PAYMENT` | Finance | FACT_REVENUE, PAYMENTS |

**Present proposed domains** to user with table assignments.

**STOPPING POINT**: Confirm domain clustering with user before proceeding.

### Step 2: Load Reference Implementation

**MANDATORY** before generating ANY scripts:

1. **Read** `example/for_the_customer/01_semantic_views.sql` - Semantic view syntax
2. **Read** `example/for_the_customer/04_agent_creation.sql` - Agent specification pattern
3. **Read** `example/for_your_demo_account/01_synthetic_datagen.sql` - Procedure patterns
4. **Read** `example/for_the_customer/02_cortex_search.sql` - Search service syntax

**Also load** `references/sql-patterns.md` for syntax reminders.

### Step 3: Apply Naming Conventions

| Object | Pattern | Example |
|--------|---------|---------|
| Role | `[CUSTOMER]_snow_intelligence` | `ACME_snow_intelligence` |
| Warehouse | `[CUSTOMER]_snow_intelligence_WH` | `ACME_snow_intelligence_WH` |
| Database | `SI_[CUSTOMER]` | `SI_ACME` |
| Schema | `[CUSTOMER]_SNOW_INTELLIGENCE` | `ACME_SNOW_INTELLIGENCE` |
| Agent | `[CUSTOMER]_Platform_Agent` | `ACME_Platform_Agent` |

### Step 4: Generate Scripts

**Create folder:** `example_[customer]/` at repository root with two subfolders.

**Generate 9 scripts by copying patterns from `example/`:**

```
example_[customer]/
├── for_the_customer/
│   ├── 00_infrastructure_[customer].sql
│   ├── 01_semantic_views_[customer].sql
│   ├── 02_cortex_search_[customer].sql
│   ├── 03_support_functions_[customer].sql
│   ├── 04_agent_creation_[customer].sql
│   └── 05_verification_[customer].sql
└── for_your_demo_account/
    ├── 00_base_tables_[customer].sql
    ├── 01_synthetic_datagen_[customer].sql
    └── 02_complete_teardown_[customer].sql
```

**Script content guidance:**

**00_infrastructure:** Role, warehouse, database, schema, views pointing to source tables

**01_semantic_views:** One semantic view per domain. Follow syntax exactly:
```sql
CREATE OR REPLACE SEMANTIC VIEW [NAME]
    TABLES (
        ALIAS AS SCHEMA.TABLE WITH SYNONYMS = ('...') COMMENT = '...'
    )
    FACTS (
        ALIAS.semantic_name AS ACTUAL_COLUMN WITH SYNONYMS = ('...') COMMENT = '...'
    )
    DIMENSIONS (
        ALIAS.semantic_name AS ACTUAL_COLUMN WITH SYNONYMS = ('...') COMMENT = '...'
    );
```

**02_cortex_search:** One search service per catalog/lookup table. Single `ON` column with concatenated SEARCH_TEXT.

**03_support_functions:** Email and Streamlit procedures

**04_agent_creation:** Use `CREATE AGENT ... FROM SPECIFICATION $$...$$` syntax. Include 10 sample questions (mix of single-domain and cross-domain).

**05_verification:** Test queries for each semantic view and search service

**00_base_tables (demo):** CREATE TABLE statements matching column definitions in synthetic datagen

**01_synthetic_datagen (demo):** Stored procedure with realistic data distributions (power-law, tiered, temporal patterns)

**02_complete_teardown (demo):** DROP statements for all objects (commented out for safety)

### Step 5: Validate Scripts

**Checklist before completing:**
- [ ] Base table schemas match columns in synthetic datagen procedure
- [ ] Semantic view column references match actual source columns
- [ ] Cortex Search references only existing columns
- [ ] Agent tool parameters match procedure signatures
- [ ] Scripts can run in sequence without errors

## Output

9 SQL scripts in `example_[customer]/` ready for deployment.

## Next Step

Instruct user to:
1. End this session (`/exit`)
2. Start new session with demo account: `cortex --connection [DEMO_CONNECTION]`
3. **Load** `deployment/SKILL.md` for deployment guidance

## Critical Reminders

**Semantic View Syntax:**
- Pattern: `ALIAS.semantic_name AS actual_source_column`
- RIGHT side must EXACTLY match column in source table
- Keywords UPPERCASE: `WITH SYNONYMS =`, `COMMENT =`

**Cortex Search:**
- Single column in `ON` clause
- Concatenate searchable fields into SEARCH_TEXT column

**Agent Tool Parameters:**
- `input_schema` property names must match procedure parameter names exactly

**Stored Procedures:**
- Use simple names for temporary tables (no fully-qualified names)
- Replace scalar subqueries with JOINs
- Use uniform() for random selection, not `ORDER BY random() LIMIT 1`
