"""Preview-first unused-calendar repair; no historical rescore or remapping."""
from datetime import datetime, timezone
import json
from rules.leagueRules import LEGACY_VERSION
from utils.ownership import lock_ownership
from .maintenance_repository import CalendarMaintenanceRepository


def _datetime(value):
    if value is None:
        return None
    stamp = datetime.fromisoformat(value) if isinstance(value,str) else value
    return stamp.replace(tzinfo=timezone.utc) if stamp.tzinfo is None else stamp.astimezone(timezone.utc)


def _bounds(start, end):
    return {'startDate':_datetime(start).isoformat() if start is not None else None,
            'endDate':_datetime(end).isoformat() if end is not None else None}


class CalendarMaintenanceService:
    def __init__(self, engine, schedule, scoring, repository=None):
        self.engine = engine
        self.schedule = schedule
        self.scoring = scoring
        self.repository = repository if repository is not None else CalendarMaintenanceRepository()

    def run(self, season_year, league_ids=None, apply=False, now=None):
        now = now if now is not None else datetime.now(timezone.utc)
        report = {'mode':'apply' if apply else 'preview','leagues':[],'scopeErrors':[],'failures':[]}
        try:
            if type(season_year) is not int or season_year<=0 or (league_ids is not None and any(type(i) is not int or i<=0 for i in league_ids)):
                raise ValueError('Invalid maintenance scope')
            with self.engine.begin() as conn:
                ids, report['scopeErrors'] = self.repository.discover(conn,season_year,league_ids)
        except Exception as exc:
            report['failures'].append({'leagueId':None,'stage':'discovery','category':type(exc).__name__})
            return report
        for league_id in ids:
            try:
                with self.engine.begin() as conn:
                    if apply:
                        result = self.apply_in_transaction(conn,league_id,season_year,now)
                    else:
                        result = {'leagueId':league_id,'outcome':'preview','plan':self.preview_in_transaction(conn,league_id,season_year)}
            except Exception as exc:
                report['failures'].append({'leagueId':league_id,'stage':'apply' if apply else 'preview','category':type(exc).__name__})
            else:
                report['leagues'].append(result)
        return report

    def _context(self, conn, league_id, year, lock=False):
        league = self.repository.league(conn,league_id,lock=lock)
        if league is None or league['seasonYear'] != year:
            raise ValueError('Maintenance scope changed')
        return league

    def preview_in_transaction(self, conn, league_id, year, lock=False, expected_sport=None):
        # Existing draft controls lock DraftState before League without ownership.
        # Never acquire a new state row while already holding the league lock.
        draft = self.repository.draft_state(conn,league_id,lock=lock)
        league = self._context(conn,league_id,year,lock=lock)
        if expected_sport is not None and league['sport'] != expected_sport:
            raise ValueError('Maintenance scope changed')
        state_changed = False
        if lock and draft is None:
            draft = self.repository.draft_state(conn,league_id)
            state_changed = draft is not None
        season = self.repository.season(conn,league['sport'],year)
        if season is None:
            raise ValueError('Missing season configuration')
        # All planning reads share this connection, including uncommitted settings.
        selected_season = self.schedule.season_for_job(league_id,conn=conn)
        if selected_season['sportSeasonId'] != season['id'] or selected_season['seasonYear'] != year:
            raise ValueError('Maintenance season changed')
        proposed = self.schedule.boundaries_for_job(league_id,conn=conn)
        numbers = [n for n,_,_ in proposed]
        if not numbers or any(type(n) is not int for n in numbers) or numbers[0] not in (0,1) or numbers != list(range(numbers[0],numbers[-1]+1)):
            raise ValueError('Invalid proposed calendar')
        previous_end = None
        for _,start,end in proposed:
            if start.tzinfo is None or end.tzinfo is None or start>end or (previous_end is not None and start<=previous_end):
                raise ValueError('Invalid proposed boundaries')
            previous_end = end
        weeks = self.repository.weeks(conn,league_id,lock=lock)
        if len({w['weekNumber'] for w in weeks}) != len(weeks):
            raise ValueError('Duplicate existing calendar periods')
        history = self.repository.histories(conn,league_id)
        reasons = ['draft_state_changed'] if state_changed else []
        if league['status'] != 'Pre-Draft':reasons.append('league_not_unused')
        if season['seasonFinalized']:reasons.append('season_finalized')
        if draft is not None and (draft['status']!='pre' or draft['currentOverallPickNumber']!=1 or draft['currentMemberId'] is not None or draft['expiresAt'] is not None or draft['lastPickAt'] is not None):reasons.append('draft_not_unused')
        if history['draftPicks']:reasons.append('draft_history')
        if history['ownership']:reasons.append('ownership_history')
        if history['transactions']:reasons.append('transaction_history')
        if history['scores']:reasons.append('score_history')
        if any(w['isLocked'] or w['scoringComplete'] for w in weeks):reasons.append('period_history')
        before = {w['weekNumber']:w for w in weeks}
        after = {n:_bounds(start,end) for n,start,end in proposed}
        periods = []
        for number in sorted(set(before)|set(after)):
            old = before.get(number)
            old_bounds = _bounds(old['startDate'],old['endDate']) if old is not None else None
            new_bounds = after.get(number)
            change = 'added' if old is None else 'removed' if new_bounds is None else 'kept' if old_bounds==new_bounds else 'changed'
            periods.append({'weekNumber':number,'weekId':old['id'] if old else None,'before':old_bounds,'after':new_bounds,'change':change})
        by_id = {p['weekId']:p for p in periods if p['weekId'] is not None}
        by_number = {p['weekNumber']:p for p in periods}
        def impact(period):
            if period is None:return 'outside_calendar'
            return {'removed':'period_removed','changed':'boundaries_changed','kept':'unchanged','added':'period_added'}[period['change']]
        ownership = [{**row,'acquiredImpact':impact(by_number.get(row['acquiredWeek'])),
                      'droppedImpact':impact(by_number.get(row['droppedWeek'])) if row['droppedWeek'] is not None else 'open_ended'} for row in history['ownership']]
        transactions = [{**row,'impact':impact(by_id.get(row['weekId']))} for row in history['transactions']]
        totals = {}
        for row in history['scores']:
            totals[row['memberId']] = totals.get(row['memberId'],0)+int(row['pointsAwarded'])
        settings = json.loads(league['settings']) if isinstance(league['settings'],str) else league['settings'] or {}
        return {'eligible':not reasons,'reasons':reasons,'periods':periods,'ownership':ownership,'transactions':transactions,
                'historyCounts':{'draftPicks':history['draftPicks'],'ownership':len(ownership),'transactions':len(transactions),'scores':len(history['scores'])},
                'scoreTotals':[{'memberId':member,'pointsAwarded':total} for member,total in sorted(totals.items())],
                'scoringInputs':{'ruleSetVersion':settings.get('ruleSetVersion',LEGACY_VERSION),'tiers':'current','games':'current','snapshots':False}}

    def apply_in_transaction(self, conn, league_id, year, now):
        hint = self._context(conn,league_id,year)
        season = self.repository.season(conn,hint['sport'],year,lock=True)
        if season is None:raise ValueError('Missing season configuration')
        lock_ownership(conn,league_id)
        plan = self.preview_in_transaction(conn,league_id,year,lock=True,expected_sport=hint['sport'])
        if not plan['eligible']:
            return {'leagueId':league_id,'outcome':'blocked','plan':plan}
        ids = {}
        for period in plan['periods']:
            number,week_id = period['weekNumber'],period['weekId']
            if period['change']=='removed':
                self.repository.delete_unreferenced_week(conn,league_id,week_id)
                continue
            start,end = (_datetime(period['after'][field]) for field in ('startDate','endDate'))
            if week_id is None:
                week_id = self.repository.insert_week(conn,league_id,number,start,end)
            elif period['change']=='changed':
                self.repository.update_week(conn,league_id,week_id,start,end)
            ids[number] = week_id
        scored = []
        for period in plan['periods']:
            if period['after'] is None or _datetime(period['after']['endDate'])>=now:continue
            number = period['weekNumber']
            self.scoring.compute_weekly_scores_for_job(league_id,number,conn=conn)
            self.repository.close_week(conn,league_id,ids[number],ids.get(number+1))
            scored.append(ids[number])
        return {'leagueId':league_id,'outcome':'applied','plan':plan,'weekIds':[ids[n] for n in sorted(ids)],'scoredWeekIds':scored}
