---
name: cortex-accelerator-validate
description: "Phase 5 of cortex-accelerator. Hard gate before pipeline execution.
  Validates the domain map, checks performance flags, confirms success criteria,
  and requires explicit user approval. Nothing builds until this phase passes."
parent_skill: cortex-accelerator
---

# Phase 5: Validate — Hard Gate

**No pipeline runs until this phase passes.**

This phase has three parts: domain map validation, performance flags, and pre-build
summary with explicit user approval.

## Part A: Domain Map Validation

Check `validated_domain_map.json` for completeness:

```
REQUIRED — pipeline halts if any are missing or unresolved:
  ✅ All domains have at least 1 confirmed entity
  ✅ All BLOCKING conflicts have human_decision set
  ✅ All entity golden records identified (no UNKNOWN)
  ✅ At least 1 metric confirmed per domain
  ✅ success_criteria[] has at least 3 questions
  ✅ Target user role confirmed
  ✅ PII gaps resolved (masked or explicitly accepted)
  ✅ Access check passed (target role has SELECT on all tables)

WARNINGS — proceed with notification:
  ⚠ Relationships flagged INFERRED (not BI-confirmed)
  ⚠ Gaps with LOW_CONFIDENCE label
  ⚠ Metrics with FEDERATED resolution (multiple definitions)
  ⚠ Domains with no BI tool confirmation
```

If any REQUIRED item is missing: halt, tell the user exactly what's needed.

## Part B: Performance Flags

Check source tables for characteristics that will make the semantic layer slow or
unusable in practice — even if logically correct.

```sql
-- Large tables without clustering
SELECT TABLE_NAME, ROW_COUNT, TABLE_SCHEMA
FROM INFORMATION_SCHEMA.TABLES
WHERE ROW_COUNT > 100000000  -- 100M rows
  AND TABLE_NAME IN (<tables_in_domain_map>);

-- Check search optimization status
SELECT TABLE_NAME, SEARCH_OPTIMIZATION
FROM INFORMATION_SCHEMA.TABLES
WHERE TABLE_NAME IN (<tables_in_domain_map>);

-- Check clustering keys
SELECT TABLE_NAME, CLUSTERING_KEY
FROM INFORMATION_SCHEMA.TABLES
WHERE TABLE_NAME IN (<tables_in_domain_map>);
```

For flagged tables, surface recommendations — don't block, but be explicit:

```
⚠ PERFORMANCE WARNING: ORDERS table (2.1B rows, no clustering key)
  Semantic view queries on this table will be slow without clustering.
  Recommended: ALTER TABLE ORDERS CLUSTER BY (ORDER_DATE, REGION_ID);
  Or: Consider a pre-aggregated ORDERS_SUMMARY view as the semantic layer target.

  [ Add clustering before build ]  [ Continue anyway — I'll fix later ]
```

## Part C: Pre-Build Summary

Present the full summary before any SQL executes:

```
╔══════════════════════════════════════════════════════════╗
║              PRE-BUILD SUMMARY                           ║
╠══════════════════════════════════════════════════════════╣
║ DOMAINS (3)                                              ║
║   CRM: Customers, Accounts, Opportunities, Contacts      ║
║   Finance: Invoices, Payments, Revenue_Summary           ║
║   Operations: Orders, Shipments, Products                ║
╠══════════════════════════════════════════════════════════╣
║ METRICS (8)                                              ║
║   revenue → finance.net_revenue (canonical)              ║
║   crm_attributed_revenue (federated)                     ║
║   customer_count, order_count, avg_order_value...        ║
╠══════════════════════════════════════════════════════════╣
║ RELATIONSHIPS (11)                                       ║
║   7 BI-confirmed (PowerBI)  4 inferred from joins        ║
╠══════════════════════════════════════════════════════════╣
║ PIPELINE PATH                                            ║
║   CRM score 61 → KG enrichment → VQR → ontology-builder ║
║   Finance score 78 → VQR direct → ontology-builder      ║
╠══════════════════════════════════════════════════════════╣
║ SUCCESS CRITERIA (5 questions)                           ║
║   1. "What was revenue last quarter by region?"          ║
║   2. "Which customers are at risk of churning?"          ║
║   3. "Top 10 products by margin this year?"              ║
║   4. "Show pipeline by rep for this quarter"             ║
║   5. "What's our customer acquisition cost by channel?"  ║
╠══════════════════════════════════════════════════════════╣
║ WARNINGS (3)                                             ║
║   ⚠ ORDERS has 4 inferred relationships                  ║
║   ⚠ 6 columns flagged LOW_CONFIDENCE                     ║
║   ⚠ ORDERS table 2.1B rows — clustering recommended      ║
╠══════════════════════════════════════════════════════════╣
║ EXCLUDED (23 staging/dormant tables)                     ║
╚══════════════════════════════════════════════════════════╝

This build will create semantic views and deploy a Cortex Agent.
All DDL runs inside your Snowflake account.

[ Proceed with build ]  [ Go back and review ]  [ Export domain map only ]
```

**⚠️ MANDATORY STOPPING POINT:** Wait for explicit user approval.
Do NOT proceed until user selects "Proceed with build."

## Gate Status

Set `validation_status` in `validated_domain_map.json`:
- `APPROVED` — user confirmed, pipeline may proceed
- `PENDING` — awaiting user decision
- `BLOCKED` — unresolved blocking items

**Next (on APPROVED):** Load `phases/build/SKILL.md`.
