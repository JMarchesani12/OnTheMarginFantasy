"""Compatibility facade for historical SportModel callers."""
from sqlalchemy.engine import Engine
from .service import SportService


class SportModel:
    def __init__(self, db: Engine):
        self.db = db

    def get_sports(self):
        return SportService(self.db).list_sports()
