"""Retry-safe weekly progress using existing durable week/transaction statuses."""
from datetime import datetime, timezone
from utils.ownership import lock_ownership
from .weekly_repository import WeeklyCompletionRepository


class WeeklyCompletionService:
    def __init__(self, engine, scoring, transactions, repository=None):
        self.engine=engine
        self.scoring=scoring
        self.transactions=transactions
        self.repository=repository if repository is not None else WeeklyCompletionRepository()

    def run(self, now=None):
        now=now if now is not None else datetime.now(timezone.utc)
        report={'closed':[],'applied':[],'blocked':[],'failures':[]}
        with self.engine.begin() as conn:
            leagues=self.repository.candidates(conn,now)
        for league_id in leagues:
            while True:
                try:
                    # One committed action per step; every retry rechecks all state.
                    with self.engine.begin() as conn:
                        lock_ownership(conn,league_id)
                        outcome=self._step(conn,league_id,now)
                except Exception as exc:
                    # Do not log exception text: it may contain SQL/row payloads.
                    report['failures'].append({'leagueId':league_id,'category':type(exc).__name__})
                    break
                kind,detail=outcome
                if kind in ('closed','applied'):
                    report[kind].append(detail)
                else:
                    if kind=='blocked':report['blocked'].append({'leagueId':league_id,**detail})
                    break
        return report

    def _step(self, conn, league_id, now):
        weeks=self.repository.periods(conn,league_id,now)
        pending=self.repository.pending(conn,league_id)
        by_id={week['id']:week for week in weeks}
        by_number={week['weekNumber']:week for week in weeks}
        for tx in pending:
            if tx['weekId'] not in by_id:
                return 'blocked',{'transactionId':tx['id'],'reason':'missing_target'}
        for index,week in enumerate(weeks):
            transactions=[tx for tx in pending if tx['weekId']==week['id']]
            if week['scoringComplete']:
                if transactions:
                    return 'blocked',{'transactionId':transactions[0]['id'],'reason':'target_already_scored'}
                continue
            predecessor=by_number.get(week['weekNumber']-1)
            if predecessor is None and (index>0 or week['weekNumber'] not in (0,1)):
                return 'blocked',{'weekId':week['id'],'reason':'missing_predecessor'}
            if predecessor is not None and not predecessor['scoringComplete']:
                return 'idle',None
            if transactions:
                if predecessor is None:
                    return 'blocked',{'transactionId':transactions[0]['id'],'reason':'missing_predecessor'}
                tx=transactions[0]
                self.transactions.apply_pending_for_job(tx['id'],conn=conn)
                return 'applied',tx['id']
            if week['ended']:
                self.scoring.compute_weekly_scores_for_job(league_id,week['weekNumber'],conn=conn)
                next_week=by_number.get(week['weekNumber']+1)
                self.repository.close(conn,league_id,week['id'],next_week['id'] if next_week else None)
                return 'closed',week['id']
            return 'idle',None
        return 'idle',None
