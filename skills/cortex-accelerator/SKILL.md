---
name: cortex-accelerator
description: >
  Guided discovery tool that validates business understanding before building Snowflake
  semantic views and Cortex Agents. Scans query history, schemas, and BI tools (Tableau,
  PowerBI, dbt) to detect gaps and conflicts, scores trust, and gates pipeline execution
  until a validated domain map is confirmed. Use when: build semantic view from data,
  build cortex agent, automate agent build, fast-track agent, accelerate semantic layer,
  I have Snowflake data and want an agent, help me build an agent from my data, guided
  agent build, customer wants semantic views but doesn't know their data.
  DO NOT attempt to build semantic views or agents without this skill when the customer
  has undocumented, messy, or multi-database schemas.
  Triggers: cortex accelerator, build agent from data, semantic layer from query history,
  fast forward agent, guided agent build, accelerate semantic view, help build agent,
  automate semantic layer, I want an agent on my data.
---

# Cortex Accelerator

Guided discovery → validated domain map → pipeline execution.

**Core principle:** Fast automation to a garbage semantic view is worse than no semantic
view. This skill gates the pipeline behind validated business understanding.
80% guided discovery. 20% pipeline.

## When to Use

- Customer wants to build semantic views or a Cortex Agent from their Snowflake data
- Schema is undocumented, cryptic, or spread across many databases
- SE wants to fast-track a semantic layer + agent build in one guided session
- Customer has BI tools (Tableau/PowerBI/dbt) that encode business meaning to harvest

## Architecture

```
PHASE 0: SCAN         schema quality, query history, data quality, PII, access
PHASE 1-3: DISCOVER   hypothesize domains/entities/metrics, gaps, conflicts + trust scores
PHASE 4: RESOLVE      BI tool intake (Tableau/PowerBI/dbt) + targeted question interview
PHASE 5: VALIDATE     ⚠️ GATE — human confirms domain map, perf flags, success criteria
PHASE 6: BUILD        pipeline delegation (kg → vqr → ontology-stack-builder → optimize)
PHASE 7: HANDOFF      schema drift watch, ops monitoring, optimization schedule
```

## Step 1: Ask Mode

Use `ask_user_question`:
```
header: "Mode"
question: "How would you like to work?"
options:
  - label: "Guided (default)"
    description: "Walk through each phase with checkpoints and explanations"
  - label: "Autonomous"
    description: "Run full scan, surface only blocking decisions"
```

## Step 2: Entry Point Detection

Run these to detect what already exists:

```sql
SHOW SEMANTIC VIEWS IN ACCOUNT;
SHOW AGENTS IN ACCOUNT;
SHOW DATABASES LIKE '%_META';
SELECT COUNT(*), COUNT(DISTINCT USER_NAME)
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
WHERE START_TIME >= DATEADD(day, -30, CURRENT_TIMESTAMP())
  AND QUERY_TYPE = 'SELECT';
```

Route based on results:

| State | Start at |
|-------|----------|
| Nothing exists | Phase 0 (full scan) |
| KG `_META` DBs exist, no SVs | Phase 1 (discovery from KG) |
| SVs exist, no agent | Phase 5 gate → Phase 6 ontology-stack-builder |
| Agent exists, needs improvement | Skip to `cortex-agent-optimization` skill |
| User names specific tables, clean schema | Phase 0 (targeted scan, skip KG path) |

## Step 3: Load Phase Sub-Skill

| Route | Load |
|-------|------|
| Full scan | `phases/scan/SKILL.md` |
| Discovery from KG manifest | `phases/discovery/SKILL.md` |
| Validate existing domain map | `phases/validate/SKILL.md` |
| Optimize existing agent | Invoke `cortex-agent-optimization` skill |

## Sub-Skills

| Phase | File | Purpose |
|-------|------|---------|
| 0 | `phases/scan/SKILL.md` | Schema, query, data quality, PII, access signals |
| 1–3 | `phases/discovery/SKILL.md` | Hypothesize, gaps, conflicts, trust scoring |
| 4 | `phases/resolution/SKILL.md` | BI tool intake + targeted question interview |
| 5 | `phases/validate/SKILL.md` | Domain map gate, perf flags, success criteria |
| 6 | `phases/build/SKILL.md` | Pipeline delegation to child skills |
| 7 | `phases/handoff/SKILL.md` | Drift watch, ops monitoring, optimization schedule |

## References

- `references/domain-map-schema.md` — Validated domain map JSON schema (gate artifact)
- `references/bi-intake.md` — BI tool extraction details (Tableau, PowerBI, dbt)
- `references/question-library.md` — Targeted question templates by gap type

## Stopping Points

- ✋ Phase 0: User confirms scan scope (which databases/schemas to include)
- ✋ Phase 3: User reviews gap + conflict report before resolution
- ✋ Phase 4: User provides BI tool artifacts or answers targeted questions
- ✋ **Phase 5: Hard gate — user confirms domain map before any pipeline runs**
- ✋ Phase 6: User approves pre-build summary before DDL/SQL executes

## Output

`validated_domain_map.json` — the gate artifact. Contains confirmed domains, entities,
metrics, relationships, resolved conflicts, accepted gaps, success criteria, and
pipeline routing decisions. All downstream skills read from this file.

---

## Build Pipeline Router

When Phase 6 (Build) loads `phases/build/SKILL.md`, execute this 4-phase inter-skill
pipeline. Each phase has explicit INPUTS, OUTPUTS, and a GATE before proceeding.
Read `validated_domain_map.json` before starting — the domain map drives all decisions.

---

### Pipeline Phase 0: KG Discovery → EMIT MANIFEST

**INPUTS**
- `validated_domain_map.domains[].databases[]` — databases in scope
- `validated_domain_map.domains[].description` — domain descriptions
- `validated_domain_map.excluded_tables[]` — tables to skip

**ACTION**: Invoke `kg-data-discovery` skill.
Tell the skill: "execution mode: AUTOPILOT — emit the EMIT MANIFEST block at the end."
**NOTE:** The message MUST start with "execution mode" to bypass kg-data-discovery's STEP ZERO interactive mode-selection prompt (AGENTS.md convention). Any other phrasing causes the pipeline to stall waiting for user input.

Skip this phase if `pipeline_path = "VQR_DIRECT"` (clean schema, ≥ 75 scan score).
In that case, jump directly to Phase 1 with INFORMATION_SCHEMA as the schema source.

**OUTPUTS — capture the EMIT MANIFEST JSON block emitted by kg-data-discovery:**
```json
{
  "domain": "<name>",
  "databases": ["<db1>", "<db2>"],
  "schemas": ["<db1.schema1>", "<db2.schema1>"],
  "enrichment_path": "KG_ENRICHED | VQR_DIRECT",
  "fk_map": [{"src": "TABLE.COL", "dst": "TABLE.COL"}],
  "css_service": "<domain>_META.META.DOMAIN_SEARCH",
  "stability_score": 1,
  "table_count": 142
}
```

Save as `kg_manifest.json` in the working directory.

**GATE**: Verify `stability_score`, `table_count`, and `fk_map` are all populated.
If `stability_score` is absent, ask kg-data-discovery to re-emit the manifest.

---

### Pipeline Phase 1: Table Inventory (sql-table-extractor)

**INPUTS**
- `kg_manifest.databases[]` and `kg_manifest.schemas[]` (KG_ENRICHED path)
- OR: INFORMATION_SCHEMA for each domain database (VQR_DIRECT path)

**ACTION**: Invoke `sql-table-extractor` skill.
Pass the manifest databases and schemas as the analysis scope.
Output: `extracted_tables.json` — tables and columns grouped by domain.

**GATE (⚠️ STOP)**:
```
ask_user_question:
  header: "Domain check"
  question: "I found {N} tables across {D} domains. Do the domain assignments look correct?"
  options:
    - "Yes, proceed to semantic view generation"
    - "No, I need to reassign some tables"
```
If user reassigns tables, update `extracted_tables.json` before Phase 2.

---

### Pipeline Phase 2: Semantic View Generation (vqr-semantic-view-generator)

**PRECONDITION — HARD GATE**: `validated_domain_map.json` must exist with
`validation_status = "APPROVED"`. If not APPROVED, halt and load
`phases/validate/SKILL.md` before continuing. Never execute Phase 2+ without an
approved domain map.

**INPUTS**
- `extracted_tables.json` (from Phase 1)
- Source queries CSV: extract from `ACCOUNT_USAGE.QUERY_HISTORY` for the domain tables
  (`domains[].entities[].columns[]` as the filter)
- `validated_domain_map.metrics[]` — seed as metric definitions
- `validated_domain_map.success_criteria[]` — seed as verified query examples

**ACTION**: Invoke `vqr-semantic-view-generator` skill.
For KG_ENRICHED path: pass KG manifest as `--input` (enriched schemas + FK map).
For VQR_DIRECT path: pass `extracted_tables.json` directly.

After the skill generates YAML files, cross-check against the domain map:
- Dimension names match `domains[].entities[].columns[]` descriptions
- Metric expressions match `metrics[].expression`
- Relationships match `relationships[]`

**GATE (⚠️ STOP)**:
Present generated YAML samples. User must approve before deploy. Check:
- All tables have real `DATABASE.SCHEMA` refs
- Facts identified correctly (numeric measures, not IDs)
- Relationships use actual foreign keys from `fk_map`

---

### Pipeline Phase 3: Route to Build Target

Use `kg_manifest.stability_score` to select the downstream skill:

| Score | Route | Rationale |
|-------|-------|-----------|
| < 3 | `ontology-stack-builder` | Cross-DB or cryptic schema — relationships ARE the value. Build the formal ontology layer before optimizing the agent. |
| ≥ 3 | `cortex-agent-optimization` | Stable, clean schema — deploy the agent directly, then optimize with eval splits. |

**INPUTS**
- Semantic view YAMLs from Phase 2 (deployed or staged)
- `validated_domain_map.json` (audience, success_criteria, entities)
- `kg_manifest.stability_score`

**If ontology-stack-builder route (stability_score < 3):**
Invoke skill `ontology-stack-builder` with:
- Phase 1b input = semantic views from Phase 2 (pass as existing SVs)
- Business questions = `validated_domain_map.success_criteria[]`
- Domain map entities and relationships already confirmed — pass as context

**If cortex-agent-optimization route (stability_score ≥ 3):**
Invoke `cortex-agent-optimization` with:
- Eval dataset seeded from `success_criteria[]` (these are the acceptance bar)
- Representative queries from `ACCOUNT_USAGE.QUERY_HISTORY` for domain tables
  (sample diverse users, exclude service accounts and high-error queries)
- Run in supervised mode unless user requested autonomous in Phase 0

Both paths end with `cortex-agent-optimization` to iterate on agent quality.
For the ontology path, run optimization after ontology-stack-builder Phase 6 completes.

**GATE (⚠️ STOP)**:
```
ask_user_question:
  header: "Build route"
  question: "stability_score={score} → recommending {route}. Proceed?"
  options:
    - "Yes, proceed"
    - "Override — use ontology-stack-builder"
    - "Override — use cortex-agent-optimization"
```

After user confirms, load `phases/build/SKILL.md` for the full step-by-step execution.
