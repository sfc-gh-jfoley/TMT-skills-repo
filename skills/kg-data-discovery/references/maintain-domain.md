# Maintain Domain

Delta refresh, schema drift detection, and stale concept cleanup.

## Refresh Types

| Type | When | What Changes |
|------|------|-------------|
| **Delta refresh** | Scheduled (daily/hourly) | New tables, altered tables, dropped tables |
| **Full re-crawl** | On demand | Complete re-harvest of all metadata |
| **Targeted re-enrich** | After drift detection | Re-enrich specific concepts with updated metadata |

## Delta Refresh Workflow

### 1. Detect Changes

```sql
-- New tables (exist in source but not in RAW_CONCEPTS)
SELECT t.table_catalog, t.table_schema, t.table_name
FROM {DB}.INFORMATION_SCHEMA.TABLES t
LEFT JOIN {DOMAIN}_META.META.RAW_CONCEPTS rc
  ON rc.source_database = t.table_catalog
  AND rc.source_schema = t.table_schema
  AND rc.source_table = t.table_name
  AND rc.concept_level = 'table'
WHERE rc.concept_id IS NULL
  AND t.table_schema NOT IN ('INFORMATION_SCHEMA');

-- Altered tables (metadata hash changed)
SELECT
  rc.concept_id,
  rc.source_database || '.' || rc.source_schema || '.' || rc.source_table AS fqn,
  rc.metadata_hash AS old_hash,
  MD5(t.table_catalog || '.' || t.table_schema || '.' || t.table_name || t.row_count::VARCHAR || COALESCE(t.last_altered::VARCHAR, '')) AS new_hash
FROM {DOMAIN}_META.META.RAW_CONCEPTS rc
JOIN {DB}.INFORMATION_SCHEMA.TABLES t
  ON rc.source_database = t.table_catalog
  AND rc.source_schema = t.table_schema
  AND rc.source_table = t.table_name
WHERE rc.concept_level = 'table'
  AND rc.metadata_hash != MD5(t.table_catalog || '.' || t.table_schema || '.' || t.table_name || t.row_count::VARCHAR || COALESCE(t.last_altered::VARCHAR, ''));

-- Dropped tables (in RAW_CONCEPTS but not in source)
SELECT rc.concept_id, rc.source_database, rc.source_schema, rc.source_table
FROM {DOMAIN}_META.META.RAW_CONCEPTS rc
LEFT JOIN {DB}.INFORMATION_SCHEMA.TABLES t
  ON rc.source_database = t.table_catalog
  AND rc.source_schema = t.table_schema
  AND rc.source_table = t.table_name
WHERE t.table_name IS NULL
  AND rc.concept_level = 'table';
```

### 2. Process Changes

**New tables:**
1. Insert into RAW_CONCEPTS (crawl)
2. Enrich (Tier 0 at minimum, higher if budget allows)
3. Insert into CONCEPTS
4. Update OBJECT_STATE → KNOWN_CURRENT

**Altered tables:**
1. Re-crawl metadata into RAW_CONCEPTS (update row)
2. Delta-enrich only changed columns/metadata
3. Update CONCEPTS row
4. Update OBJECT_STATE → KNOWN_CURRENT (reset hash)
5. Log drift in OBJECT_STATE.drift_details

**Dropped tables:**
1. Mark CONCEPTS.is_active = FALSE
2. Update OBJECT_STATE → KNOWN_DELETED

```sql
-- Mark dropped concepts inactive
UPDATE {DOMAIN}_META.META.CONCEPTS
SET is_active = FALSE, object_state = 'KNOWN_DELETED', updated_at = CURRENT_TIMESTAMP()
WHERE concept_id IN (:dropped_concept_ids);

UPDATE {DOMAIN}_META.META.OBJECT_STATE
SET object_state = 'KNOWN_DELETED', updated_at = CURRENT_TIMESTAMP()
WHERE concept_id IN (:dropped_concept_ids);
```

### 3. CSS Auto-Refresh

The CSS refreshes automatically based on TARGET_LAG. After updating the CONCEPTS table, the CSS will pick up changes within the configured lag window.

To force immediate refresh:
```sql
ALTER CORTEX SEARCH SERVICE {DOMAIN}_META.META.{DOMAIN}_SEARCH RESUME;
```

## Scheduled Refresh Task

```sql
CREATE OR REPLACE TASK {DOMAIN}_META.META.REFRESH_DOMAIN_TASK
  WAREHOUSE = COMPUTE_WH
  SCHEDULE = 'USING CRON 0 6 * * * America/New_York'
AS
  CALL {DOMAIN}_META.META.REFRESH_DOMAIN();

ALTER TASK {DOMAIN}_META.META.REFRESH_DOMAIN_TASK RESUME;
```

## Stale Concept Cleanup

Periodically review concepts that haven't been accessed or updated:

```sql
-- Concepts not used in queries (90+ days)
SELECT c.concept_id, c.concept_name, c.source_table, c.updated_at
FROM {DOMAIN}_META.META.CONCEPTS c
LEFT JOIN {DOMAIN}_META.META.QUERY_LOG ql
  ON ARRAY_CONTAINS(c.concept_id::VARIANT, PARSE_JSON(ql.concepts_used))
  AND ql.timestamp >= DATEADD('day', -90, CURRENT_TIMESTAMP())
WHERE ql.query_id IS NULL
  AND c.is_active = TRUE;

-- Consider: archive (is_active = FALSE) or delete
```

## Health Check

Quick domain health assessment:

```sql
SELECT
  'Total concepts' AS metric, COUNT(*) AS value FROM {DOMAIN}_META.META.CONCEPTS WHERE is_active = TRUE
UNION ALL
SELECT 'Avg quality score', ROUND(AVG(enrichment_quality_score), 2) FROM {DOMAIN}_META.META.CONCEPTS WHERE is_active = TRUE
UNION ALL
SELECT 'Concepts needing re-enrich', COUNT(*) FROM {DOMAIN}_META.META.CONCEPTS WHERE enrichment_quality_score < 0.5 AND is_active = TRUE
UNION ALL
SELECT 'Shadow objects', COUNT(*) FROM {DOMAIN}_META.META.OBJECT_STATE WHERE object_state LIKE 'SHADOW%'
UNION ALL
SELECT 'Drifted objects', COUNT(*) FROM {DOMAIN}_META.META.OBJECT_STATE WHERE object_state = 'KNOWN_DRIFTED'
UNION ALL
SELECT 'Last refresh', MAX(updated_at)::VARCHAR FROM {DOMAIN}_META.META.CONCEPTS;
```
