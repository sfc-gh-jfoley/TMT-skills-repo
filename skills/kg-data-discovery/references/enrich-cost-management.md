# Enrichment Cost Management

Cost math, budgeting, daily caps, and monitoring AI spend.

## Cost Per Operation

| Operation | AI Function | Approx Cost | When Used |
|-----------|------------|-------------|-----------|
| Column role classification | AI_CLASSIFY | ~$0.001/call | Ambiguous columns only |
| Table purpose extraction | AI_EXTRACT | ~$0.01/call | Undocumented tables only |
| VARIANT interpretation | AI_COMPLETE | ~$0.02-0.10/call | VARIANT columns only |
| Cross-DB relationship | AI_COMPLETE | ~$0.05/call | Cross-database inference |
| Concept synthesis | AI_COMPLETE | ~$0.05-0.10/call | Higher-order concepts |

## Cost Estimation Formula

Before enrichment, estimate total cost:

```sql
-- Count what needs each tier
WITH enrichment_needs AS (
  SELECT
    -- Tier 0 candidates (free)
    SUM(CASE WHEN comment IS NOT NULL AND comment != '' THEN 1 ELSE 0 END) AS documented_tables,
    -- Tier 1 candidates (AI_CLASSIFY)
    SUM(CASE
      WHEN (comment IS NULL OR comment = '')
      AND columns_json IS NOT NULL
      THEN (SELECT COUNT(*) FROM TABLE(FLATTEN(input => columns_json)) c
            WHERE c.value:name::VARCHAR NOT REGEXP '.*_(ID|KEY|DATE|TIME|AMOUNT|TOTAL|NAME|TYPE|STATUS|FLAG)$')
      ELSE 0
    END) AS ambiguous_columns,
    -- Tier 2 candidates (AI_EXTRACT)
    SUM(CASE WHEN (comment IS NULL OR comment = '') THEN 1 ELSE 0 END) AS undocumented_tables,
    -- Tier 3 candidates (AI_COMPLETE)
    SUM(CASE WHEN columns_json::VARCHAR LIKE '%VARIANT%' THEN 1 ELSE 0 END) AS variant_tables
  FROM {DOMAIN}_META.META.RAW_CONCEPTS
  WHERE concept_level = 'table'
)
SELECT
  documented_tables AS tier_0_free,
  ambiguous_columns * 0.001 AS tier_1_est_credits,
  undocumented_tables * 0.01 AS tier_2_est_credits,
  variant_tables * 0.05 AS tier_3_est_credits,
  (ambiguous_columns * 0.001 + undocumented_tables * 0.01 + variant_tables * 0.05) AS total_est_credits
FROM enrichment_needs;
```

## Cost Caps

Set in DOMAIN_CONFIG:

```sql
INSERT INTO {DOMAIN}_META.META.DOMAIN_CONFIG VALUES
  ('enrichment_max_tier', '2'),                  -- max tier to use (0-3)
  ('enrichment_daily_budget_credits', '5.0'),    -- daily credit limit
  ('enrichment_batch_size', '20'),               -- tables per batch
  ('enrichment_pause_on_budget', 'true');         -- stop if budget hit
```

## Monitoring Spend

Track enrichment credits:

```sql
CREATE TABLE IF NOT EXISTS {DOMAIN}_META.META.ENRICHMENT_LOG (
  log_id VARCHAR DEFAULT UUID_STRING(),
  concept_id VARCHAR,
  tier NUMBER,
  ai_function VARCHAR,
  input_tokens NUMBER,
  output_tokens NUMBER,
  estimated_credits NUMBER(10,6),
  timestamp TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);

-- Daily spend summary
SELECT
  DATE_TRUNC('day', timestamp) AS day,
  tier,
  COUNT(*) AS calls,
  SUM(estimated_credits) AS credits
FROM {DOMAIN}_META.META.ENRICHMENT_LOG
GROUP BY 1, 2
ORDER BY 1 DESC, 2;

-- Running total vs budget
SELECT
  SUM(estimated_credits) AS total_today,
  (SELECT config_value::NUMBER FROM {DOMAIN}_META.META.DOMAIN_CONFIG WHERE config_key = 'enrichment_daily_budget_credits') AS budget,
  total_today / budget * 100 AS pct_used
FROM {DOMAIN}_META.META.ENRICHMENT_LOG
WHERE DATE_TRUNC('day', timestamp) = CURRENT_DATE();
```

## Cost Optimization Strategies

1. **Skip documented tables** — If COMMENT exists and is meaningful, Tier 0 is sufficient
2. **Skip obvious columns** — _ID, _DATE, _AMOUNT patterns don't need AI
3. **Batch AI calls** — Combine multiple column classifications into one AI_CLASSIFY call
4. **Delta-only enrichment** — Only re-enrich when metadata hash changes
5. **Start low, escalate** — Begin at Tier 0-1, only escalate to Tier 2-3 for tables that fail quality threshold
6. **Sample before full** — Test enrichment on 10 tables before running full domain

## Budget Alert

```sql
-- Check if approaching daily budget
CREATE OR REPLACE PROCEDURE {DOMAIN}_META.META.CHECK_ENRICHMENT_BUDGET()
RETURNS VARCHAR
LANGUAGE SQL
AS
$$
DECLARE
  spent FLOAT;
  budget FLOAT;
BEGIN
  SELECT SUM(estimated_credits) INTO :spent
  FROM IDENTIFIER('{DOMAIN}_META.META.ENRICHMENT_LOG')
  WHERE DATE_TRUNC('day', timestamp) = CURRENT_DATE();
  
  SELECT config_value::FLOAT INTO :budget
  FROM IDENTIFIER('{DOMAIN}_META.META.DOMAIN_CONFIG')
  WHERE config_key = 'enrichment_daily_budget_credits';
  
  IF (:spent >= :budget * 0.8) THEN
    RETURN 'WARNING: ' || :spent || ' / ' || :budget || ' credits used today (' || ROUND(:spent / :budget * 100) || '%)';
  ELSE
    RETURN 'OK: ' || COALESCE(:spent, 0) || ' / ' || :budget || ' credits used today';
  END IF;
END;
$$;
```

## Typical Cost Scenarios

| Scenario | Tables | Documented | VARIANT | Est. Cost |
|----------|--------|-----------|---------|-----------|
| dbt mart (well-documented) | 50 | 45 (90%) | 0 | ~$0.10 |
| Operational replica | 100 | 20 (20%) | 5 | ~$1.50 |
| Raw data lake | 200 | 0 (0%) | 50 | ~$5.00 |
| Marketplace share | 30 | 5 (17%) | 2 | ~$0.50 |
| Mixed enterprise | 500 | 150 (30%) | 20 | ~$5.50 |

**Present cost estimate to user BEFORE running enrichment.**
