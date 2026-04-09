# KG Data Discovery — Interfaces Contract

**This file is the single source of truth for all agents building procs.**
Read this before writing any proc. Do not deviate from signatures, table names, or constants defined here.

---

## Namespace

| Object | Location |
|--------|----------|
| All stored procs | `KG_CONTROL.PUBLIC` |
| Master tables | `KG_CONTROL.PUBLIC.{DOMAIN_REGISTRY, WIZARD_STATE, QUERY_LOG}` |
| Domain tables | `{DOMAIN}_META.META.{RAW_CONCEPTS, CONCEPTS, RELATIONSHIPS, OBJECT_STATE, DOMAIN_CONFIG, ASSEMBLY_CACHE, QUESTION_PLAN, SEMANTIC_PLAN, TRANSIENT_JOIN_GRAPH, TRANSIENT_METRIC_BINDINGS, TRANSIENT_SEMANTIC_SPEC}` |
| Cortex Search Service | `{DOMAIN}_META.META.{DOMAIN}_SEARCH` |

`{DOMAIN}` = uppercase domain name, e.g. `FINANCE`, `COMMERCE`, `TMO`

---

## Constants

### Object States (CONCEPTS.object_state, OBJECT_STATE.object_state)
```
KNOWN_CURRENT          -- in KG, exists, metadata current
KNOWN_DRIFTED          -- in KG, exists, column hash diverged
KNOWN_DELETED          -- in KG, object dropped from Snowflake
ONBOARDED_INCORRECTLY  -- in KG, exists, enrichment quality score < 0.3
SHADOW_ACTIVE          -- not in KG, exists, has recent ACCESS_HISTORY
SHADOW_INACTIVE        -- not in KG, exists, no ACCESS_HISTORY in N days
GRADUATED              -- in KG, domain has ontology layer (ontology_agent IS NOT NULL)
ONTOLOGY_DRIFT         -- graduated domain, but column hash diverged from ONT_CLASS_MAP
```

### Enrichment Tiers (CONCEPTS.enrichment_tier)
```
0  FREE        -- heuristics, column name patterns, comments
1  CLASSIFY    -- AI_CLASSIFY for ambiguous column roles
2  EXTRACT     -- AI_EXTRACT for undocumented table descriptions
3  COMPLETE    -- AI_COMPLETE for VARIANT paths, cross-DB relationship inference
```

### Enrichment Sources (CONCEPTS.enrichment_source)
```
HEURISTIC     -- free tier: pattern matching
AI_CLASSIFY   -- Tier 1
AI_EXTRACT    -- Tier 2
AI_COMPLETE   -- Tier 3
ONT_CLASS     -- free: read from graduated domain's ONT_CLASS table (ontology hook)
```

### Domain Registry Status (DOMAIN_REGISTRY.status)
```
PENDING    -- bootstrap done, not yet crawled
CRAWLED    -- RAW_CONCEPTS populated
ENRICHED   -- CONCEPTS populated
ACTIVE     -- CSS deployed and serving queries
GRADUATED  -- ontology-stack-builder has been run, ontology_agent is set
```

### Crawl Sources (RAW_CONCEPTS.crawl_source)
```
ACCOUNT_USAGE        -- bulk crawl (CRAWL_DOMAIN, may be up to 90min stale)
INFORMATION_SCHEMA   -- targeted crawl (CRAWL_TABLE, CRAWL_SCHEMA, always fresh)
```

### Relationship Types (RELATIONSHIPS.relationship_type)
```
FK              -- declared FOREIGN KEY constraint
INFERRED_FK     -- name-pattern match (ORDER_ID in both tables)
SHARED_KEY      -- same column name/type, no FK but high confidence
SEMANTIC        -- AI-inferred from description similarity
ONTOLOGY        -- imported from ONT_REL_DEF in graduated domain
```

### Detection Methods (RELATIONSHIPS.detection_method)
```
CONSTRAINT      -- TABLE_CONSTRAINTS or SHOW PRIMARY KEYS
NAME_MATCH      -- column naming convention analysis
AI_INFERRED     -- AI_COMPLETE cross-table inference
MANUAL          -- user-specified
ONT_REL_DEF     -- imported from ontology layer
```

---

## Table Schemas

### KG_CONTROL.PUBLIC.DOMAIN_REGISTRY
| Column | Type | Notes |
|--------|------|-------|
| domain_name | VARCHAR PK | UPPERCASE, e.g. FINANCE |
| meta_database | VARCHAR | always `{domain_name}_META` |
| source_databases | ARRAY | databases included in this domain |
| status | VARCHAR | see Domain Registry Status constants |
| enrichment_max_tier | NUMBER(1) | 0–3 |
| enrichment_daily_budget | NUMBER(10,2) | USD hard stop |
| ontology_agent | VARCHAR NULL | FQN of Cortex Agent, set post-graduation |
| ontology_database | VARCHAR NULL | database where ONT_* tables live |
| ontology_schema | VARCHAR NULL | schema where ONT_* tables live |
| ontology_deployed_at | TIMESTAMP_NTZ NULL | when graduation happened |
| graduation_candidate | BOOLEAN | set by DISCOVER_DOMAINS when criteria met |
| css_name | VARCHAR NULL | FQN of active Cortex Search Service |
| css_last_refreshed_at | TIMESTAMP_NTZ NULL | |
| created_at / updated_at | TIMESTAMP_NTZ | |
| created_by | VARCHAR | CURRENT_USER() |

### KG_CONTROL.PUBLIC.WIZARD_STATE
| Column | Type | Notes |
|--------|------|-------|
| session_id | VARCHAR PK | |
| domain_name | VARCHAR NULL | domain being onboarded |
| current_step | NUMBER(2) | 0–9 |
| status | VARCHAR | IN_PROGRESS \| COMPLETE \| FAILED |
| step_results | VARIANT | `{step_N: {status, output, ts}}` |
| started_at / updated_at / completed_at | TIMESTAMP_NTZ | |

### {DOMAIN}_META.META.RAW_CONCEPTS
| Column | Type | Notes |
|--------|------|-------|
| concept_id | VARCHAR PK | UUID |
| concept_level | VARCHAR | database \| schema \| table |
| domain | VARCHAR | matches DOMAIN_REGISTRY.domain_name |
| source_database | VARCHAR | |
| source_schema | VARCHAR NULL | NULL for database-level |
| source_table | VARCHAR NULL | NULL for database/schema-level |
| table_fqn | VARCHAR NULL | `DB.SCHEMA.TABLE`, table-level only |
| table_type | VARCHAR NULL | TABLE \| VIEW \| EXTERNAL TABLE |
| row_count | NUMBER NULL | |
| bytes | NUMBER NULL | |
| clustering_key | VARCHAR NULL | |
| comment | VARCHAR NULL | Snowflake COMMENT ON value |
| created_at_src | TIMESTAMP_NTZ NULL | object creation time in source |
| last_altered_src | TIMESTAMP_NTZ NULL | |
| owner | VARCHAR NULL | |
| is_transient | BOOLEAN | |
| is_managed_access | BOOLEAN | |
| is_active | BOOLEAN | FALSE when object dropped |
| columns_json | VARIANT NULL | `[{name, type, nullable, comment, ordinal}]` |
| constraints_json | VARIANT NULL | `[{name, type, columns, ref_table, ref_cols}]` |
| sample_values_json | VARIANT NULL | `{col_name: [val1, val2, ...]}` |
| crawl_source | VARCHAR | ACCOUNT_USAGE \| INFORMATION_SCHEMA |
| crawl_timestamp | TIMESTAMP_NTZ | |
| metadata_hash | VARCHAR NULL | SHA2(columns_json) for drift detection |
| **UNIQUE** | | (concept_level, source_database, source_schema, source_table) |

### {DOMAIN}_META.META.CONCEPTS
| Column | Type | Notes |
|--------|------|-------|
| concept_id | VARCHAR PK | UUID |
| raw_concept_id | VARCHAR UNIQUE | FK to RAW_CONCEPTS |
| concept_level | VARCHAR | database \| schema \| table |
| domain | VARCHAR | |
| source_database / source_schema / source_table / table_fqn | VARCHAR | mirrors RAW_CONCEPTS |
| description | VARCHAR NULL | AI or ONT_CLASS generated |
| keywords | VARIANT NULL | ARRAY of strings |
| search_content | VARCHAR NULL | all searchable text concatenated for CSS |
| tables_yaml | VARCHAR NULL | YAML: table FQNs, PKs, columns with types/roles |
| join_keys_yaml | VARCHAR NULL | YAML: cross-table relationships |
| metrics_yaml | VARCHAR NULL | YAML: pre-defined aggregations |
| sample_values | VARCHAR NULL | representative values for literal matching |
| is_enum | BOOLEAN | TRUE if column has < 50 distinct values |
| enrichment_tier | NUMBER(1) | 0–3 |
| enrichment_source | VARCHAR NULL | see Enrichment Sources constants |
| enrichment_quality_score | NUMBER(3,2) NULL | 0.00–1.00 |
| enrichment_cost_usd | NUMBER(10,6) | 0 for free tiers |
| enrichment_timestamp | TIMESTAMP_NTZ NULL | |
| query_count | NUMBER | incremented by QUERY_LOG inserts |
| last_queried_at | TIMESTAMP_NTZ NULL | |
| is_active | BOOLEAN | |
| object_state | VARCHAR | see Object States constants |
| created_at / updated_at | TIMESTAMP_NTZ | |

### {DOMAIN}_META.META.RELATIONSHIPS
| Column | Type | Notes |
|--------|------|-------|
| relationship_id | VARCHAR PK | UUID |
| domain | VARCHAR | |
| source_concept_id | VARCHAR | FK to CONCEPTS |
| target_concept_id | VARCHAR | FK to CONCEPTS |
| source_table | VARCHAR | FQN |
| source_column | VARCHAR | |
| target_table | VARCHAR | FQN |
| target_column | VARCHAR | |
| relationship_type | VARCHAR | see Relationship Types constants |
| confidence | NUMBER(3,2) | 0.00–1.00 |
| detection_method | VARCHAR | see Detection Methods constants |
| is_active | BOOLEAN | |
| created_at | TIMESTAMP_NTZ | |

### {DOMAIN}_META.META.OBJECT_STATE
| Column | Type | Notes |
|--------|------|-------|
| object_fqn | VARCHAR PK | `DB`, `DB.SCHEMA`, or `DB.SCHEMA.TABLE` |
| object_level | VARCHAR | database \| schema \| table |
| domain | VARCHAR | |
| object_state | VARCHAR | see Object States constants |
| concept_id | VARCHAR NULL | FK to CONCEPTS, NULL for shadow objects |
| first_seen / last_seen / last_access | TIMESTAMP_NTZ NULL | |
| access_count_30d / distinct_users_30d | NUMBER | from ACCESS_HISTORY |
| metadata_hash / previous_hash | VARCHAR NULL | |
| drift_detected_at | TIMESTAMP_NTZ NULL | |
| drift_details | VARCHAR NULL | human-readable description of what changed |
| possible_ontology_class | VARCHAR NULL | **ontology hook** — class name hint for shadow tables in graduated domains |
| triage_action | VARCHAR NULL | onboard \| ignore \| defer \| re-enrich \| ontology_review |
| triage_reason | VARCHAR NULL | |
| triaged_by / triaged_at | VARCHAR / TIMESTAMP_NTZ NULL | |
| updated_at | TIMESTAMP_NTZ | |

### {DOMAIN}_META.META.DOMAIN_CONFIG
Key-value store. Standard keys:

| config_key | config_value type | Default | Notes |
|------------|-------------------|---------|-------|
| domain_name | string | — | UPPERCASE domain name |
| meta_database | string | — | `{DOMAIN}_META` |
| source_databases | array | [] | set by CONFIGURE_DOMAIN |
| enrichment_max_tier | number | 0 | 0–3 |
| enrichment_daily_budget | number | 10.0 | USD |
| auto_onboard_schemas | array | [] | schemas to auto-crawl on new table detection |
| ignore_schemas | array | ["INFORMATION_SCHEMA"] | always skipped |
| refresh_schedule | string | "0 6 * * *" | cron |
| watch_enabled | boolean | false | |
| watch_auto_onboard | boolean | false | auto-CRAWL_TABLE on new shadow detection |
| ontology_agent | string/null | null | **ontology hook** — FQN, set post-graduation |
| ontology_database | string/null | null | |
| ontology_schema | string/null | null | |
| ontology_deployed_at | string/null | null | ISO timestamp |

### {DOMAIN}_META.META.ASSEMBLY_CACHE
| Column | Type | Notes |
|--------|------|-------|
| cache_key | VARCHAR PK | stable hash for assembled semantic context |
| domain | VARCHAR | uppercase domain name |
| question_hash | VARCHAR | hash of original question |
| table_fqns | VARIANT | ARRAY of FQNs used in assembly |
| tables_context | VARCHAR | serialized context block for prompt or planner |
| sv_ddl | VARCHAR | transient semantic view DDL candidate |
| join_paths | VARIANT | resolved joins for candidate tables |
| quality_score | NUMBER(3,2) | planner/assembly quality |
| concept_ids | VARIANT | ARRAY of contributing concept_ids |
| created_at | TIMESTAMP_NTZ | |
| hit_count | NUMBER | cache reuse counter |
| last_hit_at | TIMESTAMP_NTZ NULL | |
| invalidated_at | TIMESTAMP_NTZ NULL | set by REFRESH_DOMAIN |

### {DOMAIN}_META.META.QUESTION_PLAN
| Column | Type | Notes |
|--------|------|-------|
| plan_id | VARCHAR PK | deterministic hash or UUID |
| user_question | VARCHAR | raw user question |
| normalized_question | VARCHAR | normalized form |
| detected_intent | VARCHAR | lookup / aggregation / compare / etc |
| detected_entities | ARRAY | extracted entities |
| detected_metrics | ARRAY | extracted metrics |
| detected_filters | VARIANT | structured filter payload |
| detected_time_scope | VARIANT | parsed relative/absolute time hints |
| detected_grain | VARCHAR NULL | daily / weekly / order / user etc |
| domain_candidates | ARRAY | ranked domain options |
| confidence | FLOAT | extraction confidence |
| created_at | TIMESTAMP_NTZ | |

### {DOMAIN}_META.META.SEMANTIC_PLAN
| Column | Type | Notes |
|--------|------|-------|
| semantic_plan_id | VARCHAR PK | planner output id |
| plan_id | VARCHAR | FK to QUESTION_PLAN |
| chosen_route | VARCHAR | EXISTING_SV / ONTOLOGY_AGENT / TRANSIENT_CONTRACT / AMBIGUOUS / BLOCKED |
| chosen_semantic_view | VARCHAR NULL | selected native semantic view |
| chosen_ontology_agent | VARCHAR NULL | selected ontology-backed agent |
| use_transient_contract | BOOLEAN | whether planner chose transient contract |
| route_confidence | FLOAT | planner confidence |
| ambiguity_reason | VARIANT NULL | why the route is ambiguous |
| blocking_conflicts | ARRAY | open blocking conflict ids |
| created_at | TIMESTAMP_NTZ | |

### {DOMAIN}_META.META.TRANSIENT_JOIN_GRAPH
| Column | Type | Notes |
|--------|------|-------|
| semantic_plan_id | VARCHAR | FK to SEMANTIC_PLAN |
| edge_order | NUMBER | join order |
| source_object | VARCHAR | left table/view |
| target_object | VARCHAR | right table/view |
| source_key | VARCHAR NULL | |
| target_key | VARCHAR NULL | |
| relationship_type | VARCHAR NULL | FK / INFERRED_FK / SHARED_KEY / ONTOLOGY |
| confidence | FLOAT | join confidence |
| provenance | VARCHAR NULL | relationship source |
| created_at | TIMESTAMP_NTZ | |

### {DOMAIN}_META.META.TRANSIENT_METRIC_BINDINGS
| Column | Type | Notes |
|--------|------|-------|
| semantic_plan_id | VARCHAR | FK to SEMANTIC_PLAN |
| metric_name | VARCHAR | user-facing metric |
| canonical_metric_name | VARCHAR NULL | ontology-canonical metric |
| sql_expression | VARCHAR NULL | resolved expression |
| grain | VARCHAR NULL | metric grain |
| source | VARCHAR NULL | ontology / sv / kg / bi |
| confidence | FLOAT | selection confidence |
| chosen | BOOLEAN | winning metric binding |
| created_at | TIMESTAMP_NTZ | |

### {DOMAIN}_META.META.TRANSIENT_SEMANTIC_SPEC
| Column | Type | Notes |
|--------|------|-------|
| semantic_plan_id | VARCHAR | FK to SEMANTIC_PLAN |
| semantic_spec | VARIANT | execution-safe semantic contract |
| generated_sql_preview | VARCHAR NULL | preview SQL |
| compile_status | VARCHAR NULL | PENDING / VALID / INVALID |
| compile_error | VARCHAR NULL | compile error text |
| created_at | TIMESTAMP_NTZ | |

---

## Stored Procedure Signatures

All procs live in `KG_CONTROL.PUBLIC`. Every proc that operates on a domain reads its config from `{DOMAIN}_META.META.DOMAIN_CONFIG`.

---

### BOOTSTRAP_KG_META (already built in 00_ddl.sql)
```sql
CALL KG_CONTROL.PUBLIC.BOOTSTRAP_KG_META(
    domain_name VARCHAR    -- e.g. 'FINANCE'
)
RETURNS VARCHAR            -- success message
```
Creates `{DOMAIN}_META.META.*` tables and seeds DOMAIN_CONFIG. Registers domain in DOMAIN_REGISTRY.

---

### DISCOVER_DOMAINS (Agent B — 01_discover.sql)
```sql
CALL KG_CONTROL.PUBLIC.DISCOVER_DOMAINS(
    mode         VARCHAR,  -- 'SHALLOW' (7-day, fast) | 'DEEP' (90-day, thorough)
    lookback_days NUMBER   -- override lookback window; ignored if mode='SHALLOW' (uses 7)
)
RETURNS TABLE (
    domain_name          VARCHAR,   -- proposed name (DB name, stripped suffixes)
    source_databases     VARCHAR,   -- comma-separated list
    table_count          NUMBER,
    schema_count         NUMBER,
    total_query_volume   NUMBER,    -- queries in lookback window
    distinct_users       NUMBER,
    fk_relationship_count NUMBER,
    schema_change_count_30d NUMBER,
    priority_tier        VARCHAR,   -- PHASE_1 | PHASE_2 | PHASE_3 | LOW
    graduation_candidate BOOLEAN,   -- TRUE if fk_count>=2 AND table_count>=3 AND query_vol>100 AND schema_change=0
    recommendation       VARCHAR    -- human-readable note
)
```
**Reads:** `SNOWFLAKE.ACCOUNT_USAGE.DATABASES`, `TABLES`, `COLUMNS`, `ACCESS_HISTORY`, `QUERY_HISTORY`, `OBJECT_DEPENDENCIES`
**Writes:** Nothing (result set only — caller decides whether to BOOTSTRAP)
**Language:** SQL

---

### CONFIGURE_DOMAIN (Agent B — 01_discover.sql)
```sql
CALL KG_CONTROL.PUBLIC.CONFIGURE_DOMAIN(
    domain_name      VARCHAR,   -- must already exist in DOMAIN_REGISTRY (run BOOTSTRAP first)
    source_databases ARRAY,     -- e.g. ARRAY_CONSTRUCT('FINANCE_DB', 'FINANCE_ARCHIVE')
    config_overrides VARIANT    -- optional JSON: {"enrichment_max_tier": 2, "ignore_schemas": ["SCRATCH"]}
                                -- NULL to use defaults
)
RETURNS VARCHAR                 -- 'CONFIGURED: FINANCE — 2 source databases, tier=2'
```
**Reads:** `KG_CONTROL.PUBLIC.DOMAIN_REGISTRY`
**Writes:** `{DOMAIN}_META.META.DOMAIN_CONFIG`, `KG_CONTROL.PUBLIC.DOMAIN_REGISTRY.source_databases`
**Language:** SQL

---

### CRAWL_DOMAIN (Agent C — 03_crawl_domain.py)
```sql
CALL KG_CONTROL.PUBLIC.CRAWL_DOMAIN(
    domain_name  VARCHAR,        -- must be CONFIGURED
    mode         VARCHAR         -- 'FULL' | 'DELTA' (skip tables already in RAW_CONCEPTS with matching hash)
)
RETURNS VARCHAR                  -- 'CRAWLED: 142 tables, 28 schemas, 3 databases. Source: ACCOUNT_USAGE.'
```
**Source:** `SNOWFLAKE.ACCOUNT_USAGE.COLUMNS`, `TABLES`, `SCHEMATA`, `DATABASES`
**Reads:** `{DOMAIN}_META.META.DOMAIN_CONFIG` for source_databases, ignore_schemas
**Writes:** `{DOMAIN}_META.META.RAW_CONCEPTS` (UPSERT on concept_level+source_database+source_schema+source_table)
**Ontology hook:** If `DOMAIN_CONFIG.ontology_agent IS NOT NULL`, after crawl compare new metadata_hash values against `{ontology_database}.{ontology_schema}.ONT_CLASS_MAP._source_table` and write `ONTOLOGY_DRIFT` state to OBJECT_STATE for any mismatches.
**Language:** Snowpark Python

---

### CRAWL_TABLE (Agent C — 04_crawl_table.py)
```sql
CALL KG_CONTROL.PUBLIC.CRAWL_TABLE(
    domain_name  VARCHAR,
    table_fqn    VARCHAR    -- 'DB.SCHEMA.TABLE'
)
RETURNS VARCHAR             -- 'CRAWLED: DB.SCHEMA.TABLE — 24 columns, 3 constraints. Source: INFORMATION_SCHEMA.'
```
**Source:** `{DB}.INFORMATION_SCHEMA.COLUMNS`, `TABLE_CONSTRAINTS`; `SELECT DISTINCT` for sample values (LIMIT 20)
**Writes:** `{DOMAIN}_META.META.RAW_CONCEPTS` (UPSERT, crawl_source='INFORMATION_SCHEMA')
**Language:** Snowpark Python

---

### CRAWL_SCHEMA (Agent C — 04_crawl_table.py)
```sql
CALL KG_CONTROL.PUBLIC.CRAWL_SCHEMA(
    domain_name  VARCHAR,
    schema_fqn   VARCHAR    -- 'DB.SCHEMA'
)
RETURNS VARCHAR             -- 'CRAWLED: DB.SCHEMA — 18 tables, 412 columns. Source: INFORMATION_SCHEMA.'
```
**Source:** Same as CRAWL_TABLE but iterates all tables in schema
**Writes:** `{DOMAIN}_META.META.RAW_CONCEPTS` (UPSERT for each table)
**Language:** Snowpark Python

---

### ENRICH_DOMAIN (Agent D — 05_enrich_domain.py)
```sql
CALL KG_CONTROL.PUBLIC.ENRICH_DOMAIN(
    domain_name  VARCHAR,
    max_tier     NUMBER     -- 0–3. Enriches up to and including this tier.
                            -- Use 0 for free-only, 3 for full AI pipeline.
)
RETURNS VARCHAR             -- 'ENRICHED: 142 concepts. Tier breakdown: 0=89, 1=31, 2=18, 3=4. Cost: $0.042.'
```
**Reads:** `{DOMAIN}_META.META.RAW_CONCEPTS` (rows where no matching CONCEPTS row, or where RAW_CONCEPTS.crawl_timestamp > CONCEPTS.enrichment_timestamp)
**Ontology hook (pre-enrichment, runs BEFORE any AI tier):**
  Check `SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA='{ontology_schema}' AND TABLE_NAME='ONT_CLASS'` in ontology_database. If table exists:
  - `SELECT _source_table, description FROM {ontology_database}.{ontology_schema}.ONT_CLASS WHERE _source_table IS NOT NULL`
  - `SELECT name, description FROM {ontology_database}.{ontology_schema}.ONT_SHARED_PROPERTY`
  - Write matching rows to CONCEPTS with enrichment_source='ONT_CLASS', enrichment_cost_usd=0
  - Skip AI tiers for those rows
**Writes:** `{DOMAIN}_META.META.CONCEPTS` (INSERT or UPDATE enriched rows); updates `DOMAIN_REGISTRY.status='ENRICHED'`
**Language:** Snowpark Python
**AI functions used:**
- `SNOWFLAKE.CORTEX.CLASSIFY_TEXT()` (Tier 1)
- `AI_EXTRACT()` (Tier 2)
- `SNOWFLAKE.CORTEX.COMPLETE('claude-3-5-sonnet', ...)` (Tier 3)

---

### DETECT_RELATIONSHIPS (Agent E — 06_detect_rels.py)
```sql
CALL KG_CONTROL.PUBLIC.DETECT_RELATIONSHIPS(
    domain_name  VARCHAR
)
RETURNS VARCHAR             -- 'DETECTED: 23 relationships (8 FK, 11 INFERRED_FK, 4 SEMANTIC).'
```
**Reads:** `{DOMAIN}_META.META.CONCEPTS` (columns_json, constraints_json), `RAW_CONCEPTS.constraints_json`
**Ontology hook:** If domain is graduated, also read `{ontology_database}.{ontology_schema}.ONT_RELATION_DEF` and import as relationship_type='ONTOLOGY', detection_method='ONT_REL_DEF', confidence=1.0
**Writes:** `{DOMAIN}_META.META.RELATIONSHIPS` (INSERT new, skip existing with same source+target+type)
**Language:** Snowpark Python
**Logic:**
1. Parse `constraints_json` for declared FKs → CONSTRAINT detection (confidence=1.0)
2. Name-pattern match: `{TABLE}_ID` or `{TABLE}S_ID` column in another table → INFERRED_FK (confidence=0.85)
3. Shared column name + type across tables with high cardinality match → SHARED_KEY (confidence=0.7)
4. Tier 3 only: AI_COMPLETE cross-table inference on column descriptions → SEMANTIC (confidence variable)

---

### REFRESH_DOMAIN (Agent F — 07_refresh.sql)
```sql
CALL KG_CONTROL.PUBLIC.REFRESH_DOMAIN(
    domain_name  VARCHAR,
    max_tier     NUMBER     -- enrichment tier ceiling (passed to ENRICH_DOMAIN)
)
RETURNS VARCHAR             -- 'REFRESHED: FINANCE. Crawl: 12 new / 3 updated. Enrich: 15 concepts. Rels: +2. CSS: refreshed.'
```
**Calls:** CRAWL_DOMAIN('DELTA') → ENRICH_DOMAIN(max_tier) → DETECT_RELATIONSHIPS() → CSS refresh
**CSS refresh:** `ALTER CORTEX SEARCH SERVICE {DOMAIN}_META.META.{DOMAIN}_SEARCH RESUME` (if suspended) or `CREATE OR REPLACE CORTEX SEARCH SERVICE ...` (if not yet created)
**Writes:** `DOMAIN_REGISTRY.status='ACTIVE'`, `DOMAIN_REGISTRY.css_last_refreshed_at`
**Language:** SQL scripting

**CSS DDL (embedded in REFRESH_DOMAIN):**
```sql
CREATE OR REPLACE CORTEX SEARCH SERVICE {DOMAIN}_META.META.{DOMAIN}_SEARCH
  ON search_content
  ATTRIBUTES concept_name, concept_level, domain, source_database, source_schema, table_fqn,
             object_state, enrichment_tier
  WAREHOUSE = <from session context>
  TARGET_LAG = '1 hour'
AS (
  SELECT concept_name, concept_level, domain, source_database, source_schema,
         table_fqn, search_content, tables_yaml, join_keys_yaml, metrics_yaml,
         sample_values, is_enum, object_state, enrichment_tier, query_count
  FROM {DOMAIN}_META.META.CONCEPTS
  WHERE is_active = TRUE
    AND object_state NOT IN ('KNOWN_DELETED', 'SHADOW_INACTIVE')
);
```

---

### RUN_WATCH (Agent G — 08_watch.py)
```sql
CALL KG_CONTROL.PUBLIC.RUN_WATCH(
    domain_name  VARCHAR
)
RETURNS TABLE (
    object_fqn        VARCHAR,
    object_level      VARCHAR,
    object_state      VARCHAR,
    triage_action     VARCHAR,
    triage_reason     VARCHAR,
    possible_ontology_class VARCHAR   -- populated for graduated domains
)
```
**Reads:** `{DOMAIN}_META.META.CONCEPTS`, `SNOWFLAKE.ACCOUNT_USAGE.TABLES`, `ACCESS_HISTORY`, `{DOMAIN}_META.META.DOMAIN_CONFIG`
**Writes:** `{DOMAIN}_META.META.OBJECT_STATE` (UPSERT)
**Ontology hook:** For graduated domains, when shadow table detected, compare its columns_json against `{ontology_database}.{ontology_schema}.ONT_CLASS._source_table` column patterns. If similarity > 0.7, set `possible_ontology_class` and triage_action='ontology_review'.
**Language:** Snowpark Python
**Logic (six-state diff):**
1. `CONCEPTS ∩ ACCOUNT_USAGE.TABLES where metadata_hash matches` → KNOWN_CURRENT
2. `CONCEPTS ∩ TABLES where hash diverged` → KNOWN_DRIFTED
3. `CONCEPTS − TABLES` → KNOWN_DELETED
4. `CONCEPTS where enrichment_quality_score < 0.3` → ONBOARDED_INCORRECTLY
5. `TABLES − CONCEPTS where ACCESS_HISTORY in last 30d` → SHADOW_ACTIVE
6. `TABLES − CONCEPTS where no ACCESS_HISTORY in 30d` → SHADOW_INACTIVE
7. For graduated: `CONCEPTS where new crawl hash ≠ ONT_CLASS_MAP hash` → ONTOLOGY_DRIFT

---

### RESOLVE_QUERY_CONTEXT (Phase 3 — semantic resolution tool)
```sql
CALL KG_CONTROL.PUBLIC.RESOLVE_QUERY_CONTEXT(
    user_question VARCHAR,
    domain_hint   VARCHAR,
    max_routes    NUMBER,
    strict_mode   BOOLEAN
)
RETURNS VARIANT
```
**Reads:** `KG_CONTROL.PUBLIC.DOMAIN_REGISTRY`, `{DOMAIN}_META.META.DOMAIN_CONFIG`, query-plane tables
**Writes:** `{DOMAIN}_META.META.QUESTION_PLAN`, `{DOMAIN}_META.META.SEMANTIC_PLAN`
**Language:** Snowpark Python
**Purpose:** Produce a route decision and execution contract seed from a user question without executing SQL directly.

---

### BUILD_TRANSIENT_CONTRACT (Phase 3 — transient semantic compiler)
```sql
CALL KG_CONTROL.PUBLIC.BUILD_TRANSIENT_CONTRACT(
    meta_db          VARCHAR,
    plan_id          VARCHAR,
    semantic_plan_id VARCHAR,
    domain_name      VARCHAR
)
RETURNS VARIANT
```
**Reads:** `{DOMAIN}_META.META.QUESTION_PLAN`
**Writes:** `{DOMAIN}_META.META.TRANSIENT_SEMANTIC_SPEC`
**Language:** Snowpark Python
**Purpose:** Build an initial transient semantic contract from planner outputs.

---

### VALIDATE_TRANSIENT_CONTRACT (Phase 3 — semantic validator)
```sql
CALL KG_CONTROL.PUBLIC.VALIDATE_TRANSIENT_CONTRACT(
    meta_db          VARCHAR,
    semantic_plan_id VARCHAR
)
RETURNS VARIANT
```
**Reads:** `{DOMAIN}_META.META.TRANSIENT_SEMANTIC_SPEC`
**Writes:** updates `compile_status`, `compile_error`
**Language:** Snowpark Python
**Purpose:** Validate transient semantic contracts before execution.

---

### DETECT_SEMANTIC_CONFLICTS (Phase 2 — ontology/KG verification)
```sql
CALL KG_CONTROL.PUBLIC.DETECT_SEMANTIC_CONFLICTS(
    domain_name VARCHAR,
    meta_db     VARCHAR,
    ont_db      VARCHAR,
    ont_schema  VARCHAR
)
RETURNS VARIANT
```
**Reads:** `{DOMAIN}_META.META.CONCEPTS`, `{DOMAIN}_META.META.RELATIONSHIPS`, `{ONT_DB}.{ONT_SCHEMA}.ONT_CONFLICT_REGISTRY`
**Language:** Snowpark Python
**Purpose:** Surface open ontology/KG conflicts for planner and governance layers.

---

### VERIFY_METRIC_BINDINGS (Phase 2 — canonical metric verification)
```sql
CALL KG_CONTROL.PUBLIC.VERIFY_METRIC_BINDINGS(
    domain_name       VARCHAR,
    ont_db            VARCHAR,
    ont_schema        VARCHAR,
    semantic_view_fqn VARCHAR
)
RETURNS VARIANT
```
**Reads:** `{ONT_DB}.{ONT_SCHEMA}.ONT_METRIC_DEF`, `CANONICAL_METRIC_DECISIONS`
**Language:** Snowpark Python
**Purpose:** Compare semantic view metric bindings to ontology-canonical metrics.

---

### ONBOARD_WIZARD (Agent H — 09_wizard.py)
```sql
CALL KG_CONTROL.PUBLIC.ONBOARD_WIZARD(
    action       VARCHAR,   -- 'START' | 'STATUS' | 'RESTART' | 'NEXT' | 'RESTART_FROM'
    step         NUMBER     -- only used for action='RESTART_FROM'
)
RETURNS VARIANT            -- {session_id, current_step, status, message, next_action}
```
**Reads/Writes:** `KG_CONTROL.PUBLIC.WIZARD_STATE`, calls all other procs
**Language:** Snowpark Python
**Steps:**
```
0  Prerequisites check     (validate warehouse, role, permissions)
1  DISCOVER_DOMAINS        (SHALLOW, 7 days)
2  Select domain           (returns options to caller — user chooses)
3  BOOTSTRAP_KG_META       + CONFIGURE_DOMAIN
4  CRAWL_DOMAIN(FULL)
5  ENRICH_DOMAIN(tier)     (tier from user config)
6  DETECT_RELATIONSHIPS
7  REFRESH_DOMAIN          (creates CSS)
8  Validation              (SHOW CONCEPTS, test CSS search, check DOMAIN_REGISTRY.status=ACTIVE)
9  Graduate check          (if graduation_candidate=TRUE, surface to caller for skill routing)
```

---

## Inter-Proc Call Graph

```
ONBOARD_WIZARD
  └── BOOTSTRAP_KG_META
  └── CONFIGURE_DOMAIN
  └── CRAWL_DOMAIN ──────────── reads: ACCOUNT_USAGE
  └── ENRICH_DOMAIN ──────────── reads: RAW_CONCEPTS + (ONT_CLASS if graduated)
  └── DETECT_RELATIONSHIPS ───── reads: CONCEPTS + (ONT_REL_DEF if graduated)
  └── REFRESH_DOMAIN
        └── CRAWL_DOMAIN(DELTA)
        └── ENRICH_DOMAIN
        └── DETECT_RELATIONSHIPS
        └── [CSS CREATE/REFRESH]

RUN_WATCH ──────────────────────── reads: CONCEPTS + ACCOUNT_USAGE + (ONT_CLASS_MAP if graduated)

CRAWL_TABLE ────────────────────── reads: INFORMATION_SCHEMA (single table, always fresh)
CRAWL_SCHEMA ───────────────────── reads: INFORMATION_SCHEMA (all tables in schema)

DISCOVER_DOMAINS ───────────────── reads: ACCOUNT_USAGE (result set, no writes)
```

---

## Ontology Integration Summary (for all agents)

All five hooks reference `DOMAIN_CONFIG` keys `ontology_agent`, `ontology_database`, `ontology_schema`.
Check `ontology_agent IS NOT NULL` before activating any hook.

| Hook | Proc | What to do |
|------|------|-----------|
| 1 | DISCOVER_DOMAINS | Set `graduation_candidate=TRUE` when: fk_count>=2 AND table_count>=3 AND query_vol>100 AND schema_change_30d=0 |
| 2 | DDL / DOMAIN_CONFIG | `ontology_agent`, `ontology_database`, `ontology_schema`, `ontology_deployed_at` keys exist in seed INSERT |
| 3 | ENRICH_DOMAIN | Pre-enrichment: read `ONT_CLASS` + `ONT_SHARED_PROPERTY` → write free descriptions, skip AI for matched rows |
| 4 | CRAWL_DOMAIN | Post-crawl: compare new metadata_hash vs `ONT_CLASS_MAP._source_table` column patterns → write `ONTOLOGY_DRIFT` to OBJECT_STATE |
| 5 | RUN_WATCH | Shadow detection: if graduated, compare shadow table columns vs `ONT_CLASS` patterns, set `possible_ontology_class` hint |

---

## Agent Assignments (Round 2+)

| Agent | Files | Procs |
|-------|-------|-------|
| B | `procs/sql/01_discover.sql` | DISCOVER_DOMAINS, CONFIGURE_DOMAIN |
| C | `procs/python/03_crawl_domain.py`, `procs/python/04_crawl_table.py` | CRAWL_DOMAIN, CRAWL_TABLE, CRAWL_SCHEMA |
| D | `procs/python/05_enrich_domain.py` | ENRICH_DOMAIN (owns ontology Hook 3) |
| E | `procs/python/06_detect_rels.py` | DETECT_RELATIONSHIPS |
| F | `procs/sql/07_refresh.sql` | REFRESH_DOMAIN (orchestrator + CSS DDL) |
| G | `procs/python/08_watch.py` | RUN_WATCH (owns ontology Hooks 4+5) |
| H | `procs/python/09_wizard.py` + `procs/deploy.sql` | ONBOARD_WIZARD, deploy script |

Each agent needs only: **this file + their assigned file(s)**. No other context required.
