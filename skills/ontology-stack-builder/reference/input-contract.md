# Input Contract — ontology-stack-builder

Full specification of required and optional inputs for both entry paths.

---

## Entry Path A: KG Graduate

Use when a `kg-data-discovery` domain has `stability_score >= 0.7` and at least 3 active table-level CONCEPTS.

### Required Inputs

| Input | Type | Source | Notes |
|-------|------|--------|-------|
| `domain` | string | EMIT MANIFEST `domain` field | Must match `DOMAIN_CONFIG.config_key = 'domain_name'` |
| `company_slug` | string | User provides | Lowercase, hyphenated (e.g. `att`, `warner-brothers-discovery`) — used in file names and DDL object names |
| `company_name` | string | User provides | Display name (e.g. `AT&T`) — used in agent config and docs |
| `output_dir` | string | User provides | Absolute or `~/` path — no hardcoded `/Users/jfoley/` |
| EMIT MANIFEST JSON | JSON block | Paste from kg-data-discovery output | Must include: `domain`, `stability_score`, `table_count`, `css_service`, `fk_map`, `enrichment_path` |

### Required Snowflake Objects

All must exist and pass validation queries before Phase 01 completes.

| Object | Validation Query | Failure Action |
|--------|-----------------|---------------|
| `{DOMAIN}_META.META.CONCEPTS` | `COUNT(*) WHERE concept_level='table' AND is_active=TRUE >= 3` | Hard stop — run kg-data-discovery ENRICH first |
| `{DOMAIN}_META.META.RELATIONSHIPS` | Table must exist (empty is OK) | Hard stop — run kg-data-discovery ONBOARD first |
| `{DOMAIN}_META.META.DOMAIN_CONFIG` | `config_key='domain_name'` returns a value | Hard stop |
| Active CSS | `DOMAIN_CONFIG.css_service_fqn` non-null AND CSS `status = 'ACTIVE'` | Hard stop |
| `KG_CONTROL.PUBLIC.DOMAIN_REGISTRY` row | `status IN ('ENRICHED', 'ACTIVE')` | Hard stop |

### Optional Accelerator Inputs

These files are not required but improve design quality when present.

| File | Effect when present |
|------|-------------------|
| `schema_summary.md` | Phase 02 uses real column names instead of inferred names in class definitions |
| `join_graph.md` | Phase 02 seeds `relations.json` with pre-confirmed HIGH/MEDIUM confidence pairs |

---

## Entry Path B: Direct Table

Use when no KG exists — user provides source tables and describes the join relationships directly.

### Required Inputs

| Input | Type | Source | Notes |
|-------|------|--------|-------|
| `company_slug` | string | User provides | Same format as Path A |
| `company_name` | string | User provides | Same format as Path A |
| `output_dir` | string | User provides | Same format as Path A |
| `demo_tables.sql` | file path | User provides | Physical foundation layer — deployed to Snowflake before Phase 03 |
| Source table list | string[] | User provides | At least 3 tables with DB.SCHEMA.TABLE FQNs |
| Join descriptions | string[] | User provides | e.g. "ORDERS.customer_id = CUSTOMERS.customer_id" |
| Business questions | string[] | User provides | 5–8 NL questions the ontology should answer |

### What is NOT Required for Path B

- KG_CONTROL or {DOMAIN}_META schemas — not needed
- EMIT MANIFEST — not needed
- Existing Cortex Search Service — one will be created or skipped

> NOTE: Phase 03 skips KG_NODE and KG_EDGE generation when BUILD_PATH = DIRECT_TABLE.
> The `demo_tables.sql` content becomes the physical foundation instead.

---

## Output Artifacts

All written to `{output_dir}` at the end of Phase 02 (design files) and Phase 03 (build files).

| Artifact | Phase | Format | Minimum |
|----------|-------|--------|---------|
| `ontology/classes.json` | 02 | JSON array | ≥ 25 class entries |
| `ontology/relations.json` | 02 | JSON array | ≥ 12 entries, ≥ 3 HIGH |
| `ontology/system_mapping.json` | 02 | JSON array | ≥ 1 entry per source system |
| `ontology/architecture_brief.md` | 02 | Markdown | WOW questions, narrative, diagram |
| `{slug}_ontology.sql` | 03 | SQL | ≥ 10 demo query blocks |
| `{slug}_agent_config.yaml` | 03 | YAML | No placeholder text in sample_questions |
| `{slug}_demo_walkthrough.md` | 03 | Markdown | 5 acts, ~25–30 min runtime |
| `streamlit/streamlit_app.py` | 03 | Python | Must use SNOWFLAKE.CORTEX.COMPLETE() via SQL |
| `streamlit/pyproject.toml` | 03 | TOML | Standard Streamlit project config |
| `streamlit/secrets.toml.example` | 03 | TOML | Connection template |
| `eval_dataset.sql` | 03 | SQL | ≥ 25 INSERT rows |

### Post-Graduation Snowflake Updates (Phase 04)

| Object | Update |
|--------|--------|
| `{DOMAIN}_META.META.DOMAIN_CONFIG` | `config_key='ontology_agent'` set to agent FQN |
| `{DOMAIN}_META.META.OBJECT_STATE` | All rows for domain set to `GRADUATED` |
| `KG_CONTROL.PUBLIC.DOMAIN_REGISTRY` | `status='GRADUATED'`, `ontology_agent`, `ontology_database`, `ontology_schema`, `ontology_deployed_at` set |

---

## Key Constraints

| Constraint | Enforcement |
|-----------|-------------|
| No duplicate column names in V_* views | Phase 03 self-validation |
| Semantic View facts/dims aliases must match underlying column names exactly | Phase 03 self-validation |
| DATA_AGENT_RUN content must be array [{type,text}], not plain string | Phase 04 agent test |
| Streamlit must use SNOWFLAKE.CORTEX.COMPLETE() via SQL — not REST API | Phase 03 self-validation |
| `keywords` column (VARIANT) — not `keywords_yaml` | Phase 01 KG query |
| WOW question sample_questions must be literal text — no placeholders | Phase 03 self-validation |
| BUILD_PATH gate is NON-NEGOTIABLE — KG and DIRECT_TABLE must not be mixed | Phase 01 stopping point |
