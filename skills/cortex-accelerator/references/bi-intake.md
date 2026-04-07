# BI Tool Intake Reference

Detailed extraction instructions for each BI tool. Load this during Phase 4.

## Trust Boost Rules

| Tool | Trust boost | Applied to |
|------|-------------|-----------|
| dbt metrics layer | +35 | Metric expressions |
| dbt test: relationships | Promoted to CONFIRMED | Relationships |
| dbt column descriptions | Direct gap fill | Column docs |
| PowerBI DAX measures | +30 | Metric expressions |
| PowerBI relationships | Promoted to CONFIRMED | Relationships |
| PowerBI RLS roles | Domain ownership signal | Domain boundaries |
| Tableau calculated fields | +25 | Metric expressions |
| Tableau field captions | Direct gap fill | Column labels |
| Tableau dashboard groupings | Domain boundary hint | Domain names |

When same definition confirmed by 2+ tools AND matches top query history trust score:
mark `bi_confirmed: true`, no human review needed for that item.

When BI tools contradict each other: elevate to BLOCKING conflict regardless of
original severity. Both tools are authoritative — human must decide.

---

## Tableau (.twb / .twbx)

### How to get the file
Ask user: "Can you export a Tableau workbook (.twb or .twbx) that queries your
[domain] data?"

`.twbx` files are ZIP archives. Extract with: `unzip workbook.twbx -d twbx_extract/`
The `.twb` XML is inside.

### What to extract (XML paths)

**Metric definitions** (highest value):
```xml
<datasource>
  <column caption='Revenue' datatype='real' role='measure'>
    <calculation formula='SUM([net_amount])-SUM([discount_amount])' />
  </column>
</datasource>
```
→ `caption` = metric label, `formula` = expression. Apply +25 trust boost.

**Dimension labels** (fills column doc gaps):
```xml
<column caption='Customer Segment' datatype='string' role='dimension' name='[cust_seg]' />
```
→ `caption` fills the label gap for `cust_seg` column. Mark as `BI_CONFIRMED`.

**Domain hints** (worksheet/dashboard names):
```xml
<worksheet name='Sales Performance Dashboard' />
<dashboard name='Finance Overview' />
```
→ Group connected datasources under the domain suggested by dashboard name.

**Data source connections** (authoritative table list):
```xml
<connection dbname='ANALYTICS_DB' schema='PUBLIC' table='ORDERS' />
```
→ Tables in Tableau connections are production tables used in real reports.

---

## PowerBI (.pbix)

### How to get the file
Ask user: "Can you share the .pbix file for your [domain] report?"

`.pbix` files are ZIP archives. Extract and look for:
- `DataModelSchema` or `Model.bim` (JSON) — the semantic model

### What to extract

**DAX measures** (highest value — explicit metric definitions):
```json
{
  "measures": [{
    "name": "Net Revenue",
    "expression": "CALCULATE(SUM(Orders[net_amount]), FILTER(Orders, Orders[status]='completed'))",
    "formatString": "$#,0.00"
  }]
}
```
→ `name` = canonical metric label, `expression` = DAX definition. Apply +30 trust boost.
→ Map DAX `SUM(Table[col])` to SQL `SUM(col)` from the matching table.

**Relationships** (resolves FK gaps — strongest signal):
```json
{
  "relationships": [{
    "fromTable": "Orders",
    "fromColumn": "customer_id",
    "toTable": "Customers",
    "toColumn": "id",
    "crossFilteringBehavior": "oneDirection",
    "cardinality": "manyToOne"
  }]
}
```
→ Promote to `CONFIRMED`. These are human-authored relationships used in production reports.

**Column semantic categories** (auto-classification hints):
```json
{ "name": "Country", "dataCategory": "Country" }
{ "name": "Revenue", "dataCategory": "Currency" }
```
→ `dataCategory` helps classify columns without needing documentation.

**Row-level security roles** (domain ownership):
```json
{ "roles": [{ "name": "Finance_Users", "tablePermissions": [{ "name": "Revenue_Summary" }] }] }
```
→ RLS role names hint at domain boundaries and table ownership.

---

## dbt

### How to get the files
Ask user: "Can you point me at your dbt project directory, or share your
`schema.yml`, `sources.yml`, and `metrics.yml` files?"

### What to extract

**Column documentation** (direct gap fill — no question needed):
```yaml
# schema.yml
models:
  - name: customers
    description: "One record per customer account"
    columns:
      - name: customer_id
        description: "Primary key. Maps to Salesforce Account ID."
      - name: ltv
        description: "Lifetime value in USD, calculated at month-end"
```
→ Model `description` fills table doc gap. Column `description` fills column doc gap.
→ Mark as `BI_CONFIRMED`, no human review needed.

**FK relationships** (promoted to CONFIRMED):
```yaml
columns:
  - name: customer_id
    tests:
      - relationships:
          to: ref('customers')
          field: id
```
→ Any `test: relationships` entry → promote relationship to `CONFIRMED` in domain map.

**Canonical metrics** (highest trust — versioned, CI-tested):
```yaml
# metrics.yml
metrics:
  - name: revenue
    label: Net Revenue
    model: ref('orders')
    calculation_method: sum
    expression: net_amount
    filters:
      - field: status
        operator: '='
        value: 'completed'
```
→ Apply +35 trust boost. This is the gold standard definition.

**Authoritative source tables**:
```yaml
# sources.yml
sources:
  - name: salesforce
    database: SFDC_SHARE_DB
    schema: PUBLIC
    tables:
      - name: accounts
        description: "Salesforce Account object — system of record for customers"
```
→ Source tables are the upstream authorities. Mark as `golden_record: true` candidates.

**Exposures** (connects dbt → Tableau/PowerBI):
```yaml
exposures:
  - name: sales_dashboard
    type: dashboard
    depends_on:
      - ref('orders')
      - ref('customers')
    owner:
      email: analytics@company.com
```
→ Use to confirm which dbt models power which BI reports. Strengthens trust chain.
