# Schema Assembly

Fragment deduplication, join resolution, and minimal context construction from search results.

## Input

Search results: array of concept rows, each containing:
- `concept_name`, `concept_level`, `domain`
- `tables_yaml` — table FQN + column definitions
- `join_keys_yaml` — relationship info
- `metrics_yaml` — aggregation definitions
- `sample_values`, `is_enum`

## Assembly Pipeline

### 1. Extract Unique Tables

Parse tables_yaml from all concept rows, deduplicate by FQN:

```python
import yaml

def extract_tables(search_results):
    tables = {}
    for result in search_results:
        if result.get("tables_yaml"):
            parsed = yaml.safe_load(result["tables_yaml"])
            if isinstance(parsed, list):
                for table_def in parsed:
                    fqn = table_def["name"]
                    if fqn not in tables:
                        tables[fqn] = table_def
                    else:
                        # Merge columns (union of both definitions)
                        existing_cols = {c["name"] for c in tables[fqn].get("columns", [])}
                        for col in table_def.get("columns", []):
                            if col["name"] not in existing_cols:
                                tables[fqn]["columns"].append(col)
    return tables
```

### 2. Resolve Join Paths

For each pair of tables, find the best join path:

```python
def resolve_joins(table_fqns, session, domain_meta_db):
    relationships = session.sql(f"""
        SELECT source_table, source_column, target_table, target_column,
               relationship_type, confidence
        FROM {domain_meta_db}.META.RELATIONSHIPS
        WHERE is_active = TRUE
          AND source_table IN ({','.join(f"'{t}'" for t in table_fqns)})
          AND target_table IN ({','.join(f"'{t}'" for t in table_fqns)})
        ORDER BY confidence DESC
    """).collect()
    
    joins = []
    for rel in relationships:
        joins.append({
            "left_table": rel["SOURCE_TABLE"],
            "right_table": rel["TARGET_TABLE"],
            "on": f"{rel['SOURCE_TABLE']}.{rel['SOURCE_COLUMN']} = {rel['TARGET_TABLE']}.{rel['TARGET_COLUMN']}",
            "type": rel["RELATIONSHIP_TYPE"],
            "confidence": float(rel["CONFIDENCE"])
        })
    return joins
```

### 3. Prune Columns

Keep only columns that are relevant to the question + join keys:

```python
def prune_columns(tables, joins, max_columns_per_table=20):
    join_columns = set()
    for j in joins:
        parts = j["on"].split(" = ")
        for p in parts:
            join_columns.add(p.strip())
    
    for fqn, table_def in tables.items():
        cols = table_def.get("columns", [])
        if len(cols) > max_columns_per_table:
            # Keep: keys, join columns, metrics, timestamps
            priority_roles = {"key", "metric", "timestamp"}
            kept = []
            for col in cols:
                col_fqn = f"{fqn}.{col['name']}"
                if col.get("role") in priority_roles or col_fqn in join_columns:
                    kept.append(col)
            # Fill remaining slots with dimensions
            remaining = max_columns_per_table - len(kept)
            for col in cols:
                if col not in kept and remaining > 0:
                    kept.append(col)
                    remaining -= 1
            table_def["columns"] = kept
    return tables
```

### 4. Format as Schema Context

#### For Prompt-Based Approach

```python
def format_for_prompt(tables, joins):
    lines = ["## Tables\n"]
    for fqn, tdef in tables.items():
        lines.append(f"### {fqn}")
        if tdef.get("description"):
            lines.append(f"Description: {tdef['description']}")
        lines.append("Columns:")
        for col in tdef.get("columns", []):
            parts = [f"  - {col['name']} ({col.get('data_type', 'VARCHAR')})"]
            if col.get("role"):
                parts.append(f"[{col['role']}]")
            if col.get("description"):
                parts.append(f"-- {col['description']}")
            lines.append(" ".join(parts))
        lines.append("")
    
    if joins:
        lines.append("## Join Paths\n")
        for j in joins:
            lines.append(f"- {j['on']} ({j['type']}, confidence: {j['confidence']})")
    
    return "\n".join(lines)
```

#### For Ephemeral SV Approach

```python
def format_for_sv(tables, joins, domain):
    sv_tables = []
    for fqn, tdef in tables.items():
        db, schema, table = fqn.split(".")
        cols = []
        for col in tdef.get("columns", []):
            col_def = f'    {col["name"]} {col.get("data_type", "VARCHAR")}'
            cols.append(col_def)
        sv_tables.append(f"  {fqn} (\n" + ",\n".join(cols) + "\n  )")
    
    relationships = []
    for j in joins:
        relationships.append(f"  {j['on']}")
    
    sv_sql = f"CREATE OR REPLACE SEMANTIC VIEW {domain}_META.META.EPHEMERAL_SV\n"
    sv_sql += "TABLES (\n" + ",\n".join(sv_tables) + "\n)\n"
    if relationships:
        sv_sql += "RELATIONSHIPS (\n" + ",\n".join(relationships) + "\n)"
    
    return sv_sql
```

## Assembly Quality Checks

Before routing to Cortex Analyst:

1. **At least 1 table** — If zero tables extracted, search returned no table-level concepts
2. **Join paths exist** — If multiple tables but no joins, warn user about potential Cartesian product
3. **Metric columns present** — If question asks for numbers but no metric columns, quality may be low
4. **Column count reasonable** — If total columns > 50, prune more aggressively
5. **FQNs valid** — Verify table FQNs exist (optional, adds latency)

## Caching

For repeated query patterns, cache assembled contexts:

```sql
CREATE TABLE IF NOT EXISTS {DOMAIN}_META.META.ASSEMBLY_CACHE (
  cache_key VARCHAR,           -- hash of sorted table FQNs
  tables_context VARCHAR,      -- assembled YAML
  joins_context VARCHAR,       -- join paths
  created_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
  hit_count NUMBER DEFAULT 0,
  PRIMARY KEY (cache_key)
);
```

Cache hit: skip assembly, reuse stored context. Invalidate when CONCEPTS or RELATIONSHIPS change.
