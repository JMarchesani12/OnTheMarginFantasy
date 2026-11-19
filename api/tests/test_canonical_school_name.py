"""Canonical labels work when School.shortName/SportTeam.displayName do not exist."""
import unittest
from endpoints.sport.service import SportService
from endpoints.league.reads.repository import LeagueReadRepository
from endpoints.schedule.ingestion_repository import ScheduleIngestionRepository
from test_league_read_authorization import ReadDatabase
from sqlalchemy import text


class CanonicalSchoolNameTests(unittest.TestCase):
    def setUp(self):
        self.db=ReadDatabase();self.addCleanup(self.db.connection.close)
        self.db.connection.executescript('''
            CREATE TABLE School(id INTEGER PRIMARY KEY,name TEXT);
            INSERT INTO School VALUES(369,'Northern Iowa');
            CREATE TABLE SportTeam(id INTEGER PRIMARY KEY,schoolId INTEGER,sportId INTEGER,externalId TEXT,tier INTEGER);
            INSERT INTO SportTeam VALUES(369,369,1,'2460',1),(525,369,2,'2460',1);
            CREATE TABLE SchoolAlias(schoolId INTEGER,alias TEXT,normalizedAlias TEXT,source TEXT,UNIQUE(schoolId,normalizedAlias));
            INSERT INTO SchoolAlias VALUES(369,'UNI','uni','preserved'),(369,'University of Northern Iowa','university of northern iowa','preserved');
        ''')

    def test_catalog_uses_one_school_name_for_both_sports(self):
        teams=SportService(self.db).team_search_catalog()['teams']
        self.assertEqual([row['teamName'] for row in teams],['Northern Iowa','Northern Iowa'])
        self.assertTrue(all('UNI' in row['aliases'] for row in teams))
        self.db.connection.execute("UPDATE School SET name='Updated School' WHERE id=369")
        self.assertEqual({row['teamName'] for row in SportService(self.db).team_search_catalog()['teams']},{'Updated School'})

    def test_rules_and_ingestion_resolve_school_name_without_old_columns(self):
        rows=LeagueReadRepository().rules_teams(self.db,1)
        self.assertEqual(rows[0]['teamName'],'Northern Iowa')
        row=ScheduleIngestionRepository().sport_teams(self.db,{'sportId':1}).fetchone()._mapping
        self.assertEqual(row['displayName'],'Northern Iowa')

    def test_seed_import_does_not_require_retired_columns(self):
        from utils.school_alias_seed import import_school_aliases
        with self.db.begin() as conn:
            import_school_aliases(conn,{'groups':[]})
        self.assertIsNotNone(self.db.connection.execute("SELECT 1 FROM SchoolAlias WHERE alias='Northern Iowa'").fetchone())
