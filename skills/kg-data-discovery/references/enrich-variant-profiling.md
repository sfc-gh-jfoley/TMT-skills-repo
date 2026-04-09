# VARIANT Profiling

Deep enrichment for VARIANT/semi-structured columns (JSON, Parquet, nested data).

## When to Use

- Tables with VARIANT, OBJECT, or ARRAY columns
- JSON payloads stored as raw strings
- Deeply nested data (event streams, API responses, IoT telemetry)
- Tables loaded from Parquet/Avro/ORC without schema inference

## Detection

```sql
-- Find all VARIANT columns in domain
SELECT
  table_catalog || '.' || table_schema || '.' || table_name AS table_fqn,
  column_name,
  data_type
FROM {DB}.INFORMATION_SCHEMA.COLUMNS
WHERE data_type IN ('VARIANT', 'OBJECT', 'ARRAY')
  AND table_schema NOT IN ('INFORMATION_SCHEMA');
```

## Path Extraction

### Method 1: FLATTEN + Sampling (Free)

```sql
-- Extract top-level keys from VARIANT column
SELECT DISTINCT
  f.key AS path_key,
  TYPEOF(f.value) AS value_type,
  COUNT(*) AS occurrence_count
FROM {TABLE} t,
  LATERAL FLATTEN(input => t.{VARIANT_COL}, RECURSIVE => FALSE) f
WHERE t.{VARIANT_COL} IS NOT NULL
SAMPLE (1000 ROWS)
GROUP BY 1, 2
ORDER BY occurrence_count DESC;

-- Extract nested paths (recursive)
SELECT DISTINCT
  f.path AS full_path,
  f.key AS leaf_key,
  TYPEOF(f.value) AS value_type,
  COUNT(*) AS occurrence_count
FROM {TABLE} t,
  LATERAL FLATTEN(input => t.{VARIANT_COL}, RECURSIVE => TRUE) f
WHERE t.{VARIANT_COL} IS NOT NULL
SAMPLE (1000 ROWS)
GROUP BY 1, 2, 3
ORDER BY occurrence_count DESC
LIMIT 100;
```

### Method 2: INFER_SCHEMA (Free, for staged files)

```sql
-- For data still on stage
SELECT *
FROM TABLE(INFER_SCHEMA(
  LOCATION => '@{STAGE}/{PATH}',
  FILE_FORMAT => '{FILE_FORMAT}',
  FILES => '{FILE_NAME}'
));
```

### Method 3: AI_COMPLETE Interpretation (Tier 3)

For complex nested structures where FLATTEN output is hard to interpret:

```sql
SELECT SNOWFLAKE.CORTEX.AI_COMPLETE(
  'claude-3-5-sonnet',
  CONCAT(
    'Analyze this VARIANT column structure and describe:\n',
    '1. What business entity does each top-level key represent?\n',
    '2. Which paths contain metrics vs dimensions?\n',
    '3. Suggest column aliases for the most useful paths.\n\n',
    'Table: ', :table_fqn, '\n',
    'Column: ', :variant_col, '\n',
    'Schema (from FLATTEN):\n', :flatten_output, '\n',
    'Sample values (3 rows):\n', :sample_values
  )
);
```

## Enrichment Strategy for VARIANT Tables

1. **FLATTEN first** (free) — Get path inventory
2. **Classify paths** — Use Tier 0 heuristics on path names
3. **AI interpret** (Tier 3, if needed) — For cryptic path names
4. **Generate column definitions** — Map paths to virtual columns for the concept

## Concept Row for VARIANT Tables

The tables_yaml should include VARIANT paths as virtual columns:

```yaml
- name: IOT_DB.EVENTS.DEVICE_TELEMETRY
  description: IoT device telemetry events with nested sensor readings
  columns:
    - name: EVENT_ID
      data_type: VARCHAR
      role: key
    - name: DEVICE_ID
      data_type: VARCHAR
      role: dimension
    - name: EVENT_TIMESTAMP
      data_type: TIMESTAMP
      role: timestamp
    - name: PAYLOAD:temperature::FLOAT
      data_type: FLOAT
      role: metric
      description: Device temperature reading in Celsius
      alias: temperature
    - name: PAYLOAD:battery_level::INTEGER
      data_type: INTEGER
      role: metric
      description: Battery percentage
      alias: battery_level
    - name: PAYLOAD:location.latitude::FLOAT
      data_type: FLOAT
      role: dimension
      description: Device latitude
      alias: latitude
    - name: PAYLOAD:location.longitude::FLOAT
      data_type: FLOAT
      role: dimension
      description: Device longitude
      alias: longitude
    - name: PAYLOAD:sensor_type::VARCHAR
      data_type: VARCHAR
      role: dimension
      description: Type of sensor
      sample_values: ["temperature", "humidity", "pressure", "motion"]
      is_enum: true
```

## Common VARIANT Patterns

| Pattern | Structure | Approach |
|---------|-----------|----------|
| Flat JSON | `{"key": "value", ...}` | FLATTEN non-recursive, straightforward |
| Nested objects | `{"user": {"name": "...", "address": {...}}}` | FLATTEN recursive, dot-path notation |
| Arrays of objects | `[{"id": 1, ...}, {"id": 2, ...}]` | FLATTEN on array, then access object keys |
| Mixed types | Same path has different types across rows | TYPEOF check, handle with TRY_CAST |
| Sparse keys | Keys present in some rows, absent in others | Track occurrence_count, flag sparse paths |

## Quality Considerations

- VARIANT columns with > 50 unique top-level keys may produce too many virtual columns — filter to most-accessed paths using QUERY_HISTORY
- Deeply nested paths (depth > 3) are often not useful for analytics — sample before including
- Sparse keys (< 10% occurrence) should be excluded unless specifically requested
