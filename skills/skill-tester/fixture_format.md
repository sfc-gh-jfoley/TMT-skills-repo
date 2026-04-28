---
name: skill-tester-fixture-format
description: YAML schema for skill test fixtures — defines inputs, stopping-point responses, and assertions
---

# Fixture Format

## Purpose

A fixture defines everything needed to run a skill without interactive user input:
1. **inputs** — what to provide to the skill at each phase (skill-specific)
2. **stopping_point_responses** — how to answer each mandatory stop
3. **assertions** — what to verify in the output

---

## Schema

```yaml
# Required metadata
skill: <skill-name>                        # name of the skill to test
scenario: <descriptive-name>               # human-readable test scenario name
connection: <snowflake-connection-name>    # Snowflake connection (if skill uses one)
description: "What this fixture tests"

# Inputs passed to the skill phases
# These are SKILL-SPECIFIC — there are no prescribed field names.
# Provide whatever the target skill's Phase 1 normally asks for.
inputs:
  # Examples vary by skill:
  #
  # semantic-view-ddl:
  #   sv_name: ORDERS_SV
  #   sv_db: SALES_DB
  #   sv_schema: PUBLIC
  #   tables: [SALES_DB.PUBLIC.ORDERS, SALES_DB.PUBLIC.CUSTOMERS]
  #   business_context: "Order analytics for the sales team"
  #
  # coco-usage:
  #   connection: snowhouse
  #   lookback_days: 30
  #
  # artifact-drift-monitor:
  #   artifact_type: SV
  #   artifact_fqn: MARKETING_DB.PUBLIC.CAMPAIGNS_SV
  #   lookback_days: 90
  #
  # rule-creator:
  #   rule_domain: "Python"
  #   rule_topic: "logging best practices"
  #   rule_range: "200-299"

# Responses injected at each STOPPING POINT
# Keys are descriptive labels — match them to the ⚠️ STOPPING POINT labels in the skill.
# Use "yes" as a default accept if no specific response needed.
stopping_point_responses:
  phase_1_confirm: "yes"
  phase_N_review: "ok"        # replace N with the actual phase number
  phase_N_execute: "go"
  phase_N_result: "accept"

# Output artifact name field (optional)
# If the skill creates a named Snowflake object, specify which inputs key holds the base name.
# The runner appends _TEST_1, _TEST_2, _TEST_3 to avoid collisions across 3 runs.
# If omitted, runs are named RUN_1, RUN_2, RUN_3.
output_name_field: null        # e.g. "sv_name" for semantic-view-ddl

# Expected result schema (optional)
# If the skill's output has well-known fields, list them here so the runner
# knows what to extract from each subagent's result JSON.
# If omitted, the runner uses generic defaults: skill_completed, phases_executed,
# phase_errors, primary_output, output_artifact_name, warnings.
result_schema:
  skill_completed: bool
  phases_executed: list
  phase_errors: list
  primary_output: string
  output_artifact_name: string
  warnings: list
  # Add skill-specific fields as needed:
  # ddl_executes: bool
  # report_sections: list
  # objects_created: int

# Fields to compare across 3 runs for consistency scoring (optional)
# If omitted, consistency is scored using primary_output length.
consistency_fields:
  # - field: primary_output
  #   weight: 1.0
  #   tolerance: 10%     # max % difference before penalizing

# Skill-specific assertions (evaluated after all phases complete)
skill_assertions:
  # Generic assertions apply to every skill automatically — no need to list them:
  #   skill_completed: true
  #   no_phase_errors: true
  #   output_not_empty: true
  #
  # Add skill-specific checks here. All assertion types are supported:
  #   boolean:    my_check: true
  #   numeric:    object_count: ">= 3"
  #   rate:       pass_rate: ">= 0.5"
  #   string:     output_contains: "EXPECTED_STRING"

# Cleanup — whether to drop Snowflake objects after testing
cleanup:
  drop_after_test: false       # keep for inspection
  output_suffix: "_TEST"       # appended to artifact names to avoid collisions
```

---

## Minimal fixture (read-only skill — no Snowflake object created)

```yaml
skill: coco-usage
scenario: 30day_summary
connection: snowhouse
description: "Verify 30-day spend summary runs without error"

inputs:
  lookback_days: 30

stopping_point_responses:
  phase_1_confirm: "yes"

skill_assertions:
  output_not_empty: true
  output_contains: "credits"
```

---

## Full fixture (write skill — creates a Snowflake object)

```yaml
skill: semantic-view-ddl
scenario: tpch_orders
connection: default
description: "TPC-H order analytics SV — 3 tables, standard relationships"

inputs:
  sv_name: TPCH_ORDER_ANALYTICS
  sv_db: SNOWFLAKE_SAMPLE_DATA
  sv_schema: TPCH_SF1
  tables:
    - SNOWFLAKE_SAMPLE_DATA.TPCH_SF1.ORDERS
    - SNOWFLAKE_SAMPLE_DATA.TPCH_SF1.LINEITEM
    - SNOWFLAKE_SAMPLE_DATA.TPCH_SF1.CUSTOMER
  business_context: "Order analytics — track order value, line item details, customer segments"

output_name_field: sv_name

stopping_point_responses:
  phase_1_confirm: "yes"
  phase_2_description_review: "yes"
  phase_3_classification: "ok"
  phase_4_relationships: "ok"
  phase_5_ddl_review: "go"
  phase_6_result: "accept"
  phase_7_verified_queries: "yes"

result_schema:
  skill_completed: bool
  ddl_executes: bool
  describe_tables: int
  describe_facts: int
  describe_dimensions: int
  describe_metrics: int
  describe_relationships: int
  descriptions_populated: int
  primary_output: string

consistency_fields:
  - field: describe_tables
    weight: 0.20
  - field: describe_relationships
    weight: 0.30
  - field: describe_facts
    weight: 0.25
  - field: describe_dimensions
    weight: 0.25

skill_assertions:
  ddl_executes: true
  describe_tables: ">= 3"
  describe_facts: ">= 4"
  describe_dimensions: ">= 6"
  describe_relationships: ">= 1"
  descriptions_populated: ">= 8"

cleanup:
  drop_after_test: false
  output_suffix: "_TEST"
```

---

## Adding overrides at stopping points

For testing edge cases, force specific behaviors:

```yaml
stopping_point_responses:
  # Reject first suggestion, request a change
  phase_2_description_review: "these descriptions are too vague, regenerate"

  # Override a specific classification
  phase_3_classification: "set VEHICLES.CONDITION_REPORT -> SKIP"
```

---

## Assertions syntax

| Format | Meaning |
|--------|---------|
| `true` | Must be true (boolean) |
| `false` | Must be false |
| `">= N"` | Value must be >= N |
| `"<= N"` | Value must be <= N |
| `"== N"` | Exact match |
| `"contains: 'text'"` | Output string must contain text |

---

## Naming convention

Fixture files: `<skill_name>_<scenario>.yaml`

Examples:
- `coco_usage_30day_summary.yaml` — read-only, 30-day spend
- `semantic_view_ddl_tpch.yaml` — write, TPC-H happy path
- `artifact_drift_monitor_sv_sf_ai_demo.yaml` — read-only, SV drift detection
- `rule_creator_python_domain.yaml` — write, rule creation
