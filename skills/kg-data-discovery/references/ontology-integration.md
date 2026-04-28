# Ontology Integration Reference

How the kg-data-discovery skill delegates to the **ontology-stack-builder** skill to graduate a domain from dynamic discovery to a formal Ontology-on-Snowflake stack.

---

## When to Suggest Graduation

Suggest graduating a domain when ALL of these are true:

| Signal | How to Check |
|--------|-------------|
| Domain is fully onboarded | `DOMAIN_META.META.DOMAIN_CONFIG` exists, CSS is ACTIVE |
| High query volume | `CONCEPTS` rows have `query_count > 0` on most table-level concepts |
| FK-rich relationships | `RELATIONSHIPS` table has >= 3 rows for this domain |
| Stable schema | WATCH shows "Known & Current" for all objects (no drift in last 30 days) |
| Entity-centric questions | User's questions involve "types of", "hierarchy", "all subtypes", "relationships between" |

Graduation is **not** appropriate for:
- Raw lakes with VARIANT-heavy tables (no clear entity structure)
- Scratch/temp databases
- Domains with fewer than 3 source tables
- Domains that change schema frequently

**Graduation readiness check:**
```sql
SELECT
  d.domain_name,
  COUNT(DISTINCT c.table_name) AS table_count,
  SUM(c.query_count) AS total_queries,
  COUNT(DISTINCT r.source_table) AS fk_relationships,
  MAX(c.last_crawled_at) AS last_crawl
FROM DOMAIN_META.META.DOMAIN_CONFIG d
JOIN DOMAIN_META.META.CONCEPTS c ON c.domain = d.domain_name AND c.concept_level = 'TABLE'
LEFT JOIN DOMAIN_META.META.RELATIONSHIPS r ON r.domain = d.domain_name
GROUP BY d.domain_name
HAVING table_count >= 3 AND fk_relationships >= 2
ORDER BY total_queries DESC;
```

---

## Pre-Graduation: Build Invocation Context

Before invoking ontology-stack-builder, extract context from the KG to seed Phase 1 and Phase 2.

### 1. Source Tables

```sql
SELECT DISTINCT table_fqn
FROM DOMAIN_META.META.CONCEPTS
WHERE domain = '{domain_name}'
  AND concept_level = 'TABLE'
  AND is_active = TRUE
ORDER BY query_count DESC
LIMIT 20;
```

### 2. Business Questions (from top concept keywords)

```sql
SELECT keyword, COUNT(*) AS freq
FROM DOMAIN_META.META.CONCEPTS,
  LATERAL FLATTEN(input => PARSE_JSON(keywords_yaml)) kw
WHERE domain = '{domain_name}'
  AND concept_level = 'TABLE'
GROUP BY keyword
ORDER BY freq DESC
LIMIT 15;
```

Use the top 5-8 keywords to auto-generate natural-language business questions for ontology-stack-builder Phase 1. Example: keyword "customer_id" + "order_total" → "What are the total orders per customer?"

### 3. Existing Relationships (candidate ontology relations)

```sql
SELECT source_table, target_table, join_key_source, join_key_target, relationship_type
FROM DOMAIN_META.META.RELATIONSHIPS
WHERE domain = '{domain_name}'
ORDER BY confidence_score DESC;
```

These FK-based relationships map directly to ontology-stack-builder `relations.json` entries.

### 4. Check for Existing Semantic Views

```sql
SHOW SEMANTIC VIEWS IN DATABASE {source_database};
```

If any exist over the source tables, pass them to ontology-stack-builder Phase 1 as the base semantic view (it will use them as-is and skip Phase 4.5).

---

## Invoking ontology-stack-builder

Invoke the skill with the following context assembled from the KG:

```
skill: ontology-stack-builder

Phase 1 context to provide:
  - Database: {source_database}
  - Schema: {source_schema}
  - Source tables: [list from Pre-Graduation Step 1 above]
  - Business questions: [5-8 questions synthesized from top concept keywords]
  - Ontology name: {domain_name} (uppercase, short — e.g. FINANCE, COMMERCE)
  - Path: Ask user (KG path for graph analytics, Direct for lightweight)
  - Existing semantic views: [from SHOW SEMANTIC VIEWS, if any]

Phase 2 enrichment context (provide alongside schema introspection):
  - For each source table, provide concept row from CONCEPTS:
      table_fqn, description, keywords_yaml, join_keys_yaml, metrics_yaml
  - For each relationship, provide:
      source_table, target_table, join_key_source, join_key_target, relationship_type
  This replaces the need for AI_COMPLETE enrichment in Phase 2 — the KG already has it.

Note to ontology-stack-builder: "This domain is already indexed in the KG. The
  CONCEPTS table has {N} table-level concept rows with AI-enriched descriptions.
  The RELATIONSHIPS table has {M} inferred FK edges. Use these as ground truth for
  class/relation proposals rather than running schema introspection from scratch."
```

The ontology-stack-builder skill will handle Phases 1-7 interactively. The kg-data-discovery skill's role is to:
1. Assemble and provide the invocation context above
2. Observe the 7-phase workflow
3. After Phase 7 validation completes → post-graduation steps below

---

## Post-Graduation Steps

After ontology-stack-builder completes successfully:

### 1. Update DOMAIN_CONFIG

```sql
UPDATE DOMAIN_META.META.DOMAIN_CONFIG
SET
  ontology_agent = '{DATABASE}.{SCHEMA}.{ONTOLOGY_NAME}_AGENT',
  ontology_deployed_at = CURRENT_TIMESTAMP(),
  ontology_path = '{KG|DIRECT}',
  ontology_database = '{DATABASE}',
  ontology_schema = '{SCHEMA}'
WHERE domain_name = '{domain_name}';
```

### 2. Update Object State

```sql
UPDATE DOMAIN_META.META.OBJECT_STATE
SET state = 'GRADUATED'
WHERE domain = '{domain_name}';
```

### 3. Verify Query Routing

Test that the query plane now routes to the ontology agent:
```sql
-- Should return ontology_agent IS NOT NULL
SELECT domain_name, ontology_agent, ontology_deployed_at
FROM DOMAIN_META.META.DOMAIN_CONFIG
WHERE domain_name = '{domain_name}';
```

Run a sample natural-language query through the skill's QUERY operation and confirm it hits the ontology agent rather than ASSEMBLE.

---

## Query Routing With Ontology Detection

The QUERY operation (SEARCH → ASSEMBLE/ROUTE → QUERY) checks for ontology graduation before assembling context.

### Detection Logic

```sql
-- Step 1: SEARCH returns domain name from matched concept rows
-- Step 2: Check graduation status
SELECT ontology_agent
FROM DOMAIN_META.META.DOMAIN_CONFIG
WHERE domain_name = '{matched_domain}'
  AND ontology_agent IS NOT NULL;
```

### Routing Decision

```
SEARCH returns domain = '{domain_name}'
    ↓
SELECT ontology_agent FROM DOMAIN_CONFIG WHERE domain_name = '{domain_name}'
    ↓ row found (not null)          ↓ null / no row
Route to ontology agent:       Dynamic ASSEMBLE path:
  SNOWFLAKE.CORTEX.AGENT(        ASSEMBLE concept fragments
    '{ontology_agent}',           → build ephemeral SV context
    PARSE_JSON('{"messages":      → Cortex Analyst
    [{"role":"user",
      "content":"{question}"}]}')
  )
```

### Fallback

If the ontology agent returns an error or empty response, fall back to dynamic ASSEMBLE automatically. Log the fallback in `DOMAIN_META.META.QUERY_LOG` with `routing='ONTOLOGY_FALLBACK'`.

### Multi-Domain Queries

When a question spans multiple domains (SEARCH returns concepts from 2+ domains):
- If ALL matched domains are graduated → invoke each ontology agent and synthesize
- If SOME are graduated → use ontology agent for graduated domains, ASSEMBLE for others
- Combine results in the final response

---

## ONT_* Tables as Free Enrichment Source

When a domain is graduated, the ontology layer's metadata tables provide premium enrichment at zero AI cost. Use in the ENRICH phase's delta processing:

| ONT_* table | Maps to ENRICH tier | What it replaces |
|-------------|---------------------|------------------|
| `ONT_CLASS` | AI_EXTRACT (Tier 2) | Table purpose descriptions |
| `ONT_SHARED_PROPERTY` | AI_CLASSIFY (Tier 1) | Column role classification |
| `ONT_RELATION_DEF` | AI_COMPLETE (Tier 3) | Cross-table relationship inference |
| `ONT_INTERFACE` | AI_COMPLETE (Tier 3) | Abstract interface/contract patterns |

**Enrichment query (ONT_CLASS → CONCEPTS description update):**

```sql
UPDATE DOMAIN_META.META.CONCEPTS c
SET
  description = ont.description,
  enrichment_source = 'ONT_CLASS',
  enrichment_tier = 2,
  enrichment_cost_usd = 0
FROM {ontology_database}.{ontology_schema}.ONT_CLASS ont
WHERE c.table_name = ont._source_table
  AND c.domain = '{domain_name}'
  AND ont.description IS NOT NULL;
```

Run this before AI enrichment tiers during `ENRICH_DOMAIN()` for graduated domains. The delta enrichment proc should check `enrichment_source = 'ONT_CLASS'` and skip AI_EXTRACT for those rows.

---

## Lifecycle Summary

```
DISCOVER → profile account, identify domains
    ↓
ONBOARD → crawl + enrich + CSS (dynamic discovery active)
    ↓
WATCH → monitor stability, flag FK-rich + stable domains
    ↓ (graduation criteria met)
GRADUATE → invoke ontology-stack-builder:
  - KG provides source tables, concepts, relationships as input
  - ontology-stack-builder builds L1-L5 ontology stack
  - DOMAIN_CONFIG.ontology_agent updated post-graduation
    ↓
QUERY (graduated domain):
  - SEARCH identifies domain
  - Ontology agent handles query (formal reasoning, hierarchy, cross-type)
  - ASSEMBLE remains as fallback for edge cases
    ↓
MAINTAIN (graduated domain):
  - Schema changes → re-crawl KG AND notify ontology layer (manual review)
  - New tables → evaluate if they map to existing ontology classes
  - ONT_* used as free enrichment source on delta crawls
```

---

## Skill Dependency

The **ontology-stack-builder** skill must be present at `~/.snowflake/cortex/skills/ontology-stack-builder/`. Verify with:

```bash
ls ~/.snowflake/cortex/skills/ontology-stack-builder/SKILL.md
```

Invoke it via the standard CoCo skill invocation: `invoke skill ontology-stack-builder`
