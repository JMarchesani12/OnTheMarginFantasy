"""Bridge historical minimal fixtures to the real School join.

Old fixture schemas omitted schoolId/School entirely. Expose their existing
labels as a temporary School view, and map omitted schoolId to that fixture's
team ID. No production code uses this adapter. Tests of canonical naming create
actual School rows and physically omit the old columns, bypassing this bridge.
"""
import re


def adapt_legacy_school_fixture(connection, statement):
    if not re.search(r'(?:FROM|JOIN) "School"(?:\s|$)', statement): return statement
    exists=connection.execute("SELECT 1 FROM sqlite_master WHERE name='School' UNION ALL SELECT 1 FROM sqlite_temp_master WHERE name='School'").fetchone()
    columns={row[1] for row in connection.execute('PRAGMA table_info("SportTeam")')}
    if not exists and 'displayName' in columns:
        key='"schoolId"' if 'schoolId' in columns else 'id'
        connection.execute(f'CREATE TEMP VIEW "School" AS SELECT {key} AS id,"displayName" AS name FROM "SportTeam"')
    legacy=connection.execute("SELECT 1 FROM sqlite_temp_master WHERE name='School' AND type='view'").fetchone()
    if legacy and 'schoolId' not in columns:
        aliases=re.findall(r'(?:FROM|JOIN) "SportTeam" ([a-zA-Z_][a-zA-Z0-9_]*)',statement)
        for alias in aliases: statement=statement.replace(f'{alias}."schoolId"',f'{alias}.id')
    return statement
