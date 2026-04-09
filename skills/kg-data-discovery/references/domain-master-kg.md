# Master KG

Federated search across all domains via a single master Cortex Search Service.

## Purpose

When a user asks "what commerce data do we have?" they shouldn't need to know which domain to search. The master KG provides a single entry point that searches all domain CSS endpoints.

## Architecture

```
User Question
    ↓
Master KG CSS (MASTER_META.META.MASTER_SEARCH)
    ↓ returns concept rows with domain + source info
    ↓
Route to domain-specific CSS for deeper search (optional)
    ↓
ASSEMBLE → QUERY → EXECUTE
```

## Setup

### 1. Create Master META Database

```sql
CREATE DATABASE IF NOT EXISTS MASTER_META;
CREATE SCHEMA IF NOT EXISTS MASTER_META.META;
```

### 2. Create Master CONCEPTS Table

Union all domain CONCEPTS tables:

```sql
CREATE OR REPLACE TABLE MASTER_META.META.CONCEPTS AS
SELECT
  concept_id,
  concept_name,
  concept_level,
  domain,
  source_database,
  source_schema,
  source_table,
  description,
  keywords,
  search_content,
  tables_yaml,
  join_keys_yaml,
  metrics_yaml,
  sample_values,
  is_enum,
  enrichment_quality_score,
  is_active,
  object_state
FROM FINANCE_META.META.CONCEPTS WHERE is_active = TRUE
UNION ALL
SELECT * FROM SALESFORCE_META.META.CONCEPTS WHERE is_active = TRUE
UNION ALL
SELECT * FROM PRODUCT_META.META.CONCEPTS WHERE is_active = TRUE;
-- Add more domains as they're onboarded
```

### 3. Auto-Discovery via SHOW

Instead of hardcoding domain unions, discover all domain CSS endpoints:

```sql
SHOW CORTEX SEARCH SERVICES IN ACCOUNT;

-- Filter to KG convention (*_SEARCH in META schema)
-- Then query each domain's CONCEPTS table dynamically
```

Stored proc for auto-union:

```sql
CREATE OR REPLACE PROCEDURE MASTER_META.META.REFRESH_MASTER()
RETURNS VARCHAR
LANGUAGE PYTHON
RUNTIME_VERSION = '3.11'
PACKAGES = ('snowflake-snowpark-python')
HANDLER = 'run'
AS
$$
def run(session):
    css_rows = session.sql("SHOW CORTEX SEARCH SERVICES IN ACCOUNT").collect()
    
    domain_queries = []
    for row in css_rows:
        db = row['database_name']
        schema = row['schema_name']
        name = row['name']
        if schema == 'META' and name.endswith('_SEARCH'):
            concepts_fqn = f"{db}.{schema}.CONCEPTS"
            try:
                session.sql(f"SELECT 1 FROM {concepts_fqn} LIMIT 1").collect()
                domain_queries.append(
                    f"SELECT * FROM {concepts_fqn} WHERE is_active = TRUE"
                )
            except:
                pass
    
    if not domain_queries:
        return "No domain CONCEPTS tables found"
    
    union_sql = " UNION ALL ".join(domain_queries)
    session.sql(f"CREATE OR REPLACE TABLE MASTER_META.META.CONCEPTS AS {union_sql}").collect()
    
    count = session.sql("SELECT COUNT(*) AS cnt FROM MASTER_META.META.CONCEPTS").collect()[0]['CNT']
    return f"Master CONCEPTS refreshed: {count} rows from {len(domain_queries)} domains"
$$;
```

### 4. Create Master CSS

```sql
CREATE OR REPLACE CORTEX SEARCH SERVICE MASTER_META.META.MASTER_SEARCH
  ON search_content
  ATTRIBUTES concept_name, concept_level, domain, source_database, source_schema
  WAREHOUSE = COMPUTE_WH
  TARGET_LAG = '1 hour'
AS (
  SELECT
    concept_name, concept_level, domain, source_database, source_schema,
    search_content, tables_yaml, join_keys_yaml, metrics_yaml,
    sample_values, is_enum
  FROM MASTER_META.META.CONCEPTS
);
```

### 5. Schedule Refresh

```sql
CREATE OR REPLACE TASK MASTER_META.META.REFRESH_MASTER_TASK
  WAREHOUSE = COMPUTE_WH
  SCHEDULE = 'USING CRON 0 7 * * * America/New_York'
AS
  CALL MASTER_META.META.REFRESH_MASTER();

ALTER TASK MASTER_META.META.REFRESH_MASTER_TASK RESUME;
```

## Query Flow with Master KG

1. Search MASTER_SEARCH with user question
2. Results include `domain` attribute — identifies which domain(s) are relevant
3. If single domain: use that domain's CONCEPTS directly for assembly
4. If multi-domain: merge concept rows from multiple domains, check cross-domain RELATIONSHIPS
5. Assemble and query as normal

## Master KG vs Domain CSS

| Aspect | Master KG | Domain CSS |
|--------|-----------|------------|
| Scope | All domains | Single domain |
| Precision | Lower (broader search) | Higher (focused) |
| Use case | Exploration, routing | SQL generation |
| Latency | Same (~100ms) | Same (~100ms) |
| Refresh | Depends on all domains | Independent |

Best practice: Use master for routing ("which domain has this data?"), then domain CSS for assembly ("give me the columns and joins").
