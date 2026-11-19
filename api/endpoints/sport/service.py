"""Public catalog use case and connection ownership, independent of HTTP."""
from .repository import SportRepository


class SportService:
    def __init__(self, engine, repository=None):
        self.engine = engine
        self.repository = repository if repository is not None else SportRepository()

    def list_sports(self):
        # This catalog is intentionally public; no member/profile lookup needed.
        with self.engine.begin() as conn:
            return self.repository.list_sports(conn)

    def team_search_catalog(self):
        # Public school metadata only: no league, owner, user, or alias sources.
        with self.engine.begin() as conn:
            rows=self.repository.team_search_catalog(conn)
        teams={}
        for row in rows:
            team=teams.setdefault(row['teamId'],dict(teamId=row['teamId'],schoolId=row['schoolId'],teamName=row['teamName'],aliases=[]))
            if row['alias'] is not None: team['aliases'].append(row['alias'])
        return {'teams':list(teams.values())}
