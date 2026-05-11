# Phase 04 — Validate

Deploy DDL to Snowflake, verify all objects exist and return data, run the agent, and execute the post-graduation KG update.

---

## Step 1 — Deploy DDL

Ask the user:

```
Has the DDL from Phase 03 already been deployed to Snowflake?
  A) Yes — deployed manually (skip to Step 2)
  B) No — deploy it now (I'll run the SQL)
```

If deploying: execute `{slug}_ontology.sql` in full. On any error, fix and retry.

---

## Step 2 — Verify Views via Stored Procedure

```sql
CALL {SLUG_UPPER}_ONTOLOGY_DEMO.{SLUG_UPPER}_KG.SP_GENERATE_{SLUG_UPPER}_ONTOLOGY_VIEWS();
```

Expected: every row has `row_count > 0`. If any view returns 0 rows:
- Check that the underlying source table or KG_NODE seed data exists
- Fix the view definition or seed data and re-run

---

## Step 3 — Run the 3 WOW Demo Queries

Execute each of the 3 WOW queries from `{slug}_ontology.sql`. Each must return at least 1 row.

On empty result:
- Verify KG_NODE/KG_EDGE seed data covers the traversal path
- Add missing seed rows and re-run

---

## Step 4 — Verify ONT_GRAPH_STATS

```sql
SELECT stat_key, stat_value
FROM {SLUG_UPPER}_ONTOLOGY_DEMO.{SLUG_UPPER}_KG.ONT_GRAPH_STATS;
```

Expected: at least `total_nodes`, `total_edges`, `class_count`, `relation_count` rows present with non-zero values.

---

## Step 5 — Verify Agent Config

Check `{slug}_agent_config.yaml`:
- `sample_questions` contains exactly 3 entries with no placeholder text
- `semantic_model` path resolves to an existing Snowflake object:

```sql
SHOW SEMANTIC VIEWS LIKE '{domain}_360_SV'
IN SCHEMA {SLUG_UPPER}_ONTOLOGY_DEMO.{SLUG_UPPER}_KG;
```

If the Semantic View does not exist yet, note it as a follow-up action but do not block graduation.

---

## Step 6 — STOPPING POINT: Run Sample Agent Query

Test the agent with the first WOW question using `DATA_AGENT_RUN`:

```sql
SELECT SNOWFLAKE.CORTEX.DATA_AGENT_RUN(
    '{SLUG_UPPER}_ONTOLOGY_DEMO.{SLUG_UPPER}_KG.{SLUG_UPPER}_AGENT',
    [{'type': 'text', 'text': '{wow_question_1}'}]
);
```

> NOTE: `content` parameter must be an ARRAY of objects — `[{type, text}]` — NOT a plain string.

Acceptable outcomes:
- Returns a SQL result → success
- Returns a natural-language answer → success
- Returns a clarification question → acceptable, note it

Hard stop if: connection error, agent not found, or authentication failure. Fix the underlying issue before proceeding.

---

## Step 7 — Post-Graduation KG Update

Execute the following to mark this domain as graduated in the KG metadata layer:

```sql
-- 1. Record ontology agent FQN in DOMAIN_CONFIG
UPDATE {DOMAIN}_META.META.DOMAIN_CONFIG
SET config_value = PARSE_JSON('"{{SLUG_UPPER}}_ONTOLOGY_DEMO.{{SLUG_UPPER}}_KG.{{SLUG_UPPER}}_AGENT"'),
    updated_at = CURRENT_TIMESTAMP(),
    updated_by = CURRENT_USER()
WHERE config_key = 'ontology_agent';

-- 2. Mark all OBJECT_STATE rows for this domain as GRADUATED
UPDATE {DOMAIN}_META.META.OBJECT_STATE
SET object_state = 'GRADUATED',
    updated_at   = CURRENT_TIMESTAMP()
WHERE domain = '{domain_name}';

-- 3. Update DOMAIN_REGISTRY with graduation details
UPDATE KG_CONTROL.PUBLIC.DOMAIN_REGISTRY
SET status              = 'GRADUATED',
    ontology_agent      = '{SLUG_UPPER}_ONTOLOGY_DEMO.{SLUG_UPPER}_KG.{SLUG_UPPER}_AGENT',
    ontology_database   = '{SLUG_UPPER}_ONTOLOGY_DEMO',
    ontology_schema     = '{SLUG_UPPER}_KG',
    ontology_deployed_at = CURRENT_TIMESTAMP(),
    updated_at          = CURRENT_TIMESTAMP()
WHERE domain_name = '{domain_name}';
```

Verify routing is active:

```sql
SELECT config_value AS ontology_agent
FROM {DOMAIN}_META.META.DOMAIN_CONFIG
WHERE config_key = 'ontology_agent';
-- Must return non-null FQN
```

---

## Step 8 — Print Completion Summary

```
╔══════════════════════════════════════════════════╗
║         DEMO BUILD COMPLETE                      ║
╠══════════════════════════════════════════════════╣
║ Domain:        {domain_name}                     ║
║ Company:       {company_name}                    ║
║ Build path:    KG | DIRECT_TABLE                 ║
╠══════════════════════════════════════════════════╣
║ DDL file:      {output_dir}/{slug}_ontology.sql  ║
║ DDL lines:     {n}                               ║
║ KG_NODE rows:  {n}                               ║
║ KG_EDGE rows:  {n}                               ║
║ V_* views:     {n}                               ║
║ VW_ONT_ views: {n}                               ║
╠══════════════════════════════════════════════════╣
║ WOW Questions:                                   ║
║   1. {wow_question_1}                            ║
║   2. {wow_question_2}                            ║
║   3. {wow_question_3}                            ║
╠══════════════════════════════════════════════════╣
║ KG Status:     GRADUATED                         ║
║ Agent FQN:     {SLUG}_ONTOLOGY_DEMO.{SLUG}_KG.   ║
║                {SLUG_UPPER}_AGENT                ║
╚══════════════════════════════════════════════════╝
```

---

## Step 9 — Offer to Persist to Memory

```
Would you like me to save the graduation record to cortex ctx memory?

  cortex ctx remember "{domain_name} graduated: ontology_agent={FQN}, 
    table_count={n}, build_path={path}, wow_questions=[{q1}, {q2}, {q3}]"

Reply "yes" to save, or "no" to skip.
```
