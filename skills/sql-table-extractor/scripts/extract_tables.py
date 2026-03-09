#!/usr/bin/env python3
"""
extract_tables.py - Extract tables and columns from SQL queries

Supports:
- Snowflake double-dot notation (database..table -> database.PUBLIC.table)
- Skipping DML/DDL operations
- Multiple input formats (CSV, JSON, SQL files, directories)
"""

import argparse
import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path


def remove_comments(sql: str) -> str:
    sql = re.sub(r'--.*?$', '', sql, flags=re.MULTILINE)
    sql = re.sub(r'/\*.*?\*/', '', sql, flags=re.DOTALL)
    sql = re.sub(r'//.*?$', '', sql, flags=re.MULTILINE)
    return sql


def is_dml_or_ddl(sql: str) -> bool:
    sql_clean = remove_comments(sql).strip().upper()
    patterns = [
        r'^\s*UPDATE\s+',
        r'^\s*DELETE\s+',
        r'^\s*INSERT\s+',
        r'CREATE\s+(OR\s+REPLACE\s+)?(TEMP|TEMPORARY|VOLATILE)?\s*TABLE\s+',
        r'^\s*DROP\s+',
        r'^\s*ALTER\s+',
        r'^\s*TRUNCATE\s+',
        r'^\s*MERGE\s+',
    ]
    for pattern in patterns:
        if re.search(pattern, sql_clean, re.MULTILINE):
            return True
    return False


def normalize_table_name(table_name: str) -> str:
    """Normalize table names, handling Snowflake double-dot notation."""
    table_name = table_name.strip().replace('"', '').upper()
    
    if '..' in table_name:
        parts = table_name.split('..')
        if len(parts) == 2:
            database = parts[0]
            table = parts[1]
            return f"{database}.PUBLIC.{table}"
    
    return table_name


def extract_tables(sql: str) -> list:
    sql_clean = remove_comments(sql)
    tables = set()
    
    table_pattern = r'(?:FROM|JOIN)\s+(["\w]+(?:\.\.?["\w]+)*)\s*(?:AS\s+)?'
    matches = re.findall(table_pattern, sql_clean, re.IGNORECASE)
    
    skip_words = {
        'SELECT', 'WHERE', 'AND', 'OR', 'ON', 'GROUP', 'ORDER', 'HAVING',
        'LIMIT', 'UNION', 'CASE', 'WHEN', 'THEN', 'ELSE', 'END', 'AS',
        'LEFT', 'RIGHT', 'INNER', 'OUTER', 'CROSS', 'FULL', 'LATERAL',
        'WITH', 'RECURSIVE', 'NOT', 'NULL', 'TRUE', 'FALSE', 'IN', 'EXISTS'
    }
    
    for match in matches:
        table_name = normalize_table_name(match)
        parts = table_name.split('.')
        
        if parts[-1] not in skip_words and not re.match(r'^\d+$', parts[-1]):
            if not parts[-1].startswith('PA') or len(parts[-1]) > 5:
                tables.add(table_name)
    
    return sorted(list(tables))


def extract_columns(sql: str) -> dict:
    sql_clean = remove_comments(sql)
    columns = defaultdict(set)
    
    col_ref_pattern = r'["\']?([A-Za-z_][A-Za-z0-9_]*)["\']?\s*\.\s*["\']?([A-Za-z_][A-Za-z0-9_]*)["\']?'
    matches = re.findall(col_ref_pattern, sql_clean)
    
    skip_cols = {'PUBLIC', 'DBO', 'SCHEMA', 'FCT', 'DIM', 'ALL'}
    
    for alias, col in matches:
        col_upper = col.upper()
        if col_upper not in skip_cols and not col_upper.startswith('PS_PRD'):
            columns[alias.upper()].add(col_upper)
    
    return {k: sorted(list(v)) for k, v in columns.items()}


def load_queries_csv(filepath: str, sql_column: str) -> list:
    queries = []
    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get(sql_column):
                queries.append({
                    'sql': row[sql_column].strip(),
                    'metadata': {k: v for k, v in row.items() if k != sql_column}
                })
    return queries


def load_queries_json(filepath: str) -> list:
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    if isinstance(data, list):
        queries = []
        for item in data:
            if isinstance(item, str):
                queries.append({'sql': item, 'metadata': {}})
            elif isinstance(item, dict) and 'sql' in item:
                queries.append({'sql': item['sql'], 'metadata': {k: v for k, v in item.items() if k != 'sql'}})
        return queries
    return []


def load_queries_sql(filepath: str) -> list:
    with open(filepath, 'r', encoding='utf-8') as f:
        sql = f.read()
    return [{'sql': sql, 'metadata': {'file': filepath}}]


def load_queries_dir(dirpath: str, sql_column: str = 'SQL') -> list:
    """Load all query files from a directory (CSV, JSON, SQL)."""
    queries = []
    dirpath = Path(dirpath)
    
    for csv_file in dirpath.glob('**/*.csv'):
        try:
            loaded = load_queries_csv(str(csv_file), sql_column)
            queries.extend(loaded)
            print(f"  Loaded CSV: {csv_file.name} ({len(loaded)} queries)", file=sys.stderr)
        except Exception as e:
            print(f"  Warning: Failed to load {csv_file}: {e}", file=sys.stderr)
    
    for json_file in dirpath.glob('**/*.json'):
        try:
            loaded = load_queries_json(str(json_file))
            queries.extend(loaded)
            print(f"  Loaded JSON: {json_file.name} ({len(loaded)} queries)", file=sys.stderr)
        except Exception as e:
            print(f"  Warning: Failed to load {json_file}: {e}", file=sys.stderr)
    
    for sql_file in dirpath.glob('**/*.sql'):
        try:
            loaded = load_queries_sql(str(sql_file))
            queries.extend(loaded)
            print(f"  Loaded SQL: {sql_file.name}", file=sys.stderr)
        except Exception as e:
            print(f"  Warning: Failed to load {sql_file}: {e}", file=sys.stderr)
    
    return queries


def detect_and_load(input_path: str, sql_column: str = 'SQL') -> list:
    """Auto-detect input type and load queries."""
    path = Path(input_path)
    
    if path.is_dir():
        print(f"Loading all files from directory: {path}", file=sys.stderr)
        return load_queries_dir(input_path, sql_column)
    elif path.suffix.lower() == '.csv':
        return load_queries_csv(input_path, sql_column)
    elif path.suffix.lower() == '.json':
        return load_queries_json(input_path)
    elif path.suffix.lower() == '.sql':
        return load_queries_sql(input_path)
    else:
        raise ValueError(f"Unknown file type: {path.suffix}")


def process_query(idx: int, query: dict) -> dict:
    sql = query['sql']
    metadata = query.get('metadata', {})
    
    sql_clean = remove_comments(sql)
    
    if is_dml_or_ddl(sql_clean):
        return {
            'index': idx,
            'metadata': metadata,
            'skipped': True,
            'reason': 'DML/DDL operation detected',
            'tables': [],
            'columns': {}
        }
    
    tables = extract_tables(sql_clean)
    columns = extract_columns(sql_clean)
    
    return {
        'index': idx,
        'metadata': metadata,
        'skipped': False,
        'tables': tables,
        'columns': columns
    }


def build_consolidated(results: list) -> dict:
    all_tables = defaultdict(list)
    
    for result in results:
        if not result['skipped']:
            for table in result['tables']:
                all_tables[table].append(result['index'])
    
    dim_tables = {}
    fct_tables = {}
    other_tables = {}
    
    for table, query_refs in sorted(all_tables.items()):
        table_name = table.split('.')[-1]
        entry = {'table': table, 'used_in_queries': query_refs}
        
        if table_name.startswith('DIM_'):
            dim_tables[table] = entry
        elif table_name.startswith('FCT_'):
            fct_tables[table] = entry
        else:
            other_tables[table] = entry
    
    return {
        'dimension_tables': dim_tables,
        'fact_tables': fct_tables,
        'other_tables': other_tables
    }


def main():
    parser = argparse.ArgumentParser(description='Extract tables and columns from SQL queries')
    parser.add_argument('--input', '-i', required=True, 
                        help='Input file (CSV/JSON/SQL) or directory containing query files')
    parser.add_argument('--sql-column', default='SQL', help='Column name containing SQL (for CSV)')
    parser.add_argument('--output', '-o', default='extracted_tables.json', help='Output JSON path')
    parser.add_argument('--no-consolidated', action='store_true', help='Skip consolidated output')
    
    args = parser.parse_args()
    
    queries = detect_and_load(args.input, args.sql_column)
    
    print(f"\nTotal loaded: {len(queries)} queries", file=sys.stderr)
    
    results = []
    skipped = 0
    processed = 0
    all_tables = set()
    
    for idx, query in enumerate(queries, 1):
        result = process_query(idx, query)
        results.append(result)
        
        if result['skipped']:
            skipped += 1
        else:
            processed += 1
            all_tables.update(result['tables'])
    
    consolidated = build_consolidated(results) if not args.no_consolidated else None
    
    output = {
        'summary': {
            'total_queries': len(queries),
            'processed': processed,
            'skipped': skipped,
            'unique_tables': len(all_tables),
            'dimension_tables': len(consolidated['dimension_tables']) if consolidated else 0,
            'fact_tables': len(consolidated['fact_tables']) if consolidated else 0,
            'other_tables': len(consolidated['other_tables']) if consolidated else 0
        },
        'queries': results
    }
    
    if consolidated:
        output['consolidated'] = consolidated
    
    with open(args.output, 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"\nSummary:", file=sys.stderr)
    print(f"  Total queries: {len(queries)}", file=sys.stderr)
    print(f"  Processed: {processed}", file=sys.stderr)
    print(f"  Skipped (DML/DDL): {skipped}", file=sys.stderr)
    print(f"  Unique tables: {len(all_tables)}", file=sys.stderr)
    print(f"\nOutput written to: {args.output}", file=sys.stderr)


if __name__ == '__main__':
    main()
