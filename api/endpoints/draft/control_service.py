"""Draft finalization authority and owned/supplied transaction orchestration."""
from actors import UserActor
from .control_repository import DraftControlRepository
from .snapshot_service import DraftSnapshotService
from .draft_rules import settings_from_league, compute_round_and_pos, draft_order_for_pick


class DraftControlService:
    def __init__(self, engine, repository=None):
        self.engine = engine
        self.repository = repository if repository is not None else DraftControlRepository()

    def assert_commissioner(self, conn, league_id, user_id):
        league = self.repository.commissioner(conn, league_id)
        if not league:
            raise ValueError(f'League {league_id} not found')
        if int(league['commissioner']) != int(user_id):
            raise PermissionError('Only the commissioner can control this draft')

    def finalize(self, actor, league_id):
        if not isinstance(actor, UserActor):
            raise TypeError('A verified UserActor is required')
        return self.force_finalize_for_user_id(league_id, actor.user_id)

    def force_finalize_for_user_id(self, league_id, user_id):
        if user_id is None:
            raise PermissionError('Only the commissioner can control this draft')
        with self.engine.begin() as conn:
            self.assert_commissioner(conn, league_id, user_id)
            result = self.finalize_for_job(league_id, conn=conn)
            self.assert_commissioner(conn, league_id, user_id)
            return result

    def finalize_for_job(self, league_id, conn=None):
        """Existing trusted final-pick path; supplied connection stays caller-owned."""
        if conn is not None:
            return self._finalize(conn, league_id)
        with self.engine.begin() as owned:
            return self._finalize(owned, league_id)

    def _finalize(self, conn, league_id):
        state = self.repository.finalize_state(conn, league_id)
        if not state:
            raise ValueError(f'DraftState not found for league {league_id}')
        league = self.repository.finalize_league(conn, league_id)
        return {'leagueId': league_id, 'draftComplete': True, 'state': state,
                'leagueStatus': league['leagueStatus'] if league else None}

    def start(self, actor, league_id):
        if not isinstance(actor, UserActor):
            raise TypeError("A verified UserActor is required")
        return self.start_for_legacy_user_id(league_id, actor.user_id)

    def start_for_job(self, league_id):
        return self.start_for_legacy_user_id(league_id, None)

    def start_for_legacy_user_id(self, league_id, user_id):
        return self._with_control(league_id, user_id, self._start)

    def pause(self, actor, league_id):
        if not isinstance(actor, UserActor):
            raise TypeError("A verified UserActor is required")
        return self.pause_for_legacy_user_id(league_id, actor.user_id)

    def pause_for_job(self, league_id):
        return self.pause_for_legacy_user_id(league_id, None)

    def pause_for_legacy_user_id(self, league_id, user_id):
        return self._with_control(league_id, user_id, self._pause)

    def resume(self, actor, league_id):
        if not isinstance(actor, UserActor):
            raise TypeError("A verified UserActor is required")
        return self.resume_for_legacy_user_id(league_id, actor.user_id)

    def resume_for_job(self, league_id):
        return self.resume_for_legacy_user_id(league_id, None)

    def resume_for_legacy_user_id(self, league_id, user_id):
        return self._with_control(league_id, user_id, self._resume)

    def _with_control(self, league_id, user_id, operation):
        with self.engine.begin() as conn:
            if user_id is not None:
                self.assert_commissioner(conn, league_id, user_id)
            result = operation(conn, league_id)
            if user_id is not None:
                self.assert_commissioner(conn, league_id, user_id)
            return result

    def draft_settings(self, conn, league_id):
        league = self.repository.settings_row(conn, league_id)
        if not league:
            raise ValueError(f'League {league_id} not found')
        return settings_from_league(league)

    def expected_member(self, conn, league_id, overall):
        return self.repository.expected_member(conn, league_id, overall)

    def seed_turns(self, conn, league_id):
        cfg = self.draft_settings(conn, league_id)
        num_players = int(cfg['numPlayers'])
        rounds = int(cfg['numberOfRounds'])
        draft_type = cfg['draftType']
        members = self.repository.seed_members(conn, league_id)
        order_to_member = {int(r['draftOrder']): int(r['memberId']) for r in members}
        rows = []
        for overall in range(1, rounds * num_players + 1):
            rnd, pos = compute_round_and_pos(overall, num_players)
            order = draft_order_for_pick(draft_type, rnd, pos, num_players)
            rows.append({'leagueId': league_id, 'overallPickNumber': overall, 'memberId': order_to_member[order]})
        self.repository.insert_turns(conn, rows)

    def _start(self, conn, league_id):
        cfg = self.draft_settings(conn, league_id)
        missing = self.repository.missing_orders(conn, league_id, cfg['numPlayers'])
        if missing:
            missing_orders = [int(r['missingOrder']) for r in missing]
            raise ValueError(f'Draft order incomplete. Missing draftOrder values: {missing_orders}')
        self.seed_turns(conn, league_id)
        first = self.expected_member(conn, league_id, 1)
        if not first:
            raise ValueError('DraftTurn not seeded correctly (missing overallPickNumber=1)')
        self.repository.start_state(conn, league_id, first, cfg['selectionTime'])
        self.repository.mark_drafting(conn, league_id)
        return DraftSnapshotService(self.engine).snapshot_for_job(league_id, conn)

    @staticmethod
    def _require_active_state(state):
        if not state:
            raise ValueError('DraftState not found. Start draft first.')
        if str(state['status']) == 'complete':
            raise ValueError('Draft is complete')

    def _pause(self, conn, league_id):
        state = self.repository.lock_state(conn, league_id)
        self._require_active_state(state)
        self.repository.pause_state(conn, league_id)
        return DraftSnapshotService(self.engine).snapshot_for_job(league_id, conn)

    def _resume(self, conn, league_id):
        cfg = self.draft_settings(conn, league_id)
        state = self.repository.lock_state(conn, league_id)
        self._require_active_state(state)
        self.repository.resume_state(conn, league_id, cfg['selectionTime'])
        return DraftSnapshotService(self.engine).snapshot_for_job(league_id, conn)

    def set_order(self, actor, league_id, member_ids):
        if not isinstance(actor, UserActor):
            raise TypeError('A verified UserActor is required')
        return self.set_order_for_legacy_user_id(league_id, member_ids, actor.user_id)

    def set_order_for_job(self, league_id, member_ids):
        return self.set_order_for_legacy_user_id(league_id, member_ids, None)

    def set_order_for_legacy_user_id(self, league_id, member_ids, user_id):
        if not member_ids:
            raise ValueError('memberIdsInOrder is required')
        return self._with_control(league_id, user_id, lambda conn, league: self._set_order(conn, league, member_ids))

    def _set_order(self, conn, league_id, member_ids):
        state = self.repository.order_state(conn, league_id)
        if state and str(state['status']) in ('live', 'paused', 'complete'):
            raise ValueError('Cannot change draft order after draft has started')
        members = self.repository.order_members(conn, league_id, member_ids)
        if len(members) != len(member_ids):
            raise ValueError('One or more memberIds are not in this league')
        self.repository.bump_orders(conn, league_id)
        self.repository.assign_order(conn, league_id, member_ids)
        return {'members': self.repository.ordered_members(conn, league_id)}
