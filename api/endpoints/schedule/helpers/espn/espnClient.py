import datetime as dt
import traceback
from typing import Any, Dict, List, Optional, Tuple

import requests


class ESPNClient:
    """
    Thin wrapper around the ESPN public API for a single sport.

    Assumptions:
    - base_url looks like: "https://site.web.api.espn.com/apis/v2/sports"
    - api_keyword is something like: "basketball/mens-college-basketball"
    - Scoreboard endpoint:
        {base_url}/{api_keyword}/scoreboard?dates=YYYYMMDD
    - Team schedule endpoint:
        {base_url}/{api_keyword}/teams/{teamId}/schedule

    There is no API token required, just GET requests.
    """

    def __init__(self, base_url: str, api_keyword: str, timeout: int = 10) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_keyword = api_keyword.strip("/")
        self.timeout = timeout

    # -------------------------------------------------------------------------
    # URL builders
    # -------------------------------------------------------------------------

    def _build_scoreboard_url(self, date_yyyymmdd: str) -> str:
        """
        Example:
          https://site.web.api.espn.com/apis/v2/sports/{api_keyword}/scoreboard?dates=20251206
        """
        return f"{self.base_url}/{self.api_keyword}/scoreboard?dates={date_yyyymmdd}"

    def _build_schedule_url(self, team_external_id: str) -> str:
        """
        Example:
          https://site.web.api.espn.com/apis/v2/sports/{api_keyword}/teams/{teamId}/schedule
        """
        return f"{self.base_url}/{self.api_keyword}/teams/{team_external_id}/schedule"

    # -------------------------------------------------------------------------
    # ISO date/time helpers
    # -------------------------------------------------------------------------

    @staticmethod
    def _parse_iso(dt_str: str) -> dt.datetime:
        """
        Parse an ESPN-style ISO timestamp, which usually ends in 'Z' (UTC).
        """
        if dt_str.endswith("Z"):
            dt_str = dt_str[:-1] + "+00:00"
        return dt.datetime.fromisoformat(dt_str)

    # -------------------------------------------------------------------------
    # Scoreboard / calendar
    # -------------------------------------------------------------------------

    def fetch_scoreboard_calendar(self, any_season_date: dt.date) -> Dict[str, Any]:
        """
        Call scoreboard for some date in the season and return the first league
        object, which holds calendar data.

        We assume there is at least one league for the sport and that the first
        one is the one we care about (true for NCAAM).
        """
        ymd = any_season_date.strftime("%Y%m%d")
        url = self._build_scoreboard_url(ymd)

        resp = requests.get(url, timeout=self.timeout)
        resp.raise_for_status()
        data = resp.json()

        leagues = data.get("leagues") or []
        if not leagues:
            raise RuntimeError("ESPN scoreboard: no leagues found in response")

        return leagues[0]

    def extract_calendar_dates(self, league_obj: Dict[str, Any]) -> List[dt.date]:
        """
        Convert league['calendar'] list of ISO strings into a sorted list of dates.
        """
        calendar = league_obj.get("calendar") or []
        dates: List[dt.date] = []

        for iso_str in calendar:
            d = self._parse_iso(iso_str).date()
            dates.append(d)

        return sorted(set(dates))

    def get_calendar_bounds(self, league_obj: Dict[str, Any]) -> Tuple[dt.date, dt.date]:
        """
        Returns (season_start_date, season_end_date) from an ESPN league object.

        Uses calendarStartDate/calendarEndDate if present, otherwise falls back
        to min/max of calendar[].
        """
        start_date: Optional[dt.date] = None
        end_date: Optional[dt.date] = None

        if "calendarStartDate" in league_obj:
            start_date = self._parse_iso(league_obj["calendarStartDate"]).date()
        if "calendarEndDate" in league_obj:
            end_date = self._parse_iso(league_obj["calendarEndDate"]).date()

        calendar = league_obj.get("calendar") or []
        if calendar:
            dates = [self._parse_iso(s).date() for s in calendar]
            if start_date is None:
                start_date = min(dates)
            if end_date is None:
                end_date = max(dates)

        if start_date is None or end_date is None:
            raise RuntimeError("Could not determine calendar start/end from ESPN response")

        return start_date, end_date

    # -------------------------------------------------------------------------
    # Team schedule
    # -------------------------------------------------------------------------

    def fetch_team_schedule(self, team_external_id: str) -> Dict[str, Any]:
        """
        Return the raw JSON for a single team's schedule.
        """
        url = self._build_schedule_url(team_external_id)
        resp = requests.get(url, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def iter_team_events(self, schedule_json: Dict[str, Any]):
        """
        Yield the "events" items from a schedule payload.
        """
        for event in schedule_json.get("events", []):
            yield event

    def fetch_scoreboard_for_date(self, datestr: str, group_id) -> Dict[str, Any]:
        """
        datestr: 'YYYYMMDD'
        """
        url = f"{self.base_url}/{self.api_keyword}/scoreboard"
        params = {"dates": datestr, "groups": group_id}
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        return resp.json()

    def extract_game_from_event(self, event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Map an ESPN schedule event into a simple dict:

        {
          "externalGameId": str,
          "date": datetime,
          "homeEspnId": str,
          "awayEspnId": str,
          "homeName": str,
          "awayName": str,
          "homeScore": int,
          "awayScore": int,
        }

        Score will usually be 0 for future games.
        """

        def _parse_score(raw) -> int:
            if raw is None or raw == "":
                return 0

            if isinstance(raw, (int, float)):
                return int(raw)

            if isinstance(raw, str):
                raw = raw.strip()
                # ESPN uses strings like "90"
                return int(raw) if raw.isdigit() else 0

            # some events return an object instead of a string
            if isinstance(raw, dict):
                # print once so you can see the schema you’re actually getting

                for k in ("value", "displayValue", "score"):
                    if k in raw and raw[k] is not None:
                        return _parse_score(raw[k])
                return 0

            return 0

        try:
            external_game_id = event["id"]
            event_dt = self._parse_iso(event["date"])

            competitions = event.get("competitions") or []
            if not competitions:
                return None
            comp = competitions[0]
            broadcast = comp.get("broadcast")
            if not broadcast:
                broadcasts = comp.get("broadcasts") or []
                if broadcasts and broadcasts[0].get("names"):
                    broadcast = broadcasts[0]["names"][0]

            competitors = comp.get("competitors") or []
            home = next((c for c in competitors if c.get("homeAway") == "home"), None)
            away = next((c for c in competitors if c.get("homeAway") == "away"), None)
            if not home or not away:
                return None

            def team_info(c: Dict[str, Any]):
                team = c.get("team") or {}
                espn_id = str(team.get("id"))
                name = team.get("displayName") or team.get("shortDisplayName") or ""
                score = _parse_score(c.get("score"))
                return espn_id, name, score

            home_id, home_name, home_score = team_info(home)
            away_id, away_name, away_score = team_info(away)

            return {
                "externalGameId": external_game_id,
                "date": event_dt,
                "homeEspnId": home_id,
                "awayEspnId": away_id,
                "homeName": home_name,
                "awayName": away_name,
                "homeScore": home_score,
                "awayScore": away_score,
                "broadcast": broadcast,
            }
        except Exception:
            print("extract_game_from_event FAILED for event.id =", event.get("id"))
            traceback.print_exc()
            return None
