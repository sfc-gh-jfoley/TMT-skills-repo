# Deploy Pipeline

CI/CD configuration, repo structure, and automated deployment for KG domains.

## Repository Structure

```
kg-discovery/
├── config/
│   ├── account.yml              # Account-level settings
│   └── domains/
│       ├── finance.yml          # Per-domain config
│       ├── salesforce.yml
│       └── product.yml
├── sql/
│   ├── bootstrap/
│   │   ├── 01_create_meta_db.sql
│   │   ├── 02_create_tables.sql
│   │   └── 03_create_procs.sql
│   ├── domains/
│   │   ├── finance/
│   │   │   ├── crawl.sql
│   │   │   ├── enrich.sql
│   │   │   └── css.sql
│   │   └── salesforce/
│   │       ├── crawl.sql
│   │       ├── enrich.sql
│   │       └── css.sql
│   └── master/
│       ├── refresh_master.sql
│       └── master_css.sql
├── procs/
│   ├── crawl_domain.py
│   ├── enrich_domain.py
│   ├── watch_domain.py
│   └── refresh_master.py
├── tasks/
│   ├── domain_refresh.sql       # Per-domain refresh task
│   ├── watch.sql                # Shadow detection task
│   └── master_refresh.sql       # Master KG refresh task
├── tests/
│   ├── test_search_quality.py
│   └── test_assembly.py
└── deploy.sh                    # Deployment script
```

## Domain Config YAML

```yaml
# config/domains/finance.yml
domain_name: FINANCE
meta_database: FINANCE_META
source_databases:
  - FINANCE_DB
ignore_schemas:
  - INFORMATION_SCHEMA
  - SCRATCH
  - STAGING
enrichment:
  max_tier: 2
  daily_budget_credits: 5.0
  batch_size: 20
css:
  warehouse: COMPUTE_WH
  target_lag: "1 hour"
watch:
  enabled: true
  auto_onboard: false
  auto_onboard_schemas:
    - PUBLIC
    - CORE
  schedule: "0 */6 * * *"
refresh:
  schedule: "0 6 * * *"
  warehouse: COMPUTE_WH
```

## Deployment Script

```bash
#!/bin/bash
# deploy.sh — Deploy or update KG domain

DOMAIN=$1
ENV=${2:-prod}  # prod, staging, dev
CONNECTION=${3:-default}

if [ -z "$DOMAIN" ]; then
  echo "Usage: ./deploy.sh <domain> [env] [connection]"
  exit 1
fi

CONFIG="config/domains/${DOMAIN}.yml"
if [ ! -f "$CONFIG" ]; then
  echo "Config not found: $CONFIG"
  exit 1
fi

echo "=== Deploying domain: $DOMAIN (env: $ENV) ==="

# Bootstrap (idempotent)
echo "1/5 Bootstrap..."
snow sql -f sql/bootstrap/01_create_meta_db.sql -c $CONNECTION \
  -D domain=$DOMAIN
snow sql -f sql/bootstrap/02_create_tables.sql -c $CONNECTION \
  -D domain=$DOMAIN
snow sql -f sql/bootstrap/03_create_procs.sql -c $CONNECTION \
  -D domain=$DOMAIN

# Domain config
echo "2/5 Loading config..."
snow sql -q "CALL ${DOMAIN}_META.META.LOAD_CONFIG('$CONFIG')" -c $CONNECTION

# Crawl
echo "3/5 Crawling..."
snow sql -q "CALL ${DOMAIN}_META.META.CRAWL_DOMAIN()" -c $CONNECTION

# Enrich
echo "4/5 Enriching..."
snow sql -q "CALL ${DOMAIN}_META.META.ENRICH_DOMAIN()" -c $CONNECTION

# Create CSS
echo "5/5 Creating search service..."
snow sql -f sql/domains/${DOMAIN}/css.sql -c $CONNECTION \
  -D domain=$DOMAIN

# Verify
echo "=== Verification ==="
snow sql -q "SELECT COUNT(*) AS concepts FROM ${DOMAIN}_META.META.CONCEPTS WHERE is_active = TRUE" -c $CONNECTION
snow sql -q "SHOW CORTEX SEARCH SERVICES LIKE '${DOMAIN}_SEARCH' IN SCHEMA ${DOMAIN}_META.META" -c $CONNECTION

echo "=== Done ==="
```

## CI/CD Pipeline (GitHub Actions)

```yaml
# .github/workflows/kg-deploy.yml
name: KG Domain Deploy

on:
  push:
    branches: [main]
    paths:
      - 'config/domains/**'
      - 'sql/**'
      - 'procs/**'

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install Snowflake CLI
        run: pip install snowflake-cli-labs

      - name: Detect changed domains
        id: changes
        run: |
          DOMAINS=$(git diff --name-only HEAD~1 HEAD | grep 'config/domains/' | sed 's|config/domains/||;s|\.yml||' | sort -u)
          echo "domains=$DOMAINS" >> $GITHUB_OUTPUT

      - name: Deploy changed domains
        env:
          SNOWFLAKE_CONNECTION_NAME: ${{ secrets.SF_CONNECTION }}
        run: |
          for domain in ${{ steps.changes.outputs.domains }}; do
            echo "Deploying $domain..."
            ./deploy.sh $domain prod
          done

      - name: Run quality tests
        run: |
          for domain in ${{ steps.changes.outputs.domains }}; do
            python tests/test_search_quality.py --domain $domain
          done
```

## Search Quality Tests

```python
# tests/test_search_quality.py
import argparse
from snowflake.core import Root

def test_search_quality(session, domain, test_cases):
    root = Root(session)
    css = root.databases[f"{domain}_META"].schemas["META"].cortex_search_services[f"{domain}_SEARCH"]
    
    passed = 0
    for tc in test_cases:
        results = css.search(
            query=tc["question"],
            columns=["concept_name", "tables_yaml"],
            limit=5
        )
        found_tables = set()
        for r in results["results"]:
            if r.get("tables_yaml"):
                # Extract table names from yaml
                found_tables.update(extract_table_names(r["tables_yaml"]))
        
        expected = set(tc["expected_tables"])
        if expected.issubset(found_tables):
            print(f"  PASS: {tc['question']}")
            passed += 1
        else:
            missing = expected - found_tables
            print(f"  FAIL: {tc['question']} — missing: {missing}")
    
    print(f"\n{passed}/{len(test_cases)} tests passed")
    return passed == len(test_cases)
```

## Task Configuration

```sql
-- Domain refresh task
CREATE OR REPLACE TASK {DOMAIN}_META.META.REFRESH_DOMAIN_TASK
  WAREHOUSE = COMPUTE_WH
  SCHEDULE = 'USING CRON 0 6 * * * America/New_York'
AS
  CALL {DOMAIN}_META.META.REFRESH_DOMAIN();

-- Watch task (child of refresh)
CREATE OR REPLACE TASK {DOMAIN}_META.META.WATCH_TASK
  WAREHOUSE = COMPUTE_WH
  AFTER {DOMAIN}_META.META.REFRESH_DOMAIN_TASK
AS
  CALL {DOMAIN}_META.META.RUN_WATCH();

-- Resume tasks
ALTER TASK {DOMAIN}_META.META.WATCH_TASK RESUME;
ALTER TASK {DOMAIN}_META.META.REFRESH_DOMAIN_TASK RESUME;
```

## Version Control

Track deployed versions:

```sql
INSERT INTO {DOMAIN}_META.META.DOMAIN_CONFIG VALUES
  ('deployed_version', '"1.0.0"'),
  ('deployed_at', TO_VARIANT(CURRENT_TIMESTAMP())),
  ('deployed_by', TO_VARIANT(CURRENT_USER())),
  ('git_sha', '":git_sha"');
```
