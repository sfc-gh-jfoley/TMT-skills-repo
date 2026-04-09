# Advanced Access Control

Dual-layer Row Access Policy, agent scoping, CSS attribute filtering, and multi-tenant patterns.

## Challenge

CSS (Cortex Search Service) cannot use Row Access Policies with subqueries. This means we can't apply traditional Snowflake RAPs to the CONCEPTS table and have CSS respect them.

## Solution: Dual-Layer Architecture

### Layer 1: RBAC on CONCEPTS Table

Standard Snowflake RAP on the CONCEPTS table for direct SQL access:

```sql
CREATE OR REPLACE ROW ACCESS POLICY {DOMAIN}_META.META.CONCEPTS_RAP
AS (domain VARCHAR, source_database VARCHAR)
RETURNS BOOLEAN ->
  IS_ROLE_IN_SESSION('SYSADMIN')
  OR IS_ROLE_IN_SESSION('ACCOUNTADMIN')
  OR EXISTS (
    SELECT 1 FROM {DOMAIN}_META.META.AGENT_TOOL_MAP
    WHERE tool_domain = domain
      AND role_name = CURRENT_ROLE()
  );

ALTER TABLE {DOMAIN}_META.META.CONCEPTS
  ADD ROW ACCESS POLICY {DOMAIN}_META.META.CONCEPTS_RAP
  ON (domain, source_database);
```

### Layer 2: Flat Table for CSS

CSS sources from a RAP-free flat table, refreshed by task:

```sql
CREATE OR REPLACE TABLE {DOMAIN}_META.META.CONCEPTS_SEARCHABLE AS
SELECT * FROM {DOMAIN}_META.META.CONCEPTS
WHERE is_active = TRUE;

-- CSS built on CONCEPTS_SEARCHABLE (no RAP)
CREATE OR REPLACE CORTEX SEARCH SERVICE {DOMAIN}_META.META.{DOMAIN}_SEARCH
  ON search_content
  ATTRIBUTES concept_name, concept_level, domain, source_database, source_schema
  WAREHOUSE = COMPUTE_WH
  TARGET_LAG = '1 hour'
AS (
  SELECT * FROM {DOMAIN}_META.META.CONCEPTS_SEARCHABLE
);
```

### Layer 3: Agent-Level Scoping via Attribute Filter

At search time, scope results using CSS ATTRIBUTE filters:

```python
# Agent-specific search (only sees its mapped domains)
agent_domains = get_agent_domains(agent_name, session)

results = css.search(
    query=user_question,
    columns=["concept_name", "tables_yaml", "domain"],
    filter={"@in": {"domain": agent_domains}},
    limit=10
)
```

## AGENT_TOOL_MAP Table

Maps agents and roles to accessible domains/tools:

```sql
CREATE TABLE IF NOT EXISTS {DOMAIN}_META.META.AGENT_TOOL_MAP (
  agent_name VARCHAR NOT NULL,
  role_name VARCHAR NOT NULL,
  tool_domain VARCHAR NOT NULL,
  tool_fqn VARCHAR,             -- specific CSS or SV FQN
  granted_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
  granted_by VARCHAR DEFAULT CURRENT_USER(),
  PRIMARY KEY (agent_name, role_name, tool_domain)
);

-- Seed: SALES_AGENT can see SALESFORCE and FINANCE domains
INSERT INTO AGENT_TOOL_MAP VALUES
  ('SALES_AGENT', 'SALES_ANALYST', 'SALESFORCE', 'SALESFORCE_META.META.SALESFORCE_SEARCH', CURRENT_TIMESTAMP(), CURRENT_USER()),
  ('SALES_AGENT', 'SALES_ANALYST', 'FINANCE', 'FINANCE_META.META.FINANCE_SEARCH', CURRENT_TIMESTAMP(), CURRENT_USER());
```

## Multi-Tenant Pattern

For platforms serving multiple customers/teams with different data access:

```sql
-- Add tenant column to CONCEPTS
ALTER TABLE {DOMAIN}_META.META.CONCEPTS ADD COLUMN tenant_id VARCHAR;

-- RAP with tenant filtering
CREATE OR REPLACE ROW ACCESS POLICY {DOMAIN}_META.META.TENANT_RAP
AS (tenant_id VARCHAR)
RETURNS BOOLEAN ->
  IS_ROLE_IN_SESSION('SYSADMIN')
  OR tenant_id = CURRENT_SESSION()::VARIANT:tenant_id::VARCHAR
  OR EXISTS (
    SELECT 1 FROM TENANT_ACCESS
    WHERE role_name = CURRENT_ROLE()
      AND tenant = tenant_id
  );
```

At search time, add tenant as attribute filter:

```python
results = css.search(
    query=user_question,
    filter={"@and": [
        {"@eq": {"concept_level": "table"}},
        {"@eq": {"tenant_id": current_tenant}}
    ]},
    limit=10
)
```

## Refresh Workflow

When CONCEPTS table changes, keep CONCEPTS_SEARCHABLE in sync:

```sql
CREATE OR REPLACE TASK {DOMAIN}_META.META.SYNC_SEARCHABLE_TASK
  WAREHOUSE = COMPUTE_WH
  SCHEDULE = 'USING CRON */15 * * * * America/New_York'
AS
  CREATE OR REPLACE TABLE {DOMAIN}_META.META.CONCEPTS_SEARCHABLE AS
  SELECT * FROM {DOMAIN}_META.META.CONCEPTS WHERE is_active = TRUE;
```

## Security Considerations

1. **CONCEPTS_SEARCHABLE has no RAP** — it contains all active concepts. CSS scoping is attribute-based, not RAP-based. Ensure the CSS itself has proper GRANT controls.
2. **GRANT USAGE on CSS** to only the roles that should search:
   ```sql
   GRANT USAGE ON CORTEX SEARCH SERVICE {DOMAIN}_META.META.{DOMAIN}_SEARCH
     TO ROLE SALES_ANALYST;
   ```
3. **Underlying tables** — Even if CSS returns concept metadata, the actual data tables still have their own RAPs/grants. A user can't query tables they don't have SELECT on.
4. **Audit trail** — Log all searches in QUERY_LOG for compliance.
