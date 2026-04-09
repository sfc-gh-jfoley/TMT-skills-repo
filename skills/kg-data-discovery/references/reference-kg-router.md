# Reference Architecture: KG Router

Existing Knowledge Graph Router implementation in SNOWFLAKE_INTELLIGENCE.KNOWLEDGE_GRAPH. This is the predecessor to the full KG Discovery system — a single-table, single-CSS knowledge graph for agent routing.

## Concept

A preprocessing/routing tool for Cortex Agents. Crawls all Semantic Views and Cortex Search Services in the account, AI-enriches them, and exposes them via one Cortex Search Service. Agents search KG first to discover which tools to use.

```
User Question → Agent calls KG_ROUTER_SEARCH first
  → Returns: domain, relevant concepts, source_tool_name
  → Agent then calls only the relevant Semantic View(s)
```

## Objects

| Object | Type | Purpose |
|--------|------|---------|
| CONCEPTS | Table (358 rows) | Business concepts extracted from all tools |
| CONCEPTS_SEARCHABLE | Table | Flat copy for CSS (no RAP) |
| TOOL_CATALOG | Table (45 tools) | Master registry of all agent tools |
| RELATIONSHIPS | Table (62 edges) | Cross-domain concept edges |
| AGENT_TOOL_MAP | Table | Maps agent_name + role to tool FQNs |
| KG_AGENT_SCOPE_RAP | Row Access Policy | RBAC + mapping table dual-layer scoping |
| CRAWL_SEMANTIC_VIEWS | Stored Proc (Python) | Crawls SHOW SEMANTIC VIEWS, AI enriches |
| CRAWL_SEARCH_SERVICES | Stored Proc (Python) | Crawls SHOW CORTEX SEARCH SERVICES, AI enriches |
| REFRESH_KG_AND_SEARCH | Stored Proc (SQL) | Master orchestrator: crawl + rebuild + relationships |
| REFRESH_KG_TASK | Task (SUSPENDED) | Daily CRON 6am ET |
| KG_ROUTER_SEARCH | Cortex Search Service | Single search over CONCEPTS_SEARCHABLE |
| KG_ROUTED_AGENT | Cortex Agent | Demo: 1 KG Search + 5 SVs |

## Key Technical Learnings

### CSS + RAP Limitation

CSS cannot be built on tables with RAPs that contain subqueries (EXISTS, IN with subquery).

**Workaround:** Maintain a flat CONCEPTS_SEARCHABLE table refreshed by task. CSS sources from this table. RAP only on the CONCEPTS table for direct SQL access.

### Agent Testing

`SNOWFLAKE.CORTEX.AGENT_RUN()` via SQL SELECT does **NOT** trigger tool orchestration. Agents must be tested via:
- Snowflake Intelligence UI
- REST API

### Dollar Quoting

Agent spec dollar-quoting: use `$$ $$` (not `$spec$`).

### AI Enrichment

AI_COMPLETE with `claude-3-5-sonnet` works well for:
- Domain classification from DDL
- Concept extraction from semantic view definitions
- Relationship inference between domains

## Dual-Layer RAP Design

- **Layer 1 (RBAC):** SYSADMIN/ACCOUNTADMIN see all rows
- **Layer 2 (Mapping):** Other roles see rows only if AGENT_TOOL_MAP has their role mapped to that tool
- RAP applied to: CONCEPTS.source_tool_name, TOOL_CATALOG.fully_qualified_name
- CONCEPTS_SEARCHABLE has NO RAP — CSS uses attribute filtering instead

## Evolution to KG Discovery

The KG Router is the routing layer. KG Discovery extends it to:

| KG Router (current) | KG Discovery (new) |
|---------------------|-------------------|
| Crawls SVs + CSS definitions | Crawls raw table metadata (INFORMATION_SCHEMA) |
| Concept = tool reference | Concept = schema fragment with columns, types, joins |
| Single CSS for all domains | CSS per domain + master CSS |
| Routes to existing tools | Assembles schema context on-the-fly |
| Requires pre-built SVs/CSS | Works with raw tables (no SVs needed) |

The KG Router continues to serve as the **tool discovery** layer. KG Discovery adds the **data discovery** layer beneath it.

## Reusable Patterns

1. **Crawl procs pattern:** SHOW + AI_COMPLETE for enrichment
2. **CONCEPTS table design:** concept_name, domain, search_content, source_tool_name
3. **CONCEPTS_SEARCHABLE:** Flat copy for CSS (RAP workaround)
4. **AGENT_TOOL_MAP:** Agent-to-tool mapping with role-based scoping
5. **REFRESH_KG_AND_SEARCH:** Orchestrator proc that crawls + rebuilds + refreshes
6. **REFRESH_KG_TASK:** Daily scheduled refresh with option to resume
