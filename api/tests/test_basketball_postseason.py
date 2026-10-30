import datetime as dt
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rules.tournamentRules import score_margin, select_phase, final_period
from startSeasonJobs.startSeason import load_manifest

UTC = dt.timezone.utc


def phase(id, type='NationalTournament', **rules):
    return dict(id=id, type=type, startDate=dt.datetime(2027, 3, 1, tzinfo=UTC),
                endDate=dt.datetime(2027, 4, 7, tzinfo=UTC), rules=rules)


class TournamentRulesTests(unittest.TestCase):
    def test_margins_clamp_per_game_before_summing(self):
        for multiplier, expected in [(2, 42), (1, 21), (.5, 11)]:
            rules = dict(positiveOnly=True, marginMultiplier=multiplier)
            self.assertEqual(score_margin(21, rules), expected)
            self.assertEqual(score_margin(-8, rules), 0)
            self.assertEqual(score_margin(0, rules), 0)
        self.assertEqual(score_margin(-8, {}), -8)

    def test_overlapping_nationals_match_source_not_date_or_priority(self):
        phases = [phase(1, sourceLabels=['NCAA Tournament']), phase(2, sourceLabels=['NIT'])]
        self.assertEqual(select_phase(phases, dict(tournamentLabels=['NIT - First Round']),
                                     dt.datetime(2027, 3, 20, tzinfo=UTC)), 2)

    def test_explicit_game_override(self):
        self.assertEqual(select_phase([phase(8, eventIds=['123'])], {'externalGameId': '123'},
                                     dt.datetime(2027, 3, 20, tzinfo=UTC)), 8)

    def test_ambiguous_and_unclassified_postseason_fail(self):
        when = dt.datetime(2027, 3, 20, tzinfo=UTC)
        with self.assertRaises(ValueError):
            select_phase([phase(1, sourceLabels=['NIT']), phase(2, sourceLabels=['NIT'])],
                         {'tournamentLabels': ['NIT']}, when)
        with self.assertRaises(ValueError):
            select_phase([phase(1)], {'seasonType': 3}, when)

    def test_conference_label_needs_matching_membership(self):
        p = phase(2, 'ConferenceTournament', sourceLabels=['ACC Tournament'])
        p['sportConferenceId'] = 7
        when = dt.datetime(2027, 3, 10, tzinfo=UTC)
        self.assertEqual(select_phase([p], {'tournamentLabels': ['ACC Tournament']}, when, {7}), 2)
        with self.assertRaises(ValueError):
            select_phase([p], {'tournamentLabels': ['ACC Tournament']}, when, {8})

    def test_regular_season_not_caught_by_overlapping_national_window(self):
        p = phase(10, 'RegularSeason')
        self.assertEqual(select_phase([p, phase(1)], {'seasonType': 2},
                                     dt.datetime(2027, 3, 2, tzinfo=UTC)), 10)

    def test_final_period_encloses_all_four_tournaments(self):
        a = phase(1, scoringPeriod='BASKETBALL_FINAL')
        b = phase(2, scoringPeriod='BASKETBALL_FINAL')
        b['startDate'] = dt.datetime(2027, 3, 16, tzinfo=UTC)
        self.assertEqual(final_period([a, b]), (dt.date(2027, 3, 1), dt.date(2027, 4, 6)))

    def test_config_validates_duplicate_tournaments(self):
        raw = json.loads((Path(__file__).parents[1] / 'startSeasonJobs/configs/ncaa-mens-basketball-2026.json').read_text())
        raw['tournaments'] = [dict(code='NIT', name='NIT', scope='National', startDate='2027-03-16', endDate='2027-04-01', rules={'sourceLabels': ['NIT']})] * 2
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / 'config.json'
            p.write_text(json.dumps(raw))
            with self.assertRaisesRegex(ValueError, 'Duplicate tournament'):
                load_manifest(p)

class BasketballIntegrationTests(unittest.TestCase):
    @staticmethod
    def _national_manifest():
        from startSeasonJobs.startSeason import SeasonManifest
        tournaments = tuple(dict(
            code=code, name=name, scope='National', startDate='2027-03-16',
            endDate='2027-04-05', rules=dict(
                positiveOnly=True, marginMultiplier=multiplier,
                scoringPeriod='BASKETBALL_FINAL', primaryPostseason=code == 'NCAA_TOURNEY',
                sourceLabels=[name]))
            for code, name, multiplier in [
                ('NCAA_TOURNEY', 'NCAA Tournament', 2), ('NIT', 'NIT', 1),
                ('CBI', 'CBI', .5), ('CROWN', 'Crown', 1)])
        return SeasonManifest(
            sport='ncaa-mens-basketball', season_year=2026,
            season_start=dt.date(2026, 11, 2), season_end=dt.date(2027, 4, 6),
            subdivisions=(), tournaments=tournaments, timezone='America/New_York')

    def test_schedule_scoring_applies_phase_after_tiers_and_keeps_double_owned_zero(self):
        from endpoints.schedule.scheduleModel import ScheduleModel
        from rules.leagueRules import resolve_rules
        db = MagicMock()
        conn = db.begin.return_value.__enter__.return_value
        rows = []
        for margin, both, mult in [(21, False, .5), (-8, False, 2), (21, True, 2), (21, False, 2)]:
            row = Mock()
            row._mapping = dict(ownsHome=True, ownsAway=both, homeTeamTier=1,
                                awayTeamTier=1, rawMemberPointDiff=margin,
                                phaseRules=dict(positiveOnly=True, marginMultiplier=mult))
            rows.append(row)
        conn.execute.return_value.fetchall.return_value = rows
        games = ScheduleModel(db, 'https://example.test').get_member_games_for_week(
            1, 2, 3, resolved_rules=resolve_rules(1, {}))
        self.assertEqual([g['memberPointDiff'] for g in games], [11, 0, 0, 42])

    def test_final_period_replaces_calendar_weeks_without_gap(self):
        from endpoints.schedule.scheduleModel import ScheduleModel
        model = ScheduleModel(Mock(), 'https://example.test')
        model._get_existing_weeks = lambda _: []
        model._get_sport_season_for_league = lambda _: dict(sportSeasonId=1,
            regularSeasonStart=dt.date(2026, 11, 2), regularSeasonEnd=dt.date(2027, 3, 7),
            postseasonStart=dt.date(2027, 3, 16), postseasonEnd=dt.date(2027, 4, 6), allSubdivisions=False)
        model._get_league_timezone = lambda _: UTC
        model._get_week_start_weekday = lambda _: 0
        p = phase(1, scoringPeriod='BASKETBALL_FINAL')
        p['startDate'] = dt.datetime(2027, 3, 16, tzinfo=UTC)
        model._get_season_phases = lambda _: [p]
        model._insert_week0 = lambda *args: dict(weekNumber=0)
        recorded = []
        def insert(league, ranges, starting_week_number=1, tzinfo=None):
            recorded.extend(ranges)
            return [dict(weekNumber=n) for n in range(starting_week_number, starting_week_number+len(ranges))]
        model._insert_weeks = insert
        model.ensure_weeks_for_league(1)
        self.assertEqual(recorded[-1], (dt.date(2027, 3, 16), dt.date(2027, 4, 6)))
        self.assertEqual(recorded[-2][1], dt.date(2027, 3, 15))
        for a, b in zip(recorded, recorded[1:]):
            self.assertEqual(a[1]+dt.timedelta(days=1), b[0])

    def test_future_final_period_cannot_award_ranking_points(self):
        from endpoints.scoring.scoringModel import ScoringModel
        model = ScoringModel(Mock(), Mock())
        model._get_league_members = lambda _: []
        model._get_week_by_number = lambda *_: dict(id=1, isFinalPeriod=True,
                                                  endDate=dt.datetime(2099, 4, 6, tzinfo=UTC))
        with self.assertRaisesRegex(ValueError, 'final scoring period'):
            model.compute_weekly_scores(1, 20)

    def test_source_metadata_survives_event_parsing(self):
        from endpoints.schedule.helpers.espn.espnClient import ESPNClient
        event = dict(id='1', date='2027-03-20T12:00Z', season={'type': 3}, competitions=[
            dict(notes=[{'headline': 'NIT - First Round'}], tournament={'id': 9, 'name': 'NIT'},
                 competitors=[dict(homeAway=side, team={'id': id}, score='10')
                              for side, id in [('home', 1), ('away', 2)]])])
        result = ESPNClient('https://example.test', 'basketball').extract_game_from_event(event)
        self.assertEqual(result['seasonType'], 3)
        self.assertIn('NIT - First Round', result['tournamentLabels'])
        self.assertEqual(result['tournamentIds'], ['9'])

    def test_failed_or_partial_bootstrap_is_not_marked_complete(self):
        from endpoints.schedule.scheduleModel import ScheduleModel
        for fail, limit, expected in [(True, None, False), (False, 1, False), (False, None, True)]:
            db = MagicMock()
            conn = db.begin.return_value.__enter__.return_value
            conn.execute.return_value.mappings.return_value.first.return_value = dict(
                id=1, sportId=1, scheduleBootstrapped=False,
                seasonStart=dt.date(2027, 3, 1), seasonEnd=dt.date(2027, 3, 2))
            model = ScheduleModel(db, 'https://example.test')
            model._get_sport_api_config = lambda _: ('basketball', [50], 'basketball')
            def ingest(*_):
                if fail:
                    raise ValueError('Unmatched tournament')
                return dict(eventsSeen=1, gamesUpserted=1)
            model.ingest_scoreboard_for_date_for_sport_season = ingest
            with tempfile.TemporaryDirectory() as folder:
                result = model.bootstrap_sport_season_schedule_by_scoreboard(
                    1, max_days=limit, checkpoint_path=Path(folder) / 'checkpoint.json')
            self.assertEqual(result['complete'], expected)
            updates = [call for call in conn.execute.call_args_list if 'UPDATE' in str(call.args[0])]
            self.assertEqual(updates[-1].args[1]['complete'], expected)

    def test_final_period_uses_tournament_calendar_timezone(self):
        p = phase(1, scoringPeriod='BASKETBALL_FINAL', timezone='America/New_York')
        p['startDate'] = dt.datetime(2027, 3, 16, 4, tzinfo=UTC)
        p['endDate'] = dt.datetime(2027, 4, 6, 4, tzinfo=UTC)
        self.assertEqual(final_period([p]), (dt.date(2027, 3, 16), dt.date(2027, 4, 5)))

    def test_basketball_rules_describe_postseason(self):
        from rules.leagueRules import describe_rules
        sections = describe_rules(1, {}, [])['sections']
        text = ' '.join(p for section in sections for p in section['paragraphs'])
        self.assertIn('CBI', text)
        self.assertIn('positive', text)
        self.assertNotIn('CBI', str(describe_rules(2, {}, [])['sections']))

    def test_regular_season_type_cannot_hide_unmatched_conference_tournament(self):
        p = phase(1, 'ConferenceTournament', sourceLabels=['ACC Tournament'])
        p['sportConferenceId'] = 7
        for labels in ([], ['ACC Championship - Final']):
            with self.assertRaisesRegex(ValueError, 'metadata required'):
                select_phase([phase(2, 'RegularSeason'), p],
                             dict(seasonType=2, tournamentLabels=labels),
                             dt.datetime(2027, 3, 10, tzinfo=UTC), {7})

    def test_rebuild_uses_same_week_plan(self):
        from scripts.rebuild_weeks_and_rescore import _compute_week_boundaries
        model = Mock()
        model.season_for_job.return_value = {'seasonYear': 2026}
        model.boundaries_for_job.return_value = [(20, '2027-03-16', '2027-04-06')]
        self.assertEqual(_compute_week_boundaries(model, 1, 2026), model.boundaries_for_job.return_value)
        model.boundaries_for_job.assert_called_once_with(1)

    def test_phase_setup_repairs_dates_rules_and_definition_names(self):
        from startSeasonJobs.startSeason import load_manifest, configure_manifest_phases, SPORT_CONFIGS
        manifest = self._national_manifest()
        conn = MagicMock()
        calls = []
        def execute(sql, params=None):
            calls.append((str(sql), params))
            result = MagicMock()
            result.fetchall.return_value = []  # no conferences in this focused fixture
            result.mappings.return_value.first.return_value = dict(id=5, scope='National', sportConferenceId=None)
            result.first.return_value = (8,)  # existing phase
            return result
        conn.execute.side_effect = execute
        configure_manifest_phases(conn, 1, SPORT_CONFIGS['ncaa-mens-basketball'], manifest)
        name_updates = [params for sql, params in calls if 'UPDATE "TournamentDefinition"' in sql]
        self.assertEqual(len(name_updates), 4)
        self.assertFalse(any('INSERT INTO "SeasonPhase"' in sql for sql, _ in calls))
        updates = [params for sql, params in calls if 'UPDATE "SeasonPhase" SET "startDate"=:start' in sql]
        self.assertEqual(len(updates), 5)  # regular + four national phases
        ncaa = next(p for p in updates if p.get('name') == 'NCAA Tournament')
        self.assertEqual(json.loads(ncaa['rules'])['marginMultiplier'], 2)
        self.assertEqual(ncaa['end'].date(), dt.date(2027, 4, 6))

    def test_final_period_covers_late_us_games_in_utc_league(self):
        p = phase(1, scoringPeriod='BASKETBALL_FINAL', timezone='America/New_York')
        p['startDate'] = dt.datetime(2027, 3, 16, 4, tzinfo=UTC)
        p['endDate'] = dt.datetime(2027, 4, 6, 4, tzinfo=UTC)
        self.assertEqual(final_period([p], UTC), (dt.date(2027, 3, 16), dt.date(2027, 4, 6)))

    def test_old_split_final_weeks_cannot_be_scored(self):
        from endpoints.scoring.scoringModel import ScoringModel
        for start, end in [(dt.datetime(2020, 3, 16, tzinfo=UTC), dt.datetime(2020, 3, 23, tzinfo=UTC)),
                           (dt.datetime(2020, 4, 1, tzinfo=UTC), dt.datetime(2020, 4, 7, tzinfo=UTC))]:
            model = ScoringModel(Mock(), Mock())
            model._get_week_by_number = lambda *_: dict(id=1, isFinalPeriod=True, startDate=start,
                endDate=end, finalPeriodStart=dt.datetime(2020, 3, 16, tzinfo=UTC),
                finalPeriodEnd=dt.datetime(2020, 4, 7, tzinfo=UTC))
            with self.assertRaisesRegex(ValueError, 'split across weeks'):
                model.compute_weekly_scores(1, 20)

    def test_conference_config_coverage_is_required_before_phase_writes(self):
        from startSeasonJobs.startSeason import configure_manifest_phases, SPORT_CONFIGS
        manifest = self._national_manifest()
        conn = MagicMock()
        conn.execute.return_value.fetchall.return_value = [(7,)]
        with self.assertRaisesRegex(ValueError, 'SportConference IDs: 7'):
            configure_manifest_phases(conn, 1, SPORT_CONFIGS['ncaa-mens-basketball'], manifest)
        self.assertEqual(conn.execute.call_count, 1)

    def test_recognized_tournament_outside_dates_never_becomes_regular(self):
        p = phase(1, 'ConferenceTournament', sourceLabels=['ACC Tournament'], eventIds=['123'])
        p['sportConferenceId'] = 7
        p['endDate'] = dt.datetime(2027, 3, 13, tzinfo=UTC)
        for game in [dict(seasonType=2, tournamentLabels=['ACC Tournament - Final']),
                     dict(seasonType=2, externalGameId='123')]:
            with self.assertRaises(ValueError):
                select_phase([phase(2, 'RegularSeason'), p], game,
                             dt.datetime(2027, 3, 13, 12, tzinfo=UTC), {7})


if __name__ == '__main__':
    unittest.main()
