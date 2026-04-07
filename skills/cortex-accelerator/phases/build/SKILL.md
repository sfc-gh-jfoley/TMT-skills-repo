---
name: cortex-accelerator-build
description: "Phase 6 of cortex-accelerator. Delegates to the correct pipeline
  skills based on the validated domain map and scan routing decision. Sequences:
  kg-data-discovery (if messy), vqr-semantic-view-generator, ontology-stack-builder,
  cortex-agent-optimization."
parent_skill: cortex-accelerator
---

# Phase 6: Build

Read `validated_domain_map.json` and route each domain to the correct pipeline path.
The domain map drives all decisions — do not re-ask questions answered in Phases 0–5.

## Routing Per Domain

For each domain in `validated_domain_map.domains[]`, check `pipeline_path`:

| Path | When | Sequence |
|------|------|----------|
| `KG_ENRICHED` | Score < 75, cross-DB, or cryptic naming | KG → VQR (enriched) → ontology-stack-builder |
| `VQR_DIRECT` | Score ≥ 75, clean schema, known tables | VQR (raw) → ontology-stack-builder |
| `SV_EXISTS` | Semantic views already present | ontology-stack-builder Phase 1b only |

All paths end with `cortex-agent-optimization` seeded from query history eval data.

## Step 1: KG Enrichment (KG_ENRICHED path only)

Invoke `kg-data-discovery` skill with these inputs from the domain map:
- Databases in scope (from `domains[].databases[]`)
- Domain names and descriptions (from `domains[].description`)
- Tables to exclude (from `excluded_tables[]`)

Tell kg-data-discovery to run in AUTOPILOT mode and emit a structured manifest:
```json
{
  "domain": "<name>",
  "enriched_schema_path": "@<stage>/enriched_schemas.json",
  "fk_map": [...],
  "css_service": "<css_name>"
}
```
Capture this manifest — it feeds VQR in the next step.

## Step 2: VQR — Bootstrap Semantic Views

Invoke `vqr-semantic-view-generator` skill.

**For KG_ENRICHED path:** Pass the KG manifest as `--input` (enriched schemas + FK map).
**For VQR_DIRECT path:** Script fetches directly from INFORMATION_SCHEMA.

Provide these from the domain map:
- Source queries CSV: extract from `ACCOUNT_USAGE.QUERY_HISTORY` for the domain's tables
- Target output directory for YAML files
- Domain prefix from `domains[].name`

Metrics and verified queries come from `domains[].metrics[]` and
`success_criteria[]` (seed as verified query examples).

After VQR completes, review generated YAML files against the domain map:
- Confirm dimension names match `domains[].entities[].columns[]` descriptions
- Confirm metric expressions match `metrics[].expression`
- Confirm relationships match `relationships[]`

**⚠️ STOPPING POINT:** Present generated YAML samples. User approves before deploy.

## Step 3: Ontology Stack Builder

Invoke `ontology-stack-builder` skill with:
- **Phase 1b input:** The semantic views generated in Step 2 (pass as existing SVs)
- **Business questions:** `success_criteria[]` questions → used for ontology class design
- **Domain map:** entities, relationships, and metrics already confirmed

The skill handles layers 1–5 (physical tables, abstract views, semantic models, agent).
Tell the skill the agent audience from `validated_domain_map.audience`.

## Step 4: Cortex Agent Optimization

After the agent is deployed, invoke `cortex-agent-optimization` skill.

Seed the eval dataset from:
1. `success_criteria[]` — the 5 confirmed questions (these are the acceptance bar)
2. Representative queries from `ACCOUNT_USAGE.QUERY_HISTORY` for the domain tables
   — sample diverse users, exclude service accounts, exclude high-error queries

Set the acceptance bar: agent must correctly answer all 5 `success_criteria` questions
before the optimization loop can declare success.

Run in **supervised mode** unless user requested autonomous in Phase 0.

## Step 5: Post-Build Verification

After all skills complete, verify:

```sql
-- Semantic views exist
SHOW SEMANTIC VIEWS IN DATABASE <target_db>;

-- Agent is deployed
SHOW AGENTS IN SCHEMA <target_db.target_schema>;

-- Test the 5 success criteria questions against the agent
```

Run each `success_criteria` question through the agent manually or via
`cortex analyst query` and confirm answers are reasonable.

**⚠️ STOPPING POINT:** Present verification results. If success criteria pass,
proceed to handoff. If not, continue `cortex-agent-optimization` iterations.

**Next:** Load `phases/handoff/SKILL.md`.
