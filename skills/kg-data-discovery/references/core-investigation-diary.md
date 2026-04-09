# Investigation Diary

Structured methodology for tracking complex multi-step KG operations. Use when an operation exceeds 5-10 exchanges or involves troubleshooting.

## When to Use

- Onboarding a domain with 50+ tables
- Debugging enrichment quality issues
- Resolving cross-database relationship mapping
- Shadow data triage with many findings
- Any operation where you find yourself going back and forth

## Diary Structure

Start a diary entry with:

```
## Investigation: [Operation Name]
**Started:** [timestamp]
**Goal:** [what we're trying to achieve]
**Domain:** [domain name, if applicable]
**Status:** IN PROGRESS | BLOCKED | COMPLETE

### Findings Log
1. [timestamp] — [observation or action taken]
2. [timestamp] — [result or next step]
...

### Decisions Made
- [decision]: [rationale]

### Open Questions
- [ ] [question that needs answering]

### Blockers
- [blocker]: [workaround or escalation path]
```

## Diary Practices

1. **Log every SQL result** that changes your understanding of the problem
2. **Log every decision** with rationale (especially enrichment tier choices, domain boundary changes)
3. **Log every surprise** — unexpected schema patterns, missing data, permission issues
4. **Update status** when blocked or complete
5. **Reference diary entries** when resuming after interruption

## Example: Domain Onboarding Diary

```
## Investigation: Onboard SALESFORCE Domain
**Started:** 2026-03-26 10:00
**Goal:** Make Salesforce data queryable via KG discovery
**Domain:** SALESFORCE
**Status:** IN PROGRESS

### Findings Log
1. 10:00 — DISCOVER showed 4 share databases: SF_ACCOUNTS, SF_OPPORTUNITIES, SF_CONTACTS, SF_ACTIVITIES
2. 10:05 — Total tables: 127 across 4 databases. 89 have cryptic names (SF_ prefix pattern)
3. 10:10 — CRAWL complete. 127 table-level + 12 schema-level + 4 database-level concepts = 143 raw concepts
4. 10:15 — Free heuristics classified 45 tables (obvious patterns). 82 need AI enrichment.
5. 10:20 — AI_CLASSIFY (Tier 1) on 82 tables: 60 classified successfully, 22 need AI_EXTRACT
6. 10:25 — AI_EXTRACT (Tier 2) on 22 tables: all classified. Total enrichment cost: ~0.3 credits
7. 10:30 — CSS created. Testing search quality with 5 sample questions...
8. 10:35 — 4/5 questions returned relevant concepts. Question #3 missed OPPORTUNITY_LINE_ITEMS.

### Decisions Made
- Used Tier 2 max (no AI_COMPLETE needed): Salesforce schemas are denormalized enough
- Grouped all 4 share databases into one domain: they share FK patterns (ACCOUNT_ID, CONTACT_ID)
- Added ACCOUNT_ID as cross-database join key in RELATIONSHIPS

### Open Questions
- [ ] Should ACTIVITY_HISTORY be included? It's 50M rows and rarely queried.

### Blockers
- None
```

## Diary in Memory

For long-running investigations that may span sessions, save the diary to memory:

```
/memories/projects/active/kg-investigation-[domain]-[date].md
```

This ensures context survives session resets.
