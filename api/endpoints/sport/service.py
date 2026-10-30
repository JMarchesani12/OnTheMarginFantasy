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
