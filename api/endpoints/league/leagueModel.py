import os
from typing import Any, Dict, List, Optional

from sqlalchemy.engine import Engine

from endpoints.schedule.scheduleModel import ScheduleModel
from utils.authorization import league_read_scope
from .admission_service import AdmissionService
from .member_service import MemberService
from .league_admin_service import LeagueAdminService
from .league_read_service import LeagueReadService
from .league_lifecycle_service import LeagueLifecycleService
from .member_repository import ALLOWED_LEAGUE_MEMBER_FIELDS
from .contracts import AdmissionDenied, AdmissionRejected
from rules.leagueRules import get_timezone_name_from_settings, validate_timezone_name, ensure_timezone_in_settings



class LeagueModel:
    def __init__(self, db: Engine):
        self.db = db
        self.scheduleModel = ScheduleModel(db, os.getenv("ESPN_BASE_URL"))

    @staticmethod
    def _league_read_scope(league_id: int, reader_user_id: Optional[int]):
        return league_read_scope(league_id, reader_user_id)

    def get_league_read_access(self, league_id: int, user_id: int):
        return LeagueReadService(self.db).access_for_reader_id(league_id, user_id)

    def get_member_previews_for_user(self, league_id: int, user_id: int):
        return LeagueReadService(self.db).member_previews_for_reader_id(league_id, user_id)

    def sync_due_league_statuses(self) -> None:
        return LeagueLifecycleService(self.db).synchronize_for_job()

    def _get_timezone_name_from_settings(self, settings: Dict[str, Any]) -> Optional[str]:
        return get_timezone_name_from_settings(settings)

    def _validate_timezone_name(self, tz_name: str) -> None:
        validate_timezone_name(tz_name)

    def _ensure_timezone_in_settings(self, settings: Dict[str, Any]) -> Dict[str, Any]:
        return ensure_timezone_in_settings(settings)

    def get_league(self, leagueId, reader_user_id: Optional[int] = None):
        service = LeagueReadService(self.db)
        sync = lambda: self.sync_due_league_statuses()
        if reader_user_id is None:
            return service.details_for_job(leagueId, sync)
        return service.details_for_reader_id(leagueId, reader_user_id, sync)

    def get_league_rules(self, league_id, reader_user_id: Optional[int] = None):
        service = LeagueReadService(self.db)
        if reader_user_id is None:
            return service.rules_for_job(league_id)
        return service.rules_for_reader_id(league_id, reader_user_id)

    def create_league(self, league: Dict[str, Any]) -> Dict[str, Any]:
        # Make a copy so we don't mutate the original dict
        return LeagueAdminService(self.db).create_for_job(
            league, lambda league_id: self.scheduleModel.ensure_weeks_for_league(league_id),
        )
    
    def update_league(self, league_id: int, patch: Dict[str, Any]) -> Dict[str, Any]:
        """Trusted model entry point; interactive HTTP must use the checked variant."""
        return self._update_league(league_id, patch)

    def update_league_as_commissioner(
        self, league_id: int, user_id: int, patch: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Update as a verified HTTP principal; caller supplies resolved user_id."""
        return self._update_league(league_id, patch, commissioner_id=user_id)

    def _update_league(
        self, league_id: int, patch: Dict[str, Any], commissioner_id: int | None = None,
    ) -> Dict[str, Any]:
        service = LeagueAdminService(self.db)
        if commissioner_id is None:
            return service.update_for_job(league_id, patch)
        return service.update_for_legacy_commissioner(league_id, commissioner_id, patch)

    
    # 1) All leagues a user is in
    def get_leagues_for_user(self, user_id: int, stage: str = "all") -> List[Dict[str, Any]]:
        return LeagueReadService(self.db).mine_for_user_id(
            user_id, lambda: self.sync_due_league_statuses(), stage,
        )


    def get_members_for_league(self, league_id: int, reader_user_id: Optional[int] = None) -> List[Dict[str, Any]]:
        service = LeagueReadService(self.db)
        timezone_for_league = lambda league: self.scheduleModel._get_league_timezone(league)
        games = lambda **kwargs: self.scheduleModel.get_member_games_for_week(**kwargs)
        if reader_user_id is None:
            return service.members_for_job(league_id, timezone_for_league, games)
        return service.members_for_reader_id(league_id, reader_user_id, timezone_for_league, games)

    def get_league_conferences(self, league_id: int, reader_user_id: Optional[int] = None) -> Dict[str, Any]:
        service = LeagueReadService(self.db)
        if reader_user_id is None:
            return service.conferences_for_job(league_id)
        return service.conferences_for_reader_id(league_id, reader_user_id)
    
    def _get_league_commissioner(self, league_id: int) -> Optional[int]:
        return AdmissionService(self.db).get_commissioner_for_job(league_id)

    def _ensure_commissioner(self, league_id: int, acting_user_id: int) -> None:
        commissioner = self._get_league_commissioner(league_id)
        if commissioner is None:
            raise ValueError(f"League {league_id} not found")
        if commissioner != acting_user_id:
            raise PermissionError("Only the commissioner can perform this action")
        

    def create_join_request(self, league_id: int, user_id: int, message: Optional[str] = None, team_name: Optional[str] = None) -> Dict[str, Any]:
        try:
            return AdmissionService(self.db).create_request_for_user_id(user_id, league_id, message, team_name)
        except AdmissionRejected as exc:
            raise ValueError(str(exc)) from exc

    def list_join_requests(self, league_id: int, status: Optional[str] = None) -> list[Dict[str, Any]]:
        """Trusted model listing; HTTP must use the commissioner-checked variant."""
        return self._list_join_requests(league_id, status)

    def list_join_requests_as_commissioner(
        self, league_id: int, user_id: int, status: Optional[str] = None,
    ) -> list[Dict[str, Any]]:
        try:
            return AdmissionService(self.db).list_requests_for_legacy_reader(user_id, league_id, status)
        except AdmissionDenied as exc:
            raise PermissionError(str(exc)) from exc
        except AdmissionRejected as exc:
            raise ValueError(str(exc)) from exc

    def _list_join_requests(
        self, league_id: int, status: Optional[str], commissioner_id: int | None = None,
    ) -> list[Dict[str, Any]]:
        service = AdmissionService(self.db)
        if commissioner_id is None:
            return service.list_requests_for_job(league_id, status)
        return service.list_requests_for_legacy_scope(commissioner_id, league_id, status)

    def approve_join_request(self, league_id: int, request_id: int, acting_user_id: int) -> Dict[str, Any]:
        try:
            return AdmissionService(self.db).approve_request_for_job(league_id, request_id, acting_user_id)
        except AdmissionRejected as exc:
            raise ValueError(str(exc)) from exc

    def approve_join_request_as_commissioner(
        self, league_id: int, request_id: int, user_id: int,
    ) -> Dict[str, Any]:
        try:
            return AdmissionService(self.db).approve_request_for_legacy_commissioner(user_id, league_id, request_id)
        except AdmissionDenied as exc:
            raise PermissionError(str(exc)) from exc
        except AdmissionRejected as exc:
            raise ValueError(str(exc)) from exc

    def _approve_join_request(
        self, conn, league_id: int, request_id: int, acting_user_id: int,
    ) -> Dict[str, Any]:
        # lock the request row to prevent double-approval races
        try:
            return AdmissionService(self.db).approve_request_in_transaction(conn, league_id, request_id, acting_user_id)
        except AdmissionRejected as exc:
            raise ValueError(str(exc)) from exc

    def deny_join_request(self, league_id: int, request_id: int, acting_user_id: int) -> Dict[str, Any]:
        try:
            return AdmissionService(self.db).deny_request_for_job(league_id, request_id, acting_user_id)
        except AdmissionRejected as exc:
            raise ValueError(str(exc)) from exc

    def deny_join_request_as_commissioner(
        self, league_id: int, request_id: int, user_id: int,
    ) -> Dict[str, Any]:
        try:
            return AdmissionService(self.db).deny_request_for_legacy_commissioner(user_id, league_id, request_id)
        except AdmissionDenied as exc:
            raise PermissionError(str(exc)) from exc
        except AdmissionRejected as exc:
            raise ValueError(str(exc)) from exc

    def _deny_join_request(
        self, conn, league_id: int, request_id: int, acting_user_id: int,
    ) -> Dict[str, Any]:
        try:
            return AdmissionService(self.db).deny_request_in_transaction(conn, league_id, request_id, acting_user_id)
        except AdmissionRejected as exc:
            raise ValueError(str(exc)) from exc

    def cancel_join_request(self, league_id: int, request_id: int, user_id: int) -> Dict[str, Any]:
        try:
            return AdmissionService(self.db).cancel_request_for_owner_id(user_id, league_id, request_id)
        except AdmissionDenied as exc:
            raise PermissionError(str(exc)) from exc
        except AdmissionRejected as exc:
            raise ValueError(str(exc)) from exc
    
    def remove_member_and_shift_draft_order(
        self,
        league_id: int,
        member_id: int,
        acting_user_id: int,
        shift_draft_order: bool = True,
    ) -> Dict[str, Any]:
        return MemberService(self.db).remove_for_legacy_commissioner(
            league_id, member_id, acting_user_id, shift_draft_order,
        )
    
    def search_leagues(
        self,
        q: str,
        sport_id: int | None = None,
        limit: int = 20,
        offset: int = 0,
    ):
        return LeagueReadService(self.db).search_public(q, sport_id, limit, offset)

    def delete_league(self, league_id: int, acting_user_id: int) -> Dict[str, Any]:
        return LeagueAdminService(self.db).delete_for_legacy_commissioner(league_id, acting_user_id)
    
    def update_owned_league_member(
        self, member_id: int, user_id: int, team_name: str,
    ) -> Dict[str, Any]:
        return MemberService(self.db).rename_for_owner_id(member_id, user_id, team_name)

    def update_league_member(self, member_id: int, updates: Dict[str, Any]) -> Dict[str, Any]:
        # keep only allowed keys that are actually present
        return MemberService(self.db).update_for_job(member_id, updates)
