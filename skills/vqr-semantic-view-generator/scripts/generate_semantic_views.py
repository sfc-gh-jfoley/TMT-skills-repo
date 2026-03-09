#!/usr/bin/env python3
"""
generate_semantic_views.py - Generate Semantic View YAMLs from extracted table/column manifests

Actions:
- analyze: Show domain/table distribution
- fetch-schemas: Get live column info from Snowflake (REQUIRED before generate)
- extract-metrics: Parse aggregations from SQL queries to derive metrics
- generate: Create YAML files per domain
"""

import argparse
import csv
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

import yaml


# ============================================================================
# DESCRIPTION GENERATION
# ============================================================================

def generate_description(col_name: str, col_type: str, table_name: str) -> str:
    """Generate intelligent description based on column name patterns."""
    name = col_name.upper()
    table = table_name.upper()
    
    # ID columns with join hints
    if name.endswith('_ID'):
        entity = name[:-3].replace('_', ' ').title()
        # Check for common dimension references
        if 'ACCT' in name:
            return f"Account identifier - join to dim_acct"
        elif 'TITLE' in name:
            return f"Title identifier - join to dim_title"
        elif 'DEVICE' in name:
            return f"Device identifier - join to dim_device"
        elif 'PRODUCT' in name:
            return f"Product identifier - join to dim_product"
        elif 'COUNTRY' in name:
            return f"Country identifier - join to dim_country"
        elif 'REGION' in name:
            return f"Region identifier - join to dim_region"
        elif 'SKU' in name:
            return f"SKU identifier - join to dim_product_sku"
        elif 'DT' in name or 'DATE' in name:
            return f"Date identifier in YYYYMMDD format"
        else:
            return f"{entity} identifier"
    
    # Date/time columns
    if name.endswith('_DT') or name.endswith('_DATE'):
        entity = name.replace('_DT', '').replace('_DATE', '').replace('_', ' ').lower()
        return f"{entity.title()} date"
    if name.endswith('_DTTM') or name.endswith('_DATETIME'):
        entity = name.replace('_DTTM', '').replace('_DATETIME', '').replace('_', ' ').lower()
        return f"{entity.title()} timestamp"
    if 'UTC' in name:
        return f"{name.replace('_', ' ').title()} (UTC timezone)"
    if 'RHQ' in name:
        return f"{name.replace('_', ' ').title()} (Regional HQ timezone)"
    
    # Amount/currency columns
    if '_USD' in name:
        base = name.replace('_USD', '').replace('_', ' ').lower()
        if 'CENTS' in name:
            return f"{base.title()} in USD cents"
        return f"{base.title()} in USD"
    if '_EUR' in name:
        base = name.replace('_EUR', '').replace('_', ' ').lower()
        return f"{base.title()} in EUR"
    if any(x in name for x in ['_AMT', 'AMOUNT', 'REVENUE', 'COST', 'PRICE', 'SPEND']):
        return f"{name.replace('_', ' ').title()} amount"
    
    # Indicator/flag columns
    if name.endswith('_IND'):
        entity = name[:-4].replace('_', ' ').lower()
        return f"Indicator flag for {entity}"
    if name.startswith('IS_'):
        entity = name[3:].replace('_', ' ').lower()
        return f"Boolean flag indicating if {entity}"
    if name.startswith('HAS_'):
        entity = name[4:].replace('_', ' ').lower()
        return f"Boolean flag indicating has {entity}"
    
    # Code columns
    if name.endswith('_CODE'):
        entity = name[:-5].replace('_', ' ').title()
        return f"{entity} code"
    
    # Count/quantity columns
    if 'QTY' in name or 'QUANTITY' in name:
        return f"Quantity count"
    if 'COUNT' in name:
        entity = name.replace('COUNT', '').replace('_', ' ').strip()
        return f"Count of {entity.lower()}" if entity else "Record count"
    
    # Name/description columns
    if name.endswith('_NAME'):
        entity = name[:-5].replace('_', ' ').title()
        return f"{entity} name"
    if name.endswith('_DESC') or name.endswith('_DESCRIPTION'):
        entity = name.replace('_DESC', '').replace('_DESCRIPTION', '').replace('_', ' ').title()
        return f"{entity} description"
    
    # Default: humanize the column name
    return name.replace('_', ' ').title()


def load_extraction_results(filepath: str) -> dict:
    with open(filepath, 'r') as f:
        return json.load(f)


def load_source_queries(filepath: str) -> list:
    """Load original queries from CSV for metric extraction."""
    queries = []
    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader, 1):
            if row.get('SQL'):
                queries.append({
                    'index': i,
                    'sql': row['SQL'],
                    'question': row.get('Question', ''),
                    'domain': row.get('Domain', 'Unknown')
                })
    return queries


def analyze_domains(data: dict) -> dict:
    """Analyze domain distribution of tables."""
    domain_tables = defaultdict(set)
    table_domains = defaultdict(set)
    table_queries = defaultdict(list)
    domain_queries = defaultdict(list)
    
    for query in data.get('queries', []):
        if query.get('skipped'):
            continue
        
        domain = query.get('metadata', {}).get('Domain', 'Unknown')
        if not domain:
            domain = 'Unknown'
        
        query_idx = query.get('index', 0)
        question = query.get('metadata', {}).get('Question', '')[:100]
        domain_queries[domain].append({'index': query_idx, 'question': question})
        
        for table in query.get('tables', []):
            domain_tables[domain].add(table)
            table_domains[table].add(domain)
            table_queries[table].append(query_idx)
    
    shared_tables = {t: list(d) for t, d in table_domains.items() if len(d) > 1}
    
    return {
        'domains': {d: sorted(list(tables)) for d, tables in domain_tables.items()},
        'domain_query_counts': {d: len(q) for d, q in domain_queries.items()},
        'shared_tables': shared_tables,
        'table_usage': {t: sorted(q) for t, q in table_queries.items()}
    }


def extract_metrics_from_queries(queries: list) -> dict:
    """Extract metric definitions from SQL aggregations."""
    agg_pattern = r'(SUM|COUNT|AVG|MIN|MAX|MEDIAN|STDDEV|VARIANCE)\s*\(\s*(DISTINCT\s+)?([^)]+)\)'
    
    domain_metrics = defaultdict(lambda: defaultdict(list))
    
    for q in queries:
        sql = q['sql']
        domain = q['domain']
        matches = re.findall(agg_pattern, sql, re.IGNORECASE)
        
        for func, distinct, expr in matches:
            expr_clean = expr.strip()
            if len(expr_clean) > 100:
                continue
            if expr_clean.upper() in ('*', '1'):
                metric_name = f"{func.lower()}_all"
                expr_clean = '*' if expr_clean == '*' else '1'
            else:
                col_match = re.search(r'([a-zA-Z_][a-zA-Z0-9_]*)\s*$', expr_clean)
                if col_match:
                    col_name = col_match.group(1)
                    metric_name = f"{func.lower()}_{col_name.lower()}"
                else:
                    continue
            
            distinct_str = 'DISTINCT ' if distinct else ''
            metric_expr = f"{func.upper()}({distinct_str}{expr_clean})"
            
            domain_metrics[domain][metric_name].append({
                'expr': metric_expr,
                'query_idx': q['index'],
                'question': q['question'][:100]
            })
    
    consolidated = {}
    for domain, metrics in domain_metrics.items():
        consolidated[domain] = {}
        for metric_name, occurrences in metrics.items():
            most_common_expr = max(set(o['expr'] for o in occurrences), 
                                   key=lambda x: sum(1 for o in occurrences if o['expr'] == x))
            consolidated[domain][metric_name] = {
                'name': metric_name,
                'expr': most_common_expr,
                'usage_count': len(occurrences),
                'sample_questions': list(set(o['question'] for o in occurrences))[:3]
            }
    
    return consolidated


def classify_column_from_schema(col_name: str, col_type: str) -> str:
    """Classify column based on name AND data type from schema."""
    name = col_name.upper()
    type_upper = col_type.upper()
    
    if name.endswith('_ID') or name.endswith('_KEY') or name == 'ID':
        return 'key'
    
    if 'DATE' in type_upper or 'TIME' in type_upper:
        return 'time_dimension'
    
    if 'NUMBER' in type_upper or 'FLOAT' in type_upper or 'DECIMAL' in type_upper or 'INT' in type_upper:
        if any(x in name for x in ['_AMT', '_AMOUNT', '_QTY', '_QUANTITY', '_COUNT', '_SUM', 
                                    '_TOTAL', '_BALANCE', '_PRICE', '_COST', '_REVENUE',
                                    '_PCT', '_RATE', '_RATIO', '_MARGIN']):
            return 'fact'
        if name.endswith('_IND') or name.startswith('IS_') or name.startswith('HAS_'):
            return 'dimension'
        if name.endswith('_ID') or name.endswith('_KEY'):
            return 'key'
        return 'fact'
    
    return 'dimension'


def generate_logical_table(table_name: str, columns: list, schemas: dict, 
                          table_metrics: dict = None) -> dict:
    """Generate a logical table definition with proper schema-based classification."""
    parts = table_name.split('.')
    
    if len(parts) == 3:
        database, schema, table = parts
    elif len(parts) == 2:
        database, table = parts[0], parts[1]
        schema = 'PUBLIC'
    else:
        database, schema, table = 'DATABASE', 'SCHEMA', parts[0]
    
    logical_table = {
        'name': table.lower(),
        'description': f"Logical table for {table}",
        'base_table': {
            'database': database,
            'schema': schema,
            'table': table
        },
        'dimensions': [],
        'time_dimensions': [],
        'facts': [],
        'metrics': []
    }
    
    if schemas and table_name in schemas:
        for col_info in schemas[table_name]:
            col_name = col_info['name']
            col_type = col_info.get('data_type', 'VARCHAR')
            col_category = classify_column_from_schema(col_name, col_type)
            
            description = generate_description(col_name, col_type, table)
            
            col_def = {
                'name': col_name.lower(),
                'description': description,
                'expr': col_name,
                'data_type': col_type
            }
            
            if col_category == 'time_dimension':
                logical_table['time_dimensions'].append(col_def)
            elif col_category == 'fact':
                col_def['access_modifier'] = 'public_access'
                logical_table['facts'].append(col_def)
            elif col_category == 'dimension':
                logical_table['dimensions'].append(col_def)
    
    if table_metrics:
        for metric_name, metric_info in table_metrics.items():
            metric_def = {
                'name': metric_name,
                'description': f"Metric: {metric_info.get('sample_questions', [''])[0][:80]}",
                'expr': metric_info['expr']
            }
            logical_table['metrics'].append(metric_def)
    
    if not logical_table['dimensions']:
        del logical_table['dimensions']
    if not logical_table['time_dimensions']:
        del logical_table['time_dimensions']
    if not logical_table['facts']:
        del logical_table['facts']
    if not logical_table['metrics']:
        del logical_table['metrics']
    
    return logical_table


def infer_relationships_from_schemas(tables: list, schemas: dict) -> list:
    """Infer relationships based on matching column names across tables."""
    relationships = []
    seen_pairs = set()
    
    table_columns = {}
    for table in tables:
        if table in schemas:
            table_columns[table] = {col['name'].upper() for col in schemas[table]}
    
    dim_tables = [t for t in tables if 'DIM_' in t.upper() and t in table_columns]
    fct_tables = [t for t in tables if 'FCT_' in t.upper() and t in table_columns]
    
    for fct in fct_tables:
        fct_name = fct.split('.')[-1].upper()
        fct_cols = table_columns.get(fct, set())
        
        for dim in dim_tables:
            dim_name = dim.split('.')[-1].upper()
            dim_cols = table_columns.get(dim, set())
            
            common_keys = []
            for col in fct_cols:
                if col.endswith('_ID') or col.endswith('_KEY'):
                    if col in dim_cols:
                        common_keys.append(col)
            
            if common_keys:
                pair_key = (fct_name, dim_name)
                if pair_key not in seen_pairs:
                    seen_pairs.add(pair_key)
                    relationships.append({
                        'name': f"{fct_name.lower()}_to_{dim_name.lower()}",
                        'left_table': fct_name.lower(),
                        'right_table': dim_name.lower(),
                        'relationship_columns': [
                            {'left_column': key, 'right_column': key}
                            for key in common_keys[:3]
                        ]
                    })
    
    return relationships


def generate_verified_queries(source_queries: list, domain: str) -> list:
    """Generate verified_queries section with actual SQL."""
    verified = []
    
    for q in source_queries:
        if q.get('domain') != domain:
            continue
        
        question = q.get('question', '')
        sql = q.get('sql', '')
        
        if not question or not sql:
            continue
        
        if 'CREATE' in sql.upper() or 'UPDATE' in sql.upper() or 'DELETE' in sql.upper():
            continue
        
        verified.append({
            'name': f"vqr_{q.get('index', 0)}",
            'question': question[:500],
            'sql': sql,
            'use_as_onboarding_question': len(verified) < 5
        })
        
        if len(verified) >= 50:
            break
    
    return verified


def generate_semantic_view_yaml(domain: str, tables: list, data: dict, 
                                schemas: dict, metrics: dict,
                                source_queries: list, view_prefix: str = 'sv') -> dict:
    """Generate complete semantic view YAML for a domain."""
    
    if not schemas:
        print(f"WARNING: No schemas provided. Run fetch-schemas first for accurate results.", file=sys.stderr)
    
    domain_metrics = metrics.get(domain, {})
    
    logical_tables = []
    for table in sorted(tables):
        table_short = table.split('.')[-1].upper()
        
        relevant_metrics = {k: v for k, v in domain_metrics.items() 
                          if table_short.lower() in k.lower()}
        
        logical_table = generate_logical_table(table, [], schemas, relevant_metrics)
        logical_tables.append(logical_table)
    
    relationships = infer_relationships_from_schemas(tables, schemas)
    
    verified_queries = generate_verified_queries(source_queries, domain)
    
    domain_slug = domain.lower().replace(' ', '_').replace('&', 'and')
    
    semantic_view = {
        'name': f"{view_prefix}_{domain_slug}",
        'description': f"Semantic view for {domain} analytics",
        'tables': logical_tables
    }
    
    if relationships:
        semantic_view['relationships'] = relationships
    
    if verified_queries:
        semantic_view['verified_queries'] = verified_queries
    
    return semantic_view


def fetch_schemas_from_snowflake(tables: list, connection_name: str) -> dict:
    """Fetch actual column schemas from Snowflake."""
    try:
        import snowflake.connector
    except ImportError:
        print("Error: snowflake-connector-python not installed", file=sys.stderr)
        return {}
    
    conn = snowflake.connector.connect(
        connection_name=os.getenv("SNOWFLAKE_CONNECTION_NAME") or connection_name
    )
    
    schemas = {}
    cursor = conn.cursor()
    
    for table in tables:
        try:
            cursor.execute(f"DESCRIBE TABLE {table}")
            columns = []
            for row in cursor.fetchall():
                columns.append({
                    'name': row[0],
                    'data_type': row[1]
                })
            schemas[table] = columns
            print(f"  ✓ {table}: {len(columns)} columns", file=sys.stderr)
        except Exception as e:
            print(f"  ✗ {table}: {e}", file=sys.stderr)
    
    cursor.close()
    conn.close()
    
    return schemas


def main():
    parser = argparse.ArgumentParser(description='Generate Semantic View YAMLs from extracted tables')
    parser.add_argument('--input', '-i', required=True, help='Path to extracted tables JSON')
    parser.add_argument('--action', '-a', choices=['analyze', 'fetch-schemas', 'extract-metrics', 'generate'], 
                        required=True, help='Action to perform')
    parser.add_argument('--schemas', '-s', help='Path to schemas JSON (REQUIRED for generate)')
    parser.add_argument('--metrics', '-m', help='Path to metrics JSON (for generate)')
    parser.add_argument('--source-csv', help='Path to source CSV with queries (for extract-metrics and generate)')
    parser.add_argument('--output-dir', '-o', default='.', help='Output directory for YAML files')
    parser.add_argument('--output', help='Output file path (for fetch-schemas, extract-metrics)')
    parser.add_argument('--view-prefix', default='sv', help='Prefix for semantic view names')
    parser.add_argument('--connection', '-c', help='Snowflake connection name')
    parser.add_argument('--domain', '-d', help='Generate for specific domain only')
    
    args = parser.parse_args()
    
    data = load_extraction_results(args.input)
    analysis = analyze_domains(data)
    
    if args.action == 'analyze':
        print("\n=== Domain Analysis ===\n")
        for domain, tables in sorted(analysis['domains'].items()):
            query_count = analysis['domain_query_counts'].get(domain, 0)
            print(f"\n{domain} ({query_count} queries, {len(tables)} tables):")
            
            dims = [t for t in tables if 'DIM_' in t]
            facts = [t for t in tables if 'FCT_' in t]
            others = [t for t in tables if 'DIM_' not in t and 'FCT_' not in t]
            
            if dims:
                print(f"  Dimensions ({len(dims)}): {', '.join(t.split('.')[-1] for t in dims[:5])}{'...' if len(dims) > 5 else ''}")
            if facts:
                print(f"  Facts ({len(facts)}): {', '.join(t.split('.')[-1] for t in facts[:5])}{'...' if len(facts) > 5 else ''}")
            if others:
                print(f"  Other ({len(others)}): {', '.join(t.split('.')[-1] for t in others[:5])}{'...' if len(others) > 5 else ''}")
        
        if analysis['shared_tables']:
            print(f"\n=== Shared Tables (across domains) ===")
            print(f"Tables used in multiple domains: {len(analysis['shared_tables'])}")
            for table, domains in list(analysis['shared_tables'].items())[:10]:
                print(f"  {table.split('.')[-1]}: {', '.join(domains)}")
    
    elif args.action == 'fetch-schemas':
        connection = args.connection or os.getenv("SNOWFLAKE_CONNECTION_NAME")
        
        if not connection:
            print("\n=== Snowflake Connection Required ===\n", file=sys.stderr)
            print("To fetch live schemas, please provide a Snowflake connection name.", file=sys.stderr)
            print("This should match a connection configured in your Snowflake CLI or environment.\n", file=sys.stderr)
            connection = input("Enter Snowflake connection name: ").strip()
            
            if not connection:
                print("Error: Connection name is required for fetch-schemas", file=sys.stderr)
                sys.exit(1)
        
        all_tables = set()
        for tables in analysis['domains'].values():
            all_tables.update(tables)
        
        print(f"\nFetching schemas for {len(all_tables)} tables using connection '{connection}'...\n", file=sys.stderr)
        schemas = fetch_schemas_from_snowflake(sorted(all_tables), connection)
        
        output_path = args.output or 'schemas.json'
        with open(output_path, 'w') as f:
            json.dump(schemas, f, indent=2)
        
        print(f"\n✓ Schemas saved to: {output_path}", file=sys.stderr)
        print(f"  Tables fetched: {len(schemas)}/{len(all_tables)}", file=sys.stderr)
    
    elif args.action == 'extract-metrics':
        if not args.source_csv:
            print("Error: --source-csv required for extract-metrics", file=sys.stderr)
            sys.exit(1)
        
        print(f"Loading queries from {args.source_csv}...", file=sys.stderr)
        source_queries = load_source_queries(args.source_csv)
        
        print(f"Extracting metrics from {len(source_queries)} queries...", file=sys.stderr)
        metrics = extract_metrics_from_queries(source_queries)
        
        output_path = args.output or 'metrics.json'
        with open(output_path, 'w') as f:
            json.dump(metrics, f, indent=2)
        
        print(f"\n✓ Metrics saved to: {output_path}", file=sys.stderr)
        for domain, domain_metrics in metrics.items():
            print(f"  {domain}: {len(domain_metrics)} unique metrics", file=sys.stderr)
    
    elif args.action == 'generate':
        if not args.schemas:
            print("Error: --schemas required for generate. Run fetch-schemas first.", file=sys.stderr)
            sys.exit(1)
        
        with open(args.schemas, 'r') as f:
            schemas = json.load(f)
        
        metrics = {}
        if args.metrics:
            with open(args.metrics, 'r') as f:
                metrics = json.load(f)
        
        source_queries = []
        if args.source_csv:
            source_queries = load_source_queries(args.source_csv)
        
        output_dir = Path(args.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        domains_to_generate = [args.domain] if args.domain else analysis['domains'].keys()
        
        for domain in domains_to_generate:
            if domain not in analysis['domains']:
                print(f"Warning: Domain '{domain}' not found", file=sys.stderr)
                continue
            
            tables = analysis['domains'][domain]
            semantic_view = generate_semantic_view_yaml(
                domain, tables, data, schemas, metrics, source_queries, args.view_prefix
            )
            
            domain_slug = domain.lower().replace(' ', '_').replace('&', 'and')
            output_file = output_dir / f"{args.view_prefix}_{domain_slug}.yaml"
            
            with open(output_file, 'w') as f:
                yaml.dump(semantic_view, f, default_flow_style=False, sort_keys=False, 
                         allow_unicode=True, width=1000)
            
            table_count = len(semantic_view.get('tables', []))
            rel_count = len(semantic_view.get('relationships', []))
            vqr_count = len(semantic_view.get('verified_queries', []))
            
            total_dims = sum(len(t.get('dimensions', [])) for t in semantic_view.get('tables', []))
            total_facts = sum(len(t.get('facts', [])) for t in semantic_view.get('tables', []))
            total_metrics = sum(len(t.get('metrics', [])) for t in semantic_view.get('tables', []))
            
            print(f"\n✓ Generated: {output_file}", file=sys.stderr)
            print(f"  Tables: {table_count} | Dims: {total_dims} | Facts: {total_facts} | Metrics: {total_metrics}", file=sys.stderr)
            print(f"  Relationships: {rel_count} | Verified Queries: {vqr_count}", file=sys.stderr)


if __name__ == '__main__':
    main()
