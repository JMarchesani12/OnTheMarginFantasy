import json
from sqlalchemy import text

DRAFT_NOTIFY_CHANNEL = "draft_updated"

def notify_draft_updated(conn, league_id: int, reason: str) -> None:
    payload = json.dumps({"leagueId": league_id, "reason": reason})
    conn.execute(
        text("SELECT pg_notify(:channel, :payload)"),
        {"channel": DRAFT_NOTIFY_CHANNEL, "payload": payload},
    )
