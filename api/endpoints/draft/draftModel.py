"""SQL-free legacy facade: pick inheritance preserves public/helper overrides."""
from contextlib import contextmanager
from typing import Any, Dict, List, Optional
from .pick_service import DraftPickService
from .control_service import DraftControlService
from .snapshot_service import DraftSnapshotService


class DraftModel(DraftPickService):
    def _assert_draft_commissioner(self, conn, league_id: int, acting_user_id: int):
        return DraftControlService(None).assert_commissioner(conn, league_id, acting_user_id)


    @contextmanager
    def _draft_control_transaction(self, league_id: int, acting_user_id: Optional[int]):
        # Trusted defaults stay independent of HTTP. Supplied principals must
        # retain commissioner authority through the final transaction check.
        # These checks add no row locks or concurrent-removal guarantee.
        with self.db.begin() as conn:
            if acting_user_id is not None:
                self._assert_draft_commissioner(conn, league_id, acting_user_id)
            yield conn
            if acting_user_id is not None:
                self._assert_draft_commissioner(conn, league_id, acting_user_id)


    def force_finalize_draft(self, league_id: int, acting_user_id: int) -> Dict[str, Any]:
        return DraftControlService(getattr(self, "db", None)).force_finalize_for_user_id(league_id, acting_user_id)


    def _repair_completed_draft_state(self, league_id: int, state: Dict[str, Any], conn) -> Dict[str, Any]:
        return DraftSnapshotService(None).repair_completed(league_id, state, conn)


    def start_draft(self, league_id: int, *, acting_user_id: Optional[int] = None) -> Dict[str, Any]:
        service = DraftControlService(self.db)
        if acting_user_id is None:
            return service.start_for_job(league_id)
        return service.start_for_legacy_user_id(league_id, acting_user_id)


    def pause_draft(self, league_id: int, *, acting_user_id: Optional[int] = None) -> Dict[str, Any]:
        service = DraftControlService(self.db)
        if acting_user_id is None:
            return service.pause_for_job(league_id)
        return service.pause_for_legacy_user_id(league_id, acting_user_id)


    def resume_draft(self, league_id: int, *, acting_user_id: Optional[int] = None) -> Dict[str, Any]:
        service = DraftControlService(self.db)
        if acting_user_id is None:
            return service.resume_for_job(league_id)
        return service.resume_for_legacy_user_id(league_id, acting_user_id)


    def seed_draft_turns(self, conn, league_id: int) -> None:
        return DraftControlService(None).seed_turns(conn, league_id)


    def get_draft_state_snapshot(
        self, league_id: int, conn=None, *, reader_user_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        service = DraftSnapshotService(getattr(self, 'db', None))
        if reader_user_id is None:
            return service.snapshot_for_job(league_id, conn)
        return service.snapshot_for_reader_id(league_id, reader_user_id, conn)


    def set_draft_order(self, league_id: int, member_ids_in_order: List[int], *, acting_user_id: Optional[int] = None) -> Dict[str, Any]:
        service = DraftControlService(getattr(self, "db", None))
        if acting_user_id is None:
            return service.set_order_for_job(league_id, member_ids_in_order)
        return service.set_order_for_legacy_user_id(league_id, member_ids_in_order, acting_user_id)
