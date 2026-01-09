import time
import traceback
from typing import Optional, Tuple

from sqlalchemy import text

from endpoints.draft.draftModel import DraftModel
from db import engine


# Safety bounds: never sleep longer than this without re-checking (handles config changes)
MAX_SLEEP_SECONDS = 30
MIN_SLEEP_SECONDS = 0.5


def _get_next_expired_or_soonest_deadline(conn) -> Optional[Tuple[int, float]]:
    """
    Returns:
      (league_id, seconds_until_deadline)
    Where deadline = expiresAt + graceSeconds.
    If already expired, seconds_until_deadline will be <= 0.
    """
    row = conn.execute(
        text("""
            SELECT
                ds."leagueId" AS "leagueId",
                EXTRACT(EPOCH FROM (
                    (ds."expiresAt" + ((l.settings->'draft'->>'graceSeconds') || ' seconds')::interval)
                    - now()
                )) AS "secondsUntilDeadline"
            FROM "DraftState" ds
            JOIN "League" l ON l.id = ds."leagueId"
            WHERE ds.status = 'live'
              AND ds."expiresAt" IS NOT NULL
            ORDER BY (ds."expiresAt" + ((l.settings->'draft'->>'graceSeconds') || ' seconds')::interval) ASC
            LIMIT 1
        """)
    ).fetchone()

    if not row:
        return None

    league_id = int(row._mapping["leagueId"])
    secs = float(row._mapping["secondsUntilDeadline"] or 0.0)
    return league_id, secs


def run():
    model = DraftModel(engine)

    while True:
        try:
            with engine.begin() as conn:
                nxt = _get_next_expired_or_soonest_deadline(conn)

            if not nxt:
                # No live drafts with a clock running
                time.sleep(MAX_SLEEP_SECONDS)
                continue

            league_id, seconds_until_deadline = nxt

            if seconds_until_deadline > 0:
                # Sleep until the soonest deadline (bounded)
                sleep_for = max(MIN_SLEEP_SECONDS, min(MAX_SLEEP_SECONDS, seconds_until_deadline))
                time.sleep(sleep_for)
                continue

            # If we're here, it's expired now (or overdue): process it
            action = model.process_expired_pick_if_needed(league_id)

            # action may be None if it became unexpired / was picked manually meanwhile
            # Broadcasting will be triggered by pg_notify inside process_expired_pick_if_needed
            # (assuming you added self._notify_draft_updated calls in there).
            # No socket code needed here.

            # Tiny pause to avoid tight loop if multiple expirations are at same instant
            time.sleep(MIN_SLEEP_SECONDS)

        except Exception:
            print("Draft timeout worker error:")
            traceback.print_exc()
            time.sleep(2)


if __name__ == "__main__":
    run()