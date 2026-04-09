# Reference Architecture: Whoop Cortex AI Stack

Real-world 7-layer production Cortex AI stack from a Snowflake customer. This architecture demonstrates how curated Semantic Views (static) work at scale — the KG Discovery layer (this skill) adds a dynamic complement.

## Account Profile

- Business Critical edition, AWS US-WEST-2
- ~51,500 L30 credits
- 20+ semantic views, 5+ Cortex Search Services
- Consumer-facing AI Coach product in production
- Custom agent management framework (AVA)

## Seven Layers

### Layer 1: Data Foundation

```
DATALAKE_PROD          → Raw ingested data (Airbyte, Fivetran)
POSTGRES_MART          → Replicated operational databases
ANALYTICS_INTERMEDIATE → dbt intermediate models
ANALYTICS_MART         → dbt mart models (source of truth)
ANALYTICS              → Production analytics (SVs, search services)
ANALYTICS_QA           → QA environment (mirrors ANALYTICS)
SCRATCH                → Developer sandbox schemas
```

dbt Cloud runs tiered warehouses (XS/M/L) for cost control. Monte Carlo monitors freshness and quality.

### Layer 2: Semantic Views via CI/CD

- ~9,700 CREATE SEMANTIC VIEW to QA, ~1,300 to PROD per 91-day window
- Deployed via CircleCI with `{{TARGET_DB}}` templating
- SQL files version-controlled with 4-10 synonyms per table, rich COMMENT blocks, explicit PRIMARY KEY, FACTS section
- Domain coverage: memberships, health, sleep, commerce, support, AI costs, app events, ML/firmware

### Layer 3: Cortex Search & RAG

- **Google Drive Knowledge Base:** Chunks indexed with `snowflake-arctic-embed-l-v2.0`, 50-minute refresh
- **Semantic View Catalog Search:** Agent-searchable catalog of all SV definitions
- **Agent Memory Search:** Conversation history for RAG context, ~48s refresh cycle

### Layer 4: Agent Framework (AVA)

Custom agent management platform with:
- `AGENTS` table — registry with versioning, draft/deployed states
- `AGENT_VERSIONS` — version-controlled configs (model, instructions, tools)
- `TOOLS` — tool registry (type, source_type, database/schema/object, environment)
- `AGENT_TOOLS` — many-to-many with ordinal ordering, spec overrides
- `MODELS_REGISTRY` — nightly catalog of available Snowflake models
- `MODEL_HISTORY` — tracks model add/remove/update events
- API function: `GET_AGENT_TOOLS_FOR_API(agent_id)` returns merged tool specs

### Layer 5: Semantic View Auto-Generation Agent

Automated agent that:
1. Takes base tables as input
2. Profiles columns (sample values, cardinality, enum detection)
3. Generates SV YAML with dimensions, facts, synonyms
4. Creates SV via `SYSTEM$CREATE_SEMANTIC_VIEW_FROM_YAML`
5. Stores YAML in searchable catalog
6. Runs integration tests across roles

Three environments: `PUBLIC`, `TEST_AGENT`, `TEST_CI`

### Layer 6: AI Coach (Consumer Product)

- Structured output scoring with AI_COMPLETE (5 dimensions: trust, understanding, utility, emotional, personal context)
- Cost tracking via SVs over OpenAI billing data
- Evaluation via Hex notebooks + Sigma dashboards

### Layer 7: Self-Service Analytics

- Analytics Genie (Cortex Analyst front-end) for business users
- Dynamic table pre-aggregations
- Sigma dashboards, Hex notebooks for data science

## Relevance to KG Discovery

This stack demonstrates **curated SVs at scale** (Layer 2) — the static layer. KG Discovery adds:

- **Layer 2.5 (Dynamic Discovery):** Makes data queryable without authoring SVs first
- **Layer 4.5 (Routing):** KG Router replaces hardcoded tool lists in agents with dynamic tool discovery
- **Graduation path:** Dynamic discovery → repeated patterns → auto-generated SV (Layer 5) → curated SV (Layer 2)

## Key Patterns to Adopt

1. **CI/CD for SVs** — Version control, QA→PROD promotion, templated database names
2. **Column profiling** — Automated `is_enum` and `sample_values` detection dramatically improves Cortex Analyst literal matching
3. **Catalog search** — Searchable catalog of all SVs enables agent self-discovery
4. **Multi-environment testing** — Role-level integration tests catch permission issues before production
5. **Agent framework** — Versioned configs with tool registry and model catalog
