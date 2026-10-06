---
name: snowflake-intelligence-discovery
description: "Discovery phase for SI Accelerator. Find customer accounts, BI warehouses, and high-value objects from Snowhouse."
parent_skill: snowflake-intelligence-accelerator-via-snowhouse
---

# Discovery Phase

Find customer accounts, identify BI warehouses, and discover high-value data objects from Snowhouse metadata.

## When to Load

- User says "build SI for [customer]" or "find accounts for [customer]"
- Starting the full intelligence accelerator workflow

## Prerequisites

- Connected to **SNOWHOUSE** (`cortex --connection SNOWHOUSE`)

## Workflow

### Step 1: Find Customer Accounts

**Goal:** Identify all Snowflake accounts for the customer

**Action:** Execute account discovery query:
```sql
SELECT DISTINCT 
    salesforce_account_id,
    salesforce_account_name, 
    snowflake_account_id,
    snowflake_account_name, 
    snowflake_account_alias,
    snowflake_deployment
FROM FINANCE.CUSTOMER.SUBSCRIPTION
WHERE salesforce_account_name ILIKE '%[CUSTOMER_NAME]%';
```

**Present results** to user in a table format.

**MANDATORY STOPPING POINT**: Ask user which account to analyze.

**Capture:** Note the `snowflake_deployment` value - this is required for all subsequent queries.

### Step 2: Identify BI/Reporting Warehouses

**Goal:** Find warehouses used for analytics and reporting

**Action:** Execute warehouse discovery query using the `snowflake_deployment`:
```sql
SELECT 
    WAREHOUSE_NAME,
    COUNT(*) as query_count,
    AVG(EXECUTION_TIME) as avg_execution_ms,
    SUM(CREDITS_USED) as total_credits,
    COUNT(DISTINCT dpo:"JobDPO:userId"::STRING) as distinct_users
FROM SNOWHOUSE_IMPORT.[snowflake_deployment].JOB_RAW_V
WHERE ACCOUNT_ID = [snowflake_account_id]
  AND START_TIME >= DATEADD(day, -14, CURRENT_TIMESTAMP())
GROUP BY 1
HAVING query_count > 100
ORDER BY query_count DESC;
```

**Look for warehouses with:**
- Names containing: `BI`, `REPORTING`, `ANALYTICS`, `SIGMA`, `TABLEAU`, `LOOKER`, `POWERBI`, `MODE`, `METABASE`
- High query count with low avg execution time (interactive queries)
- Multiple distinct users (shared reporting)

**Present findings** with recommendation.

**STOPPING POINT**: Confirm BI warehouse selection with user.

### Step 3: Discover High-Value Objects

**Goal:** Find the most-queried tables/views from BI warehouses

**Action:** Execute object discovery query:
```sql
SELECT 
    DATABASE_NAME,
    SCHEMA_NAME,
    NAME as object_name,
    OBJECT_TYPE,
    COUNT(*) as query_count,
    COUNT(DISTINCT dpo:"JobDPO:userId"::STRING) as distinct_users
FROM SNOWHOUSE_IMPORT.[snowflake_deployment].TABLE_ETL_V
WHERE ACCOUNT_ID = [snowflake_account_id]
  AND WAREHOUSE_NAME IN ([BI_WAREHOUSES])
  AND QUERY_START_TIME >= DATEADD(day, -14, CURRENT_TIMESTAMP())
GROUP BY 1, 2, 3, 4
ORDER BY query_count DESC
LIMIT 100;
```

### Step 4: Analyze Query Patterns

**Goal:** Understand business use cases from actual queries

**Action:** Execute query pattern analysis:
```sql
SELECT 
    dpo:"JobDPO:description"::STRING as query_text,
    COUNT(*) as execution_count
FROM SNOWHOUSE_IMPORT.[snowflake_deployment].JOB_RAW_V
WHERE ACCOUNT_ID = [snowflake_account_id]
  AND WAREHOUSE_NAME IN ([BI_WAREHOUSES])
  AND START_TIME >= DATEADD(day, -14, CURRENT_TIMESTAMP())
  AND query_text ILIKE '%SELECT%'
  AND (query_text ILIKE '%SUM(%' OR query_text ILIKE '%COUNT(%' 
       OR query_text ILIKE '%AVG(%' OR query_text ILIKE '%GROUP BY%')
GROUP BY 1
ORDER BY execution_count DESC
LIMIT 50;
```

### Step 5: Get Column Metadata

**Goal:** Extract column details for semantic view design

**Action:** For top tables, execute:
```sql
SELECT 
    TABLE_NAME,
    COLUMN_NAME,
    DATA_TYPE,
    ORDINAL
FROM SNOWHOUSE_IMPORT.[snowflake_deployment].TABLE_COLUMN_ETL_V
WHERE ACCOUNT_ID = [snowflake_account_id]
  AND DATABASE_NAME = '[DATABASE]'
  AND TABLE_NAME IN ([TOP_TABLES])
ORDER BY TABLE_NAME, ORDINAL;
```

## Output

Collected discovery data:
- Customer account details (ID, deployment)
- BI warehouse(s) identified
- Top 20-50 high-value tables with query counts
- Sample business queries showing use cases
- Column metadata for key tables

## Next Step

**Load** `generation/SKILL.md` to cluster domains and generate scripts.

## Troubleshooting

**"No accounts found"**
- Check customer name spelling
- Try partial names: "Door" instead of "DoorDash"

**"No BI warehouses identified"**
- Customer may use non-standard naming
- Ask user to specify warehouse name directly

**Column mapping reference:**
| ACCOUNT_USAGE | Snowhouse |
|---------------|-----------|
| QUERY_TEXT | `dpo:"JobDPO:description"::STRING` |
| USER_NAME | `dpo:"JobDPO:userId"::STRING` |
| TABLE_NAME | NAME |
| ORDINAL_POSITION | ORDINAL |
