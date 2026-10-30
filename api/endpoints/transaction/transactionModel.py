import json
from contextlib import contextmanager
from typing import Any, Dict, List, Optional

from sqlalchemy.engine import Engine
from utils.authorization import require_owned_league_member
from endpoints.league.leagueModel import LeagueModel
from .service import TransactionService
from .contracts import TradeRejected, TransactionNotFound, TransactionAccessDenied


from .workflow_service import TransactionWorkflowService


class TransactionModel(TransactionWorkflowService):
    """SQL-free legacy facade; constants/exception/helper identity is inherited."""
    def __init__(self, db: Engine):
        self.db = db
        self._transaction_service = TransactionService(db)
