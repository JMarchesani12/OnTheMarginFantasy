"""Synthetic capacity tables and PostgreSQL JSON adaptation for isolated tests."""
import json
from types import SimpleNamespace


def install_capacity_fixture(db, max_rounds=8):
    connection = db.connection
    def add_column(table, column, definition):
        if column not in {row[1] for row in connection.execute(f'PRAGMA table_info("{table}")')}:
            connection.execute(f'ALTER TABLE "{table}" ADD COLUMN "{column}" {definition}')
    connection.execute('CREATE TABLE IF NOT EXISTS "Sport" (id INTEGER PRIMARY KEY)')
    add_column('Sport', 'maxDraftRounds', f'INTEGER DEFAULT {max_rounds}')
    connection.execute('INSERT OR IGNORE INTO "Sport" (id) VALUES (1)')
    add_column('League', 'sport', 'INTEGER DEFAULT 1')
    add_column('League', 'seasonYear', 'INTEGER DEFAULT 2026')
    add_column('League', 'status', "TEXT DEFAULT 'Pre-Draft'")
    add_column('League', 'settings', "TEXT DEFAULT '{}'")
    add_column('League', 'updatedAt', 'TEXT')
    connection.executescript('''
        CREATE TABLE IF NOT EXISTS "DraftState" ("leagueId" INTEGER PRIMARY KEY, status TEXT);
        CREATE TABLE IF NOT EXISTS "SportTeam" (id INTEGER PRIMARY KEY, "sportId" INTEGER, "displayName" TEXT);
        CREATE TABLE IF NOT EXISTS "SportConference" (id INTEGER PRIMARY KEY, "sportId" INTEGER, "maxTeamsPerOwner" INTEGER);
        CREATE TABLE IF NOT EXISTS "ConferenceMembership" ("sportTeamId" INTEGER, "sportId" INTEGER, "seasonYear" INTEGER, "sportConferenceId" INTEGER);
    ''')
    if not connection.execute('SELECT 1 FROM "SportConference"').fetchone():
        connection.execute('INSERT INTO "SportConference" (id,"sportId","maxTeamsPerOwner") VALUES (501,1,?)', (max_rounds,))
        for team in range(101, 133):
            connection.execute('INSERT INTO "SportTeam" VALUES (?,1,?)', (team, f'Team {team}'))
            connection.execute('INSERT INTO "ConferenceMembership" VALUES (?,1,2026,501)', (team,))
    execute = db.execute
    def capacity_execute(statement, params):
        sql = str(statement)
        if 'AS "memberCount"' not in sql and 'AS "teamsInConference"' not in sql and 'capacitySettings' not in sql:
            return execute(statement, params)
        if getattr(db, 'before_query', None): db.before_query(sql)
        if getattr(db, 'fail_league_update', False) and 'capacitySettings' in sql:
            raise RuntimeError('Synthetic failure after membership INSERT')
        cursor = connection.execute(sql.replace('CAST(:capacitySettings AS jsonb)', ':capacitySettings'), params)
        def mapped(row):
            if row is None: return None
            value = dict(row)
            if isinstance(value.get('settings'), str): value['settings'] = json.loads(value['settings'])
            return SimpleNamespace(_mapping=value)
        class Result:
            def fetchone(self): return mapped(cursor.fetchone())
            def fetchall(self): return [mapped(row) for row in cursor.fetchall()]
        return Result()
    db.execute = capacity_execute
    connection.commit()
