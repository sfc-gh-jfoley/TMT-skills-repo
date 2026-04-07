---
name: cortex-accelerator-resolution
description: "Phase 4 of cortex-accelerator. Resolves gaps and conflicts via BI
  tool intake (Tableau, PowerBI, dbt) and targeted question interview. Updates
  trust scores with BI-confirmed boosts. Produces a draft domain map for Phase 5."
parent_skill: cortex-accelerator
---

# Phase 4: Resolution

Two tracks run in parallel — BI tool intake and targeted questions.
BI tools are processed first; they often eliminate questions entirely.

## Track A: BI Tool Intake

Ask the user which BI tools are in use. Load `references/bi-intake.md` for
detailed extraction instructions per tool.

**Quick reference:**

| Tool | What to ask for | What it resolves |
|------|----------------|-----------------|
| Tableau | `.twb` or `.twbx` workbook files | Metric definitions, dimension labels, domain groupings |
| PowerBI | `.pbix` file | Metric definitions (DAX), FK relationships, domain ownership |
| dbt | `schema.yml`, `sources.yml`, `metrics.yml` | Column docs, FK tests, canonical metrics, authoritative sources |

**For each artifact provided:**
1. Extract relevant fields (see `references/bi-intake.md`)
2. Match against open gaps and conflicts
3. Apply trust score boost per tool tier
4. Mark resolved items as `BI_CONFIRMED` — no question needed

**After BI intake, recount open items:**
```
Before BI intake: 34 gaps, 3 BLOCKING conflicts
After dbt schema.yml: 21 gaps resolved, 1 conflict resolved (dbt metrics matched Finance def)
Remaining: 13 gaps, 2 BLOCKING conflicts → targeted questions needed
```

## Track B: Targeted Question Interview

Load `references/question-library.md` for full question templates.

Only ask about items that:
1. Are still open after BI tool intake
2. Have HIGH impact (blocking, or affect >20% of queries)

**Interview rules:**
- Max 15 questions per session. Beyond that: accept defaults with LOW_CONFIDENCE flags.
- Always show evidence: "We see X used in 340 queries like this: [example]. What is it?"
- Always offer pre-populated choices based on scan signals, with free-text fallback.
- Always state the consequence of skipping: "If skipped, will be labeled 'Col A'."
- Group by domain: all CRM questions, then Finance, then others.

**Question priority order:**
1. BLOCKING conflicts (entity golden record, canonical keys)
2. Metric disambiguation (cryptic column names in aggregations)
3. Domain boundary decisions (ambiguous table clusters)
4. Temporal definition (which date column defines "monthly X")
5. Staging exclusion confirmation (auto-generated, just confirm)

**Interview opening:**
```
We have N questions remaining after reviewing your BI tools.
Estimated time: ~12 minutes.

Each answer resolves a gap that would otherwise produce LOW CONFIDENCE
or BLOCKED items in your semantic layer.

Questions you skip will use our best guess and be flagged for review.

[Start interview]  [Skip to summary — accept all defaults]
```

**Auto-handle without asking (just notify user):**
- Tables matching `%_TMP%`, `%_STAGING%`, `%_LOAD%`, `%_BACKUP%` → exclude
- Columns in <3 queries total → exclude, note in report
- Tables with 0 queries in 30 days → flag as dormant, exclude
- WHERE-only columns → auto-classify as dimension filter

## Audience & Intent Collection

This is separate from gap resolution. Ask regardless of BI tool coverage:

```
ask_user_question:
  header: "Audience"
  question: "Who will primarily use this agent?"
  options:
    - label: "Business users / executives"
      description: "Plain language, KPI-focused, no SQL knowledge"
    - label: "Analysts"
      description: "Technical users, comfortable with metrics and filters"
    - label: "Mixed"
      description: "Both business and technical users"
```

Then ask for the **5 questions this agent must answer correctly** — these become:
1. The acceptance bar for Phase 5 success criteria
2. The eval seed dataset for `cortex-agent-optimization`

```
"List the 5 business questions this agent must answer correctly.
 These define success. Examples:
 - 'What was our revenue last quarter by region?'
 - 'Which customers are at risk of churning?'
 - 'Show me the top 10 products by margin this year'"
```

## Phase 4 Output: Draft Domain Map

After BI intake + interview, produce the draft `validated_domain_map.json`.
See `references/domain-map-schema.md` for full schema.

Key sections that must be populated before Phase 5:
- `domains[]` — all confirmed with entity lists
- `metrics[]` — all confirmed or federated with canonical names
- `relationships[]` — all confirmed or flagged INFERRED
- `conflicts[]` — all with `human_decision` filled or `severity: NON_BLOCKING`
- `gaps_accepted[]` — any remaining gaps with `consequence` documented
- `success_criteria[]` — the 5 questions from audience intake
- `excluded_tables[]` — staging/dormant tables removed from scope

**⚠️ STOPPING POINT:** Present draft domain map summary to user for review.
```
DRAFT DOMAIN MAP SUMMARY
  Domains confirmed:          3
  Entities confirmed:         14
  Metrics confirmed:          8  (2 federated, 6 canonical)
  Relationships confirmed:    11  (7 BI-confirmed, 4 inferred)
  BLOCKING conflicts:         0/2 resolved  ← still open
  Gaps with LOW_CONFIDENCE:   6
  Excluded tables:            23

  Status: NOT READY — 2 blocking conflicts unresolved
```

Do not proceed to Phase 5 until all BLOCKING conflicts have `human_decision` set.

**Next:** Load `phases/validate/SKILL.md`.
