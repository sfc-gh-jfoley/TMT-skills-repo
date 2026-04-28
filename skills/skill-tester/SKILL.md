---
name: skill-tester
description: Test CoCo skills end-to-end by running them with pre-defined fixture inputs and evaluating outputs against assertions. Modeled after agent-flag-tester — spawns 3 parallel runs, compares consistency, reports pass/fail per assertion.
triggers:
  - test skill
  - run skill test
  - skill test
  - verify skill works
  - skill tester
---

# Skill Tester

## When to use

Use after building or modifying a CoCo skill to verify it:
- Follows its phases correctly with pre-defined inputs
- Produces valid, consistent outputs across multiple runs
- Handles edge cases and error conditions

Modeled on the `agent-flag-tester` pattern: 3 parallel runs → compare consistency → assertion scoring → pass/fail report.

---

## How skills are tested

Skills have **interactive stopping points** where they normally wait for user input.
The tester bypasses these by injecting pre-defined responses from a **fixture file**.

Each test run spawns a subagent that:
1. Reads the target skill's phase files
2. Executes each phase using fixture-provided inputs at stopping points
3. At the end, runs assertions and returns a structured result

Three parallel runs catch:
- **Consistency failures**: same inputs, different DDL/outputs (indicates non-determinism)
- **Validity failures**: DDL that doesn't execute or fails DESCRIBE
- **Quality failures**: descriptions blank, wrong column counts, etc.

---

## Entry points

### Run tests against an existing fixture

**→ Load [test_runner.md](test_runner.md)**

Tell the runner which skill and fixture to use:
```
Test skill: semantic-view-ddl
Fixture: fixtures/semantic_view_ddl_cox_hol.yaml
Runs: 3
```

### Build a new fixture for a skill

**→ Load [fixture_format.md](fixture_format.md)**

### Understand assertions

**→ Load [assertions.md](assertions.md)**

---

## Available fixtures

All 36 fixture files in `fixtures/` are listed below — run any with: `"Run skill tester on fixtures/<filename>.yaml"`. To build a new fixture, load [fixture_format.md](fixture_format.md).

| Fixture file | Skill | Scenario |
|-------------|-------|---------|
| [fixtures/agent_flag_tester_3variant.yaml](fixtures/agent_flag_tester_3variant.yaml) | agent-flag-tester | 3-variant flag comparison — BASE/AGENTIC/FASTPATH_OFF |
| [fixtures/agent_flag_tester_3variant_comparison.yaml](fixtures/agent_flag_tester_3variant_comparison.yaml) | agent-flag-tester | Full 3-variant comparison with eval dataset build and winner recommendation |
| [fixtures/artifact_drift_monitor_sv_sf_ai_demo.yaml](fixtures/artifact_drift_monitor_sv_sf_ai_demo.yaml) | artifact-drift-monitor | SV drift — SF_AI_DEMO marketing SV, 90-day lookback |
| [fixtures/artifact_drift_monitor_dt_iot_telemetry.yaml](fixtures/artifact_drift_monitor_dt_iot_telemetry.yaml) | artifact-drift-monitor | DT schema drift — ATT_IOT_DEMO telemetry DT, 30-day lookback |
| [fixtures/bulk_rule_reviewer_staleness.yaml](fixtures/bulk_rule_reviewer_staleness.yaml) | bulk-rule-reviewer | STALENESS mode — all rules/*.md, 115pt threshold check |
| [fixtures/bulk_rule_reviewer_directory_scan.yaml](fixtures/bulk_rule_reviewer_directory_scan.yaml) | bulk-rule-reviewer | FULL mode review of Python rules subset (rules/200-*.md) |
| [fixtures/coco_usage_my_spend.yaml](fixtures/coco_usage_my_spend.yaml) | coco-usage | Personal spend today — connection detect, user ID resolve |
| [fixtures/coco_usage_30day_summary.yaml](fixtures/coco_usage_30day_summary.yaml) | coco-usage | 30-day credit and token spend summary |
| [fixtures/cortex_accelerator_discovery_to_gate.yaml](fixtures/cortex_accelerator_discovery_to_gate.yaml) | cortex-accelerator | Guided discovery Phases 0–5, produces validated_domain_map.json gate |
| [fixtures/cortex_accelerator_guided_discovery.yaml](fixtures/cortex_accelerator_guided_discovery.yaml) | cortex-accelerator | Guided mode from Phase 0 through domain map approval gate |
| [fixtures/cortex_agent_flags_discovery.yaml](fixtures/cortex_agent_flags_discovery.yaml) | cortex-agent-flags | Freshness check + present applicable flags for analyst agent |
| [fixtures/cortex_agent_flags_freshness_check.yaml](fixtures/cortex_agent_flags_freshness_check.yaml) | cortex-agent-flags | Freshness check + flag info lookup before agent configuration |
| [fixtures/cortex_agent_opt_setup.yaml](fixtures/cortex_agent_opt_setup.yaml) | cortex-agent-optimization | SETUP intent — scaffold workspace, eval split, ctx rules |
| [fixtures/cortex_agent_optimization_iterative.yaml](fixtures/cortex_agent_optimization_iterative.yaml) | cortex-agent-optimization | Supervised 2-iteration optimization loop |
| [fixtures/cortex_agent_optimization_dev_test_loop.yaml](fixtures/cortex_agent_optimization_dev_test_loop.yaml) | cortex-agent-optimization | Iterative DEV/TEST improvement loop for an existing agent |
| [fixtures/doc_reviewer_readme_full.yaml](fixtures/doc_reviewer_readme_full.yaml) | doc-reviewer | FULL mode README review — 6 dims/100pt, cross-ref + link tables |
| [fixtures/doc_reviewer_readme_audit.yaml](fixtures/doc_reviewer_readme_audit.yaml) | doc-reviewer | FULL mode README audit — 6-dimension, 100-point rubric |
| [fixtures/memory_organizer_consolidation.yaml](fixtures/memory_organizer_consolidation.yaml) | memory-organizer | Organize and consolidate /memories directory |
| [fixtures/plan_reviewer_full_mode.yaml](fixtures/plan_reviewer_full_mode.yaml) | plan-reviewer | FULL mode plan review — 8 dims/100pt, Priority 1 compliance |
| [fixtures/prompt_determinism_tester_single_prompt.yaml](fixtures/prompt_determinism_tester_single_prompt.yaml) | prompt-determinism-tester | Single prompt SUGGEST mode determinism test |
| [fixtures/query_cortex_agent_single_question.yaml](fixtures/query_cortex_agent_single_question.yaml) | query-cortex-agent | Single question via DATA_AGENT_RUN |
| [fixtures/release_change_monitor_bcr_scan.yaml](fixtures/release_change_monitor_bcr_scan.yaml) | release-change-monitor | Full BCR bundle scan against account pipelines |
| [fixtures/rule_creator_snowflake_rule.yaml](fixtures/rule_creator_snowflake_rule.yaml) | rule-creator | Create Snowflake Hybrid Tables rule — 5 phases, schema validation |
| [fixtures/rule_creator_python_domain.yaml](fixtures/rule_creator_python_domain.yaml) | rule-creator | Python logging best practices rule in the 200-299 range |
| [fixtures/rule_loader_task_context.yaml](fixtures/rule_loader_task_context.yaml) | rule-loader | Load rules relevant to a Python ETL pipeline task |
| [fixtures/rule_reviewer_full_mode.yaml](fixtures/rule_reviewer_full_mode.yaml) | rule-reviewer | FULL mode review — 8 dims/115pt scale, line ref verification |
| [fixtures/self_healing_pipeline_task_failure.yaml](fixtures/self_healing_pipeline_task_failure.yaml) | self-healing-pipeline | Build agent monitoring a Snowflake task DAG for failures |
| [fixtures/semantic_view_ddl_cox_hol.yaml](fixtures/semantic_view_ddl_cox_hol.yaml) | semantic-view-ddl | Cox Automotive HOL — 5 tables, dealer/vehicle analytics |
| [fixtures/semantic_view_ddl_governance_mtt.yaml](fixtures/semantic_view_ddl_governance_mtt.yaml) | semantic-view-ddl | Governance MTT scenario |
| [fixtures/semantic_view_ddl_governance_pii.yaml](fixtures/semantic_view_ddl_governance_pii.yaml) | semantic-view-ddl | Governance PII scenario |
| [fixtures/semantic_view_ddl_tpch.yaml](fixtures/semantic_view_ddl_tpch.yaml) | semantic-view-ddl | TPC-H order analytics |
| [fixtures/skill_tester_meta_test.yaml](fixtures/skill_tester_meta_test.yaml) | skill-tester | Meta-test: run skill-tester against coco_usage_my_spend fixture |
| [fixtures/skill_timing_single_skill.yaml](fixtures/skill_timing_single_skill.yaml) | skill-timing | Time single skill execution with start/checkpoint/end |
| [fixtures/snowflake_ml_container_runtime_xgboost.yaml](fixtures/snowflake_ml_container_runtime_xgboost.yaml) | snowflake-ml-container-runtime | Train XGBoost classifier in Container Runtime (CPU) |
| [fixtures/sql_table_extractor_query_file.yaml](fixtures/sql_table_extractor_query_file.yaml) | sql-table-extractor | Extract tables/columns from a SQL file |
| [fixtures/vqr_semantic_view_generator_domain.yaml](fixtures/vqr_semantic_view_generator_domain.yaml) | vqr-semantic-view-generator | Generate domain SVs from sql-table-extractor JSON manifest |

---

## Quick start

"Run skill tester against semantic-view-ddl using the Cox HOL fixture, 3 runs."

→ Loads test_runner.md → spawns 3 parallel subagents → returns consolidated report
