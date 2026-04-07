---
name: cortex-accelerator-handoff
description: "Phase 7 of cortex-accelerator. Post-deployment handoff: sets up
  schema drift monitoring via KG watch, configures ops monitoring via
  si-ops-monitoring, schedules optimization runs, and hands off to the customer."
parent_skill: cortex-accelerator
---

# Phase 7: Handoff

The agent is deployed and passing success criteria. This phase sets up the
ongoing health infrastructure so the semantic layer doesn't decay silently.

## Step 1: Schema Drift Monitoring (KG Watch)

If the KG path was used, activate the watch service:

```sql
-- Enable KG watch for schema drift detection
CALL KG_BOOTSTRAP_DB.PUBLIC.RUN_WATCH();
```

If KG was not used, set up a lightweight drift check task:

```sql
CREATE OR REPLACE TASK SEMANTIC_LAYER_DRIFT_CHECK
  WAREHOUSE = <warehouse>
  SCHEDULE = 'USING CRON 0 6 * * 1 UTC'  -- weekly Monday 6am
AS
-- Check if any tables in the domain map have had schema changes
SELECT TABLE_NAME, LAST_ALTERED, COLUMN_COUNT
FROM INFORMATION_SCHEMA.TABLES
WHERE TABLE_NAME IN (<tables_from_domain_map>)
  AND LAST_ALTERED > DATEADD(day, -7, CURRENT_TIMESTAMP());
```

Alert the SE/customer team if tables in the semantic layer are altered.

## Step 2: Ops Monitoring

Invoke `si-ops-monitoring` skill to set up:
- Agent health checks (latency, error rate, query success rate)
- Alerting thresholds (email/Slack on degraded performance)
- Baseline capture (capture current performance metrics as the baseline)
- Runbook generation for common failure modes

Pass the deployed agent name and the 5 `success_criteria` questions as the
monitoring baseline — if the agent stops answering these correctly, alert fires.

## Step 3: Optimization Schedule

Set the expectation for the next `cortex-agent-optimization` run:

```
Recommended: re-run cortex-agent-optimization after:
  • 30 days (new query patterns may emerge)
  • Any significant schema change in source tables
  • After adding a new domain to the semantic layer
  • If agent accuracy drops below the success criteria bar
```

Create a reminder or document this in the customer handoff notes.

## Step 4: Customer Handoff Summary

Produce a concise handoff document:

```
CORTEX ACCELERATOR — HANDOFF SUMMARY
=====================================
Customer: <name>
Date: <date>
SE: <name>

WHAT WAS BUILT
  Domains: CRM, Finance, Operations
  Semantic Views: 3 (one per domain)
  Cortex Agent: ANALYTICS_AGENT (ANALYTICS_DB.PUBLIC)
  Ontology Layer: ANALYTICS_DB.ONTOLOGY schema

HOW TO ACCESS
  Agent endpoint: <endpoint>
  Test with: cortex analyst query "your question" --view=...
  Admin role: ANALYTICS_ADMIN

SUCCESS CRITERIA (all passing ✅)
  1. "What was revenue last quarter by region?" ✅
  2. "Which customers are at risk of churning?" ✅
  3. "Top 10 products by margin this year?" ✅
  4. "Show pipeline by rep for this quarter" ✅
  5. "What's our customer acquisition cost by channel?" ✅

KNOWN LIMITATIONS
  • 6 columns flagged LOW_CONFIDENCE — review labels in CRM semantic view
  • ORDERS relationships are inferred (not FK-confirmed) — validate join results
  • Marketing domain excluded — insufficient data quality (score: 31)

MAINTENANCE
  • Schema drift monitor: running weekly (SEMANTIC_LAYER_DRIFT_CHECK task)
  • Ops monitoring: configured via si-ops-monitoring
  • Next optimization run: recommended in 30 days

DOMAIN MAP
  Saved at: validated_domain_map.json
  Back up this file — it is the source of truth for the semantic layer design.
```

**⚠️ STOPPING POINT:** Review handoff summary with customer/SE.

## Done

The `cortex-accelerator` workflow is complete. The domain map is the persistent
artifact — save it alongside the Snowflake objects. Future rebuilds or expansions
should start from Phase 5 (validate) using the existing domain map as the base.
