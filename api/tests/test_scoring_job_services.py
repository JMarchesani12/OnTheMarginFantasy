"""Execute actual job builder functions without configured startup imports."""
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest
from endpoints.scoring.service import ScoringService


class ScoringJobServiceTests(unittest.TestCase):
    def test_both_builders_construct_service_without_http_adapter(self):
        for filename in ('cronComputeWeeklyScores.py','cronComputeFinalScoreboard.py'):
            with self.subTest(filename=filename):
                path=Path(__file__).resolve().parents[1]/'cronJobs'/filename
                tree=ast.parse(path.read_text())
                builder=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='build_scoring')
                schedule=object()
                namespace={'load_dotenv':lambda:None,'os':SimpleNamespace(getenv=lambda _: 'https://provider.example.test'),
                           'ScheduleModel':lambda engine,url:schedule,'ScoringService':ScoringService}
                exec(compile(ast.Module(body=[builder],type_ignores=[]),str(path),'exec'),namespace)
                engine=object()
                service=namespace['build_scoring'](engine)
                self.assertIsInstance(service,ScoringService)
                self.assertIs(service.db,engine)
                self.assertIs(service.schedule_model,schedule)
