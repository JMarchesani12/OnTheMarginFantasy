"""Trusted calendar policy and original per-helper transaction boundaries.

No provider client, HTTP adapter, configured engine or compatibility-model imports.
Legacy method names remain inherited by ScheduleModel for helper overrides.
"""
import datetime as dt
import json
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo
from rules.tournamentRules import final_period
from .helpers.weekHelper import compute_weeks_from_start, partition_initial_partial_week
from .calendar_repository import ScheduleCalendarRepository

WEEKDAY_NUMBERS = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}

SPORT_WEEK_START_WEEKDAYS = {2: WEEKDAY_NUMBERS["tuesday"]}


class ScheduleCalendarService:
    def __init__(self, db, repository=None):
        self.db = db
        self._calendar_repository = repository if repository is not None else ScheduleCalendarRepository()

    @property
    def calendar_repository(self):
        repository = getattr(self, '_calendar_repository', None)
        if repository is None:
            repository = ScheduleCalendarRepository()
            self._calendar_repository = repository
        return repository

    def _get_league(self, league_id: int) -> Dict[str, Any]:
        
        with self.db.begin() as conn:
            row = self.calendar_repository.league(conn, {"leagueId": league_id}).fetchone()

        if not row:
            raise ValueError(f"League {league_id} not found")

        return dict(row._mapping)

    def _get_league_settings(self, league_id: int) -> Dict[str, Any]:
        league = self._get_league(league_id)
        settings = league.get("settings") or {}
        if isinstance(settings, str):
            settings = json.loads(settings)
        return settings or {}

    def get_league_timezone(self, league_id: int) -> dt.tzinfo:
        """Timezone capability for callers that compose schedule reads."""
        return self._get_league_timezone(league_id)

    def _get_league_timezone(self, league_id: int) -> dt.tzinfo:
        settings = self._get_league_settings(league_id)
        schedule_cfg = settings.get("schedule") or {}
        tz_name = (
            settings.get("timezone")
            or settings.get("timeZone")
            or schedule_cfg.get("timezone")
            or schedule_cfg.get("timeZone")
        )
        if not tz_name:
            return dt.timezone.utc
        try:
            return ZoneInfo(tz_name)
        except Exception:
            return dt.timezone.utc

    def _get_week_start_weekday(self, league_id: int) -> int:
        league = self._get_league(league_id)
        settings = league.get("settings") or {}
        if isinstance(settings, str):
            settings = json.loads(settings)

        schedule_cfg = settings.get("schedule") or {}
        configured = schedule_cfg.get("weekStartDay")
        if configured is None:
            configured = schedule_cfg.get("weekStartWeekday")

        if configured is None:
            return SPORT_WEEK_START_WEEKDAYS.get(int(league["sport"]), 0)

        if isinstance(configured, str):
            weekday = WEEKDAY_NUMBERS.get(configured.strip().lower())
            if weekday is not None:
                return weekday
        elif isinstance(configured, int) and not isinstance(configured, bool):
            if 0 <= configured <= 6:
                return configured

        raise ValueError(
            "League settings.schedule.weekStartDay must be a weekday name "
            "or an integer from 0 (Monday) through 6 (Sunday)"
        )

    def _get_sport_season_for_league(self, league_id: int) -> Dict[str, Any]:
        

        with self.db.begin() as conn:
            row = self.calendar_repository.season_for_league(conn, {"leagueId": league_id}).mappings().first()
            if not row:
                raise ValueError(
                    "No SportSeason found for this league's sport + seasonYear. "
                    "Make sure SportSeason exists."
                )

            subdivision_rows = self.calendar_repository.subdivisions(conn, {"sportSeasonId": row["sportSeasonId"]}).mappings().all()

        season = dict(row)
        settings = season.pop("settings") or {}
        if isinstance(settings, str):
            settings = json.loads(settings)
        schedule_cfg = settings.get("schedule") or {}
        configured_code = settings.get("subdivision") or schedule_cfg.get("subdivision")

        if not subdivision_rows:
            raise ValueError(
                f"SportSeason {season['sportSeasonId']} has no subdivision windows"
            )

        normalized_code = str(configured_code).strip().upper() if configured_code else None
        use_all_subdivisions = normalized_code == "ALL" or (
            normalized_code is None and len(subdivision_rows) > 1
        )

        subdivision = None
        if use_all_subdivisions:
            postseason_starts = [
                item["postseasonStart"]
                for item in subdivision_rows
                if item["postseasonStart"] is not None
            ]
            postseason_ends = [
                item["postseasonEnd"]
                for item in subdivision_rows
                if item["postseasonEnd"] is not None
            ]
            subdivision = {
                "sportSeasonSubdivisionId": None,
                "subdivisionCode": "ALL",
                "subdivisionName": "All Subdivisions",
                "regularSeasonStart": min(
                    item["regularSeasonStart"] for item in subdivision_rows
                ),
                "regularSeasonEnd": max(
                    item["regularSeasonEnd"] for item in subdivision_rows
                ),
                "postseasonStart": min(postseason_starts) if postseason_starts else None,
                "postseasonEnd": max(postseason_ends) if postseason_ends else None,
                "allSubdivisions": True,
            }
        elif normalized_code:
            subdivision = next(
                (
                    item
                    for item in subdivision_rows
                    if str(item["subdivisionCode"]).upper() == normalized_code
                ),
                None,
            )
            if subdivision is None:
                available = ", ".join(row["subdivisionCode"] for row in subdivision_rows)
                raise ValueError(
                    f"Subdivision {normalized_code!r} is not configured for league {league_id}. "
                    f"Available subdivisions: {available or 'none'}, ALL"
                )
        elif len(subdivision_rows) == 1:
            subdivision = subdivision_rows[0]
        season.update(dict(subdivision))
        season.setdefault("allSubdivisions", False)
        return season

    def _get_existing_weeks(self, league_id: int) -> List[Dict[str, Any]]:
        
        with self.db.begin() as conn:
            rows = self.calendar_repository.weeks_for_league(conn, {"leagueId": league_id}).fetchall()
        return [dict(r._mapping) for r in rows]

    def _insert_week0(self, league_id: int, start_dt, end_dt) -> Dict[str, Any]:
        with self.db.begin() as conn:
            row = self.calendar_repository.insert_week_zero(conn, {"leagueId": league_id, "startDate": start_dt, "endDate": end_dt}).mappings().first()
        return dict(row)

    def _insert_weeks(
        self,
        league_id: int,
        weeks: List[tuple[dt.date, dt.date]],
        starting_week_number: int = 1,
        tzinfo: Optional[dt.tzinfo] = None,
    ) -> List[Dict[str, Any]]:
        if not weeks:
            return []

        

        created: List[Dict[str, Any]] = []

        with self.db.begin() as conn:
            for idx, (start_d, end_d) in enumerate(weeks, start=starting_week_number):
                if tzinfo is None:
                    start_dt = dt.datetime.combine(start_d, dt.time.min, tzinfo=dt.timezone.utc)
                    end_dt = dt.datetime.combine(end_d, dt.time.max, tzinfo=dt.timezone.utc)
                else:
                    start_local = dt.datetime.combine(start_d, dt.time.min, tzinfo=tzinfo)
                    end_local = dt.datetime.combine(end_d, dt.time.max, tzinfo=tzinfo)
                    start_dt = start_local.astimezone(dt.timezone.utc)
                    end_dt = end_local.astimezone(dt.timezone.utc)

                row = self.calendar_repository.insert_week(conn, {
                        "leagueId": league_id,
                        "weekNumber": idx,
                        "startDate": start_dt,
                        "endDate": end_dt,
                    }).fetchone()
                created.append(dict(row._mapping))

        print(f"Inserted {len(created)} weeks for league {league_id} (starting_week_number={starting_week_number})")
        return created

    def ensure_weeks_for_league(self, league_id: int) -> List[Dict[str, Any]]:
        """
        If Week rows already exist for this league, returns them.

        Otherwise:
          - Uses the league's subdivision window(s) to build weeks:
              Basketball folds the opening window into Week 1; other sports
              keep Week 0 for any partial opening week.
              Week 1+ use the sport's full week boundary through regEnd
          - A single subdivision appends its postseason range.
          - Multiple subdivisions use one continuous window through the latest
            postseason end so their overlapping phases do not duplicate weeks.
        """
        existing = self._get_existing_weeks(league_id)
        if existing:
            return existing
        local_tz, week0_start, week0_end, ranges = self._get_league_week_ranges(league_id)
        created = []
        if week0_start is not None:
            created.append(self._insert_week0(league_id, week0_start, week0_end))
        created.extend(self._insert_weeks(league_id, ranges, starting_week_number=1, tzinfo=local_tz))
        return created

    def _get_league_week_ranges(self, league_id):
        season = self._get_sport_season_for_league(league_id)
        local_tz = self._get_league_timezone(league_id)
        week_start_weekday = self._get_week_start_weekday(league_id)

        merged_final = final_period(self._get_season_phases(season['sportSeasonId']), local_tz)
        # Regular season weeks (season dates are timezone-agnostic)
        reg_start_date = season["regularSeasonStart"]
        reg_end_date = season["regularSeasonEnd"]
        if season["allSubdivisions"] and season.get("postseasonEnd"):
            reg_end_date = max(reg_end_date, season["postseasonEnd"])

        if merged_final:
            reg_end_date = merged_final[0] - dt.timedelta(days=1)

        all_regular_week_ranges = compute_weeks_from_start(
            reg_start_date,
            reg_end_date,
            week_start_weekday=week_start_weekday,
        )
        opening_partial_week, regular_week_ranges = partition_initial_partial_week(
            all_regular_week_ranges,
            week_start_weekday,
        )

        week0_end_date = opening_partial_week[1] if opening_partial_week else reg_start_date - dt.timedelta(days=1)
        week0_end = dt.datetime.combine(week0_end_date, dt.time.max, tzinfo=local_tz)
        week0_start = week0_end + dt.timedelta(microseconds=1) - dt.timedelta(days=7)
        ranges = list(regular_week_ranges)
        if merged_final:
            ranges.append(merged_final)
        elif not season['allSubdivisions'] and season.get('postseasonStart') and season.get('postseasonEnd'):
            ranges.extend(compute_weeks_from_start(
                season['postseasonStart'], season['postseasonEnd'], week_start_weekday=week_start_weekday))
        if season.get('sportId') == 1:
            # Include early games in Week 1 without shifting any later weeks.
            # Retain the former opening window, including when the configured
            # season begins on a full week boundary.
            if ranges:
                ranges[0] = (week0_start.date(), ranges[0][1])
            elif opening_partial_week:
                ranges = [(week0_start.date(), opening_partial_week[1])]
            return local_tz, None, None, ranges
        return local_tz, week0_start.astimezone(dt.timezone.utc), week0_end.astimezone(dt.timezone.utc), ranges

    def get_week_boundaries(self, league_id):
        """Shared, read-only week plan for new leagues and deliberate rebuilds."""
        local_tz, week0_start, week0_end, ranges = self._get_league_week_ranges(league_id)
        opening = [(0, week0_start, week0_end)] if week0_start is not None else []
        return opening + [
            (number,
             dt.datetime.combine(start, dt.time.min, tzinfo=local_tz).astimezone(dt.timezone.utc),
             dt.datetime.combine(end, dt.time.max, tzinfo=local_tz).astimezone(dt.timezone.utc))
            for number, (start, end) in enumerate(ranges, start=1)
        ]

    def _get_season_phases(self, sport_season_id):
        with self.db.begin() as conn:
            return [dict(r) for r in self.calendar_repository.season_phases(conn, {"season": sport_season_id}).mappings().all()]

    def ensure_weeks_for_job(self, league_id):
        return self.ensure_weeks_for_league(league_id)

    def boundaries_for_job(self, league_id):
        return self.get_week_boundaries(league_id)

    def timezone_for_job(self, league_id):
        return self.get_league_timezone(league_id)
