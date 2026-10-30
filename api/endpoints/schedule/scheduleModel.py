import datetime as dt
import json
import re
from typing import Any, Dict, List, Optional

from rules.leagueRules import resolve_rules, adjust_margin
from rules.tournamentRules import score_margin, select_phase, final_period
from sqlalchemy.engine import Engine
from .calendar_service import ScheduleCalendarService, WEEKDAY_NUMBERS, SPORT_WEEK_START_WEEKDAYS
from .read_service import ScheduleReadService
from zoneinfo import ZoneInfo

from endpoints.schedule.helpers.espn.espnClient import ESPNClient
from endpoints.schedule.helpers.bootstrapCheckpoint import (
    BootstrapCheckpoint, default_checkpoint_path, fingerprint,
)
from endpoints.schedule.helpers.weekHelper import (
    compute_weeks_from_start,
    partition_initial_partial_week,
)


# Basketball and future sports default to Monday. College football uses Tuesday.


from .ingestion_service import ScheduleIngestionService


class ScheduleModel(ScheduleIngestionService):
    """SQL-free compatibility facade preserving constructor/helper dispatch."""
    def __init__(self, db: Engine, espn_base_url: str) -> None:
        self.db = db
        self.espn_base_url = espn_base_url.rstrip("/")
