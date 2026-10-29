"""Trusted operational paths use real domain SQL on disposable fixtures only.

The finalizer function is loaded without module startup imports, configured DB,
bootstrap, app factory or scheduler. Its collaborators are synthetic/in-memory.
"""
import ast
import datetime as dt
import io
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
import unittest
from sqlalchemy import text
import test_trade_action_authorization as actions
import test_free_agency_authorization as fixture
import test_scoring_authorization as scoring


class ApplyDatabase(actions.TradeActionDatabase):
    def execute(self, statement, params=None):
        if isinstance(params,list):
            result=None
            for row in params:
                result=super().execute(statement,row)
            return result
        return super().execute(statement,params)


class TrustedOperationalTests(unittest.TestCase):
    def test_trusted_pending_apply_persists_both_sides_without_http_context(self):
        base=fixture.FreeAgencyAuthorizationTests()
        base.database_type=ApplyDatabase
        base.setUp()
        self.addCleanup(base.doCleanups)
        db=base.db
        db.connection.executescript('''
            ALTER TABLE League ADD COLUMN tradeDeadline TEXT;
            INSERT INTO "Transaction" (id,leagueId,weekId,type,memberFromId,memberToId,status,fromTeamIds,toTeamIds)
                VALUES (1,10,100,'TRADE',11,12,'PENDING_APPLY','[101]','[102]');
        ''')
        self.assertIsNone(base.model.apply_pending_transaction(1))
        self.assertEqual(db.connection.execute('SELECT status FROM "Transaction" WHERE id=1').fetchone()[0],'COMPLETED')
        slots=base.state()['LeagueTeamSlot']
        self.assertEqual([(r['memberId'],r['sportTeamId'],r['droppedWeek']) for r in slots[:2]],[(11,101,1),(12,102,1)])
        self.assertEqual([(r['memberId'],r['sportTeamId'],r['acquiredWeek'],r['acquiredVia']) for r in slots[3:]],
                         [(12,101,1,'TRADE'),(11,102,1,'TRADE')])

    def test_finalizer_uses_trusted_model_and_persists_synthetic_completion(self):
        base=scoring.ScoringAuthorizationTests()
        base.setUp()
        self.addCleanup(base.doCleanups)
        db=base.db
        db.connection.executescript('''
            ALTER TABLE League ADD COLUMN sport INTEGER DEFAULT 1;
            ALTER TABLE League ADD COLUMN seasonYear INTEGER DEFAULT 2026;
            ALTER TABLE League ADD COLUMN status TEXT DEFAULT 'Active';
            ALTER TABLE League ADD COLUMN updatedAt TEXT;
            CREATE TABLE SportSeason (id INTEGER,sportId INTEGER,seasonYear INTEGER,seasonEnd TEXT,seasonFinalized BOOLEAN);
            INSERT INTO SportSeason VALUES (1,1,2026,'2000-01-01',false);
        ''')
        path=Path(__file__).resolve().parents[1]/'cronJobs'/'cronComputeFinalScoreboard.py'
        tree=ast.parse(path.read_text(),filename=str(path))
        module=ast.Module(body=[node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name=='main'],type_ignores=[])
        namespace=dict(engine=db,datetime=dt.datetime,timezone=dt.timezone,text=text,
                       build_scoring=lambda engine:SimpleNamespace(scoringModel=base.model))
        exec(compile(module,str(path),'exec'),namespace)
        with redirect_stdout(io.StringIO()):
            namespace['main']()
        self.assertEqual([row[0] for row in db.connection.execute('SELECT status FROM League')],['Completed']*3)
        self.assertTrue(db.connection.execute('SELECT seasonFinalized FROM SportSeason').fetchone()[0])
