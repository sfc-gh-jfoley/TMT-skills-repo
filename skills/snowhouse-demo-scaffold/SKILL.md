---
name: snowflake-intelligence-accelerator-via-snowhouse
description: "Build Snowflake Intelligence setups for customers using Snowhouse metadata discovery. Use when: build SI, create intelligence agent, snowflake intelligence for [customer]. Triggers: intelligence accelerator, SI setup, build intelligence, snowhouse discovery, build SI for."
---

# Snowflake Intelligence Accelerator via Snowhouse

Build complete Snowflake Intelligence setups for any customer using autonomous discovery from Snowhouse metadata.

## Prerequisites

- **SNOWHOUSE connection** for metadata discovery (Session 1)
- **Demo account connection** for deployment testing (Session 2)

## Workflow Overview

```
User provides customer name
         ↓
Phase 1: Discovery (SNOWHOUSE)
    - Find customer accounts
    - Identify BI warehouses
    - Discover high-value objects
         ↓
Phase 2: Generation
    - Cluster into business domains
    - Generate 9 deployment scripts
         ↓
Phase 3: Deployment (Demo Account)
    - Run scripts in order
    - Generate synthetic data
    - Verify setup
```

## Intent Detection

| Intent | Triggers | Action |
|--------|----------|--------|
| DISCOVER | "build SI for [customer]", "find accounts for", "discover" | **Load** `discovery/SKILL.md` |
| GENERATE | "create scripts", "generate setup", "now generate" | **Load** `generation/SKILL.md` |
| DEPLOY | "deploy", "run scripts", "verify setup" | **Load** `deployment/SKILL.md` |
| FULL | "build snowflake intelligence for [customer]" | Start with `discovery/SKILL.md`, then flow through all phases |

## Quick Start

**Full workflow trigger:**
```
Build Snowflake Intelligence for [CUSTOMER_NAME]
```

This initiates the complete workflow starting with discovery.

## Two-Session Architecture

| Session | Connection | Phases |
|---------|------------|--------|
| 1 | SNOWHOUSE | Discovery + Generation |
| 2 | Demo Account | Deployment + Verification |

**Important:** CoCo connects to one account at a time. After generating scripts in Session 1, user must start a new session connected to their demo account for deployment.

## Output

Scripts generated in `example_[customer]/`:
```
example_[customer]/
├── for_the_customer/           # Hand over to customer
│   ├── 00_infrastructure.sql
│   ├── 01_semantic_views.sql
│   ├── 02_cortex_search.sql
│   ├── 03_support_functions.sql
│   ├── 04_agent_creation.sql
│   └── 05_verification.sql
└── for_your_demo_account/      # Internal testing only
    ├── 00_base_tables.sql
    ├── 01_synthetic_datagen.sql
    └── 02_complete_teardown.sql
```

## References

- `references/snowhouse-queries.md` - Discovery SQL queries
- `references/sql-patterns.md` - Semantic view, agent, procedure syntax

## Stopping Points

- After account list (user selects account)
- After BI warehouse identification (user confirms)
- After domain clustering (user approves domains)
- Before script generation (user approves plan)
- Before deployment (user switches to demo account session)
