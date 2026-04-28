---
name: vqr-semantic-view-generator
description: "Generate Semantic View YAML files from VQR/SQL query analysis grouped by domain. Requires sql-table-extractor output (extracted tables JSON) as mandatory input — run sql-table-extractor first. Use for: creating semantic views from extracted tables, building domain-specific semantic models, converting query manifests to semantic views. Triggers: generate semantic view from queries, create semantic model by domain, VQR to semantic view. For HOL/pure-SQL single semantic view creation, use semantic-view-ddl instead."
---

# VQR Semantic View Generator

Generate Snowflake Semantic View YAML files from extracted table/column manifests, grouped by domain.

## Prerequisites

- Output from `sql-table-extractor` (JSON with tables/columns by query)
- Original source CSV with SQL queries (for metrics + verified queries)
- Access to Snowflake to fetch actual table schemas (**REQUIRED**)

## Workflow

### Step 1: Analyze Domains

```bash
uv run --project <SKILL_DIR> python <SKILL_DIR>/scripts/generate_semantic_views.py \
  --input <EXTRACTED_TABLES_JSON> \
  --action analyze
```

Displays domains, table counts, and shared tables.

**⚠️ STOP**: Confirm domains look correct.

### Step 2: Fetch Live Schemas (REQUIRED)

```bash
uv run --project <SKILL_DIR> python <SKILL_DIR>/scripts/generate_semantic_views.py \
  --input <EXTRACTED_TABLES_JSON> \
  --action fetch-schemas \
  --output schemas.json
```

If `--connection` is not provided, the script will **prompt interactively** for a Snowflake connection name.
You can also set the `SNOWFLAKE_CONNECTION_NAME` environment variable.

This fetches actual column names and data types from Snowflake.
**Without this step, fact/dimension classification will be poor.**

### Step 3: Extract Metrics from Query History

```bash
uv run --project <SKILL_DIR> python <SKILL_DIR>/scripts/generate_semantic_views.py \
  --input <EXTRACTED_TABLES_JSON> \
  --action extract-metrics \
  --source-csv <ORIGINAL_QUERIES_CSV> \
  --output metrics.json
```

Parses SQL aggregations (SUM, COUNT, AVG, etc.) to derive metric definitions.
Groups by domain and deduplicates.

**⚠️ STOP**: Review extracted metrics.

### Step 4: Generate Semantic View YAMLs

```bash
uv run --project <SKILL_DIR> python <SKILL_DIR>/scripts/generate_semantic_views.py \
  --input <EXTRACTED_TABLES_JSON> \
  --action generate \
  --schemas schemas.json \
  --metrics metrics.json \
  --source-csv <ORIGINAL_QUERIES_CSV> \
  --output-dir <OUTPUT_DIR> \
  --view-prefix <PREFIX>
```

Generates per-domain YAML files with:
- Tables (dimensions, time_dimensions, facts from schema types)
- Metrics (from query aggregations)
- Relationships (inferred from matching keys)
- Verified Queries (actual SQL from source)

### Step 5: Review & Refine

Compare generated YAMLs to working examples. Check:
- [ ] All tables have real database/schema refs
- [ ] Facts identified correctly (numeric measures)
- [ ] Metrics have meaningful expressions
- [ ] Relationships use actual foreign keys
- [ ] Verified queries include real SQL

**⚠️ STOP**: Get approval before deploying.

### Step 6: Deploy to Snowflake (Optional)

```sql
CALL SYSTEM$CREATE_SEMANTIC_VIEW_FROM_YAML(
  '<database>.<schema>.<view_name>',
  '<yaml_content>'
);
```

## Tools

### generate_semantic_views.py

**Actions:**
| Action | Description | Required Args |
|--------|-------------|---------------|
| `analyze` | Show domain/table distribution | `--input` |
| `fetch-schemas` | Get live columns from Snowflake | `--input` (prompts for connection) |
| `extract-metrics` | Parse aggregations from SQL | `--input`, `--source-csv` |
| `generate` | Create YAML files | `--input`, `--schemas` |

**Full Example:**
```bash
SKILL_DIR=".cortex/skills/vqr-semantic-view-generator"

# Step 1: Analyze
uv run --project $SKILL_DIR python $SKILL_DIR/scripts/generate_semantic_views.py \
  -i extracted.json -a analyze

# Step 2: Fetch schemas
uv run --project $SKILL_DIR python $SKILL_DIR/scripts/generate_semantic_views.py \
  -i extracted.json -a fetch-schemas -c my_connection -o schemas.json

# Step 3: Extract metrics
uv run --project $SKILL_DIR python $SKILL_DIR/scripts/generate_semantic_views.py \
  -i extracted.json -a extract-metrics --source-csv queries.csv -o metrics.json

# Step 4: Generate
uv run --project $SKILL_DIR python $SKILL_DIR/scripts/generate_semantic_views.py \
  -i extracted.json -a generate -s schemas.json -m metrics.json \
  --source-csv queries.csv -o semantic_views/ --view-prefix my_company
```

## Stopping Points

- ✋ Step 1: Confirm domain analysis
- ✋ Step 3: Review extracted metrics
- ✋ Step 5: Review generated YAMLs before deploy

## Output

Per-domain Semantic View YAML files with:
- `tables[]` - logical tables with dimensions, time_dimensions, facts, metrics
- `relationships[]` - inferred from schema key matches
- `verified_queries[]` - actual SQL from source VQRs
