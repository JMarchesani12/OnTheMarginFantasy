from datetime import datetime
from typing import Any, Dict


class ESPNParser:
    """
    Converts ESPN JSON into your app's unified game format.

    IMPORTANT:
    Replace example field lookups ("events", "date", "home", "away")
    once you paste actual ESPN JSON.
    """

    def parse_raw_games(self, json_data: dict) -> list:
        # TODO: Replace "events" with actual ESPN key
        return json_data.get("events", [])

    def parse_game_date(self, raw_game: Dict[str, Any]) -> datetime:
        # TODO: Replace "date" with the actual field path
        date_str = raw_game.get("date")

        if not date_str:
            raise ValueError("Missing 'date' in ESPN game object")

        # Convert Z → +00:00 if needed
        if date_str.endswith("Z"):
            date_str = date_str.replace("Z", "+00:00")

        return datetime.fromisoformat(date_str)

    def map_game(self, raw_game: Dict[str, Any], my_team_external_id: str) -> Dict[str, Any]:
        """
        Convert ESPN JSON to your Sicko Basketball format.
        """
        game_date = self.parse_game_date(raw_game)

        # TODO: Replace these with real ESPN structure
        home = raw_game.get("home", {})
        away = raw_game.get("away", {})

        home_id = str(home.get("id", ""))
        away_id = str(away.get("id", ""))

        home_name = home.get("name", "Home")
        away_name = away.get("name", "Away")

        home_score = home.get("score")
        away_score = away.get("score")

        if home_id == my_team_external_id:
            my_side = "home"
            opp_id = away_id
            opp_name = away_name
        else:
            my_side = "away"
            opp_id = home_id
            opp_name = home_name

        return {
            "gameId": raw_game.get("id"),  # TODO adjust
            "date": game_date.isoformat(),
            "myTeamExternalId": my_team_external_id,
            "myTeamSide": my_side,
            "opponentExternalId": opp_id,
            "opponentName": opp_name,
            "homeScore": home_score,
            "awayScore": away_score
        }
