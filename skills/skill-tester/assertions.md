---
name: skill-tester-assertions
description: Assertion evaluation library for skill test results — evaluates numeric, boolean, string, and rate assertions
---

# Assertions Library

## Purpose

After each test run returns a result JSON, evaluate assertions from the fixture.

---

## Generic assertions (auto-applied to every skill)

These three assertions apply to every run regardless of skill. The test runner evaluates them automatically — do NOT re-list them in `fixture.skill_assertions`.

| Assertion | How to evaluate |
|-----------|----------------|
| `skill_completed` | `result["skill_completed"] == true` |
| `no_phase_errors` | `result["phase_errors"]` is empty |
| `output_not_empty` | `result["primary_output"]` is non-null and non-empty |

---

## Skill-specific assertion types

These come from `fixture.skill_assertions` and are evaluated against fields in the result JSON returned by each subagent run.

The subagent is responsible for populating the result fields declared in `fixture.result_schema`. Evaluate each assertion by looking up the field in the result and applying the operator.

### Boolean assertions

```yaml
ddl_executes: true
governance_panel_shown: false
phase_4_reached: true
```

Evaluate: `result[key] == expected_value`

---

### Numeric comparison assertions

```yaml
object_count: ">= 3"
describe_facts: ">= 4"
phase_count: "== 7"
```

Parse operator from string: `>=`, `<=`, `==`, `>`, `<`

Evaluate: `result[key] <op> threshold`

---

### Rate assertions

```yaml
pass_rate: ">= 0.5"
self_test_pass_rate: ">= 0.75"
```

Same as numeric comparison — value is a float between 0 and 1.

---

### String content assertions

```yaml
output_contains: "RELATIONSHIPS"
output_contains: "AI_SQL_GENERATION"
```

Evaluate: `assertion_value in result["primary_output"]`

---

## Assertion evaluation output

For each assertion, produce:

```python
{
  "assertion": "describe_tables >= 3",
  "run_1": { "value": 5, "passed": True },
  "run_2": { "value": 5, "passed": True },
  "run_3": { "value": 5, "passed": True },
  "status": "PASS",   # PASS = all 3 pass, WARN = 1-2 pass, FAIL = 0 pass
  "note": ""
}
```

---

## Consistency scoring algorithm

If `fixture.consistency_fields` is set, compare those specific fields across runs with their weights and tolerances:

```python
for field_spec in fixture.consistency_fields:
    values = [run1[field], run2[field], run3[field]]
    if all_same(values):
        score = 1.0
    elif max(values) - min(values) <= 1:
        score = 0.80
    elif max(values) - min(values) <= 2:
        score = 0.50
    else:
        score = 0.0
    weighted_total += score * field_spec.weight
```

If `consistency_fields` is NOT set, use the generic fallback:

```python
lengths = [len(run["primary_output"]) for run in runs]
spread = (max(lengths) - min(lengths)) / max(lengths)
if spread <= 0.10:
    consistency = 1.0   # within 10%
elif spread <= 0.25:
    consistency = 0.80  # within 25%
else:
    consistency = 0.50
```

**Interpretation**:
- 90–100%: Excellent — skill is deterministic
- 75–89%: Good — minor variation
- 60–74%: Acceptable
- < 60%: Poor — skill has non-determinism issue

---

## Common assertion failures and their meaning

| Assertion fails | Likely root cause |
|----------------|-------------------|
| `skill_completed: false` | Skill crashed in a phase; check `phase_errors` |
| `no_phase_errors: false` | A phase threw an error; check `phase_errors` list for which phase |
| `output_not_empty: false` | Skill exited early (stopping point not handled by fixture) |
| `output_contains` fails | Skill skipped the expected section; check stopping_point_responses |
| Numeric `>= N` fails | Skill produced fewer objects than expected; check phase logic or fixture inputs |
| Boolean fails | Skill took a different branch than fixture anticipated; refine stopping_point_responses |
| Consistency < 75% | Non-determinism in skill — likely a classification or AI generation step |
