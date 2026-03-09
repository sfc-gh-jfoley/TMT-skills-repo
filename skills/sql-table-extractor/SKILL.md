---
name: sql-table-extractor
description: "Extract tables and columns from SQL queries. Use for: analyzing SQL files, building table lineage, discovering schema usage, VQR analysis, semantic model preparation. Triggers: extract tables from SQL, find tables in queries, SQL lineage, table dependencies, analyze queries."
---

# SQL Table Extractor

Extract tables and columns referenced in SQL queries, with support for Snowflake-specific syntax.

## Features

- **Auto-detect input**: Pass a file or directory, format is detected automatically
- **Multi-file support**: Process all CSV/JSON/SQL files in a directory
- Snowflake double-dot notation: `database..table` → `database.PUBLIC.table`
- Skip DML/DDL operations (UPDATE, DELETE, INSERT, CREATE TABLE, DROP, etc.)
- Remove SQL comments (`--`, `/* */`, `//`)
- Extract from FROM/JOIN clauses
- Output per-query and consolidated results

## Workflow

### Step 1: Run Extraction

```bash
uv run --project <SKILL_DIR> python <SKILL_DIR>/scripts/extract_tables.py \
  --input <INPUT_PATH> \
  --output <OUTPUT_PATH>
```

**Input can be:**
- A directory (processes all .csv, .json, .sql files)
- A single CSV file (looks for SQL column)
- A single JSON file
- A single SQL file

**Parameters:**
- `--input`: Path to input file or directory
- `--sql-column`: Column containing SQL (for CSV, default: "SQL")
- `--output`: Output JSON path (default: extracted_tables.json)

### Step 2: Review Results

Summary shows:
- Total queries processed
- Queries skipped (DML/DDL)
- Unique tables found
- Tables by category (DIM_*, FCT_*, other)

## Example

```bash
# Process all files in input/vqrs/
uv run --project .cortex/skills/sql-table-extractor \
  python .cortex/skills/sql-table-extractor/scripts/extract_tables.py \
  --input input/vqrs/ \
  --output output/extracted.json
```

## Output

```json
{
  "summary": {
    "total_queries": 146,
    "processed": 144,
    "skipped": 2,
    "unique_tables": 123
  },
  "queries": [...],
  "consolidated": {
    "dimension_tables": {"DIM_*": {...}},
    "fact_tables": {"FCT_*": {...}},
    "other_tables": {...}
  }
}
```
