"""Compatibility facade for existing roster model and trusted direct callers."""
from typing import Any, Dict, List, Optional
from sqlalchemy.engine import Engine
from .contracts import RosterAccessDenied, RosterWeekUnavailable
from .service import RosterService


class RosterModel:
    def __init__(self, db: Engine):
        self.db = db
        self._roster_service = RosterService(db)

    def _get_week_by_number(self, conn, league_id: int, week_number: int):
        return self._roster_service.repository.get_week_by_number(conn, league_id, week_number)

    def _get_next_unlocked_week_number(self, conn, league_id: int, week_number: int) -> int:
        try:
            return self._roster_service.next_unlocked_week_in_transaction(conn, league_id, week_number)
        except RosterWeekUnavailable as exc:
            raise ValueError(str(exc)) from exc

    def get_member_teams_for_week(
        self,
        league_id: int,
        member_id: int,
        week_number: int,
        *, reader_user_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        try:
            if reader_user_id is None:
                return self._roster_service.get_member_teams_for_job(league_id, member_id, week_number)
            return self._roster_service.get_member_teams_for_legacy_reader(
                reader_user_id, league_id, member_id, week_number,
            )
        except RosterAccessDenied as exc:
            raise PermissionError(str(exc)) from exc
        except RosterWeekUnavailable as exc:
            raise ValueError(str(exc)) from exc

    def get_available_teams_for_week(
        self,
        league_id: int,
        week_number: int,
        *, reader_user_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        try:
            if reader_user_id is None:
                return self._roster_service.get_available_teams_for_job(league_id, week_number)
            return self._roster_service.get_available_teams_for_legacy_reader(
                reader_user_id, league_id, week_number,
            )
        except RosterAccessDenied as exc:
            raise PermissionError(str(exc)) from exc
        except RosterWeekUnavailable as exc:
            raise ValueError(str(exc)) from exc
