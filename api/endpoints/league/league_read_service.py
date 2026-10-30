"""League read orchestration and actor scope, independent of HTTP."""
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
