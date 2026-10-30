import time
import traceback
from typing import Optional, Tuple


from endpoints.draft.pick_service import DraftPickService
from endpoints.draft.pick_repository import DraftPickRepository
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
    row = DraftPickRepository().next_timeout_deadline(conn).fetchone()

    if not row:
        return None

    league_id = int(row._mapping["leagueId"])
    secs = float(row._mapping["secondsUntilDeadline"] or 0.0)
    return league_id, secs


def run():
    service = DraftPickService(engine)

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
            action = service.process_timeout_for_job(league_id)

            # action may be None if it became unexpired / was picked manually meanwhile
            # Existing timeout publication remains inside the service transaction.

            # Tiny pause to avoid tight loop if multiple expirations are at same instant
            time.sleep(MIN_SLEEP_SECONDS)

        except Exception:
            print("Draft timeout worker error:")
            traceback.print_exc()
            time.sleep(2)


if __name__ == "__main__":
    run()