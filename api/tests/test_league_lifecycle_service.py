"""Lifecycle policy matrix and rollback with adapted actual SQL on SQLite."""
import sqlite3
import unittest
from contextlib import contextmanager
from endpoints.league.leagueModel import LeagueModel

FIXTURE='''CREATE TABLE "League" (id INTEGER PRIMARY KEY,status TEXT,"updatedAt" TEXT,"draftDate" TEXT,sport INTEGER,"seasonYear" INTEGER);
CREATE TABLE "DraftState" ("leagueId" INTEGER,status TEXT);
CREATE TABLE "SportSeason" ("sportId" INTEGER,"seasonYear" INTEGER,"seasonStart" TEXT,"seasonEnd" TEXT);
INSERT INTO "SportSeason" VALUES (1,2026,'2026-11-10','2026-12-31'),(2,2026,'2026-10-01','2026-11-30'),
(3,2026,'2026-08-01','2026-10-01'),(4,2026,'2026-10-30','2026-11-15'),(5,2026,'2026-10-01','2026-10-30');
INSERT INTO "League" VALUES
(1,'Unknown','old','2026-11-01',1,2026),(2,'Unknown','old','2026-11-01',1,2026),
(3,'Unknown','old','2026-11-01',1,2026),(4,'Unknown','old','2026-11-01',1,2026),
(5,'Unknown','old',NULL,2,2026),(6,'Unknown','old','2026-11-01',3,2026),
(7,'Unknown','old','2026-11-01',3,2026),(8,'Completed','old',NULL,2,2026),
(9,'Pre-Draft','old','2026-11-01',1,2026),(10,'Custom','old',NULL,99,2026),
(11,'Custom','old',NULL,2,2025),(12,'Unknown','old',NULL,4,2026),(13,'Unknown','old',NULL,5,2026);
INSERT INTO "DraftState" VALUES (2,'live'),(3,'paused'),(4,'complete'),(6,'live'),(7,'complete');'''
EXPECTED={1:'Pre-Draft',2:'Drafting',3:'Drafting',4:'Post-Draft',5:'In-Season',6:'Completed',7:'Completed',
          8:'Completed',9:'Pre-Draft',10:'Custom',11:'Custom',12:'In-Season',13:'In-Season'}


class LifecycleDatabase:
    def __init__(self):
        self.connection=sqlite3.connect(':memory:');self.connection.row_factory=sqlite3.Row
        self.connection.create_function('now',0,lambda:'2026-10-30T12:00:00Z')
        self.connection.executescript(FIXTURE);self.begins=0;self.statements=0;self.fail_after=None
    @contextmanager
    def begin(self):
        self.begins+=1
        with self.connection:yield self
    def execute(self,statement):
        sql=str(statement).replace('UPDATE "League" l','UPDATE "League" AS l').replace('now()::date','date(now())')
        sql=sql.replace('ss."seasonStart"::date','date(ss."seasonStart")').replace('ss."seasonEnd"::date','date(ss."seasonEnd")')
        result=self.connection.execute(sql);self.statements+=1
        if self.statements==self.fail_after:raise RuntimeError('synthetic post-phase failure')
        return result
    def rows(self):return [dict(r) for r in self.connection.execute('SELECT * FROM "League" ORDER BY id')]


class LeagueLifecycleServiceTests(unittest.TestCase):
    def setUp(self):
        self.db=LifecycleDatabase();self.addCleanup(self.db.connection.close)
    def service(self):
        from endpoints.league.league_lifecycle_service import LeagueLifecycleService
        return LeagueLifecycleService(self.db)
    def test_ordered_transitions_boundaries_and_completed_precedence(self):
        self.assertIsNone(self.service().synchronize_for_job())
        self.assertEqual({r['id']:r['status'] for r in self.db.rows()},EXPECTED)
        self.assertEqual(self.db.begins,1)
        self.assertEqual([r['updatedAt'] for r in self.db.rows() if r['id'] in (8,9,10,11)],['old']*4)
    def test_failure_after_every_phase_restores_entire_previous_state(self):
        service=self.service();before=self.db.rows()
        for phase in range(1,6):
            self.db.statements=0;self.db.fail_after=phase
            with self.assertRaises(RuntimeError):service.synchronize_for_job()
            self.assertEqual(self.db.rows(),before)
    def test_repeated_statuses_converge(self):
        service=self.service();service.synchronize_for_job();service.synchronize_for_job()
        self.assertEqual({r['id']:r['status'] for r in self.db.rows()},EXPECTED)
    def test_db_only_legacy_facade_none_success(self):
        model=LeagueModel.__new__(LeagueModel);model.db=self.db
        self.assertIsNone(model.sync_due_league_statuses())
        self.assertEqual({r['id']:r['status'] for r in self.db.rows()},EXPECTED)
