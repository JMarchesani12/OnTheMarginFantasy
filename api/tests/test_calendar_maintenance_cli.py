"""Actual maintenance CLI composition/defaults without configured engines or Flask."""
import ast
import io
import json
from contextlib import redirect_stdout,redirect_stderr
from pathlib import Path
import unittest
from unittest.mock import patch
import test_calendar_maintenance as fixture
from scripts import rebuild_weeks_and_rescore as cli


class CalendarMaintenanceCliTests(unittest.TestCase):
    def setUp(self):
        self.base=fixture.CalendarMaintenanceTests();self.base.setUp();self.addCleanup(self.base.doCleanups)

    def test_default_is_preview_and_explicit_apply_creates_unused_calendar(self):
        before=self.base.state()
        with patch.object(cli,'build_maintenance',return_value=self.base.service),redirect_stdout(io.StringIO()) as output:
            report=cli.main(['--season-year','2026','--league-id','10'],engine=self.base.db)
        self.assertEqual(report['mode'],'preview');self.assertEqual(self.base.state(),before)
        self.assertEqual(json.loads(output.getvalue()),report);self.assertEqual(cli.exit_code(report),0)
        with patch.object(cli,'build_maintenance',return_value=self.base.service),redirect_stdout(io.StringIO()):
            report=cli.main(['--season-year','2026','--league-id','10','--apply'],engine=self.base.db)
        self.assertEqual(report['leagues'][0]['outcome'],'applied');self.assertEqual(len(self.base.state()['Week']),3)

    def test_historical_preview_succeeds_but_apply_and_bad_scope_exit_nonzero(self):
        self.base.create_weeks();self.base.db.connection.executescript('INSERT INTO LeagueTeamSlot VALUES (1,10,11,101,1,NULL);')
        before=self.base.state()
        with patch.object(cli,'build_maintenance',return_value=self.base.service),redirect_stdout(io.StringIO()):
            preview=cli.main(['--season-year','2026'],engine=self.base.db)
            apply=cli.main(['--season-year','2026','--apply'],engine=self.base.db)
            wrong=cli.main(['--season-year','2026','--league-id','999'],engine=self.base.db)
        self.assertEqual((cli.exit_code(preview),cli.exit_code(apply),cli.exit_code(wrong)),(0,1,1))
        self.assertEqual(self.base.state(),before)

    def test_real_cli_entrypoint_sanitizes_startup_error_and_exits_one(self):
        tree=ast.parse(Path(cli.__file__).read_text())
        entry=next(node for node in tree.body if isinstance(node,ast.If))
        code=compile(ast.Module(body=entry.body,type_ignores=[]),cli.__file__,'exec')
        stdout,stderr=io.StringIO(),io.StringIO()
        with patch.object(cli,'build_maintenance',side_effect=RuntimeError('private SQL token')),redirect_stdout(stdout),redirect_stderr(stderr):
            with self.assertRaises(SystemExit) as result:
                exec(code,{'main':lambda:cli.main(['--season-year','2026'],engine=self.base.db),'exit_code':cli.exit_code})
        self.assertEqual(result.exception.code,1);self.assertEqual(stderr.getvalue(),'')
        self.assertNotIn('private',stdout.getvalue())
        self.assertEqual(json.loads(stdout.getvalue())['failures'],[{'leagueId':None,'stage':'startup','category':'RuntimeError'}])
