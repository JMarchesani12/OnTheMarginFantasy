"""Atomic season validation/completion; standings and bonuses remain computed reads."""
from datetime import datetime, timezone
import math
from utils.ownership import lock_ownership
from .finalization_repository import SeasonFinalizationRepository


class SeasonNotReady(ValueError):
    def __init__(self, reason, league_id=None):
        self.reason = reason
        self.league_id = league_id
        super().__init__(reason)


class InvalidStandings(ValueError):
    pass


class SeasonFinalizationService:
    def __init__(self, engine, scoring, repository=None):
        self.engine = engine
        self.scoring = scoring
        self.repository = repository if repository is not None else SeasonFinalizationRepository()

    def run(self, now=None):
        now = now if now is not None else datetime.now(timezone.utc)
        report = {'finalized': [], 'skipped': [], 'blocked': [], 'failures': []}
        try:
            with self.engine.begin() as conn:
                seasons = self.repository.candidates(conn, now.date())
        except Exception as exc:
            report['failures'].append({'sportSeasonId': None, 'stage': 'discovery', 'category': type(exc).__name__})
            return report
        for season_id in seasons:
            try:
                with self.engine.begin() as conn:
                    outcome = self.finalize_in_transaction(conn, season_id, now)
            except SeasonNotReady as exc:
                detail = {'sportSeasonId': season_id, 'reason': exc.reason}
                if exc.league_id is not None:
                    detail['leagueId'] = exc.league_id
                report['blocked'].append(detail)
            except Exception as exc:
                # Never expose SQL, standings or exception messages in job logs.
                report['failures'].append({'sportSeasonId': season_id, 'category': type(exc).__name__})
            else:
                report[outcome].append(season_id)
        return report

    def finalize_in_transaction(self, conn, season_id, now):
        """Trusted caller owns commit/rollback; season -> sorted ownership -> rows."""
        season = self.repository.lock_season(conn, season_id, now.date())
        if season is None or season['seasonFinalized'] or not season['ended']:
            return 'skipped'
        league_ids = self.repository.scope_ids(conn, season['sportId'], season['seasonYear'])
        if not league_ids:
            raise SeasonNotReady('empty_scope')
        for league_id in league_ids:
            lock_ownership(conn, league_id)
        for league_id in league_ids:
            league = self.repository.lock_league(conn, league_id)
            if league is None or (league['sport'], league['seasonYear']) != (season['sportId'], season['seasonYear']):
                raise SeasonNotReady('scope_changed', league_id)
            weeks = self.repository.weeks(conn, league_id, now)
            if not weeks or not all(week['ready'] for week in weeks):
                raise SeasonNotReady('weeks_not_ready', league_id)
            numbers = [week['weekNumber'] for week in weeks]
            if numbers[0] not in (0, 1) or numbers != list(range(numbers[0], numbers[-1] + 1)):
                raise SeasonNotReady('weeks_not_ready', league_id)
            if self.repository.pending(conn, league_id):
                raise SeasonNotReady('pending_application', league_id)
            members = self.repository.member_ids(conn, league_id)
            if not members:
                raise SeasonNotReady('empty_membership', league_id)
            standings = self.scoring.get_season_standings_for_job(league_id, conn=conn)
            self._validate_standings(standings, league_id, members)
        if self.repository.scope_ids(conn, season['sportId'], season['seasonYear']) != league_ids:
            raise SeasonNotReady('scope_changed')
        for league_id in league_ids:
            self.repository.mark_league(conn, league_id)
        self.repository.mark_season(conn, season_id)
        return 'finalized'

    @staticmethod
    def _validate_standings(result, league_id, member_ids):
        if not isinstance(result, dict) or type(result.get('leagueId')) is not int or result['leagueId'] != league_id or 'error' in result:
            raise InvalidStandings('Invalid standings result')
        members = result.get('members')
        if not isinstance(members, list) or len(members) != len(member_ids):
            raise InvalidStandings('Invalid standings members')
        ids = []
        for member in members:
            if not isinstance(member, dict) or type(member.get('memberId')) is not int:
                raise InvalidStandings('Invalid standings member')
            ids.append(member['memberId'])
            for field in ('weeklyPoints', 'bonusPoints', 'totalPoints'):
                value = member.get(field)
                if type(value) not in (int, float) or not math.isfinite(value):
                    raise InvalidStandings('Invalid standings points')
        if sorted(ids) != sorted(member_ids):
            raise InvalidStandings('Invalid standings membership')
