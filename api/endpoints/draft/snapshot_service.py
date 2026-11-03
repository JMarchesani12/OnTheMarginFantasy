"""Draft snapshot member policy, repair orchestration and transaction scope."""
from datetime import datetime, timezone
from actors import UserActor
from .snapshot_repository import DraftSnapshotRepository


class DraftSnapshotService:
    def __init__(self, engine, repository=None):
        self.engine = engine
        self.repository = repository if repository is not None else DraftSnapshotRepository()

    def snapshot(self, actor, league_id, conn=None):
        if not isinstance(actor, UserActor):
            raise TypeError('A verified UserActor is required')
        return self.snapshot_for_reader_id(league_id, actor.user_id, conn)

    def snapshot_for_reader_id(self, league_id, user_id, conn=None):
        return self._snapshot(league_id, conn, user_id)

    def snapshot_for_job(self, league_id, conn=None):
        return self._snapshot(league_id, conn)

    def _snapshot(self, league_id, conn=None, reader_user_id=None):
        if conn is not None:
            return self._snapshot_in_connection(conn, league_id, reader_user_id)
        with self.engine.begin() as owned:
            return self._snapshot_in_connection(owned, league_id, reader_user_id)

    def repair_completed(self, league_id, state, conn):
        if str(state.get('status')) != 'complete':
            return state
        if state.get('currentMemberId') is None and state.get('expiresAt') is None:
            return state
        row = self.repository.repair_completed(conn, league_id)
        return row if row else state

    def next_unpicked_turn(self, conn, league_id, start_overall):
        return self.repository.next_unpicked_turn(conn, league_id, start_overall)

    def _snapshot_in_connection(self, conn, league_id, reader_user_id):
        league = self.repository.snapshot_league(conn, league_id, reader_user_id)
        if not league:
            if reader_user_id is not None:
                raise PermissionError('League not found')
            raise ValueError(f'League {league_id} not found')
        settings = league['settings'] or {}
        draft_settings = settings.get('draft') or {}
        state = self.repository.snapshot_state(conn, league_id)
        if state:
            state = self.repair_completed(league_id, dict(state), conn)
        members = self.repository.snapshot_members(conn, league_id)
        picks = self.repository.snapshot_picks(conn, league_id)
        on_deck = None
        in_the_hole = None
        if state and state.get("currentOverallPickNumber") is not None:
            current_overall = int(state["currentOverallPickNumber"])
            on_deck = self.next_unpicked_turn(conn, league_id, current_overall + 1)
            if on_deck:
                in_the_hole = self.next_unpicked_turn(conn, league_id, on_deck[0] + 1)

        member_id_to_name = {int(m["memberId"]): m["teamName"] for m in members}

        def _turn_payload(turn):
            if not turn:
                return None
            overall, member_id = turn
            return {
                "overallPickNumber": overall,
                "memberId": member_id,
                "memberTeamName": member_id_to_name.get(member_id),
            }

        return {
            "leagueId": league_id,
            "draftSettings": draft_settings,
            "serverNow": datetime.now(timezone.utc).isoformat(),
            "state": dict(state) if state else None,
            "members": [dict(m) for m in members],
            "picks": [dict(p) for p in picks],
            "onDeck": _turn_payload(on_deck),
            "inTheHole": _turn_payload(in_the_hole),
        }
