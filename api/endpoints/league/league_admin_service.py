"""League administration authority and transaction ownership, independent of HTTP."""
import json
from actors import UserActor
from rules.leagueRules import settings_for_update, get_timezone_name_from_settings, validate_timezone_name
from .league_admin_repository import LeagueAdminRepository


class LeagueAdminService:
    def __init__(self, engine, repository=None):
        self.engine = engine
        self.repository = repository if repository is not None else LeagueAdminRepository()

    def delete(self, actor, league_id):
        if not isinstance(actor, UserActor):
            raise TypeError('A verified UserActor is required')
        return self.delete_for_legacy_commissioner(league_id, actor.user_id)

    def delete_for_legacy_commissioner(self, league_id, acting_user_id):
        """Legacy context-free call; commissioner authority is mandatory."""
        with self.engine.begin() as conn:
            league = self.repository.lock_for_delete(conn, league_id)
            if not league:
                raise ValueError('League not found')
            if int(league['commissioner']) != int(acting_user_id):
                raise PermissionError('Only the commissioner can delete this league')
            deleted = self.repository.delete_if_commissioner(conn, league_id, acting_user_id)
            if not deleted:
                raise RuntimeError('Failed to delete league')
        return {'deletedLeagueId': deleted['id'], 'deletedLeagueName': deleted['name']}

    def update(self, actor, league_id, patch):
        if not isinstance(actor, UserActor):
            raise TypeError('A verified UserActor is required')
        return self.update_for_legacy_commissioner(league_id, actor.user_id, patch)

    def update_for_legacy_commissioner(self, league_id, user_id, patch):
        return self.update_in_scope(league_id, patch, commissioner_id=user_id)

    def update_for_job(self, league_id, patch):
        """Existing trusted update; HTTP cannot select this path via input."""
        return self.update_in_scope(league_id, patch)

    def update_in_scope(self, league_id, patch, commissioner_id=None):
        # Preserve separate read and write scopes; write rechecks authority.
        with self.engine.begin() as conn:
            current = self.repository.current_for_update(conn, league_id)
        if not current:
            raise ValueError(f'League {league_id} not found')
        if commissioner_id is not None and current['commissioner'] != commissioner_id:
            raise PermissionError('Only the commissioner can perform this action')
        allowed_fields = {'name', 'numPlayers', 'status', 'settings', 'draftDate',
                          'tradeDeadline', 'freeAgentDeadline'}
        patch = dict(patch)
        if 'settings' in patch:
            if not isinstance(patch['settings'], dict):
                raise ValueError('League settings must be an object')
            patch['settings'] = settings_for_update(current['sport'], current.get('settings'), patch['settings'])
            tz_name = get_timezone_name_from_settings(patch['settings'])
            if tz_name:
                validate_timezone_name(tz_name)
        payload = {}
        for key, value in patch.items():
            if key not in allowed_fields:
                continue
            if key == 'settings' and isinstance(value, (dict, list)):
                value = json.dumps(value)
            payload[key] = value
        if not payload:
            raise ValueError('No valid fields to update')
        with self.engine.begin() as conn:
            updated = self.repository.update_fields(conn, league_id, payload, commissioner_id)
        if not updated:
            if commissioner_id is not None:
                raise PermissionError('Only the commissioner can perform this action')
            raise RuntimeError('Failed to update League')
        return updated
