# KG Optimization

Query logging, concept usage feedback loops, auto-promotion to curated SVs, and self-improving KG.

## Feedback Loop Architecture

```
User Question → Search → Assemble → Query → Execute → Results
                  ↓                              ↓
              concept_ids                    row_count, exec_time
                  ↓                              ↓
              QUERY_LOG ←────────────────────────┘
                  ↓
              Analysis (scheduled)
                  ↓
              ┌────────────────────┐
              │ Optimize concepts  │ — improve low-performing concepts
              │ Promote to SV      │ — graduate frequent patterns
              │ Retire unused      │ — deactivate stale concepts
              │ Expand coverage    │ — identify gaps
              └────────────────────┘
```

## QUERY_LOG Table

```sql
CREATE TABLE IF NOT EXISTS {DOMAIN}_META.META.QUERY_LOG (
  query_id VARCHAR DEFAULT UUID_STRING(),
  question VARCHAR NOT NULL,
  concepts_used VARIANT,           -- array of concept_ids
  tables_used VARIANT,             -- array of table FQNs
  sql_generated VARCHAR,
  approach VARCHAR,                -- 'prompt' or 'ephemeral_sv'
  execution_status VARCHAR,        -- 'success', 'error', 'no_results'
  row_count NUMBER,
  execution_time_ms NUMBER,
  user_name VARCHAR DEFAULT CURRENT_USER(),
  user_feedback VARCHAR,           -- 'helpful', 'unhelpful', NULL
  error_message VARCHAR,
  timestamp TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
  PRIMARY KEY (query_id)
);
```

## Analysis Queries

### Concept Usage Ranking

```sql
-- Most used concepts (last 30 days)
SELECT
  c.concept_id,
  c.concept_name,
  c.source_table,
  COUNT(DISTINCT ql.query_id) AS usage_count,
  AVG(CASE WHEN ql.execution_status = 'success' THEN 1 ELSE 0 END) AS success_rate,
  AVG(CASE WHEN ql.user_feedback = 'helpful' THEN 1
           WHEN ql.user_feedback = 'unhelpful' THEN 0
           ELSE NULL END) AS helpfulness_rate
FROM {DOMAIN}_META.META.CONCEPTS c
JOIN {DOMAIN}_META.META.QUERY_LOG ql
  ON ARRAY_CONTAINS(c.concept_id::VARIANT, ql.concepts_used)
WHERE ql.timestamp >= DATEADD('day', -30, CURRENT_TIMESTAMP())
GROUP BY 1, 2, 3
ORDER BY usage_count DESC;
```

### Failed Queries (Gap Analysis)

```sql
-- Questions that returned no results or errors
SELECT
  question,
  execution_status,
  error_message,
  COUNT(*) AS occurrence_count
FROM {DOMAIN}_META.META.QUERY_LOG
WHERE execution_status IN ('error', 'no_results')
  AND timestamp >= DATEADD('day', -30, CURRENT_TIMESTAMP())
GROUP BY 1, 2, 3
ORDER BY occurrence_count DESC
LIMIT 20;
```

These represent KG coverage gaps — questions the system couldn't answer.

### Concept Quality Correlation

```sql
-- Do higher quality concepts produce better results?
SELECT
  c.enrichment_quality_score,
  COUNT(DISTINCT ql.query_id) AS queries,
  AVG(CASE WHEN ql.execution_status = 'success' THEN 1 ELSE 0 END) AS success_rate
FROM {DOMAIN}_META.META.CONCEPTS c
JOIN {DOMAIN}_META.META.QUERY_LOG ql
  ON ARRAY_CONTAINS(c.concept_id::VARIANT, ql.concepts_used)
WHERE ql.timestamp >= DATEADD('day', -30, CURRENT_TIMESTAMP())
GROUP BY 1
ORDER BY 1;
```

### Graduation Candidates

```sql
-- Table combinations queried frequently — promote to curated SV
SELECT
  tables_used,
  COUNT(*) AS query_count,
  AVG(CASE WHEN execution_status = 'success' THEN 1 ELSE 0 END) AS success_rate,
  ARRAY_AGG(DISTINCT question) AS sample_questions
FROM {DOMAIN}_META.META.QUERY_LOG
WHERE timestamp >= DATEADD('day', -30, CURRENT_TIMESTAMP())
  AND execution_status = 'success'
GROUP BY tables_used
HAVING COUNT(*) >= 5
ORDER BY query_count DESC;
```

## Optimization Actions

### 1. Improve Low-Performing Concepts

If a concept has low success_rate or helpfulness_rate:

```sql
-- Find concepts with low success rate
SELECT concept_id, concept_name, success_rate
FROM concept_usage_ranking
WHERE usage_count >= 5 AND success_rate < 0.5;
```

Actions:
- Re-enrich at a higher tier
- Add more keywords
- Improve description
- Add sample values for literal matching
- Add missing join keys

### 2. Auto-Promote to Curated SV

When a table combination hits the graduation threshold:

1. Generate SV YAML from assembled context
2. Add verified queries from successful QUERY_LOG entries
3. Present to user for review
4. If approved, CREATE SEMANTIC VIEW

### 3. Retire Unused Concepts

```sql
-- Concepts never used in 90 days
SELECT c.concept_id, c.concept_name, c.source_table, c.updated_at
FROM {DOMAIN}_META.META.CONCEPTS c
LEFT JOIN {DOMAIN}_META.META.QUERY_LOG ql
  ON ARRAY_CONTAINS(c.concept_id::VARIANT, ql.concepts_used)
  AND ql.timestamp >= DATEADD('day', -90, CURRENT_TIMESTAMP())
WHERE ql.query_id IS NULL
  AND c.is_active = TRUE;

-- Consider: archive or re-enrich
```

### 4. Expand Coverage (Fill Gaps)

From failed query analysis:

1. Identify common question patterns that fail
2. Check if relevant tables exist but aren't onboarded
3. If tables exist: onboard them
4. If tables don't exist: report as data gap to user

## Scheduled Optimization Task

```sql
CREATE OR REPLACE TASK {DOMAIN}_META.META.OPTIMIZE_KG_TASK
  WAREHOUSE = COMPUTE_WH
  SCHEDULE = 'USING CRON 0 8 * * 1 America/New_York'  -- Weekly Monday 8am
AS
  CALL {DOMAIN}_META.META.ANALYZE_AND_OPTIMIZE();
```

The proc should:
1. Generate concept usage rankings
2. Flag low-performing concepts
3. Identify graduation candidates
4. Flag unused concepts
5. Identify coverage gaps
6. Store analysis in a OPTIMIZATION_REPORT table
7. Optionally send summary via notification integration
