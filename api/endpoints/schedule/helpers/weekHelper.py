import datetime as dt
from typing import List, Tuple


def compute_weeks_from_start(
    first_week_start: dt.date,
    last_game_date: dt.date,
) -> List[Tuple[dt.date, dt.date]]:
    """
    Build week ranges from an explicit first-week start date to the last game date.

    Week 1:
      - starts at first_week_start (could be Thu, Sun, etc.)
      - ends at the upcoming Sunday, or last_game_date, whichever is earlier

    Week 2+:
      - start Monday
      - end Sunday, capped at last_game_date
    """
    if first_week_start > last_game_date:
        return []

    weeks: List[Tuple[dt.date, dt.date]] = []

    # Week 1 (partial is allowed)
    first_weekday = first_week_start.weekday()  # Monday=0 .. Sunday=6
    days_until_sunday = 6 - first_weekday
    week1_end_candidate = first_week_start + dt.timedelta(days=days_until_sunday)
    week1_end = min(week1_end_candidate, last_game_date)
    weeks.append((first_week_start, week1_end))

    # Week 2+ (Mon–Sun)
    cur_start = week1_end + dt.timedelta(days=1)
    while cur_start <= last_game_date:
        cur_end_candidate = cur_start + dt.timedelta(days=6)
        cur_end = min(cur_end_candidate, last_game_date)
        weeks.append((cur_start, cur_end))
        cur_start = cur_end + dt.timedelta(days=1)

    return weeks
