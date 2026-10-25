import datetime as dt
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from endpoints.schedule.scheduleModel import ScheduleModel


class BootstrapResumeTests(unittest.TestCase):
    def setUp(self):
        output = patch('builtins.print')
        output.start()
        self.addCleanup(output.stop)

    def model(self, callback, bootstrapped=False):
        db = MagicMock()
        db.url = 'postgresql://example.test/test'
        conn = db.begin.return_value.__enter__.return_value
        conn.execute.return_value.mappings.return_value.first.return_value = dict(
            id=1, sportId=1, scheduleBootstrapped=bootstrapped,
            seasonStart=dt.date(2027, 3, 1), seasonEnd=dt.date(2027, 3, 3))
        model = ScheduleModel(db, 'https://example.test')
        model._get_season_phases = lambda _: []
        model._get_sport_api_config = lambda _: ('basketball', [50], 'basketball')
        model.ingest_scoreboard_for_date_for_sport_season = callback
        return model

    @staticmethod
    def success(*_):
        return dict(eventsSeen=0, gamesUpserted=0)

    def test_interrupted_run_resumes_after_completed_dates_including_empty_days(self):
        calls = []
        def interrupted(_, day):
            calls.append(day)
            if day.day == 2:
                raise KeyboardInterrupt()
            return self.success()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'progress.json'
            with self.assertRaises(KeyboardInterrupt):
                self.model(interrupted).bootstrap_sport_season_schedule_by_scoreboard(1, checkpoint_path=path)
            self.assertEqual(json.loads(path.read_text())['completedDates'], ['2027-03-01'])
            calls.clear()
            def resume(_, day):
                calls.append(day)
                return self.success()
            result = self.model(resume).bootstrap_sport_season_schedule_by_scoreboard(1, checkpoint_path=path)
            self.assertEqual([d.day for d in calls], [2, 3])
            self.assertTrue(result['complete'])
            self.assertEqual(result['daysSkipped'], 1)

    def test_failed_date_retried_but_later_successes_skipped(self):
        def failed(_, day):
            if day.day == 2:
                raise ValueError('temporary failure')
            return self.success()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'progress.json'
            result = self.model(failed).bootstrap_sport_season_schedule_by_scoreboard(1, checkpoint_path=path)
            self.assertFalse(result['complete'])
            callback = MagicMock(side_effect=self.success)
            result = self.model(callback).bootstrap_sport_season_schedule_by_scoreboard(1, checkpoint_path=path)
            self.assertEqual([call.args[1].day for call in callback.call_args_list], [2])
            self.assertTrue(result['complete'])

    def test_max_days_advances_to_next_pending_batch(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'progress.json'
            for day in [1, 2, 3]:
                callback = MagicMock(side_effect=self.success)
                result = self.model(callback).bootstrap_sport_season_schedule_by_scoreboard(1, max_days=1, checkpoint_path=path)
                self.assertEqual(callback.call_args.args[1].day, day)
                self.assertEqual(result['complete'], day == 3)

    def test_force_restarts_but_interrupted_force_can_resume_without_force(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'progress.json'
            self.model(self.success).bootstrap_sport_season_schedule_by_scoreboard(1, checkpoint_path=path)
            def interrupt(_, day):
                if day.day == 2:
                    raise KeyboardInterrupt()
                return self.success()
            with self.assertRaises(KeyboardInterrupt):
                self.model(interrupt, True).bootstrap_sport_season_schedule_by_scoreboard(1, force=True, checkpoint_path=path)
            callback = MagicMock(side_effect=self.success)
            result = self.model(callback, True).bootstrap_sport_season_schedule_by_scoreboard(1, checkpoint_path=path)
            self.assertEqual([c.args[1].day for c in callback.call_args_list], [2, 3])
            self.assertTrue(result['complete'])

    def test_changed_rules_invalidate_partial_checkpoint(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'progress.json'
            self.model(self.success).bootstrap_sport_season_schedule_by_scoreboard(1, max_days=1, checkpoint_path=path)
            callback = MagicMock(side_effect=self.success)
            model = self.model(callback)
            model._get_season_phases = lambda _: [dict(id=1, rules={'marginMultiplier': 2})]
            model.bootstrap_sport_season_schedule_by_scoreboard(1, checkpoint_path=path)
            self.assertEqual(len(callback.call_args_list), 3)

    def test_corrupt_checkpoint_requires_explicit_force(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'progress.json'
            path.write_text('broken')
            with self.assertRaisesRegex(ValueError, 'checkpoint'):
                self.model(self.success).bootstrap_sport_season_schedule_by_scoreboard(1, checkpoint_path=path)
            self.assertTrue(self.model(self.success).bootstrap_sport_season_schedule_by_scoreboard(
                1, force=True, checkpoint_path=path)['complete'])

    def test_routine_metadata_updates_do_not_invalidate_resume(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'progress.json'
            model = self.model(self.success)
            model._get_season_phases = lambda _: [dict(id=1, rules={}, updatedAt='old', name='old')]
            model.bootstrap_sport_season_schedule_by_scoreboard(1, max_days=1, checkpoint_path=path)
            callback = MagicMock(side_effect=self.success)
            model = self.model(callback)
            model._get_season_phases = lambda _: [dict(id=1, rules={}, updatedAt='new', name='new')]
            model.bootstrap_sport_season_schedule_by_scoreboard(1, checkpoint_path=path)
            self.assertEqual([c.args[1].day for c in callback.call_args_list], [2, 3])

    def test_atomic_save_preserves_previous_checkpoint_when_replace_fails(self):
        from endpoints.schedule.helpers.bootstrapCheckpoint import BootstrapCheckpoint
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'progress.json'
            checkpoint = BootstrapCheckpoint(path, 'test')
            checkpoint.completed.add(dt.date(2027, 3, 1))
            checkpoint.save()
            checkpoint.completed.add(dt.date(2027, 3, 2))
            with patch('endpoints.schedule.helpers.bootstrapCheckpoint.os.replace', side_effect=OSError('disk error')):
                with self.assertRaises(OSError):
                    checkpoint.save()
            self.assertEqual(BootstrapCheckpoint(path, 'test').completed, {dt.date(2027, 3, 1)})
            self.assertEqual(list(Path(folder).iterdir()), [path])

    def test_changed_scoreboard_groups_invalidate_partial_checkpoint(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'progress.json'
            self.model(self.success).bootstrap_sport_season_schedule_by_scoreboard(1, max_days=1, checkpoint_path=path)
            callback = MagicMock(side_effect=self.success)
            model = self.model(callback)
            model._get_sport_api_config = lambda _: ('basketball', [50, 100], 'basketball')
            model.bootstrap_sport_season_schedule_by_scoreboard(1, checkpoint_path=path)
            self.assertEqual(len(callback.call_args_list), 3)


if __name__ == '__main__':
    unittest.main()
