# Domain Map Schema

The `validated_domain_map.json` is the gate artifact for Phase 5.
No pipeline runs until `validation_status` is `APPROVED`.

```json
{
  "version": "1.0",
  "created": "<ISO8601>",
  "customer": "<name>",
  "validation_status": "PENDING | APPROVED | BLOCKED",
  "audience": "business | analyst | mixed",
  "pipeline_routing": "KG_ENRICHED | VQR_DIRECT | SV_EXISTS",

  "domains": [
    {
      "name": "CRM",
      "description": "Customer relationship data — accounts, opportunities, contacts",
      "databases": ["SALESFORCE_SHARE_DB"],
      "pipeline_path": "KG_ENRICHED | VQR_DIRECT",
      "scan_score": 61,
      "entities": [
        {
          "name": "Customer",
          "table": "SALESFORCE_SHARE_DB.PUBLIC.CUSTOMERS",
          "type": "CORE_ENTITY | BRIDGE | AGGREGATE | STAGING",
          "golden_record": true,
          "validated": true,
          "columns": [
            {
              "name": "CUST_ID",
              "label": "Customer ID",
              "role": "key | dimension | time_dimension | metric",
              "confidence": "HIGH | MEDIUM | LOW",
              "source": "user_confirmed | dbt | powerbi | tableau | inferred"
            }
          ]
        }
      ]
    }
  ],

  "metrics": [
    {
      "name": "revenue",
      "canonical_name": "net_revenue",
      "expression": "SUM(net_amount)",
      "domain": "Finance",
      "resolution": "canonical | federated | unified | deferred",
      "trust_score": 91,
      "bi_confirmed": true,
      "bi_source": "dbt_metrics | powerbi_dax | tableau_calc",
      "validated": true,
      "aliases": [
        { "name": "crm_attributed_revenue", "domain": "CRM", "expression": "SUM(opportunity_amount)" }
      ]
    }
  ],

  "relationships": [
    {
      "from_table": "ORDERS",
      "from_column": "CUST_ID",
      "to_table": "CUSTOMERS",
      "to_column": "CUST_ID",
      "cardinality": "many_to_one",
      "confidence": "CONFIRMED | INFERRED",
      "source": "powerbi | dbt_test | fk_constraint | join_pattern"
    }
  ],

  "conflicts": [
    {
      "id": "C001",
      "concept": "revenue",
      "conflict_type": "metric_calculation | entity_scope | key_mismatch | temporal_grain | column_overload",
      "severity": "BLOCKING | NON_BLOCKING | INFORMATIONAL",
      "recommended_definition": "Finance definition",
      "recommended_trust_score": 91,
      "human_decision": "canonical | federated | unified | deferred | null",
      "decision_notes": "",
      "status": "RESOLVED | PENDING | ACCEPTED_WITH_WARNING"
    }
  ],

  "gaps_accepted": [
    {
      "id": "G001",
      "description": "6 columns in CUSTOMERS with no documentation",
      "consequence": "Will be labeled LOW_CONFIDENCE in semantic view",
      "resolution": "low_confidence_flag | excluded | user_documented | bi_confirmed",
      "items": ["CUSTOMERS.COL_X", "CUSTOMERS.AMT_FLG"]
    }
  ],

  "excluded_tables": [
    {
      "table": "ORDERS_STAGING_TMP_V3",
      "reason": "staging | dormant | low_frequency | user_excluded"
    }
  ],

  "success_criteria": [
    "What was our revenue last quarter by region?",
    "Which customers are at risk of churning?",
    "Top 10 products by margin this year?",
    "Show pipeline by rep for this quarter",
    "What is our customer acquisition cost by channel?"
  ],

  "target_role": "ANALYST_ROLE",
  "pii_acknowledged": true,
  "access_confirmed": true,
  "performance_warnings_acknowledged": true
}
```

## Validation Checklist (Phase 5)

Before setting `validation_status: APPROVED`, verify ALL of:

- [ ] All `domains[]` have at least 1 `CORE_ENTITY` with `validated: true`
- [ ] All `conflicts[]` with `severity: BLOCKING` have `human_decision` set (not null)
- [ ] All `metrics[]` used in `success_criteria` have `validated: true`
- [ ] `success_criteria[]` has at least 3 questions
- [ ] `target_role` is set and access confirmed
- [ ] `pii_acknowledged: true`
- [ ] `access_confirmed: true`
