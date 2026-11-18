"""Preview-first unused-calendar maintenance CLI; historical repairs are refused."""
import argparse
import json
from endpoints.schedule.read_service import ScheduleReadService
from endpoints.schedule.maintenance_service import CalendarMaintenanceService
from endpoints.scoring.service import ScoringService


def _compute_week_boundaries(schedule_model, league_id, season_year, conn=None):
    """Compatibility helper: same planner and season check as calendar generation."""
    supplied = {'conn':conn} if conn is not None else {}
    season = schedule_model.season_for_job(league_id,**supplied)
    if int(season['seasonYear']) != season_year:
        raise ValueError('League does not belong to requested season')
    return schedule_model.boundaries_for_job(league_id,**supplied)


def build_maintenance(engine):
    schedule = ScheduleReadService(engine)
    return CalendarMaintenanceService(engine,schedule,ScoringService(engine,schedule))


def _positive_int(value):
    parsed = int(value)
    if parsed<=0:raise argparse.ArgumentTypeError('must be a positive integer')
    return parsed


def main(argv=None, engine=None):
    parser = argparse.ArgumentParser(description='Preview calendar repairs; --apply permits unused Pre-Draft leagues only.',allow_abbrev=False)
    parser.add_argument('--season-year',type=_positive_int,required=True)
    parser.add_argument('--league-id',type=_positive_int,action='append',help='Repeat to select explicit league IDs in that season')
    parser.add_argument('--apply',action='store_true',help='Apply eligible unused repairs atomically; no history bypass')
    args = parser.parse_args(argv)
    try:
        if engine is None:
            from runtime import configured_engine
            engine = configured_engine()
        report = build_maintenance(engine).run(args.season_year,args.league_id,apply=args.apply)
    except Exception as exc:
        report = {'mode':'apply' if args.apply else 'preview','leagues':[],'scopeErrors':[],
                  'failures':[{'leagueId':None,'stage':'startup','category':type(exc).__name__}]}
    print(json.dumps(report,sort_keys=True))
    return report


def exit_code(report):
    return int(bool(report['failures'] or report['scopeErrors'] or
                    (report['mode']=='apply' and any(row['outcome']=='blocked' for row in report['leagues']))))


if __name__ == '__main__':
    raise SystemExit(exit_code(main()))
