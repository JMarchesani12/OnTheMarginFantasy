"""Trusted lifecycle orchestration and transaction ownership."""
from .league_lifecycle_repository import LeagueLifecycleRepository


class LeagueLifecycleService:
    def __init__(self, engine, repository=None):
        self.engine = engine
        self.repository = repository if repository is not None else LeagueLifecycleRepository()

    def synchronize_for_job(self):
        """Preserve global synchronization; completed seasons take precedence last."""
        with self.engine.begin() as conn:
            self.repository.mark_pre_draft(conn)
            self.repository.mark_drafting(conn)
            self.repository.mark_post_draft(conn)
            self.repository.mark_in_season(conn)
            self.repository.mark_completed(conn)
