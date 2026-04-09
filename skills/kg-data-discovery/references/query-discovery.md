# Query Discovery

End-to-end flow: user question → KG search → schema assembly → SQL generation → execution.

## Flow Overview

```
User Question
    ↓
Step 4: SEARCH — hit domain/master CSS (~100ms)
    ↓ returns top-K concept rows
Step 5: ASSEMBLE — deduplicate, resolve joins, build context (~100-200ms)
    ↓ minimal schema context
Step 6: QUERY — Cortex Analyst generates SQL (~1-2s)
    ↓ SQL statement
Step 7: EXECUTE — run SQL, return results, log usage
```

## Step 4: Search

### Single Domain Search

```python
from snowflake.core import Root

root = Root(session)
css = root.databases["{DOMAIN}_META"].schemas["META"].cortex_search_services["{DOMAIN}_SEARCH"]

results = css.search(
    query=user_question,
    columns=[
        "concept_name", "concept_level", "domain",
        "source_database", "source_schema",
        "tables_yaml", "join_keys_yaml", "metrics_yaml",
        "sample_values", "is_enum", "search_content"
    ],
    filter={"@eq": {"concept_level": "table"}},  # table-level for SQL generation
    limit=10
)
```

### Exploration Search (All Levels)

For "what data do we have about X?" questions, search all concept levels:

```python
results = css.search(
    query=user_question,
    columns=["concept_name", "concept_level", "domain", "search_content", "description"],
    limit=15  # no concept_level filter — returns DB, schema, and table concepts
)
```

### Cross-Domain Search (Master KG)

```python
master_css = root.databases["MASTER_META"].schemas["META"].cortex_search_services["MASTER_SEARCH"]

results = master_css.search(
    query=user_question,
    columns=["concept_name", "concept_level", "domain", "tables_yaml"],
    filter={"@eq": {"concept_level": "table"}},
    limit=15
)

# Group results by domain
domains_found = set(r["domain"] for r in results)
```

## Step 5: Assemble

See `query-schema-assembly.md` for detailed assembly logic.

Quick version:
1. Extract unique table FQNs from concept rows
2. Check RELATIONSHIPS for join paths between tables
3. Build minimal column set (only relevant columns + join keys)
4. Format as schema context

## Step 6: Query — Two Approaches

### Approach A: Prompt-Based (Simpler)

Inject assembled schema context directly into an AI_COMPLETE prompt:

```sql
SELECT SNOWFLAKE.CORTEX.AI_COMPLETE(
  'claude-3-5-sonnet',
  CONCAT(
    'You are a SQL expert. Generate a Snowflake SQL query to answer the user''s question.\n\n',
    '## Available Tables\n\n', :assembled_schema_yaml, '\n\n',
    '## Join Paths\n\n', :join_paths_yaml, '\n\n',
    '## Rules\n',
    '- Use only the tables and columns listed above\n',
    '- Use fully qualified table names (DB.SCHEMA.TABLE)\n',
    '- Return only the SQL, no explanation\n',
    '- Use appropriate aggregations and GROUP BY\n\n',
    '## Question\n', :user_question
  )
);
```

**Pros:** Fast, simple, no DDL required
**Cons:** Less structured, no verified queries, no Cortex Analyst features

### Approach B: Ephemeral Semantic View (More Structured)

Create a temporary SV from assembled context, then route through Cortex Analyst:

```sql
CREATE OR REPLACE SEMANTIC VIEW {DOMAIN}_META.META.EPHEMERAL_SV
  TABLES (
    {assembled_table_definitions}
  )
  RELATIONSHIPS (
    {assembled_relationships}
  );
```

Then use Cortex Analyst API:

```python
from snowflake.cortex import analyst

response = analyst.ask(
    semantic_view="{DOMAIN}_META.META.EPHEMERAL_SV",
    question=user_question
)
```

**Pros:** Leverages Cortex Analyst's SQL generation, verified query support
**Cons:** Requires DDL (CREATE SV), slightly slower

### Choosing an Approach

| Factor | Prompt-Based | Ephemeral SV |
|--------|-------------|-------------|
| Speed | Faster (~1s) | Slower (~2s with DDL) |
| SQL quality | Good | Better (Cortex Analyst) |
| Setup | None | CREATE SV required |
| Best for | Ad-hoc exploration | Repeated patterns |
| Graduation path | Manual | Can save as curated SV |

## Step 7: Execute & Log

```sql
-- Execute the generated SQL
-- (handled by the caller)

-- Log the query for feedback loop
INSERT INTO {DOMAIN}_META.META.QUERY_LOG (
  question,
  concepts_used,     -- array of concept_ids from search results
  tables_used,       -- array of table FQNs
  sql_generated,     -- the SQL from Step 6
  approach,          -- 'prompt' or 'ephemeral_sv'
  row_count,         -- result count
  execution_time_ms,
  user_name,
  timestamp
)
VALUES (
  :user_question,
  :concept_ids::VARIANT,
  :table_fqns::VARIANT,
  :generated_sql,
  :approach,
  :result_row_count,
  :exec_ms,
  CURRENT_USER(),
  CURRENT_TIMESTAMP()
);
```

## Handling "No Results" / Poor Results

If search returns no relevant concepts:

1. Try broader search (remove concept_level filter)
2. Try master KG (cross-domain)
3. If still nothing: suggest running DISCOVER or onboarding the relevant data source
4. If concepts found but SQL fails: check assembly logic, verify join paths

## Graduation to Curated SV

When a query pattern is used repeatedly (tracked in QUERY_LOG):

```sql
-- Find repeated query patterns (same tables_used, similar questions)
SELECT
  tables_used,
  COUNT(*) AS query_count,
  ARRAY_AGG(DISTINCT question) AS sample_questions
FROM {DOMAIN}_META.META.QUERY_LOG
WHERE timestamp >= DATEADD('day', -30, CURRENT_TIMESTAMP())
GROUP BY tables_used
HAVING COUNT(*) >= 5
ORDER BY query_count DESC;
```

These are candidates for promotion to a curated Semantic View with verified queries.
