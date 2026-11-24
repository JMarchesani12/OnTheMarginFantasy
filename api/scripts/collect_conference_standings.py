"""Inspect automatic standings collection; --apply persists validated snapshots."""
import argparse
import json
from operations import job_gate
from endpoints.scoring.standings_service import ConferenceStandingsService


def main(argv=None, engine=None):
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument('--sport-season-id',type=int,required=True)
    parser.add_argument('--apply',action='store_true')
    args = parser.parse_args(argv)
    if args.sport_season_id <= 0:
        parser.error('sport-season-id must be positive')
    try:
        if engine is None:
            from runtime import configured_engine
            engine = configured_engine()
        # Same gate as automatic collection; an inspection never cancels a job.
        with job_gate(engine,'ingest') as gate:
            if not gate:
                result={'outcome':'already_running'}
            else:
                gate.check()
                result=ConferenceStandingsService(engine).collect_for_job(args.sport_season_id,apply=args.apply)
                gate.check()
    except Exception as exc:
        result={'failures':[{'category':type(exc).__name__}]}
    print(json.dumps(result,sort_keys=True))
    return result


if __name__=='__main__':
    result=main()
    raise SystemExit(int(bool(result.get('failures') or (result.get('applied') and result.get('pending')))))
