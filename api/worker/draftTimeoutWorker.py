import threading
import signal
from operations import safe_event, run_id
from typing import Optional, Tuple


from endpoints.draft.pick_service import DraftPickService
from endpoints.draft.pick_repository import DraftPickRepository


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


def run(engine=None, stop_event=None):
    if engine is None:
        from runtime import configured_engine
        engine = configured_engine()
    stop_event = stop_event if stop_event is not None else threading.Event()
    identity = run_id()
    safe_event('timeout', 'started', identity)
    service = DraftPickService(engine)

    while not stop_event.is_set():
        try:
            with engine.begin() as conn:
                nxt = _get_next_expired_or_soonest_deadline(conn)

            if stop_event.is_set():break

            if not nxt:
                # No live drafts with a clock running
                stop_event.wait(MAX_SLEEP_SECONDS)
                continue

            league_id, seconds_until_deadline = nxt

            if seconds_until_deadline > 0:
                # Sleep until the soonest deadline (bounded)
                sleep_for = max(MIN_SLEEP_SECONDS, min(MAX_SLEEP_SECONDS, seconds_until_deadline))
                stop_event.wait(sleep_for)
                continue

            # If we're here, it's expired now (or overdue): process it
            action = service.process_timeout_for_job(league_id)

            # action may be None if it became unexpired / was picked manually meanwhile
            # Existing timeout publication remains inside the service transaction.

            # Tiny pause to avoid tight loop if multiple expirations are at same instant
            stop_event.wait(MIN_SLEEP_SECONDS)

        except Exception as exc:
            safe_event('timeout', 'failed', identity, category=exc)
            stop_event.wait(2)
    safe_event('timeout','stopped',identity)


def main():
    stop = threading.Event()
    previous = {}
    def halt(signum, frame): stop.set()
    try:
        for sig in (signal.SIGTERM, signal.SIGINT):
            previous[sig] = signal.signal(sig, halt)
        run(stop_event=stop)
    except Exception as exc:
        safe_event('timeout','failed',run_id(),category=exc)
        raise SystemExit(1) from None
    finally:
        for sig, handler in previous.items(): signal.signal(sig, handler)


if __name__ == "__main__":
    main()
