"""League read orchestration and actor scope, independent of HTTP."""
import logging
import datetime as dt
from actors import UserActor
from rules.leagueRules import describe_rules
from .league_read_repository import LeagueReadRepository


class LeagueReadService:
    def __init__(self, engine, repository=None):
        self.engine = engine
        self.repository = repository if repository is not None else LeagueReadRepository()

    def rules(self, actor, league_id):
        if not isinstance(actor, UserActor):
            raise TypeError('A verified UserActor is required')
        return self.rules_for_reader_id(league_id, actor.user_id)

    def rules_for_reader_id(self, league_id, user_id):
        return self._rules(league_id, user_id)

    def rules_for_job(self, league_id):
        return self._rules(league_id)

    def _rules(self, league_id, reader_user_id=None):
        with self.engine.connect() as conn:
            league = self.repository.rules_league(conn, league_id, reader_user_id)
            if not league:
                return None
            teams = self.repository.rules_teams(conn, league['sport'])
        payload = describe_rules(league['sport'], league.get('settings'), teams)
        payload.update(leagueId=league_id, leagueName=league['name'], seasonYear=league['seasonYear'])
        for key in ('tradeDeadline', 'freeAgentDeadline', 'draftDate'):
            value = league.get(key)
            payload['settings'][key] = value.isoformat() if hasattr(value, 'isoformat') else value
        return payload

    def conferences(self, actor, league_id):
        if not isinstance(actor, UserActor):
            raise TypeError('A verified UserActor is required')
        return self.conferences_for_reader_id(league_id, actor.user_id)

    def conferences_for_reader_id(self, league_id, user_id):
        return self._conferences(league_id, user_id)

    def conferences_for_job(self, league_id):
        return self._conferences(league_id)

    def _conferences(self, league_id, reader_user_id=None):
        with self.engine.begin() as conn:
            league = self.repository.conference_league(conn, league_id, reader_user_id)
            if not league:
                raise ValueError(f'League {league_id} not found')
            sport_id = league['sportId']
            season_year = league.get('seasonYear')
            if season_year is None:
                raise ValueError('League.seasonYear is null/missing; cannot compute season-scoped memberships')
            conferences = self.repository.season_conferences(conn, sport_id, season_year)
        return {'leagueId': league_id, 'sportId': sport_id, 'seasonYear': season_year, 'conferences': conferences}

    def access(self, actor, league_id):
        if not isinstance(actor, UserActor):
            raise TypeError('A verified UserActor is required')
        return self.access_for_reader_id(league_id, actor.user_id)

    def access_for_reader_id(self, league_id, user_id):
        """Internal entitlement facts; HTTP owns concealment and preview policy."""
        with self.engine.begin() as conn:
            return self.repository.access_metadata(conn, league_id, user_id)

    def member_previews(self, actor, league_id):
        if not isinstance(actor, UserActor):
            raise TypeError('A verified UserActor is required')
        return self.member_previews_for_reader_id(league_id, actor.user_id)

    def member_previews_for_reader_id(self, league_id, user_id):
        with self.engine.begin() as conn:
            return self.repository.member_previews(conn, league_id, user_id)

    def search_public(self, q, sport_id=None, limit=20, offset=0):
        q = (q or '').strip()
        if len(q) < 2:
            return []
        limit = max(1, min(int(limit), 50))
        offset = max(0, int(offset))
        with self.engine.begin() as conn:
            return self.repository.search_discoverable(conn, q, sport_id, limit, offset)

    def details(self, actor, league_id, sync_statuses):
        if not isinstance(actor, UserActor):
            raise TypeError('A verified UserActor is required')
        return self.details_for_reader_id(league_id, actor.user_id, sync_statuses)

    def details_for_reader_id(self, league_id, user_id, sync_statuses):
        return self._details(league_id, sync_statuses, user_id)

    def details_for_job(self, league_id, sync_statuses):
        return self._details(league_id, sync_statuses)

    def _details(self, league_id, sync_statuses, reader_user_id=None):
        sync_statuses()
        with self.engine.begin() as conn:
            return self.repository.details(conn, league_id, reader_user_id)

    def mine(self, actor, sync_statuses, stage='all'):
        if not isinstance(actor, UserActor):
            raise TypeError('A verified UserActor is required')
        return self.mine_for_user_id(actor.user_id, sync_statuses, stage)

    def mine_for_user_id(self, user_id, sync_statuses, stage='all'):
        stage = (stage or 'all').lower()
        if stage not in ('all', 'active', 'completed'):
            stage = 'all'
        sync_statuses()
        with self.engine.connect() as conn:
            rows = self.repository.own_leagues(conn, user_id, stage)
        logging.debug('get_leagues_for_user(user_id=%s, stage=%s) -> %d rows', user_id, stage, len(rows))
        return rows

    def members(self, actor, league_id, timezone_for_league, games_for_member_week):
        if not isinstance(actor, UserActor):
            raise TypeError('A verified UserActor is required')
        return self.members_for_reader_id(league_id, actor.user_id, timezone_for_league, games_for_member_week)

    def members_for_reader_id(self, league_id, user_id, timezone_for_league, games_for_member_week):
        return self._members(league_id, timezone_for_league, games_for_member_week, user_id)

    def members_for_job(self, league_id, timezone_for_league, games_for_member_week):
        return self._members(league_id, timezone_for_league, games_for_member_week)

    def _members(self, league_id, timezone_for_league, games_for_member_week, reader_user_id=None):
        with self.engine.connect() as conn:
            rows = self.repository.member_rows(conn, league_id, reader_user_id)
            current_week_row = self.repository.member_current_week(conn, league_id, reader_user_id)
        current_week_number = None
        current_week_start = None
        current_week_end = None
        if current_week_row:
            current_week_number = int(current_week_row[0])
            current_week_start = current_week_row[1]
            current_week_end = current_week_row[2]

        members = []
        local_tz = timezone_for_league(league_id)
        date_keys = []
        if current_week_start and current_week_end:
            start_dt = current_week_start
            end_dt = current_week_end
            if isinstance(start_dt, str):
                start_dt = dt.datetime.fromisoformat(start_dt)
            if isinstance(end_dt, str):
                end_dt = dt.datetime.fromisoformat(end_dt)
            if start_dt.tzinfo is None:
                start_dt = start_dt.replace(tzinfo=dt.timezone.utc)
            if end_dt.tzinfo is None:
                end_dt = end_dt.replace(tzinfo=dt.timezone.utc)
            cur_date = start_dt.astimezone(local_tz).date()
            end_date = end_dt.astimezone(local_tz).date()
            while cur_date <= end_date:
                date_keys.append(cur_date)
                cur_date = cur_date + dt.timedelta(days=1)

        for r in rows:
            member_id = r["memberId"]
            current_week_point_differential = 0
            daily_point_differentials = []
            if current_week_number is not None:
                games = games_for_member_week(
                    league_id=league_id,
                    member_id=member_id,
                    week_number=current_week_number,
                )
                daily_totals = {d: 0 for d in date_keys}
                for g in games:
                    current_week_point_differential += int(g["memberPointDiff"])
                    game_dt = g.get("date")
                    if game_dt is None:
                        continue
                    if isinstance(game_dt, str):
                        game_dt = dt.datetime.fromisoformat(game_dt)
                    if game_dt.tzinfo is None:
                        game_dt = game_dt.replace(tzinfo=dt.timezone.utc)
                    game_date = game_dt.astimezone(local_tz).date()
                    if game_date in daily_totals:
                        daily_totals[game_date] += int(g["memberPointDiff"])
                daily_point_differentials = [
                    {"date": d.isoformat(), "pointDifferential": daily_totals[d]}
                    for d in date_keys
                ]

            members.append(
                {
                    "id": r["memberId"],
                    "createdAt": r["memberCreatedAt"],
                    "leagueId": r["leagueId"],
                    "userId": r["userId"],
                    "teamName": r["teamName"],
                    "draftOrder": r["draftOrder"],
                    "seasonPoints": r["seasonPoints"],
                    "displayName": r['displayName'],
                    "currentWeekPointDifferential": current_week_point_differential,
                    "dailyPointDifferentials": daily_point_differentials,
                }
            )

        return members
