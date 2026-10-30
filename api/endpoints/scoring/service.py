"""Scoring use cases and rules, independent of HTTP and configured startup."""
import json
import datetime as dt
from typing import Any, Dict, List, Optional
from utils.authorization import league_read_access
from .contracts import ScoringRejected
from .rules import playoff_depth_bonus, conference_champion_bonus, conference_bottom_bonus
from actors import UserActor
from .contracts import ScoringReadDenied
from .repository import ScoringRepository


class ScoringReadService:
    def __init__(self, engine, repository=None):
        self.engine = engine
        self.repository = repository if repository is not None else ScoringRepository()

    @staticmethod
    def _normalize_weeks(week_numbers):
        if not week_numbers:
            return []
        return sorted({int(w) for w in week_numbers if int(w) >= 0})

    def get_weekly_points(self, actor, league_id, week_numbers):
        if not isinstance(actor, UserActor):
            raise TypeError('A verified UserActor is required')
        return self.get_weekly_points_for_legacy_reader(actor.user_id, league_id, week_numbers)

    def get_weekly_points_for_legacy_reader(self, user_id, league_id, week_numbers):
        if isinstance(user_id, bool) or not isinstance(user_id, int):
            raise TypeError('A verified integer reader is required')
        rows = []
        with self.engine.connect() as conn:
            allowed = self.repository.league_read_allowed(conn, league_id, user_id)
            if allowed:
                weeks = self._normalize_weeks(week_numbers)
                if weeks:
                    rows = self.repository.weekly_points(conn, league_id, weeks)
                allowed = self.repository.league_read_allowed(conn, league_id, user_id)
        # Match the existing guard's denial after its read connection closes.
        if not allowed:
            raise ScoringReadDenied('League not found')
        return rows

    def get_weekly_points_for_job(self, league_id, week_numbers):
        weeks = self._normalize_weeks(week_numbers)
        if not weeks:
            return []
        with self.engine.connect() as conn:
            return self.repository.weekly_points(conn, league_id, weeks)



class ScoringService:
    """Scoring orchestration and rules. Schedule reads precede atomic score replacement."""
    PRIMARY_POSTSEASON_PHASE_TYPES = ['NationalTournament', 'PrimaryPlayoffs']
    SEGMENT_POSTSEASON_PHASE_TYPES = ['ConferenceTournament', 'SegmentPlayoffs']
    BONUS_HANDLERS = {'playoffDepth': '_bonus_playoff_depth', 'conferenceChampion': '_bonus_conference_champion', 'conferenceBottom': '_bonus_conference_bottom'}

    def __init__(self, db, schedule_model, repository=None):
        self.db = db
        self.schedule_model = schedule_model
        self.repository = repository if repository is not None else ScoringRepository()
        self._scoring_read_service = ScoringReadService(db, self.repository)

    def _get_league_settings(self, league_id: int) -> Dict[str, Any]:
        """
        Return League.settings JSON (may include bonuses, transactions, schedule).
        """
        with self.db.begin() as conn:
            row = self.repository.league_settings(conn, league_id)
        if not row:
            raise ScoringRejected(f'League {league_id} not found')
        settings = row[0]
        if isinstance(settings, str):
            return json.loads(settings)
        return settings or {}

    def _get_week_by_number(self, league_id: int, week_number: int) -> Dict[str, Any]:
        with self.db.begin() as conn:
            row = self.repository.week_metadata(conn, league_id, week_number)
        if not row:
            raise ScoringRejected(f'Week {week_number} not found for league {league_id}')
        return dict(row._mapping)

    def _get_league_members(self, league_id: int) -> List[Dict[str, Any]]:
        with self.db.begin() as conn:
            rows = self.repository.league_members(conn, league_id)
        return [dict(r._mapping) for r in rows]

    def _delete_existing_weekly_scores(self, conn, league_id: int, week_id: int) -> None:
        self.repository.delete_weekly_scores(conn, league_id, week_id)

    def _get_sport_season_for_league(self, league_id: int) -> Dict[str, Any]:
        """
        Look up the SportSeason row that matches League.sport + League.seasonYear.
        """
        with self.db.begin() as conn:
            row = self.repository.sport_season(conn, league_id)
        if not row:
            raise ScoringRejected(f'SportSeason not found for league {league_id}')
        return dict(row._mapping)

    def _get_member_owned_team_ids(self, league_id: int, member_id: int) -> List[int]:
        """
        All SportTeam ids ever owned in this league by this member (any week).
        Used for season-level tiebreakers where we don't care about weekly windows.
        """
        with self.db.begin() as conn:
            rows = self.repository.owned_teams(conn, league_id, member_id)
        return [int(r[0]) for r in rows]

    def compute_member_point_diff_for_week(self, league_id: int, member_id: int, week_number: int) -> int:
        """
        Sum memberPointDiff across all games for this member in this week.

        Uses ScheduleModel.get_member_games_for_week, which must return rows with:
          - memberPointDiff: int (0 for double-owned, +diff for owned side)
        """
        games = self.schedule_model.get_member_games_for_week(league_id=league_id, member_id=member_id, week_number=week_number)
        total = 0
        for g in games:
            total += int(g['memberPointDiff'])
        return total

    def compute_weekly_scores_for_job(self, league_id: int, week_number: int) -> Dict[str, Any]:
        """
        Compute weekly scores for all members in a league for a given week:

        - Uses global GameResult via ScheduleModel
        - Everyone-vs-everyone
        - Waterfall points: N, N-1, ..., 1
        - Applies weekly tiebreakers to break ties in pointDifferential:
            1) weekly head-to-head PD
            2) biggest single-game margin
            3) split (no change)
        - Writes into WeeklyTeamScore.
        """
        if week_number < 0:
            raise ScoringRejected('Week number must be >= 0')
        week = self._get_week_by_number(league_id, week_number)
        week_id = int(week['id'])
        split_final = week.get('finalPeriodEnd') and week['endDate'] < week['finalPeriodEnd'] - dt.timedelta(microseconds=1) or (week.get('finalPeriodStart') and week['startDate'] > week['finalPeriodStart'])
        if week.get('isFinalPeriod') and split_final:
            raise ScoringRejected('Rebuild weeks before scoring: final scoring period is split across weeks')
        if week.get('isFinalPeriod') and week['endDate'] >= dt.datetime.now(dt.timezone.utc):
            raise ScoringRejected('Cannot award points until the final scoring period ends')
        members = self._get_league_members(league_id)
        if not members:
            raise ScoringRejected(f'No members found for league {league_id}')
        member_scores: List[Dict[str, Any]] = []
        for m in members:
            member_id = int(m['id'])
            pdiff = self.compute_member_point_diff_for_week(league_id=league_id, member_id=member_id, week_number=week_number)
            member_scores.append({'memberId': member_id, 'teamName': m['teamName'], 'pointDifferential': pdiff})
        member_scores.sort(key=lambda x: (-x['pointDifferential'], int(x['memberId'])))
        member_scores = self.apply_weekly_tiebreakers(league_id=league_id, week_number=week_number, members=member_scores)
        num_members = len(member_scores)
        for idx, ms in enumerate(member_scores):
            rank = idx + 1
            points_awarded = num_members - idx
            ms['rank'] = rank
            ms['pointsAwarded'] = points_awarded
        with self.db.begin() as conn:
            self._delete_existing_weekly_scores(conn, league_id, week_id)
            for ms in member_scores:
                self.repository.insert_weekly_score(conn, league_id, week_id, ms['memberId'], ms['pointDifferential'], ms['rank'], ms['pointsAwarded'])
        return {'leagueId': league_id, 'weekNumber': week_number, 'weekId': week_id, 'scores': member_scores}

    def apply_weekly_tiebreakers(self, league_id: int, week_number: int, members: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        For each tie group (same pointDifferential), apply:

          1) head-to-head point differential
          2) biggest single-game margin
          3) split (leave as-is)
        """
        i = 0
        while i < len(members):
            j = i + 1
            while j < len(members) and members[j]['pointDifferential'] == members[i]['pointDifferential']:
                j += 1
            if j - i > 1:
                tied_group = members[i:j]
                resolved = self._resolve_weekly_ties(league_id, week_number, tied_group)
                members[i:j] = resolved
            i = j
        return members

    def _resolve_weekly_ties(self, league_id: int, week_number: int, group: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        result = self._tb_weekly_head_to_head(league_id, week_number, group)
        if result is not None:
            return result
        result = self._tb_weekly_biggest_single_margin(league_id, week_number, group)
        if result is not None:
            return result
        return group

    def _tb_weekly_head_to_head(self, league_id: int, week_number: int, group: List[Dict[str, Any]]) -> List[Dict[str, Any]] | None:
        """
        For all tied members in group:
          - For each pair (A,B), get all head-to-head games in this week
          - Sum point differential for each member
          - Sort group by total head-to-head PD (desc)

        Requires ScheduleModel.get_head_to_head_games(
            league_id, member_a_id, member_b_id, week_number
        ) returning rows with:
          - homeScore, awayScore
          - homeOwnedByA, awayOwnedByA
          - homeOwnedByB, awayOwnedByB
        """
        totals: Dict[int, int] = {int(m['memberId']): 0 for m in group}
        member_ids = list(totals.keys())
        for i, a_id in enumerate(member_ids):
            for b_id in member_ids[i + 1:]:
                games = self.schedule_model.get_head_to_head_games(league_id=league_id, member_a_id=a_id, member_b_id=b_id, week_number=week_number)
                a_pd = 0
                b_pd = 0
                for g in games:
                    home_score = int(g['homeScore'])
                    away_score = int(g['awayScore'])
                    if g.get('homeOwnedByA'):
                        a_pd += home_score - away_score
                    if g.get('awayOwnedByA'):
                        a_pd += away_score - home_score
                    if g.get('homeOwnedByB'):
                        b_pd += home_score - away_score
                    if g.get('awayOwnedByB'):
                        b_pd += away_score - home_score
                totals[a_id] += a_pd
                totals[b_id] += b_pd
        if len(set(totals.values())) <= 1:
            return None
        sorted_group = sorted(group, key=lambda m: (-totals[int(m['memberId'])], int(m['memberId'])))
        return sorted_group

    def _tb_weekly_biggest_single_margin(self, league_id: int, week_number: int, group: List[Dict[str, Any]]) -> List[Dict[str, Any]] | None:
        """
        For each tied member:
          - Look at all their games that week
          - Take max(abs(memberPointDiff)) across games
          - Higher wins
        """
        margins: Dict[int, int] = {}
        for m in group:
            member_id = int(m['memberId'])
            games = self.schedule_model.get_member_games_for_week(league_id=league_id, member_id=member_id, week_number=week_number)
            biggest = 0
            for g in games:
                diff = int(g['memberPointDiff'])
                if abs(diff) > biggest:
                    biggest = abs(diff)
            margins[member_id] = biggest
        if len(set(margins.values())) <= 1:
            return None
        sorted_group = sorted(group, key=lambda m: (-margins[int(m['memberId'])], int(m['memberId'])))
        return sorted_group

    def _compute_season_standings(self, league_id: int, *, reader_user_id: Optional[int]=None) -> Dict[str, Any]:
        """
        Aggregate WeeklyTeamScore + computed bonuses for a league:

        - weeklyPoints = sum of WeeklyTeamScore.pointsAwarded
        - bonusPoints  = computed via bonus handlers based on League.settings.bonuses
        - totalPoints  = weeklyPoints + bonusPoints
        - Apply season tiebreakers within ties on totalPoints.
        """
        with league_read_access(self.db, league_id, reader_user_id):
            with self.db.begin() as conn:
                rows = list(self.repository.season_points(conn, league_id))
            member_ids: List[int] = [int(r._mapping['memberId']) for r in rows]
            bonus_points_by_member: Dict[int, float] = self._compute_bonus_points(league_id, member_ids)
            members: List[Dict[str, Any]] = []
            for r in rows:
                m = r._mapping
                member_id = int(m['memberId'])
                weekly = float(m['weeklyPoints'])
                bonus = float(bonus_points_by_member.get(member_id, 0.0))
                total = weekly + bonus
                members.append({'memberId': member_id, 'teamName': m['teamName'], 'weeklyPoints': weekly, 'bonusPoints': bonus, 'totalPoints': total})
            members.sort(key=lambda x: (-x['totalPoints'], -x['weeklyPoints'], int(x['memberId'])))
            members = self._apply_season_tiebreakers(league_id, members)
            return {'leagueId': league_id, 'members': members}

    def _apply_season_tiebreakers(self, league_id: int, standings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        For each tie group on totalPoints, apply:

          1) playoff depth in primary postseason (e.g. main playoff bracket)
          2) number of segment/subdivision playoff champions (e.g. conference tournaments)
          3) head-to-head in primary postseason
          4) head-to-head in segment/subdivision postseason
          5) latest non-tied week
        """
        i = 0
        while i < len(standings):
            j = i + 1
            while j < len(standings) and standings[j]['totalPoints'] == standings[i]['totalPoints']:
                j += 1
            if j - i > 1:
                tied_group = standings[i:j]
                resolved = self._resolve_season_ties(league_id, tied_group)
                standings[i:j] = resolved
            i = j
        return standings

    def _resolve_season_ties(self, league_id: int, group: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        result = self._tb_season_playoff_depth(league_id, group)
        if result is not None:
            return result
        result = self._tb_season_num_segment_champs(league_id, group)
        if result is not None:
            return result
        result = self._tb_season_playoff_head_to_head(league_id, group)
        if result is not None:
            return result
        result = self._tb_season_segment_postseason_head_to_head(league_id, group)
        if result is not None:
            return result
        result = self._tb_season_latest_non_tied_week(league_id, group)
        if result is not None:
            return result
        return group

    def _tb_season_playoff_depth(self, league_id: int, group: List[Dict[str, Any]]) -> List[Dict[str, Any]] | None:
        """
        Tiebreaker 1: whoever has the team that goes the farthest
        in the primary postseason (e.g. main playoff bracket).

        Uses GameResult.roundOrder as 'depth' within those phases.
        """
        season = self._get_sport_season_for_league(league_id)
        sport_season_id = int(season['sportSeasonId'])
        with self.db.begin() as conn:
            phase_rows = self.repository.primary_phases(conn, sport_season_id, self.PRIMARY_POSTSEASON_PHASE_TYPES)
        if not phase_rows:
            return None
        nt_phase_ids = [int(r[0]) for r in phase_rows]
        depths: Dict[int, int] = {}
        for m in group:
            member_id = int(m['memberId'])
            team_ids = self._get_member_owned_team_ids(league_id, member_id)
            if not team_ids:
                depths[member_id] = 0
                continue
            with self.db.begin() as conn:
                row = self.repository.playoff_depth(conn, sport_season_id, nt_phase_ids, team_ids)
            depths[member_id] = int(row._mapping['max_round']) if row else 0
        if len(set(depths.values())) <= 1:
            return None
        sorted_group = sorted(group, key=lambda m: (-depths[int(m['memberId'])], int(m['memberId'])))
        return sorted_group

    def _tb_season_num_segment_champs(self, league_id: int, group: List[Dict[str, Any]]) -> List[Dict[str, Any]] | None:
        """
        Tiebreaker 2: whichever member has the most champions
        in segment-level postseason tournaments (e.g. conference tournaments,
        division playoffs, league cups).

        For each SeasonPhase whose type is in SEGMENT_POSTSEASON_PHASE_TYPES:
          - Find final game (max roundOrder)
          - Champion = winner of that game
        """
        season = self._get_sport_season_for_league(league_id)
        sport_season_id = int(season['sportSeasonId'])
        with self.db.begin() as conn:
            phase_rows = self.repository.segment_phases(conn, sport_season_id, self.SEGMENT_POSTSEASON_PHASE_TYPES)
        if not phase_rows:
            return None
        phase_ids = [int(r[0]) for r in phase_rows]
        champions: set[int] = set()
        with self.db.begin() as conn:
            for pid in phase_ids:
                row = self.repository.segment_final(conn, sport_season_id, pid)
                if not row:
                    continue
                home_id, away_id, home_score, away_score = row
                if home_score > away_score:
                    champions.add(int(home_id))
                elif away_score > home_score:
                    champions.add(int(away_id))
        if not champions:
            return None
        champ_counts: Dict[int, int] = {}
        for m in group:
            member_id = int(m['memberId'])
            team_ids = self._get_member_owned_team_ids(league_id, member_id)
            champ_counts[member_id] = len(champions.intersection(set(team_ids)))
        if len(set(champ_counts.values())) <= 1:
            return None
        sorted_group = sorted(group, key=lambda m: (-champ_counts[int(m['memberId'])], int(m['memberId'])))
        return sorted_group

    def _head_to_head_pd_in_phases(self, league_id: int, group: List[Dict[str, Any]], phase_types: List[str]) -> List[Dict[str, Any]] | None:
        """
        Generic helper:
          - For all tied members in group
          - Within SeasonPhase rows whose `type` is in `phase_types`
          - Compute total head-to-head point differential vs other group members.
        """
        season = self._get_sport_season_for_league(league_id)
        sport_season_id = int(season['sportSeasonId'])
        with self.db.begin() as conn:
            phase_rows = self.repository.head_to_head_phases(conn, sport_season_id, phase_types, phase_types == self.PRIMARY_POSTSEASON_PHASE_TYPES)
        if not phase_rows:
            return None
        phase_ids = [int(r[0]) for r in phase_rows]
        member_team_ids: Dict[int, List[int]] = {}
        for m in group:
            mid = int(m['memberId'])
            member_team_ids[mid] = self._get_member_owned_team_ids(league_id, mid)
        totals: Dict[int, int] = {int(m['memberId']): 0 for m in group}
        member_ids = list(totals.keys())
        all_team_ids = sorted({tid for tids in member_team_ids.values() for tid in tids})
        if not all_team_ids:
            return None
        with self.db.begin() as conn:
            rows = self.repository.head_to_head_games(conn, sport_season_id, phase_ids, all_team_ids)
        for row in rows:
            home_id, away_id, home_score, away_score = row
            home_id = int(home_id)
            away_id = int(away_id)
            home_score = int(home_score)
            away_score = int(away_score)
            home_members = [m for m in member_ids if home_id in member_team_ids[m]]
            away_members = [m for m in member_ids if away_id in member_team_ids[m]]
            for hm in home_members:
                for am in away_members:
                    pd = home_score - away_score
                    totals[hm] += pd
                    totals[am] -= pd
        if len(set(totals.values())) <= 1:
            return None
        sorted_group = sorted(group, key=lambda m: (-totals[int(m['memberId'])], int(m['memberId'])))
        return sorted_group

    def _tb_season_playoff_head_to_head(self, league_id: int, group: List[Dict[str, Any]]) -> List[Dict[str, Any]] | None:
        """
        Tiebreaker 3: head-to-head performance in primary postseason phases.
        """
        return self._head_to_head_pd_in_phases(league_id, group, phase_types=self.PRIMARY_POSTSEASON_PHASE_TYPES)

    def _tb_season_segment_postseason_head_to_head(self, league_id: int, group: List[Dict[str, Any]]) -> List[Dict[str, Any]] | None:
        """
        Tiebreaker 4: head-to-head performance in segment-level postseason phases
        (e.g. conference tournaments, division playoffs).
        """
        return self._head_to_head_pd_in_phases(league_id, group, phase_types=self.SEGMENT_POSTSEASON_PHASE_TYPES)

    def _tb_season_latest_non_tied_week(self, league_id: int, group: List[Dict[str, Any]]) -> List[Dict[str, Any]] | None:
        """
        Tiebreaker 5: latest non-tied week score.

        Walk weeks from latest -> earliest. For each:
          - Compare WeeklyTeamScore.rank among tied members.
          - If any difference, sort by rank (1 is best) for that week.
        """
        member_ids = [int(m['memberId']) for m in group]
        with self.db.begin() as conn:
            weeks = self.repository.weeks_descending(conn, league_id)
        if not weeks:
            return None
        for w in weeks:
            week_id = int(w._mapping['id'])
            with self.db.begin() as conn:
                rows = self.repository.weekly_ranks(conn, league_id, week_id, member_ids)
            if not rows:
                continue
            ranks = {int(r._mapping['memberId']): int(r._mapping['rank']) for r in rows}
            if len(set(ranks.values())) <= 1:
                continue
            sorted_group = sorted(group, key=lambda m: (ranks.get(int(m['memberId']), 9999), int(m['memberId'])))
            return sorted_group
        return None

    def _get_league_bonus_config(self, league_id: int) -> Dict[str, Dict[str, float]]:
        """
        Returns the bonuses config for a league.

        Example shape:
        {
          "conferenceChampion": { "first": 1.5, "second": 1.0, "third": 0.5 },
          "conferenceBottom":   { "last": -1.5, "secondLast": -1.0, "thirdLast": -0.5 },
          "playoffDepth":       { "first": 3.0 }
        }
        """
        settings = self._get_league_settings(league_id)
        bonuses = settings.get('bonuses') or {}
        return bonuses

    def _compute_bonus_points(self, league_id: int, member_ids: List[int]) -> Dict[int, float]:
        """
        For the given league and list of member IDs, compute total bonus points
        according to League.settings.bonuses.

        Returns:
            { memberId: total_bonus_points }
        """
        config = self._get_league_bonus_config(league_id)
        totals: Dict[int, float] = {mid: 0.0 for mid in member_ids}
        if not config:
            return totals
        for bonus_code, bonus_cfg in config.items():
            handler_name = self.BONUS_HANDLERS.get(bonus_code)
            if not handler_name:
                continue
            handler = getattr(self, handler_name, None)
            if not handler:
                continue
            contrib: Dict[int, float] = handler(league_id, member_ids, bonus_cfg or {})
            for mid, pts in contrib.items():
                if mid in totals:
                    totals[mid] = float(totals.get(mid, 0.0)) + float(pts)
        return totals

    def _get_playoff_depth_by_member(self, league_id: int, member_ids: List[int]) -> Dict[int, int]:
        """
        For each member, compute the deepest round reached in primary postseason
        phases by any of their teams.
        """
        season = self._get_sport_season_for_league(league_id)
        sport_season_id = int(season['sportSeasonId'])
        with self.db.begin() as conn:
            phase_rows = self.repository.primary_phases(conn, sport_season_id, self.PRIMARY_POSTSEASON_PHASE_TYPES)
        if not phase_rows:
            return {mid: 0 for mid in member_ids}
        phase_ids = [int(r[0]) for r in phase_rows]
        depths: Dict[int, int] = {mid: 0 for mid in member_ids}
        for mid in member_ids:
            team_ids = self._get_member_owned_team_ids(league_id, mid)
            if not team_ids:
                depths[mid] = 0
                continue
            with self.db.begin() as conn:
                row = self.repository.playoff_depth(conn, sport_season_id, phase_ids, team_ids)
            depths[mid] = int(row._mapping['max_round']) if row and row._mapping['max_round'] is not None else 0
        return depths

    def _bonus_playoff_depth(self, league_id: int, member_ids: List[int], config: Dict[str, float]) -> Dict[int, float]:
        """
        Bonus based on how deep a member's teams go in primary postseason.

        Config keys (optional):
          - "first", "second", "third", "fourth", ... -> points

        Only members with depth > 0 can receive points.
        """
        depths = self._get_playoff_depth_by_member(league_id, member_ids)
        return playoff_depth_bonus(depths, member_ids, config)

    def _get_segment_champ_counts_by_member(self, league_id: int, member_ids: List[int]) -> Dict[int, int]:
        """
        For each member, count how many segment-level tournaments
        (conference/division/segment playoffs) they won.
        """
        season = self._get_sport_season_for_league(league_id)
        sport_season_id = int(season['sportSeasonId'])
        with self.db.begin() as conn:
            phase_rows = self.repository.segment_phases(conn, sport_season_id, self.SEGMENT_POSTSEASON_PHASE_TYPES)
        if not phase_rows:
            return {mid: 0 for mid in member_ids}
        phase_ids = [int(r[0]) for r in phase_rows]
        champ_counts: Dict[int, int] = {mid: 0 for mid in member_ids}
        team_to_member: Dict[int, int] = {}
        for mid in member_ids:
            team_ids = self._get_member_owned_team_ids(league_id, mid)
            for tid in team_ids:
                team_to_member[int(tid)] = mid
        with self.db.begin() as conn:
            for pid in phase_ids:
                row = self.repository.segment_final(conn, sport_season_id, pid)
                if not row:
                    continue
                home_id, away_id, home_score, away_score = row
                if home_id is None or away_id is None:
                    continue
                home_id = int(home_id)
                away_id = int(away_id)
                home_score = int(home_score)
                away_score = int(away_score)
                if home_score > away_score:
                    champ_team = home_id
                elif away_score > home_score:
                    champ_team = away_id
                else:
                    continue
                mid = team_to_member.get(champ_team)
                if mid is not None:
                    champ_counts[mid] += 1
        return champ_counts

    def _bonus_conference_champion(self, league_id: int, member_ids: List[int], config: Dict[str, float]) -> Dict[int, float]:
        """
        Bonus based on how many segment-level tournaments a member won.

        Config keys:
          - "first", "second", "third", "fourth", ... -> points
        """
        champ_counts = self._get_segment_champ_counts_by_member(league_id, member_ids)
        return conference_champion_bonus(champ_counts, member_ids, config)

    def _get_segment_pd_by_member(self, league_id: int, member_ids: List[int]) -> Dict[int, int]:
        """
        For each member, compute total point differential across all
        segment-level postseason games (ConferenceTournament / SegmentPlayoffs).

        PD = (points scored by their teams) - (points allowed).
        """
        season = self._get_sport_season_for_league(league_id)
        sport_season_id = int(season['sportSeasonId'])
        with self.db.begin() as conn:
            phase_rows = self.repository.segment_phases(conn, sport_season_id, self.SEGMENT_POSTSEASON_PHASE_TYPES)
        if not phase_rows:
            return {mid: 0 for mid in member_ids}
        phase_ids = [int(r[0]) for r in phase_rows]
        team_to_member: Dict[int, int] = {}
        for mid in member_ids:
            team_ids = self._get_member_owned_team_ids(league_id, mid)
            for tid in team_ids:
                team_to_member[int(tid)] = mid
        pd_totals: Dict[int, int] = {mid: 0 for mid in member_ids}
        with self.db.begin() as conn:
            rows = self.repository.segment_games(conn, sport_season_id, phase_ids)
        for row in rows:
            home_id, away_id, home_score, away_score = row
            if home_id is None or away_id is None:
                continue
            home_id = int(home_id)
            away_id = int(away_id)
            home_score = int(home_score)
            away_score = int(away_score)
            home_mid = team_to_member.get(home_id)
            away_mid = team_to_member.get(away_id)
            if home_mid is not None:
                pd_totals[home_mid] += home_score - away_score
            if away_mid is not None:
                pd_totals[away_mid] += away_score - home_score
        return pd_totals

    def _bonus_conference_bottom(self, league_id: int, member_ids: List[int], config: Dict[str, float]) -> Dict[int, float]:
        """
        Negative bonus (penalty) for poor performance in segment-level tournaments.

        Config keys:
          - "last", "secondLast", "thirdLast", ... -> negative points

        We rank members by total segment-tournament PD (worst = most negative).
        """
        pd_totals = self._get_segment_pd_by_member(league_id, member_ids)
        return conference_bottom_bonus(pd_totals, member_ids, config)

    def get_season_standings(self, actor, league_id):
        if not isinstance(actor, UserActor):
            raise TypeError('A verified UserActor is required')
        return self.get_season_standings_for_legacy_reader(actor.user_id, league_id)

    def get_season_standings_for_legacy_reader(self, user_id, league_id):
        if isinstance(user_id, bool) or not isinstance(user_id, int):
            raise TypeError('A verified integer reader is required')
        try:
            return self._compute_season_standings(league_id, reader_user_id=user_id)
        except PermissionError as exc:
            raise ScoringReadDenied('League not found') from exc

    def get_season_standings_for_job(self, league_id):
        return self._compute_season_standings(league_id)
