"""Schedule read/scoring policy with original per-helper transaction scopes.

Internal trusted capabilities preserve existing caller policy; transport/job wiring
is migrated separately. No provider URL/client or configured engine is needed.
"""
import re
from typing import Any, Dict, List, Optional
from rules.leagueRules import resolve_rules, adjust_margin, rule_summary
from rules.tournamentRules import score_margin
from .calendar_service import ScheduleCalendarService
from .read_repository import ScheduleReadRepository


class ScheduleReadService(ScheduleCalendarService):
    def __init__(self, db, repository=None, calendar_repository=None):
        super().__init__(db, calendar_repository)
        self._read_repository = repository if repository is not None else ScheduleReadRepository()

    @property
    def read_repository(self):
        repository = getattr(self, '_read_repository', None)
        if repository is None:
            repository = ScheduleReadRepository()
            self._read_repository = repository
        return repository

    def get_member_games_for_week(
        self,
        league_id: int,
        member_id: int,
        week_number: int,
        resolved_rules: Optional[dict] = None,
    ) -> list[dict]:
        """
        Return all games that count for this member in this week, with memberPointDiff
        already computed (everyone-vs-everyone, single-owner perspective).
        """
        if resolved_rules is None:
            league = self._get_league(league_id)
            resolved_rules = resolve_rules(league['sport'], league.get('settings'))
        

        with self.db.begin() as conn:
            rows = self.read_repository.member_games(conn, {
                    "leagueId": league_id,
                    "memberId": member_id,
                    "weekNumber": week_number,
                }).fetchall()

        games = []
        rules = resolved_rules
        for row in rows:
            game = dict(row._mapping)
            owns_home, owns_away = game['ownsHome'], game['ownsAway']
            owned_tier = game.get('homeTeamTier') if owns_home else game.get('awayTeamTier')
            opponent_tier = game.get('awayTeamTier') if owns_home else game.get('homeTeamTier')
            adjustment = adjust_margin(game['rawMemberPointDiff'], owned_tier, opponent_tier,
                                       rules, double_owned=owns_home and owns_away)
            if not owns_home and not owns_away:
                adjustment = adjust_margin(0, None, None, rules)
            game['memberPointDiff'] = score_margin(adjustment['adjustedMargin'], game.get('phaseRules') or {})
            game['tournamentAdjustment'] = {
                'positiveOnly': (game.get('phaseRules') or {}).get('positiveOnly', False),
                'multiplier': (game.get('phaseRules') or {}).get('marginMultiplier', 1),
                'scoringMargin': game['memberPointDiff'],
            }
            game['tierAdjustment'] = adjustment
            games.append(game)

        return games

    def get_head_to_head_games(
        self,
        league_id: int,
        member_a_id: int,
        member_b_id: int,
        week_number: int,
    ) -> list[dict]:
        """
        All games in this week where a team owned by member A played
        a team owned by member B (in either home/away direction).
        """
        

        with self.db.begin() as conn:
            rows = self.read_repository.head_to_head_games(conn, {
                    "leagueId": league_id,
                    "weekNumber": week_number,
                    "memberA": member_a_id,
                    "memberB": member_b_id,
                }).fetchall()

        return [dict(r._mapping) for r in rows]

    def get_week_for_league(
        self,
        league_id: int,
        week_number: int,
    ) -> dict | None:
        """
        Return the Week row for a given league + weekNumber, or None if missing.
        """
        

        with self.db.begin() as conn:
            row = self.read_repository.week(conn, {
                    "leagueId": league_id,
                    "weekNumber": week_number,
                }).fetchone()

        return dict(row._mapping) if row else None

    def get_owned_teams_for_member(
        self,
        league_id: int,
        member_id: int,
        week_number: int,
    ) -> list[dict]:
        """
        Return all teams this member owns in this league for the given week.
        Uses the same acquisition / drop logic as get_member_games_for_week.
        """
        

        with self.db.begin() as conn:
            rows = self.read_repository.owned_teams(conn, {
                    "leagueId": league_id,
                    "memberId": member_id,
                    "weekNumber": week_number,
                }).fetchall()

        return [dict(r._mapping) for r in rows]

    def member_games_for_job(self, league_id, member_id, week_number, resolved_rules=None):
        return self.get_member_games_for_week(league_id, member_id, week_number, resolved_rules)

    def head_to_head_for_job(self, league_id, member_a_id, member_b_id, week_number):
        return self.get_head_to_head_games(league_id, member_a_id, member_b_id, week_number)

    def week_for_job(self, league_id, week_number):
        return self.get_week_for_league(league_id, week_number)

    def owned_teams_for_job(self, league_id, member_id, week_number):
        return self.get_owned_teams_for_member(league_id, member_id, week_number)

    def _get_week_window(self, league_id: int, week_number: int) -> tuple[str, str]:
        """
        Returns (startDate, endDate) for the league week.
        """
        
        with self.db.begin() as conn:
            row = self.read_repository.week_window(conn, {"leagueId": league_id, "weekNumber": week_number}).fetchone()

        if not row:
            raise ValueError(f"Week not found for leagueId={league_id}, weekNumber={week_number}")

        m = row._mapping
        return (m["startDate"], m["endDate"])

    def get_conference_games_by_week(
        self,
        league_id: int,
        week_number: int,
        season_year: int,
        sport_conference_id: int,
    ) -> List[Dict[str, Any]]:
        week_start, week_end = self._get_week_window(league_id, week_number)

        

        with self.db.begin() as conn:
            rows = self.read_repository.conference_games(conn, {
                "leagueId": league_id,
                "weekNumber": week_number,
                "sportConferenceId": sport_conference_id,
                "seasonYear": season_year,
                "weekStart": week_start,
                "weekEnd": week_end,
            }).fetchall()

        return [dict(r._mapping) for r in rows]

    def get_team_games_by_season(
        self,
        sport_team_id: int,
        season_year: int,
        league_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        All games for a given SportTeam across the entire SportSeason for seasonYear.
        """
        
        

        with self.db.begin() as conn:
            week_number = 999
            if league_id is not None:
                league_context = self.read_repository.team_owner_context(conn, {"leagueId": league_id}).fetchone()
                if league_context:
                    week_number = int(league_context._mapping["weekNumber"] or 999)

            rows = self.read_repository.team_season_games(conn, {
                    "sportTeamId": sport_team_id,
                    "seasonYear": season_year,
                    "leagueId": league_id,
                    "weekNumber": week_number,
                }).fetchall()

        return [dict(r._mapping) for r in rows]

    @staticmethod
    def _normalize_team_search_text(value: str) -> str:
        abbreviations = {
            "st": "state",
            "univ": "university",
        }
        cleaned = re.sub(
            r"[^a-z0-9]+",
            " ",
            (value or "").lower().replace("&", " and "),
        )
        tokens = [abbreviations.get(token, token) for token in cleaned.split()]
        return " ".join(tokens)

    @classmethod
    def _team_search_rank(cls, row: Dict[str, Any], query: str) -> int:
        normalized_query = cls._normalize_team_search_text(query)
        if not normalized_query:
            return 0

        normalized_candidate = cls._normalize_team_search_text(row.get("teamName") or "")
        if normalized_candidate == normalized_query:
            return 100
        if normalized_candidate.startswith(normalized_query):
            return 90
        if normalized_query in normalized_candidate:
            return 75

        candidate_tokens = normalized_candidate.split()
        query_tokens = normalized_query.split()
        if query_tokens and all(
            any(candidate_token.startswith(query_token) for candidate_token in candidate_tokens)
            for query_token in query_tokens
        ):
            return 50
        return 0

    def search_teams_for_league(
        self,
        league_id: int,
        query: str,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        limit = max(1, min(int(limit or 20), 50))
        normalized_query = self._normalize_team_search_text(query)
        if len(normalized_query) < 2:
            return []

        

        

        with self.db.begin() as conn:
            league_row = self.read_repository.search_league_context(conn, {"leagueId": league_id}).fetchone()
            if not league_row:
                raise ValueError(f"League not found: {league_id}")

            league = dict(league_row._mapping)
            rows = self.read_repository.search_teams(conn, {
                    "leagueId": league_id,
                    "sport": league["sport"],
                    "seasonYear": league["seasonYear"],
                    "weekNumber": int(league["weekNumber"] or 999),
                }).fetchall()

        ranked = []
        for row in rows:
            item = dict(row._mapping)
            rank = self._team_search_rank(item, normalized_query)
            if rank > 0:
                ranked.append((rank, item["teamName"], item))

        ranked.sort(key=lambda value: (-value[0], value[1]))
        return [item for _, _, item in ranked[:limit]]

    def conference_games_for_job(self, league_id, week_number, season_year, sport_conference_id):
        return self.get_conference_games_by_week(league_id, week_number, season_year, sport_conference_id)

    def team_games_for_job(self, sport_team_id, season_year, league_id=None):
        return self.get_team_games_by_season(sport_team_id, season_year, league_id)

    def search_teams_for_job(self, league_id, query, limit=20):
        return self.search_teams_for_league(league_id, query, limit)

    @staticmethod
    def _apply_tier_adjustment(
        raw_point_diff: int,
        owned_team_tier: Optional[int],
        opponent_team_tier: Optional[int],
        sport_id: Optional[int] = None,
    ) -> int:
        return adjust_margin(raw_point_diff, owned_team_tier, opponent_team_tier,
                             resolve_rules(sport_id, {}))['adjustedMargin']

    def member_schedule_for_job(self, league_id, member_id, week_number):
        league = self._get_league(league_id)
        rules = resolve_rules(league['sport'], league.get('settings'))
        games = self.get_member_games_for_week(league_id, member_id, week_number, resolved_rules=rules)
        week = self.get_week_for_league(league_id, week_number)
        owned = self.get_owned_teams_for_member(league_id, member_id, week_number)
        return {
            'rules': {'version': rules['version'], 'summary': rule_summary(rules), 'tierAdjustment': rules},
            'ownedTeams': owned, 'week': week, 'games': games,
        }
