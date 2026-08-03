import datetime as dt
from typing import List, Optional, Tuple


def compute_weeks_from_start(
    first_week_start: dt.date,
    last_game_date: dt.date,
    week_start_weekday: int = 0,
) -> List[Tuple[dt.date, dt.date]]:
    """
    Build week ranges from an explicit first-week start date to the last game date.

    Week 1:
      - starts at first_week_start (could be Thu, Sun, etc.)
      - ends the day before week_start_weekday, or at last_game_date

    Week 2+:
      - start on week_start_weekday
      - span seven days, capped at last_game_date

    Uses Python weekday numbering: Monday=0 through Sunday=6.
    """
    if not 0 <= week_start_weekday <= 6:
        raise ValueError("week_start_weekday must be between 0 and 6")

    if first_week_start > last_game_date:
        return []

    weeks: List[Tuple[dt.date, dt.date]] = []

    # Week 1 (partial is allowed)
    week_end_weekday = (week_start_weekday - 1) % 7
    days_until_week_end = (week_end_weekday - first_week_start.weekday()) % 7
    week1_end_candidate = first_week_start + dt.timedelta(days=days_until_week_end)
    week1_end = min(week1_end_candidate, last_game_date)
    weeks.append((first_week_start, week1_end))

    # Week 2+ are complete seven-day windows unless capped by last_game_date.
    cur_start = week1_end + dt.timedelta(days=1)
    while cur_start <= last_game_date:
        cur_end_candidate = cur_start + dt.timedelta(days=6)
        cur_end = min(cur_end_candidate, last_game_date)
        weeks.append((cur_start, cur_end))
        cur_start = cur_end + dt.timedelta(days=1)

    return weeks


def partition_initial_partial_week(
    weeks: List[Tuple[dt.date, dt.date]],
    week_start_weekday: int,
) -> Tuple[Optional[Tuple[dt.date, dt.date]], List[Tuple[dt.date, dt.date]]]:
    """Separate a partial opening range so scored weeks begin on a full boundary."""
    if not 0 <= week_start_weekday <= 6:
        raise ValueError("week_start_weekday must be between 0 and 6")

    if not weeks or weeks[0][0].weekday() == week_start_weekday:
        return None, weeks

    return weeks[0], weeks[1:]
