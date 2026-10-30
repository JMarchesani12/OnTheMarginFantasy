"""Transaction use cases and connection ownership, independent of transport."""
from actors import UserActor
from .contracts import TransactionAccessDenied, TransactionNotFound, TradeRejected
from .repository import TransactionRepository


class TransactionService:
    def __init__(self, engine, repository=None):
        self.engine = engine
        self.repository = repository if repository is not None else TransactionRepository()

    def list_transactions(self, actor: UserActor, league_id: int, status=None):
        if not isinstance(actor, UserActor):
            raise TypeError('A verified UserActor is required')
        return self.list_transactions_for_legacy_reader(actor.user_id, league_id, status)

    def list_transactions_for_legacy_reader(self, user_id: int, league_id: int, status=None):
        """Compatibility bridge for existing verified-ID callers, never a job flag."""
        if isinstance(user_id, bool) or not isinstance(user_id, int):
            raise TypeError('A verified integer reader is required')
        with self.engine.connect() as conn:
            if not self.repository.league_read_allowed(conn, league_id, user_id):
                raise TransactionAccessDenied('League not found')
            return self.repository.list_transactions(conn, league_id, status, user_id)

    def list_transactions_for_job(self, league_id: int, status=None):
        with self.engine.connect() as conn:
            return self.repository.list_transactions(conn, league_id, status)

    def assert_trade_deadline_in_transaction(self, conn, league_id: int):
        past = self.repository.past_trade_deadline(conn, league_id)
        if past is None:
            raise TransactionNotFound(f'League {league_id} not found')
        if past:
            raise TradeRejected('Trade deadline has passed')

    def validate_trade_in_transaction(self, conn, league_id, week_number,
                                      from_member_id, to_member_id,
                                      from_team_ids, to_team_ids):
        ownership = self.repository.trade_ownership(conn, league_id, week_number,
                                                   from_team_ids, to_team_ids)
        for member_id, team_ids in ((from_member_id, from_team_ids), (to_member_id, to_team_ids)):
            for team_id in team_ids:
                if ownership.get(team_id) != member_id:
                    raise TradeRejected(f'Member {member_id} does not own team {team_id}')
        # Preserve query order and existing conference semantics during extraction.
        from_counts = self.repository.conference_counts(conn, league_id, week_number, from_member_id, from_team_ids)
        to_counts = self.repository.conference_counts(conn, league_id, week_number, to_member_id, to_team_ids)
        from_incoming = self.repository.incoming_confs(conn, to_team_ids)
        to_incoming = self.repository.incoming_confs(conn, from_team_ids)
        limits = self.repository.conference_limits(conn)
        for conf_id, add in from_incoming.items():
            if from_counts.get(conf_id, 0) + add > limits.get(conf_id, 999):
                raise TradeRejected('Conference limit exceeded for proposing member')
        for conf_id, add in to_incoming.items():
            if to_counts.get(conf_id, 0) + add > limits.get(conf_id, 999):
                raise TradeRejected('Conference limit exceeded for receiving member')

    def apply_trade_for_job(self, transaction_id: int) -> None:
        with self.engine.begin() as conn:
            tx = self.repository.lock_trade(conn, transaction_id)
            if tx is None:
                raise TransactionNotFound('Transaction not found')
            if tx['type'] != 'TRADE':
                raise TradeRejected('Not a trade transaction')
            if tx['status'] != 'PENDING_APPLY':
                raise TradeRejected('Transaction is not pending apply')
            self.assert_trade_deadline_in_transaction(conn, tx['leagueId'])
            week = self.repository.trade_week(conn, tx['leagueId'], tx['weekId'])
            if week is None:
                raise TransactionNotFound('Week not found for league')
            self.validate_trade_in_transaction(conn, tx['leagueId'], week['weekNumber'],
                                               tx['memberFromId'], tx['memberToId'],
                                               tx['fromTeamIds'], tx['toTeamIds'])
            self.repository.transfer_ownership(conn, tx['leagueId'], week['weekNumber'],
                                               tx['memberFromId'], tx['memberToId'],
                                               tx['fromTeamIds'], tx['toTeamIds'])
            self.repository.mark_trade_completed(conn, transaction_id)
