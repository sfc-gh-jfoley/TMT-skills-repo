---
name: agent-evaluation
description: "Evaluate Cortex Agents using native Snowflake Agent Evaluations (preview). Use when: running agent evaluations, testing agent accuracy, measuring tool selection/execution accuracy, checking logical consistency. Triggers: evaluate agent, run agent evaluation, test agent accuracy, agent metrics."
---

# Cortex Agent Evaluation Skill

End-to-end workflow for evaluating Cortex Agents: discover the agent, build an evaluation dataset, run the evaluation, analyze results, and iterate to improve agent quality.

## Metrics Reference

| Metric | API Name | Requires Ground Truth | Description |
|--------|----------|----------------------|-------------|
| Answer Correctness | `correctness` | Yes | Semantic match of agent's final answer vs expected |
| Tool Selection Accuracy | `tool_selection_accuracy` | Yes | Did agent pick the right tools in the right order? |
| Tool Execution Accuracy | `tool_execution_accuracy` | Yes | Correct tool inputs/outputs? |
| Logical Consistency | `logical_consistency` | No | Consistency across instructions, planning, and tool calls (reference-free) |

## Prerequisites

```sql
-- Required grants for the role running evaluations
GRANT DATABASE ROLE SNOWFLAKE.CORTEX_USER TO ROLE <role>;
GRANT EXECUTE TASK ON ACCOUNT TO ROLE <role>;
GRANT CREATE FILE FORMAT ON SCHEMA <agent_schema> TO ROLE <role>;
GRANT CREATE DATASET ON SCHEMA <agent_schema> TO ROLE <role>;
GRANT CREATE TASK ON SCHEMA <agent_schema> TO ROLE <role>;
GRANT IMPERSONATE ON USER <user> TO ROLE <role>;
GRANT MONITOR ON AGENT <database>.<schema>.<agent> TO ROLE <role>;
```

---

## Phase 1: Discover Agent

### 1.1 Identify the Agent

Ask the user for:
- Agent name (fully qualified: `DATABASE.SCHEMA.AGENT_NAME`)
- Connection name to use

### 1.2 Extract Agent Configuration

```sql
DESCRIBE AGENT <DATABASE>.<SCHEMA>.<AGENT_NAME>;
```

Parse the `agent_spec` column. Extract:
- **Tools**: `tools[]` array — each has `tool_spec.type`, `tool_spec.name`, `tool_spec.description`
- **Instructions**: What the agent is designed to do, guardrails, persona
- **Sample questions**: From the agent's instructions (if any)

Tool types: `cortex_analyst_text_to_sql`, `cortex_search`, `generic`

### 1.3 Present Summary

```
Agent: DATABASE.SCHEMA.AGENT_NAME

Instructions summary: [brief summary of agent persona and purpose]

Tools:
  1. revenue_analyst (cortex_analyst_text_to_sql) - Revenue and sales data
  2. policy_search (cortex_search) - Company policies
  3. get_weather (generic) - Weather lookups

Sample questions from spec: [if any]
```

**STOP** — Confirm agent details with user before proceeding.

---

## Phase 2: Choose Metrics

Ask user which metrics to evaluate:

```
Which metrics do you want to evaluate?

1. [ ] correctness — Does the agent give correct final answers?
       Requires: expected answer text for each question

2. [ ] tool_selection_accuracy — Does the agent pick the right tools?
       Requires: expected tool name(s) and sequence for each question

3. [ ] tool_execution_accuracy — Does the agent use tools correctly?
       Requires: expected tool inputs/outputs for each question

4. [ ] logical_consistency — Is agent reasoning consistent? (reference-free)
       Requires: nothing extra

Select metrics (e.g., "1,2,4" or "all"):
```

### Decision Table

| Selection | Dataset Needs |
|-----------|--------------|
| Only `logical_consistency` | Just `INPUT_QUERY` — skip to Phase 3C |
| `correctness` | `ground_truth_output` + `ground_truth_invocations` with `tool_name`/`tool_sequence` |
| `tool_selection_accuracy` | `ground_truth_invocations` with `tool_name`/`tool_sequence` |
| `tool_execution_accuracy` | Above + `tool_output` (SQL patterns or search results) |

**STOP** — Confirm metrics before proceeding.

---

## Phase 3: Build Evaluation Dataset

### Phase 3A: User Has Existing Data

If user has an existing table, ask for:
- Table name (fully qualified)
- Question column name
- Expected answer column (if applicable)
- Expected tool column (if applicable)

Then use convert_eval_dataset.py or transform directly with SQL.

### Phase 3B: Build Dataset Interactively (Recommended)

#### 3B.1 Review Agent Instructions

**CRITICAL** — Read the agent's instructions before creating questions. Many agents have:
- **Guardrails** that refuse certain question types
- **Persona restrictions** (customer-facing vs analytics)
- **Scope limits** (only answers about specific topics)

Common pitfall: Creating analytics questions for a customer-service agent → agent refuses to use tools → 0% accuracy.

| Agent Type | Good Questions | Bad Questions |
|------------|----------------|---------------|
| Customer service | "What's popular?", "Help me order" | "Show me quarterly revenue" |
| Analytics | "Revenue by quarter", "Top products" | "Place an order for me" |
| Support | "How do I reset my password?" | "Show me financial data" |

#### 3B.2 Generate Questions and Ground Truth

**Target: 10-20 queries** depending on complexity:
- Simple agent (1-2 tools): 10-12 queries
- Medium agent (3-4 tools): 12-16 queries
- Complex agent (5+ tools): 16-20 queries

**Cover:**
- Every tool at least 2-3 times
- Edge cases and multi-tool questions
- Questions that test guardrails (should agent refuse?)

**DO NOT run the agent to capture ground truth.** Instead, predict expected behavior based on:
- Agent instructions and persona
- Tool purposes and the data they access
- Semantic model / search corpus contents

#### 3B.3 Pre-flight: Batch Test Questions (Optional but Recommended)

Before formal evaluation, optionally invoke the agent against proposed questions to validate they trigger the expected tools:

Write `/tmp/invoke_agent.py` (from scripts/invoke_agent.py) and run:

```bash
python /tmp/invoke_agent.py <DATABASE> <SCHEMA> <AGENT_NAME> "<question>" <CONNECTION>
```

Check output for:
- Does the agent use the expected tool?
- Does the answer contain the expected facts?
- Does the agent refuse or deflect?

If a question doesn't trigger the expected tool, revise the question or update ground truth.

#### 3B.4 Present Full Dataset for Review

```
| # | Question | Expected Tool(s) | Ground Truth Output (brief) |
|---|----------|------------------|-----------------------------|
| 1 | What's our top campaign by ROI? | query_metrics | Back to School has highest ROI at 203%. |
| 2 | What do customers say about pricing? | feedback_search | Customers find pricing competitive. |
| ... | ... | ... | ... |
```

**STOP** — Get user approval on the full dataset before creating the table.

### Phase 3C: Reference-Free Only (Logical Consistency)

Simplified flow — just questions, no ground truth.

```sql
CREATE OR REPLACE TABLE <DATABASE>.<SCHEMA>.<AGENT_NAME>_EVAL_LC (
    INPUT_QUERY VARCHAR(16777216),
    EXPECTED_TOOLS VARCHAR(16777216)
);

INSERT INTO <DATABASE>.<SCHEMA>.<AGENT_NAME>_EVAL_LC (INPUT_QUERY, EXPECTED_TOOLS)
VALUES 
    ('What is the most popular item?', '{}'),
    ('Show me options under $10', '{}');
```

Then skip to Phase 4 with only `logical_consistency` metric.

---

### 3.5 Create the Evaluation Table

**CRITICAL FORMAT REQUIREMENTS:**
- Column names: `INPUT_QUERY` (VARCHAR) and `EXPECTED_TOOLS` (VARCHAR)
- `EXPECTED_TOOLS` is **VARCHAR**, not OBJECT or VARIANT
- Insert JSON as plain string — no PARSE_JSON needed

```sql
CREATE OR REPLACE TABLE <DATABASE>.<SCHEMA>.<AGENT_NAME>_EVAL_DATASET (
    INPUT_QUERY VARCHAR(16777216),
    EXPECTED_TOOLS VARCHAR(16777216)
);
```

### 3.6 Insert Ground Truth

**Standard format (works for all metrics):**

```sql
INSERT INTO <DATABASE>.<SCHEMA>.<AGENT_NAME>_EVAL_DATASET (INPUT_QUERY, EXPECTED_TOOLS)
VALUES (
    'What is the top campaign by ROI?',
    '{"ground_truth_invocations": [{"tool_name": "query_metrics", "tool_sequence": 1}], "ground_truth_output": "Back to School has highest ROI at 203%."}'
);
```

**Multi-tool example:**
```sql
INSERT INTO ... VALUES (
    'Find popular items and place an order',
    '{"ground_truth_invocations": [{"tool_name": "search_items", "tool_sequence": 1}, {"tool_name": "place_order", "tool_sequence": 2}], "ground_truth_output": "Strawberry Frosted is most popular. Order confirmed."}'
);
```

**With tool_output (for `tool_execution_accuracy`):**
```sql
INSERT INTO ... VALUES (
    'What campaign has the best ROI?',
    '{"ground_truth_invocations": [{"tool_name": "query_metrics", "tool_sequence": 1, "tool_output": {"SQL": "SELECT campaign_name, roi FROM campaigns ORDER BY roi DESC LIMIT 5"}}], "ground_truth_output": "Back to School has highest ROI at 203%."}'
);
```

**For Cortex Search tool_output:**
```sql
-- Use "search results" (with space, not underscore)
'{"ground_truth_invocations": [{"tool_name": "my_search", "tool_sequence": 1, "tool_output": {"search results": ["relevant context 1", "relevant context 2"]}}], "ground_truth_output": "Answer based on search."}'
```

### Ground Truth Guidelines

| Rule | Detail |
|------|--------|
| Keep `ground_truth_output` concise | 1-2 sentences with key facts. NOT verbose paragraphs. |
| Semantic matching | LLM judge compares meaning, not exact wording |
| `tool_output.SQL` | Use uppercase "SQL" key for Cortex Analyst |
| `tool_output["search results"]` | Use "search results" (space) for Cortex Search |
| Escape single quotes | Double them: `''` |

**STOP** — Review dataset with user before proceeding.

---

## Phase 4: Register Dataset & Run Evaluation

### 4.1 Set Database Context

```sql
USE DATABASE <DATABASE>;
USE SCHEMA <SCHEMA>;
```

### 4.2 Register the Dataset

```sql
CALL SYSTEM$CREATE_EVALUATION_DATASET(
    'Cortex Agent',
    '<DATABASE>.<SCHEMA>.<AGENT_NAME>_EVAL_DATASET',
    '<AGENT_NAME>_EVAL_DS_<YYYYMMDD_HHMMSS>',
    OBJECT_CONSTRUCT(
        'query_text', 'INPUT_QUERY',
        'expected_tools', 'EXPECTED_TOOLS'
    )
);
```

### 4.3 Run the Evaluation

```sql
CALL SYSTEM$EXECUTE_AI_OBSERVABILITY_RUN(
    OBJECT_CONSTRUCT(
        'object_name', '<DATABASE>.<SCHEMA>.<AGENT_NAME>',
        'object_type', 'CORTEX AGENT'
    ),
    OBJECT_CONSTRUCT(
        'run_name', '<AGENT_NAME>_eval_<YYYYMMDD_HHMMSS>',
        'label', 'evaluation',
        'description', 'Evaluation: <brief description>'
    ),
    OBJECT_CONSTRUCT(
        'type', 'dataset',
        'dataset_name', '<DATABASE>.<SCHEMA>.<AGENT_NAME>_EVAL_DS_<YYYYMMDD_HHMMSS>',
        'dataset_version', 'SYSTEM_AI_OBS_CORTEX_AGENT_DATASET_VERSION_DO_NOT_DELETE'
    ),
    ARRAY_CONSTRUCT(<SELECTED_METRICS>),
    ARRAY_CONSTRUCT('INGESTION', 'COMPUTE_METRICS')
);
```

**Metric array examples:**
```sql
ARRAY_CONSTRUCT('correctness', 'tool_selection_accuracy', 'tool_execution_accuracy', 'logical_consistency')
ARRAY_CONSTRUCT('correctness', 'logical_consistency')
ARRAY_CONSTRUCT('logical_consistency')
```

### 4.4 Open Results in Snowsight

Get org/account and open browser:

```sql
SELECT LOWER(CURRENT_ORGANIZATION_NAME()), LOWER(CURRENT_ACCOUNT_NAME());
```

```bash
open "https://app.snowflake.com/<org>/<account>/#/agents/database/<DATABASE>/schema/<SCHEMA>/agent/<AGENT_NAME>/evaluations/<RUN_NAME>/records"
```

---

## Phase 5: Analyze Results

After the evaluation completes, analyze the results to identify specific weaknesses.

### 5.1 Check Run Status

Navigate to Snowsight Evaluations tab or check the run status. Runs show:
- Per-input scores for each metric
- Thread details with agent reasoning
- Trace details with tool call information

### 5.2 Score Breakdown Analysis

Review each metric and categorize questions:

| Score Range | Category | Action |
|-------------|----------|--------|
| ≥80% | High accuracy | No action needed |
| 30-79% | Medium accuracy | Investigate — may need tuning |
| <30% | Failed | Root cause analysis required |

### 5.3 Root Cause Analysis by Metric

#### Low `correctness`

The agent gives wrong or incomplete answers.

**Investigate:**
1. Is the ground truth too specific or too verbose? (Use concise factual statements)
2. Does the agent have access to the right data?
3. Are the agent instructions causing it to omit key information?

**Fixes:**
- Simplify ground truth to key facts only
- Add specific instructions: "Always include percentages when discussing metrics"
- Verify semantic model/search service has the needed data

#### Low `tool_selection_accuracy`

The agent picks the wrong tool or no tool.

**Investigate:**
1. Are tool descriptions clear enough for the LLM to route correctly?
2. Does the question overlap between multiple tools' domains?
3. Do agent instructions explicitly guide tool routing?

**Fixes:**
- Improve tool descriptions to be more specific about what each tool handles
- Add routing instructions: "For revenue questions, always use the revenue_analyst tool"
- Add disambiguation: "If the question involves both X and Y, use tool A first, then tool B"

#### Low `tool_execution_accuracy`

The agent calls the right tool but with wrong parameters or gets unexpected output.

**Investigate:**
1. Is the semantic model/search service configured correctly?
2. Does the tool input match expectations? (Check query reformulation)
3. Is the expected tool_output realistic? (SQL patterns may vary)

**Fixes:**
- Use `semantic-view-optimization` skill to fix semantic view issues
- Loosen expected SQL patterns (exact match is hard — focus on key tables/columns)
- Add tool-specific instructions in agent spec

#### Low `logical_consistency`

The agent contradicts itself or its reasoning doesn't align with actions.

**Investigate:**
1. Are agent instructions contradictory?
2. Does the agent plan one thing but do another?
3. Are there ambiguous instructions that the LLM interprets differently across runs?

**Fixes:**
- Remove contradictory instructions
- Make instructions more explicit and deterministic
- Add step-by-step reasoning guidance

### 5.4 Generate Improvement Report

Present findings:

```
## Evaluation Results Summary

Run: <RUN_NAME>
Agent: <DATABASE>.<SCHEMA>.<AGENT_NAME>
Questions: <N>

### Metric Averages
| Metric | Score | Status |
|--------|-------|--------|
| Correctness | 72% | ⚠️ Medium |
| Tool Selection | 90% | ✅ High |
| Tool Execution | 65% | ⚠️ Medium |
| Logical Consistency | 85% | ✅ High |

### Weak Areas
1. Questions 3, 7, 11 scored <30% on correctness
   - Common theme: multi-step questions where agent omits second tool's data
   - Suggested fix: Add instruction "When answering multi-part questions, synthesize results from all tools"

2. Questions 5, 9 scored <30% on tool_execution_accuracy
   - Common theme: Cortex Analyst generates different SQL than expected
   - Suggested fix: Review semantic model for ambiguous column names

### Recommended Changes
1. [Agent instructions] Add: "Always synthesize data from multiple tools when needed"
2. [Semantic model] Clarify column descriptions for revenue_by_campaign table
3. [Evaluation dataset] Loosen ground truth for Q5, Q9 — SQL variation is acceptable
```

---

## Phase 6: Improve Agent & Re-Evaluate

### 6.1 Apply Fixes

| Issue Category | Skill to Use | Action |
|----------------|-------------|--------|
| Agent instructions | `agent-optimization` | Refine instructions, add routing guidance |
| Semantic view issues | `semantic-view-optimization` | Fix column descriptions, add VQRs |
| Search quality | `search-optimization` | Tune search service config |
| Dataset issues | This skill | Revise ground truth for unrealistic expectations |

### 6.2 Update Agent (if instruction changes needed)

```sql
CREATE OR REPLACE CORTEX AGENT <DATABASE>.<SCHEMA>.<AGENT_NAME>
  COMMENT = 'Updated instructions based on eval run <RUN_NAME>'
  AGENT_SPEC = $$
  <updated_spec>
  $$;
```

### 6.3 Re-Run Evaluation

Use the same dataset with a new run name to measure improvement:

```sql
CALL SYSTEM$EXECUTE_AI_OBSERVABILITY_RUN(
    OBJECT_CONSTRUCT(
        'object_name', '<DATABASE>.<SCHEMA>.<AGENT_NAME>',
        'object_type', 'CORTEX AGENT'
    ),
    OBJECT_CONSTRUCT(
        'run_name', '<AGENT_NAME>_eval_v2_<YYYYMMDD_HHMMSS>',
        'label', 'evaluation',
        'description', 'Re-eval after instruction improvements'
    ),
    OBJECT_CONSTRUCT(
        'type', 'dataset',
        'dataset_name', '<DATABASE>.<SCHEMA>.<AGENT_NAME>_EVAL_DS_<YYYYMMDD_HHMMSS>',
        'dataset_version', 'SYSTEM_AI_OBS_CORTEX_AGENT_DATASET_VERSION_DO_NOT_DELETE'
    ),
    ARRAY_CONSTRUCT(<SAME_METRICS>),
    ARRAY_CONSTRUCT('INGESTION', 'COMPUTE_METRICS')
);
```

### 6.4 Compare Runs

Present before/after comparison:

```
### Comparison: v1 → v2

| Metric | v1 | v2 | Delta |
|--------|----|----|-------|
| Correctness | 72% | 84% | +12% ✅ |
| Tool Selection | 90% | 92% | +2% |
| Tool Execution | 65% | 78% | +13% ✅ |
| Logical Consistency | 85% | 88% | +3% |

Improvements attributed to:
- Instruction change: multi-tool synthesis guidance (+12% correctness)
- Semantic model fix: clearer column descriptions (+13% tool execution)
```

---

## Troubleshooting

### Agent Refuses to Use Tools (0% scores, no errors)

Evaluation questions don't match the agent's persona. Check `DESCRIBE AGENT` for guardrails in instructions. Fix by creating questions the agent is designed to answer.

### "No current database" Error

`SYSTEM$CREATE_EVALUATION_DATASET` requires database context:
```sql
USE DATABASE <DATABASE>;
USE SCHEMA <SCHEMA>;
```

### Ground Truth Not Parsed (Expected tools: [])

The table schema is wrong. Verify:

1. Column name is `EXPECTED_TOOLS` (not GROUND_TRUTH)
2. Column type is `VARCHAR` (not OBJECT/VARIANT)
3. JSON is inserted as plain string (no PARSE_JSON)
4. JSON uses `ground_truth_invocations` with `tool_name`/`tool_sequence`

```sql
-- Verify format
DESC TABLE <EVAL_TABLE>;
-- Should show: INPUT_QUERY VARCHAR, EXPECTED_TOOLS VARCHAR

SELECT INPUT_QUERY, EXPECTED_TOOLS FROM <EVAL_TABLE> LIMIT 3;
```

**Wrong formats (will show empty expected tools):**
```
["tool1", "tool2"]
{"tools": ["tool1"]}
{"expected_tools": ["tool1"]}
```

**Correct format:**
```json
{"ground_truth_invocations": [{"tool_name": "tool1", "tool_sequence": 1}], "ground_truth_output": "Brief answer."}
```

### Tool Output Key Names

- Cortex Analyst: `"SQL"` (uppercase)
- Cortex Search: `"search results"` (with space, not underscore)

### Agent Invocation via REST

Agents are invoked via REST API, not SQL:
```
POST /api/v2/databases/{db}/schemas/{schema}/agents/{agent}:run
Authorization: Snowflake Token="<session_token>"
```

Use `scripts/invoke_agent.py` for testing.

---

## Stopping Points

- **Phase 1** — Agent identified, tools analyzed
- **Phase 2** — Metrics selected
- **Phase 3** — Dataset reviewed and approved
- **Phase 4** — Evaluation run started
- **Phase 5** — Results analyzed, improvement report generated
- **Phase 6** — Fixes applied, re-evaluation run, comparison presented

## Artifacts Produced

- Evaluation dataset table: `<DATABASE>.<SCHEMA>.<AGENT_NAME>_EVAL_DATASET`
- Registered dataset: `<AGENT_NAME>_EVAL_DS_<YYYYMMDD_HHMMSS>`
- Evaluation runs viewable in Snowsight Evaluations UI
- Improvement report with specific fix recommendations
- Before/after comparison across evaluation runs
