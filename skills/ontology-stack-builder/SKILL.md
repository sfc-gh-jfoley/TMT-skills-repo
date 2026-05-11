---
name: ontology-stack-builder
description: >
  Build a production Ontology-on-Snowflake stack from a KG Data Discovery
  manifest or a set of source tables. Creates ONT_* analytical views, a
  Semantic View, and a Cortex Agent — entirely within the customer's Snowflake
  account. Graduates stable, FK-rich KG domains into a formal ontology layer.
triggers:
  - ontology
  - graduate KG domain
  - build ontology
  - ontology stack
  - knowledge graph to semantic view
  - formal entity model
---

# Ontology Stack Builder

## The Two-Layer Model

| Layer | What it does |
|-------|-------------|
| **KG** (kg-data-discovery) | Discovers that connections EXIST — finds join keys, detects FK patterns, assigns stability scores |
| **Ontology** (this skill) | Physically implements those connections as SQL views (ONT_*) — the actual joins |

KG and Ontology work **together**, not sequentially. KG finds the connections; this skill materializes them.

## What This Skill Produces

```
KG_EDGE (join conditions discovered by KG)
    ↓
ONT_<ENTITY_A>_<ENTITY_B> views  ← physical joins, one per KG_EDGE relationship
    ↓
SEMANTIC VIEW: <domain>_360_SV   ← built on ONT_* views, not raw tables
    ↓
CORTEX AGENT with two tools:
  cortex_search_tool  → KG domain CSS  (answers "what connections exist?")
  cortex_analyst_text_to_sql → Semantic View  (answers "calculate metrics")
```

## Two Entry Paths

| Path | When to use |
|------|-------------|
| **KG Graduate** | A kg-data-discovery domain has reached stability_score >= 3. KG_NODE and KG_EDGE are populated. |
| **Direct Table** | No KG — user provides source tables and describes join relationships directly. |

## Prerequisites
- SYSADMIN or equivalent role on target database
- Target DB/schema for ontology objects (ONT_* views land here)
- If KG Graduate path: KG_NODE, KG_EDGE, DOMAIN_CONFIG populated in source schema
- Warehouse (default: COMPUTE_WH)

## STEP ZERO: Detect Entry Path

Ask the user:

```
Which path are you taking?
  A) Graduate a KG domain — I have KG_NODE/KG_EDGE tables ready
  B) Start from source tables — I'll describe the joins myself
  C) Auto-detect — point me at a DB/schema and I'll figure it out
```

## Phases

→ [phases/01_intake.md](phases/01_intake.md) — Confirm inputs, validate KG tables or source tables exist
→ [phases/02_design.md](phases/02_design.md) — Present entity/join plan for approval before any DDL
→ [phases/03_build.md](phases/03_build.md) — Execute: ONT_* views → Semantic View → Cortex Agent
→ [phases/04_validate.md](phases/04_validate.md) — Verify all objects exist, run sample DATA_AGENT_RUN test

## Reference

→ [reference/input-contract.md](reference/input-contract.md) — Full input spec for both entry paths

## Notes
- All objects are created in the customer's Snowflake account. No Snowhouse required.
- ONT_* views must NOT have duplicate column names across joined tables.
- Semantic View facts/dimension aliases MUST match the underlying column name exactly.
- Agent uses DATA_AGENT_RUN — content must be array [{type,text}], not plain string.
