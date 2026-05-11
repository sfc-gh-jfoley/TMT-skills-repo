# Phase 02 — Design

Map KG concepts and relationships to an ontology class hierarchy, define the join plan, identify WOW questions, and get explicit user approval before writing any files.

---

## Step 1 — Build Class Hierarchy

Using the enrichment context from Phase 01 (top 20 CONCEPTS, RELATIONSHIPS, optional `schema_summary.md`):

1. **Identify source systems** — group tables by source database. Each source database typically maps to 1–3 abstract ontology classes.
2. **Assign concrete classes** — each high-frequency table becomes a concrete class (leaf node). Naming: `PascalCase`, singular noun (e.g. `Customer`, `Order`, `NetworkElement`).
3. **Define abstract classes** — 6–15 top-level abstract classes that group concrete classes (e.g. `Party`, `Product`, `NetworkAsset`). 2–3 levels max.
4. **Populate `classes.json` schema** (written after approval):

```json
[
  {
    "class_id": "customer",
    "label": "Customer",
    "abstract": false,
    "parent": "party",
    "source_table": "DB.SCHEMA.CUSTOMERS",
    "pk_column": "customer_id",
    "key_columns": ["customer_id", "account_id", "segment"],
    "description": "End subscriber or enterprise account"
  }
]
```

Minimum: ≥ 25 entries. At least 6 abstract classes.

---

## Step 2 — Build Relationship Graph

Using RELATIONSHIPS rows from Phase 01 and optional `join_graph.md`:

1. **Map declared FKs** (confidence = 1.0, detection_method = CONSTRAINT) → mark `HIGH`
2. **Map inferred FKs** (confidence ≥ 0.7, detection_method = NAME_MATCH or AI_INFERRED) → mark `MEDIUM`
3. **Add semantic edges** where business logic implies a join even without a FK (e.g. `Order` → `Customer` via `account_id`) → mark `MEDIUM` or `LOW`
4. **Seed from `join_graph.md`** if present — upgrade confidence for matching pairs

`relations.json` schema (written after approval):

```json
[
  {
    "relation_id": "customer_has_order",
    "label": "has_order",
    "source_class": "customer",
    "target_class": "order",
    "source_column": "customer_id",
    "target_column": "customer_id",
    "cardinality": "ONE_TO_MANY",
    "confidence": "HIGH",
    "detection_method": "CONSTRAINT",
    "join_sql": "a.customer_id = b.customer_id"
  }
]
```

Minimum: ≥ 12 entries, ≥ 3 marked `HIGH`.

---

## Step 3 — Identify 3 WOW Questions

Select 3 questions from the Phase 01 business question list that best demonstrate the ontology's cross-system value. WOW criteria:

- Spans at least 2 source databases
- Would require a multi-table join that is currently "impossible" without the ontology
- Has a clear business punchline (revenue, churn, network impact, customer experience)

For each WOW question, sketch the graph traversal path:

```
WOW #1: "Which enterprise customers have open support tickets AND network 
         degradation alerts in the same region this week?"
Graph:   Customer → ServiceSubscription → NetworkElement → NetworkAlert
         Customer → SupportTicket
```

---

## Step 4 — Build System Mapping

`system_mapping.json` schema (written after approval):

```json
[
  {
    "source_system": "BSS_DB",
    "source_description": "Billing & subscriber management",
    "maps_to_classes": ["Customer", "Account", "Subscription", "Invoice"]
  }
]
```

---

## STOPPING POINT — Mandatory Approval Gate

Present the following summary to the user. **Do not write any files until the user explicitly approves.**

```
## Ontology Design Summary

### Class Hierarchy ({n} classes)
| Class | Type | Parent | Source Table |
|-------|------|--------|-------------|
| ...   | ...  | ...    | ...         |

### Relationship Graph ({n} relationships)
| Relationship | Type | Source → Target | Confidence |
|-------------|------|----------------|-----------|
| ...         | ...  | ...            | ...       |

### 3 WOW Questions
1. {question} — Graph: {A → B → C}
2. {question} — Graph: {A → B → C}
3. {question} — Graph: {A → B → C}

### Build Path: KG | DIRECT_TABLE
{justification}

---
Does this design look right? Reply "proceed" to write the design files, or 
describe any changes you'd like.
```

Accept revision requests and re-present until the user approves.

---

## Step 5 — Write Design Files (after approval)

Write to `{output_dir}`:

**`ontology/classes.json`** — full class hierarchy (≥25 entries)

**`ontology/relations.json`** — typed relationship graph (≥12 entries, ≥3 HIGH)

**`ontology/system_mapping.json`** — source system to class mapping

**`ontology/architecture_brief.md`** — contains:
- Executive summary (3–5 sentences)
- 3 WOW questions with graph traversal sketches
- Business narrative (what does this ontology enable?)
- Build path recommendation with justification
- ASCII or Mermaid diagram of the top-level class hierarchy

---

## Phase 02 Outputs

On completion:

```
Phase 02 complete:
  classes.json:         {n} classes ({n} abstract, {n} concrete)
  relations.json:       {n} relationships ({n} HIGH, {n} MEDIUM, {n} LOW)
  system_mapping.json:  {n} source systems mapped
  architecture_brief.md: written

Proceeding to Phase 03 — Build.
```
