"""Trusted operational paths use real domain SQL on disposable fixtures only.

The finalizer uses the actual service/cron composition outside Flask with synthetic
state, without configured DB, app factory, provider or scheduler startup.
"""
import io
from contextlib import redirect_stdout
import unittest
from test_operational_jobs import fake_gate
import test_trade_action_authorization as actions
import test_free_agency_authorization as fixture


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

    def test_finalizer_uses_trusted_service_outside_http_and_returns_scoped_report(self):
        from unittest.mock import patch
        from test_season_finalization import SeasonFinalizationTests
        from cronJobs import cronComputeFinalScoreboard as final
        base=SeasonFinalizationTests();base.setUp();self.addCleanup(base.doCleanups)
        with patch.object(final,'job_gate',fake_gate), patch.object(final,'build_scoring',return_value=base.scoring), redirect_stdout(io.StringIO()):
            report=final.main(engine=base.engine)
        self.assertEqual(report,{'finalized':[1,2],'skipped':[],'blocked':[],'failures':[]})
        self.assertEqual([row[1] for row in base.state()[0]],['Completed']*3)

    def test_finalizer_cli_safely_reports_discovery_and_startup_failures(self):
        import ast
        import json
        from pathlib import Path
        from contextlib import redirect_stderr
        from unittest.mock import patch
        from test_season_finalization import SeasonFinalizationTests
        from endpoints.scoring.finalization_repository import SeasonFinalizationRepository
        from cronJobs import cronComputeFinalScoreboard as final
        base=SeasonFinalizationTests();base.setUp();self.addCleanup(base.doCleanups)
        tree=ast.parse(Path(final.__file__).read_text())
        entry=next(node for node in tree.body if isinstance(node,ast.If))
        code=compile(ast.Module(body=entry.body,type_ignores=[]),final.__file__,'exec')
        for stage in ('discovery','job'):
            with self.subTest(stage=stage):
                stdout,stderr=io.StringIO(),io.StringIO()
                target=(patch.object(SeasonFinalizationRepository,'candidates',side_effect=RuntimeError('private SQL row token')) if stage=='discovery' else patch.object(final,'build_scoring',side_effect=RuntimeError('private SQL row token')))
                with target,patch.object(final,'job_gate',fake_gate),redirect_stdout(stdout),redirect_stderr(stderr):
                    with self.assertRaises(SystemExit) as exit_result:
                        exec(code,{'main':lambda:final.main(engine=base.engine)})
                self.assertEqual(exit_result.exception.code,1)
                self.assertNotIn('private',stderr.getvalue())
                self.assertTrue(all('runId' in json.loads(line) for line in stderr.getvalue().splitlines()))
                self.assertNotIn('private',stdout.getvalue())
                self.assertEqual(json.loads(stdout.getvalue())['failures'],[{'sportSeasonId':None,'stage':stage,'category':'RuntimeError'}])
