"""Member edit policy and transaction ownership, independent of HTTP."""
from actors import UserActor
from .member_repository import MemberRepository, ALLOWED_LEAGUE_MEMBER_FIELDS


class MemberService:
    def __init__(self, engine, repository=None):
        self.engine = engine
        self.repository = repository if repository is not None else MemberRepository()

    def rename(self, actor, member_id, team_name):
        if not isinstance(actor, UserActor):
            raise TypeError('A verified UserActor is required')
        if not isinstance(team_name, str) or not team_name.strip():
            raise ValueError('Team name is required')
        return self.rename_for_owner_id(member_id, actor.user_id, team_name)

    def rename_for_owner_id(self, member_id, user_id, team_name):
        """Preserve legacy ID method inputs; HTTP selects checked rename."""
        with self.engine.begin() as conn:
            row = self.repository.rename_owned(conn, member_id, user_id, team_name)
        if not row:
            raise LookupError('LeagueMember not found')
        return row

    def update_for_job(self, member_id, updates):
        """Trusted legacy fields; interactive callers cannot select this path."""
        payload = {k: updates[k] for k in updates.keys() if k in ALLOWED_LEAGUE_MEMBER_FIELDS}
        if not payload:
            raise ValueError('No valid fields provided to update')
        with self.engine.begin() as conn:
            row = self.repository.update_member(conn, member_id, payload)
        if not row:
            raise ValueError('LeagueMember not found')
        return row

    def remove(self, actor, league_id, member_id, shift_draft_order=True):
        if not isinstance(actor, UserActor):
            raise TypeError('A verified UserActor is required')
        if not isinstance(shift_draft_order, bool):
            raise ValueError('shiftDraftOrder must be a boolean')
        return self.remove_for_legacy_commissioner(league_id, member_id, actor.user_id, shift_draft_order)

    def remove_for_legacy_commissioner(self, league_id, member_id, acting_user_id, shift_draft_order=True):
        """Existing context-free method; authority is always checked under lock."""
        with self.engine.begin() as conn:
            league = self.repository.lock_league_for_removal(conn, league_id)
            if not league:
                raise ValueError('League not found')
            if int(league['commissioner']) != int(acting_user_id):
                raise PermissionError('Only the commissioner can remove members')
            member = self.repository.lock_member_for_removal(conn, league_id, member_id)
            if not member:
                raise ValueError('Member not found in this league')
            if int(member['userId']) == int(league['commissioner']):
                raise ValueError('Cannot remove the commissioner')
            removed_order = int(member['draftOrder'])
            self.repository.delete_member(conn, league_id, member_id)
            if shift_draft_order:
                self.repository.shift_after_removal(conn, league_id, removed_order)
            self.repository.decrement_count(conn, league_id)
            members = self.repository.remaining_members(conn, league_id)
        return {'removedMemberId': member_id, 'removedDraftOrder': removed_order, 'members': members}
