---
name: kg-data-discovery
description: "Knowledge Graph-powered data discovery using Cortex Search for dynamic schema assembly. Onboard new data sources, enrich with cost-tiered AI functions, index as domain CSSs, and query any data via natural language without pre-built Semantic Views. Use for **ALL** requests involving: data discovery, knowledge graph, crawl database, onboard data source, make data discoverable, index domain, what data do we have, explore data lake, find tables, dynamic semantic view, schema discovery. DO NOT attempt KG data discovery manually - invoke this skill first. Triggers: data discovery, knowledge graph, crawl database, onboard data, index domain, discoverable, explore lake, schema discovery, KG, dynamic SV, what tables."
---

# KG Data Discovery

A Knowledge Graph-powered data discovery system that makes any Snowflake data queryable via natural language — without pre-authoring Semantic Views. Uses Cortex Search (~100ms) over AI-enriched schema fragments to dynamically assemble minimal, perfectly-scoped schema context at query time.

## Two Complementary Layers

This skill handles the **discovery layer**. It complements (does not replace) curated Semantic Views:

| Layer | Purpose | When |
|-------|---------|------|
| **Curated SVs** | BI replacement, known KPIs, dashboards | "How are sales this week?" |
| **KG Discovery** (this skill) | Explore unknown data, cross-domain questions, new sources | "What device telemetry do we have?" |
| **Ontology Layer** (graduated) | Formal reasoning, entity hierarchy, cross-type queries | "What are all subtypes of Customer with orders > $10k?" |

Discovery graduates to curated SVs over time. Stable, FK-rich domains can graduate further to a full ontology stack via the **ontology-stack-builder** skill — the KG is the top of the funnel.

---

## STEP ZERO: Ask Mode (ALWAYS DO THIS FIRST)

Every invocation of this skill MUST begin by asking the user how they want to work. No detection, no guessing — just ask.

Use `ask_user_question`:
```
header: "Mode"
question: "How would you like to work?"
options:
  - label: "Just run it"
    description: "Point me at a database or domain and I'll handle everything automatically"
  - label: "Walk me through it"
    description: "I'll guide you step by step, explain what's happening, and let you make choices"
```

**One exception:** If the user's message starts with "execution mode" (from AGENTS.md), skip the question and use AUTOPILOT.

Remember the chosen mode for the entire session. NEVER ask again. If the user says "just do it" later in GUIDED mode, switch to AUTOPILOT immediately for remaining steps.

---

### AUTOPILOT Mode

**Contract:** User points, you run. Minimal output. No `ask_user_question` except for genuinely ambiguous targets (which database? which domain?).

**Behavior:**
- Execute procs directly via `snowflake_sql_execute`
- Print brief status lines: "Crawling 3 databases... 142 tables found. Enriching..."
- If something fails, fix it or report the error — don't ask what to do
- Skip optional steps (deep scan, task scheduling) unless user mentioned them
- At the end, print a summary table of what was created

**Autopilot flow (new account, no existing KG):**
1. Check prerequisites silently (fix warehouse/role issues if possible)
2. If user named a specific DB → skip DISCOVER, go straight to ONBOARD
3. If user said "everything" or "whole account" → run DISCOVER('SHALLOW', 7), pick PHASE_1 domains, onboard them all
4. CRAWL → ENRICH(0) → DETECT_RELATIONSHIPS → create CSS → validate
5. Print summary

**Autopilot flow (existing KG):**
1. Detect existing domains via `SHOW DATABASES LIKE '%_META'`
2. If user names a domain → refresh it (CRAWL → ENRICH → update CSS)
3. If user says "watch" or "what's new" → run RUN_WATCH(), print shadow report
4. If user says "add [X]" → onboard new domain into existing KG

**Autopilot flow (user names a specific database):**
1. `CALL DISCOVER_DOMAINS('SHALLOW', 7)` — but only to confirm the DB exists and get stats
2. Auto-name the domain (strip _DB/_DW/_PROD suffixes)
3. `CALL CONFIGURE_DOMAIN(name, ARRAY_CONSTRUCT('DB_NAME'))`
4. Bootstrap → CRAWL → ENRICH → RELATIONSHIPS → CSS → validate
5. Print summary

---

### GUIDED Mode

**Contract:** Interactive walkthrough. Use `ask_user_question` at every decision point. Explain what each step does before running it. Show results and ask if they look right before continuing.

**Behavior:**
- Use `ask_user_question` liberally — this is a conversation
- Explain each step in 1-2 sentences before executing
- Show results (tables, counts, proposed domains) and ask for confirmation
- Let the user skip, restart, or change direction at any point
- Reference the wizard checklist so they always know where they are

**Guided flow (new user):**

**Step 0 — Prerequisites:**
Run prereq checks. If issues found, explain each one and how to fix it. If all good, confirm and continue.

**Step 1 — Discover:**
```
ask_user_question:
  header: "Scan depth"
  question: "I'll scan your account to find what data you have. How far back should I look at query history?"
  options:
    - label: "Last 7 days"
      description: "Fast (~30s). Good enough to see what's actively used right now."
    - label: "Last 30 days"
      description: "More complete picture. Still interactive speed."
    - label: "Last 90 days"
      description: "Thorough but takes a few minutes. Catches seasonal patterns."
```

Run DISCOVER_DOMAINS with chosen lookback. Show the proposed domain table.

**Step 2 — Select domain:**
```
ask_user_question:
  header: "Domain"
  question: "Here are the domains I found. Which one do you want to onboard first? (Start with PHASE_1 for best results)"
  options: [dynamically built from DISCOVER results — top 4-6 domains]
```

**Step 3 — Configure:**
Confirm the domain name and source databases. Ask about enrichment tier:
```
ask_user_question:
  header: "Enrichment"
  question: "How much AI enrichment should I apply? More = better descriptions but costs credits."
  options:
    - label: "Free only (Tier 0)"
      description: "Pattern matching and metadata only. Zero AI cost. Good for well-documented data."
    - label: "Light AI (Tier 1)"
      description: "Adds AI classification for ambiguous columns. ~$0.001/column."
    - label: "Full AI (Tier 2)"
      description: "Generates descriptions for undocumented tables. ~$0.01/table."
```

**Steps 4-9 — Execute:**
For each step, briefly explain what's about to happen, run it, show the result, then ask:
```
ask_user_question:
  header: "Continue"
  question: "[Step result summary]. Ready to continue to [next step]?"
  options:
    - label: "Continue"
      description: "Proceed to the next step"
    - label: "Show me more detail"
      description: "I'll show the full output before continuing"
    - label: "Restart this step"
      description: "Run this step again (useful if you changed something)"
```

**Steps 10-11 — Optional:**
```
ask_user_question:
  header: "Deep scan"
  question: "Your domain is live! Want to schedule a deeper offline scan? It runs in the background and finds more cross-database patterns."
  options:
    - label: "Yes, 90 days"
      description: "Schedule background scan with 90-day lookback"
    - label: "Yes, full year"
      description: "Schedule background scan with 365-day lookback"
    - label: "Skip for now"
      description: "You can always run this later"
```

**At ANY point in guided mode, if the user says "just do it" or "run the rest" → switch to AUTOPILOT for remaining steps.**

---

## Session Prerequisites (Always First — Both Modes)

Before any operation, validate session state. Operations will fail without a valid environment.

1. Load `references/core-architecture.md` and `references/core-session.md`
2. Follow the Session Start Workflow (connection check, account profiling, existing KG detection)
3. Only proceed once target scope is confirmed (account, database, or domain)

**Context Management:**

- **Read references fully** when loading them, not just partial sections
- **Re-read references** at key workflow steps to ensure context is fresh
- If unsure of Cortex Search or Semantic View syntax, check `snowflake_product_docs` before executing DDL
- Use investigation diary methodology when Secondary/Advanced operations become complex

---

## Stored Procedures (Execute via snowflake_sql_execute)

All KG operations are implemented as stored procedures. The skill orchestrates them.

| Proc | Purpose | When |
|------|---------|------|
| `DISCOVER_DOMAINS('SHALLOW', 7)` | Fast domain discovery, 7-day lookback | First thing on any new account |
| `DISCOVER_DOMAINS('DEEP', 90)` | Deep scan with co-access clustering | Offline, for richer domain proposals |
| `SCHEDULE_DEEP_SCAN(90)` | Run deep scan as background task | When user doesn't want to wait |
| `ONBOARD_WIZARD()` | State-machine wizard, picks up where you left off | Guided mode entry point |
| `ONBOARD_WIZARD('STATUS')` | Show checklist with progress markers | Anytime |
| `ONBOARD_WIZARD('RESTART')` | Start over | When user wants a fresh start |
| `ONBOARD_WIZARD('RESTART', N)` | Restart from step N | When user wants to redo a specific step |
| `CONFIGURE_DOMAIN(name, dbs)` | Set domain name + source databases | Between DISCOVER and CRAWL |
| `CRAWL_DOMAIN()` | Three-level metadata harvest | Index plane |
| `ENRICH_DOMAIN(tier)` | Cost-tiered AI enrichment | Index plane |
| `DETECT_RELATIONSHIPS()` | FK + name-based join inference | Index plane |
| `REFRESH_DOMAIN(tier)` | Orchestrator: CRAWL→ENRICH→RELATIONSHIPS→sync | Scheduled or manual refresh |
| `RUN_WATCH()` | Shadow detection + drift + triage | Scheduled or manual |

**SQL files location:** `procs/sql/` (00-10, deploy in order)

---

## Routing Principles

1. **Mode first** — Detect AUTOPILOT vs GUIDED before anything else
2. **Session second** — Validate connection and detect existing KG state
3. **Primary wins ties** — If ambiguous between tiers, choose Primary
4. **Never suggest Advanced** — Only route to Advanced on explicit technical language
5. **Discover before onboard** — For brownfield accounts (hundreds+ tables), always run DISCOVER first
6. **Cost before enrich** — Show estimated AI function cost before running any enrichment (GUIDED only)
7. **Diary for complexity** — Use investigation diary methodology when operations become complex
8. **Mode switching** — If user says "just do it" during GUIDED, switch to AUTOPILOT immediately
9. **Ontology-first for graduated domains** — If a domain has an ontology layer (ONT_* tables + ontology agent), route queries to the ontology agent before attempting dynamic ASSEMBLE

**Confirmation checkpoint** (GUIDED mode only — skip in AUTOPILOT):

> "It sounds like you want to [detected intent]. Is that right, or were you looking for something else?"

---

## Primary Operations

These are the common operations users perform regularly. Route here confidently for any general data discovery request.

### Data Source Detection

If the user mentions a data source by name, route to ONBOARD with source-specific enrichment hints:

**Known source patterns:**
- **Shared databases** (Salesforce, Snowflake Marketplace, provider shares) — read-only, may need heavier AI enrichment for cryptic column names
- **dbt marts** (ANALYTICS, MART, WAREHOUSE schemas) — well-documented, light enrichment, rich comments
- **Raw lakes** (S3, Iceberg, VARIANT-heavy, JSON/Parquet) — deeply nested, undocumented, needs AI_COMPLETE tier
- **Operational replicas** (PostgreSQL, MySQL via replication/CDC) — normalized, lots of FKs, mostly free metadata
- **Third-party shares** (Marketplace datasets) — unknown schema, no control, full enrichment pipeline
- **Internal apps** (custom schemas, service account writes) — varies, check ACCESS_HISTORY for patterns

### Primary Routing Table

| User Language | Operation | Reference |
|---------------|-----------|-----------|
| Existing account, thousands of tables, what do we have, profile account, where to start, brownfield, assess | Discover Account | `references/discover-account.md` |
| Onboard, add data source, new domain, crawl database, make discoverable, index this | Onboard Domain | `references/onboard-domain.md` |
| Watch, shadow data, what's new, untracked tables, drift, ungoverned, not onboarded | Watch for Shadow Data | `references/watch-shadow-detection.md` |
| Deploy, CI/CD, pipeline, promote, version control, automate refresh | Deploy Pipeline | `references/deploy-pipeline.md` |
| Query, search, what data, find tables, explore, discover specific data | Query Discovery | `references/query-discovery.md` |
| Refresh, re-crawl, update, schema changed, new tables appeared | Maintain Domain | `references/maintain-domain.md` |
| Graduate, formalize, promote to ontology, build ontology stack, ontology layer, OWL, formal model, formal classes | Graduate to Ontology Layer | `references/ontology-integration.md` |

---

## Secondary Operations

Route here when user language contains explicit problem or operational indicators. These operations may become complex — consider using investigation diary methodology if they exceed 5-10 exchanges.

**Confirm before routing:**

> "It sounds like you're looking to [issue/need]. Would you like me to help with that?"

### Secondary Routing Table

| Explicit Indicators | Operation | Reference |
|---------------------|-----------|-----------|
| Enrich, classify columns, AI functions, improve descriptions, VARIANT paths, undocumented | Enrichment Tuning | `references/enrich-pipeline.md` |
| Cost, spending, budget, how much will this cost, AI function usage, credits | Cost Analysis | `references/enrich-cost-management.md` |
| Relationships, joins, cross-database, link domains, foreign keys, how tables connect | Relationship Mapping | `references/domain-relationships.md` |
| Assemble, build SV, dynamic semantic view, compose schema, on-the-fly | Schema Assembly | `references/query-schema-assembly.md` |
| Master KG, discover all domains, federated search, single search across everything | Master KG Setup | `references/domain-master-kg.md` |
| Domain boundaries, split domain, merge domains, reorganize, wrong grouping | Domain Restructuring | `references/domain-model.md` |
| Stale, unused tables, cleanup, what's not queried, dead data | Stale Data Analysis | `references/discover-account.md` |
| Shadow alerts, triage new tables, review drift report, what landed | Shadow Triage | `references/watch-shadow-detection.md` |

---

## Advanced Operations

Route here ONLY when user explicitly uses technical terminology. These users know what they're asking for. Do not suggest these operations to users who haven't asked.

Use investigation diary methodology for these operations — they are inherently complex.

### Advanced Routing Table

| Technical Language Required | Operation | Reference |
|-----------------------------|-----------|-----------|
| Concept extraction, concept granularity, concept row design, fragment structure | Concept Design | `references/advanced-concept-design.md` |
| RAP, row access policy, agent scoping, per-agent filtering, multi-tenant | Access Control | `references/advanced-access-control.md` |
| Feedback loop, query logging, concept usage tracking, self-improving KG | KG Optimization | `references/advanced-kg-optimization.md` |
| Micropartition metadata, clustering depth, overlap ratio, partition pruning signals | Physical Profiling | `references/discover-signals.md` |
| VARIANT path extraction, semi-structured profiling, nested JSON/Parquet interpretation | VARIANT Profiling | `references/enrich-variant-profiling.md` |
| Ontology classes, OWL, relations, abstract views, hierarchy, inference engine, cardinality | Ontology Layer | `references/ontology-integration.md` |

---

## Architecture Overview

```
DISCOVER (one-time)         INDEX PLANE (async)                QUERY PLANE (sync, <2s)
┌──────────┐               ┌────────┐  ┌─────────┐  ┌───────┐  ┌────────┐  ┌──────────┐  ┌───────┐  ┌──────┐
│0.DISCOVER│ → domains →   │1.CRAWL │→ │2.ENRICH │→ │3.INDEX│  │4.SEARCH│→ │5.ASSEMBLE│→ │6.QUERY│→ │7.EXEC│
│acct prof │               │metadata│  │AI-tiered│  │CSS per│  │KG ~100ms  │fragments │  │Analyst│  │SQL   │
│free SQL  │               │free SQL│  │cost-cap │  │domain │  └────────┘  └──────────┘  └───────┘  └──────┘
└──────────┘               └────────┘  └─────────┘  └───────┘
                                                        ↑              ↑
                           ┌──────────┐                 │              │ ontology layer present?
                           │  WATCH   │─── drift/shadow ─┘              ↓
                           │scheduled │    detection          ┌──────────────────────────┐
                           └──────────┘                       │ ONTOLOGY AGENT (skip     │
                                  │                           │ ASSEMBLE — route to      │
                                  │ stable + FK-rich domain   │ ontology-stack-builder   │
                                  ↓                           │ agent directly)          │
                           ┌──────────────────┐              └──────────────────────────┘
                           │  GRADUATE        │
                           │  → ontology-     │
                           │    stack-builder │
                           │  skill           │
                           └──────────────────┘
```

**Query plane routing detail:**
```
4.SEARCH returns domain + concept rows
    ↓
Check: does this domain have an ontology layer?
  SHOW TABLES LIKE 'ONT_%' IN SCHEMA {domain}_META.META → rows found?
  OR
  SHOW SEMANTIC VIEWS LIKE '{domain}_%_MODEL' IN SCHEMA {domain_db}.{schema}
    ↓ YES                           ↓ NO
Ontology agent path:          Dynamic assembly path:
Route to {domain}_AGENT       5.ASSEMBLE concept fragments
(created by ontology-         6.QUERY via Cortex Analyst
 stack-builder)               (existing behavior)
```

Load `references/core-architecture.md` for full step-by-step details.

---

## Concept Hierarchy

The KG indexes at **three levels** — databases, schemas, and tables — not just tables. Each level carries distinct signal that the others don't.

| Level | What the Concept Captures | Sources (All Free) |
|-------|--------------------------|---------------------|
| **Database** | Purpose, origin (share/clone/transient), owner, sub-domains, tool ecosystem, creation date | `SHOW DATABASES`, `DATABASES` view, `GRANTS_TO_ROLES` |
| **Schema** | Domain, data tier (raw/staging/mart), table groupings, access patterns, managed access flag | `SCHEMATA`, `OBJECT_DEPENDENCIES`, schema-level `GRANTS` |
| **Table** | Columns, types, grain, relationships, metrics, dimensions, sample values, clustering keys | `COLUMNS`, `TABLE_CONSTRAINTS`, `TABLE_STORAGE_METRICS`, sample queries |

When someone asks "what commerce data do we have?" — the schema-level concept answers directly. When someone asks "what databases does data science use?" — the database-level concept answers from grants. Table-level concepts provide the column-level detail for SQL generation.

The search corpus contains all three levels. The `concept_level` attribute on each row enables filtering: return only table-level concepts when assembling SQL context, return schema/database-level for exploration questions.

---

## Object State Model

Every database, schema, and table in the account is in one of these states. WATCH continuously classifies objects and routes them to the correct action.

| State | In KG? | Exists? | Metadata Current? | Action |
|-------|--------|---------|-------------------|--------|
| **Known & Current** | ✓ | ✓ | ✓ | Healthy — no action |
| **Known & Drifted** | ✓ | ✓ | ✗ (schema changed) | Re-crawl, delta enrich, flag for review |
| **Known & Deleted** | ✓ | ✗ | — | Mark concept inactive, exclude from search |
| **Onboarded Incorrectly** | ✓ | ✓ | Partial/wrong | Quality issue — re-enrich, validate, flag |
| **Shadow (Active)** | ✗ | ✓ | — (has query activity) | Alert, triage, recommend onboarding |
| **Shadow (Inactive)** | ✗ | ✓ | — (no query activity) | Log, monitor, may be temp/scratch |
| **Graduated (Ontology)** | ✓ | ✓ | ✓ + formal ontology | Queries route to ontology agent; KG concept rows remain as fallback |

### Detection Queries (All Free SQL)

```
Known & Current:       CONCEPTS ∩ ACCOUNT_USAGE.TABLES where metadata hash matches
Known & Drifted:       CONCEPTS ∩ TABLES where column_hash or row_count diverged
Known & Deleted:       CONCEPTS − TABLES (object dropped)
Onboarded Incorrectly: CONCEPTS where enrichment_quality_score < threshold
Shadow (Active):       TABLES − CONCEPTS where ACCESS_HISTORY shows recent reads
Shadow (Inactive):     TABLES − CONCEPTS where no ACCESS_HISTORY in N days
Graduated (Ontology):  CONCEPTS where domain_config.ontology_agent IS NOT NULL
```

The comparison runs at all three levels — new databases, new schemas, and new tables are each detected independently. A new schema in a production database is a higher-signal event than a new table in SCRATCH.

Load `references/watch-shadow-detection.md` for the full WATCH workflow, triage rules, and alert configuration.

---

## Domain Model

A **domain** is a logical grouping of one or more databases. Each domain gets:

```
DOMAIN_META.META.RAW_CONCEPTS          -- SQL-harvested metadata (DB, schema, and table level)
DOMAIN_META.META.CONCEPTS              -- AI-enriched, searchable (all three levels)
DOMAIN_META.META.RELATIONSHIPS         -- join paths (including cross-database)
DOMAIN_META.META.OBJECT_STATE          -- current state of every known + shadow object
DOMAIN_META.META.DOMAIN_SEARCH         -- CSS over CONCEPTS
DOMAIN_META.META.DOMAIN_CONFIG         -- enrichment settings, cost caps, ontology_agent ref
```

The `DOMAIN_CONFIG.ontology_agent` field (nullable) stores the FQN of the Cortex Agent created by ontology-stack-builder if this domain has been graduated. When set, query routing skips ASSEMBLE and routes to the ontology agent instead.

### Flexible Boundaries

```
-- Single database = single domain (default)
FINANCE.META.DOMAIN_SEARCH

-- Multi-database domain (e.g., multiple Salesforce shares)
SALESFORCE_META.META.DOMAIN_SEARCH     ← spans 4 share databases

-- Sub-domains within one database
ANALYTICS.META.SALES_SEARCH
ANALYTICS.META.MARKETING_SEARCH

-- Mixed
IOT_TELEMETRY.META.DOMAIN_SEARCH      ← whole DB
ANALYTICS.META.SALES_SEARCH            ← carved out schema
```

Convention: META schema, `*_SEARCH` CSS name. Master KG discovers via `SHOW CORTEX SEARCH SERVICES`.

Load `references/domain-model.md` for full domain design patterns.

---

## Cost-Tiered Enrichment Model

**Principle: exhaust free metadata before spending on AI. DISCOVER (Step 0) and CRAWL (Step 1) should extract 80%+ of the KG value at zero AI cost.**

```
         ╱╲
        ╱ $$$╲     AI_COMPLETE — VARIANT interpretation, cross-DB relationship
       ╱      ╲    inference, concept synthesis. BATCH. DELTA ONLY.
      ╱────────╲
     ╱  $$ mod  ╲   AI_EXTRACT — domain/purpose on undocumented tables
    ╱            ╲   (skip tables with existing comments)
   ╱──────────────╲
  ╱   $ cheap      ╲  AI_CLASSIFY — ambiguous column role detection
 ╱                  ╲  (skip obvious _ID, _DATE, AMOUNT patterns)
╱────────────────────╲
╱    FREE — SQL only    ╲ ACCOUNT_USAGE views, INFORMATION_SCHEMA, SHOW,
╱  DISCOVER + CRAWL      ╲ DESCRIBE, FLATTEN, micropartition metadata,
╱   80%+ of KG value      ╲ ACCESS_HISTORY, QUERY_HISTORY, OBJECT_DEPENDENCIES,
╱──────────────────────────╲ TABLE_STORAGE_METRICS, clustering info, sample values
```

**Ontology enrichment bonus:** If a domain has been graduated (ONT_* tables exist), the ENRICH phase can read class descriptions, relationship types, and property definitions directly from `ONT_CLASS`, `ONT_RELATION_DEF`, and `ONT_SHARED_PROPERTY` — substituting free structured metadata for AI_COMPLETE on the covered tables.

Load `references/enrich-pipeline.md` for tier details and cost math.

---

## Compound Requests

If the user describes multiple operations:

1. Create a todo list capturing all requested operations
2. Ask the user to confirm the order:

> "I've identified these tasks: [list]. What order would you like me to tackle them?"

3. Execute in confirmed order, completing each before moving to the next
4. Note: Some operations have natural dependencies (e.g., discover before onboard, onboard before query, crawl before enrich, onboard before graduate)

### Common Compound Patterns

**"Onboard and make queryable"** decomposes to:
1. ONBOARD → crawl + enrich + create CSS
2. Verify → test search quality with sample questions
3. Optionally DEPLOY → generate CI/CD config for ongoing maintenance

**"Set up discovery for the whole account"** decomposes to:
1. DISCOVER → profile account, propose domain boundaries, rank by priority
2. Review domain map with user, adjust boundaries
3. ONBOARD top 2-3 domains first (highest query volume / user count)
4. Verify → test search quality with sample questions
5. ONBOARD remaining domains in priority order
6. MASTER KG setup → create master CSS
7. DEPLOY → CI/CD for all domains + master refresh task

**"New data source just landed"** decomposes to:
1. Identify source type (share, lake, replica, etc.)
2. ONBOARD with source-specific enrichment hints
3. Link to existing domains → update RELATIONSHIPS
4. Update CI/CD config if DEPLOY pipeline exists

**"Make sure nothing slips through"** decomposes to:
1. WATCH → set up shadow detection task (scheduled diff at all 3 levels: databases, schemas, tables)
2. Configure triage rules:
   - Auto-ignore: SCRATCH schemas, temp/transient tables, tables with zero access in 30 days
   - Auto-alert: new databases, new schemas in production DBs, high-usage shadow tables
   - Auto-flag: known objects where metadata hash diverged (drift)
   - Quality check: concepts with low enrichment scores or missing descriptions
3. Review shadow report → triage each finding: onboard, ignore, defer, or re-enrich
4. Optionally connect alerts to Slack/email via notification integration
5. Optionally enable auto-onboard for trusted domains (new tables in onboarded schemas auto-crawl + enrich)

**"Formalize this domain" / "build ontology on [domain]"** decomposes to:
1. Verify domain is onboarded (`CONCEPTS` exists, CSS active, enrichment quality score >= threshold)
2. Read source tables from `DOMAIN_META.META.DOMAIN_CONFIG`
3. Read top concepts from `CONCEPTS` ordered by `query_count` → surface to ontology-stack-builder as candidate classes
4. Check for existing FK-based relationships in `RELATIONSHIPS` → surface as candidate ontology relations
5. Invoke skill `ontology-stack-builder` with source tables + concepts as enrichment context + business questions derived from top concept keywords
6. After ontology stack deployed, update `DOMAIN_CONFIG.ontology_agent` with the new agent FQN
7. Future queries for this domain → ontology agent (dynamic ASSEMBLE remains as fallback for uncovered concepts)

Load `references/ontology-integration.md` for the full graduation workflow, invocation context, and query routing changes.

---

## EMIT MANIFEST

At the end of any complete skill execution (ONBOARD, REFRESH, DISCOVER, or WATCH cycle), emit a structured JSON manifest. This manifest is the handoff artifact for downstream skills (`vqr-semantic-view-generator`, `ontology-stack-builder`, `cortex-agent-optimization`) and for `cortex ctx remember` persistence.

**When to emit:**
- After a successful ONBOARD (CSS created and validated)
- After a REFRESH cycle completes
- After DISCOVER if the user confirms domain boundaries (even before onboarding)
- On demand if the user says "show manifest", "emit manifest", or "what did you build?"

**Do NOT emit** for partial runs, failed steps, or query-only sessions.

Output the manifest as a labeled fenced block so downstream skills can parse it:

```
EMIT MANIFEST — kg-data-discovery
```

```json
{
  "domain": "<domain name, e.g. SALESFORCE, FINANCE, TELEMETRY>",
  "databases": ["<DB1>", "<DB2>"],
  "schemas": ["<DB1.SCHEMA1>", "<DB1.SCHEMA2>", "<DB2.SCHEMA1>"],
  "enrichment_path": "<tier_0 | tier_1 | tier_2 | mixed>",
  "fk_map": {
    "<TABLE_A>": ["<TABLE_B via COLUMN_X>", "<TABLE_C via COLUMN_Y>"],
    "<TABLE_B>": ["<TABLE_A via COLUMN_X>"]
  },
  "css_service": "<fully-qualified CSS name, e.g. SALESFORCE_META.META.DOMAIN_SEARCH>",
  "stability_score": "<0.0–1.0 float — ratio of Known & Current objects to total indexed>",
  "table_count": <integer — total table-level concepts indexed>
}
```

**Field guidance:**

| Field | What to populate |
|-------|-----------------|
| `domain` | The domain name set in `DOMAIN_CONFIG` |
| `databases` | All source DBs passed to `CONFIGURE_DOMAIN` |
| `schemas` | Schemas harvested during CRAWL (from `RAW_CONCEPTS` where `concept_level = 'schema'`) |
| `enrichment_path` | Tier used during ENRICH: `tier_0` (free SQL only), `tier_1` (+ AI_CLASSIFY), `tier_2` (+ AI_EXTRACT/COMPLETE), `mixed` (per-table variable) |
| `fk_map` | Top-N FK relationships from `RELATIONSHIPS` table — omit if empty, include up to 20 entries |
| `css_service` | FQN of the created Cortex Search Service — read from `DOMAIN_CONFIG.css_service_fqn` |
| `stability_score` | `(Known & Current count) / (total OBJECT_STATE count)` — 1.0 = fully stable, 0.0 = all shadow/drifted |
| `table_count` | `SELECT COUNT(*) FROM CONCEPTS WHERE concept_level = 'table'` |

After emitting, offer to persist the manifest to memory:

> "Manifest emitted. Want me to save this to `cortex ctx remember` so downstream skills can pick it up?"

If yes, run: `cortex ctx remember "<domain> KG manifest: css_service=<css_service>, table_count=<n>, enrichment=<enrichment_path>, stability=<stability_score>" --keywords kg-manifest <domain> css-service`

---

## Reference Index

### Core (Load at Session Start)

| Reference | Purpose |
|-----------|---------|
| `references/core-architecture.md` | Two-plane design, 8 steps (0-7), concept row DDL, end-to-end flow |
| `references/core-session.md` | Session start workflow, connection check, existing KG detection, scope confirmation |
| `references/core-investigation-diary.md` | Diary methodology for complex multi-step operations |

### Account Discovery

| Reference | Purpose |
|-----------|---------|
| `references/discover-account.md` | Account profiling workflow, domain clustering, priority ranking, rollout planning |
| `references/discover-signals.md` | Full ACCOUNT_USAGE signal inventory: schema, data shape, usage, governance |

### Domain Operations

| Reference | Purpose |
|-----------|---------|
| `references/domain-model.md` | Domain design patterns, flexible boundaries, META schema convention, config.yml schema |
| `references/domain-relationships.md` | Relationship table design, cross-database FK inference, join path resolution |
| `references/domain-master-kg.md` | Master CSS setup, federated search, domain auto-discovery via SHOW CORTEX SEARCH SERVICES |
| `references/onboard-domain.md` | Step-by-step onboarding: create META, crawl, enrich, create CSS, validate |
| `references/maintain-domain.md` | Delta refresh, schema drift detection, stale concept cleanup |
| `references/watch-shadow-detection.md` | Shadow data detection, drift monitoring, alert triage, auto-onboard rules |

### Enrichment

| Reference | Purpose |
|-----------|---------|
| `references/enrich-pipeline.md` | Cost tiers, AI function patterns, batch strategies, delta processing |
| `references/enrich-cost-management.md` | Cost math, budgeting, daily caps, monitoring AI spend, cost-per-table estimates |
| `references/enrich-variant-profiling.md` | VARIANT/semi-structured path extraction, FLATTEN patterns, nested JSON interpretation |

### Query & Assembly

| Reference | Purpose |
|-----------|---------|
| `references/query-discovery.md` | Search → assemble → query flow, prompt-based vs ephemeral SV approach, ontology-first routing |
| `references/query-schema-assembly.md` | Fragment deduplication, join resolution, minimal SV construction, context formatting |

### Ontology Integration

| Reference | Purpose |
|-----------|---------|
| `references/ontology-integration.md` | When to graduate a domain, invocation context for ontology-stack-builder, query routing with ontology detection, ONT_* as enrichment source, DOMAIN_CONFIG.ontology_agent field |

### CI/CD & Deployment

| Reference | Purpose |
|-----------|---------|
| `references/deploy-pipeline.md` | CI/CD config, repo structure, deploy scripts, config.yml schema, automated testing |

### Advanced (Load Only When Requested)

| Reference | Purpose |
|-----------|---------|
| `references/advanced-concept-design.md` | Concept granularity, row structure, keyword strategies, concept-per-table vs concept-per-question |
| `references/advanced-access-control.md` | Dual-layer RAP, AGENT_TOOL_MAP, CSS attribute filtering, multi-tenant scoping |
| `references/advanced-kg-optimization.md` | Query logging, concept usage feedback loops, auto-promotion to curated SVs |

### Reference Architecture

| Reference | Purpose |
|-----------|---------|
| `references/reference-whoop-arch.md` | Real-world 7-layer Cortex AI stack: CI/CD SVs, agent framework, auto-profiling, AI Coach |
| `references/reference-kg-router.md` | Existing KG Router implementation: single CSS, RAP scoping, crawl procs, agent integration |
