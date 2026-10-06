---
name: snowflake-intelligence-deployment
description: "Deployment phase for SI Accelerator. Deploy scripts to demo account and verify setup."
parent_skill: snowflake-intelligence-accelerator-via-snowhouse
---

# Deployment Phase

Deploy generated scripts to demo account and verify the Snowflake Intelligence setup.

## When to Load

- After generation phase completed scripts
- User connected to demo account and says "deploy", "run scripts", or "verify"

## Prerequisites

- Generation phase completed (9 scripts in `example_[customer]/`)
- **New session** connected to demo account: `cortex --connection [DEMO_CONNECTION]`

## Workflow

### Step 1: Verify Connection

**Confirm** user is connected to demo account, not SNOWHOUSE:
```sql
SELECT CURRENT_ACCOUNT(), CURRENT_ROLE();
```

If still on SNOWHOUSE, instruct user to start new session.

### Step 2: Execute Scripts in Order

**For Demo Account Testing (with synthetic data):**

Execute in this specific order:

1. **`for_your_demo_account/00_base_tables`** - Creates source databases
   ```
   Run for_your_demo_account/00_base_tables_[customer].sql
   ```
   Verify: Source databases and tables created

2. **`for_the_customer/00_infrastructure`** - Creates SI infrastructure
   ```
   Run for_the_customer/00_infrastructure_[customer].sql
   ```
   Verify: Role, warehouse, database, schema, views created

3. **`for_your_demo_account/01_synthetic_datagen`** - Creates test data procedure
   ```
   Run for_your_demo_account/01_synthetic_datagen_[customer].sql
   ```
   Verify: Procedure created in SI schema

4. **Generate synthetic data:**
   ```sql
   CALL SI_[CUSTOMER].[CUSTOMER]_SNOW_INTELLIGENCE.GENERATE_[CUSTOMER]_SYNTHETIC_DATA('SMALL');
   ```
   Scale options: `'TINY'`, `'SMALL'`, `'MEDIUM'`, `'LARGE'`

5. **`for_the_customer/01-05`** - Semantic views, search, functions, agent
   ```
   Run for_the_customer/01_semantic_views_[customer].sql
   Run for_the_customer/02_cortex_search_[customer].sql
   Run for_the_customer/03_support_functions_[customer].sql
   Run for_the_customer/04_agent_creation_[customer].sql
   Run for_the_customer/05_verification_[customer].sql
   ```

### Step 3: Verify Setup

**Run verification queries from script 05:**

- [ ] Each semantic view returns data
- [ ] Each Cortex Search service is active
- [ ] Agent responds to sample questions
- [ ] Email function configured (if applicable)
- [ ] Streamlit generator works (if applicable)

**Test agent in Snowflake UI:**
```
https://app.snowflake.com/[ORG]/[ACCOUNT]/#/ai
Select: [CUSTOMER]_Platform_Agent
```

### Step 4: Cleanup (When Done Testing)

**CAUTION:** Only run teardown on demo accounts with synthetic data!

```
Run for_your_demo_account/02_complete_teardown_[customer].sql
```

This removes ALL objects including:
- Intelligence database (`SI_[CUSTOMER]`)
- Source databases (created by base_tables script)
- Warehouse, role, and agent

## Alternative: Production Deployment

For customer accounts with existing data, run only `for_the_customer/` scripts:

1. `00_infrastructure` - Modify views to point to actual source tables
2. `01_semantic_views`
3. `02_cortex_search`
4. `03_support_functions`
5. `04_agent_creation`
6. `05_verification`

Skip `for_your_demo_account/` scripts entirely.

## Troubleshooting

**"Insufficient privileges on schema"**
```sql
USE ROLE ACCOUNTADMIN;
GRANT USAGE ON SCHEMA SI_[CUSTOMER].[CUSTOMER]_SNOW_INTELLIGENCE TO ROLE ACCOUNTADMIN;
GRANT CREATE TABLE ON SCHEMA ... TO ROLE ACCOUNTADMIN;
```

**"Synthetic data generation fails"**
- Ensure infrastructure script ran first
- Check procedure exists:
  ```sql
  SHOW PROCEDURES IN SI_[CUSTOMER].[CUSTOMER]_SNOW_INTELLIGENCE;
  ```
- Grant write privileges to both ACCOUNTADMIN and Intelligence role

**"View definition declared X columns, but query produces Y"**
- Base table and synthetic datagen have mismatched columns
- Verify column definitions match exactly

**"Agent not visible in UI"**
- Must use `CREATE AGENT ... FROM SPECIFICATION` syntax
- Grant USAGE to PUBLIC role:
  ```sql
  GRANT USAGE ON AGENT SNOWFLAKE_INTELLIGENCE.AGENTS.[CUSTOMER]_Platform_Agent TO ROLE PUBLIC;
  ```

**"Cortex Search syntax error"**
- `ON` clause must specify single column
- Create SEARCH_TEXT column that concatenates searchable fields

## Output

Deployed Snowflake Intelligence setup:
- Intelligence database with semantic views
- Cortex Search services for entity lookup
- Agent with all tools configured
- Verification queries passing

## Customer Handover

Share `for_the_customer/` folder with customer:
1. They run scripts 00-05 in order
2. Modify `00_infrastructure` to point to their actual source tables
3. Run `05_verification` to confirm
