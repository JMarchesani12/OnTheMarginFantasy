"""Read boundary and scoped lifecycle orchestration; PostgreSQL locks tested natively."""
import unittest
from unittest.mock import MagicMock
from actors import UserActor
from endpoints.league.reads.service import LeagueReadService


class ReadOnlyBoundaryTests(unittest.TestCase):
    def test_reader_details_and_mine_do_not_synchronize_or_update(self):
        engine=MagicMock();repo=MagicMock();repo.details.return_value={'id':1};repo.own_leagues.return_value=[]
        reader=LeagueReadService(engine,repo)
        self.assertEqual(reader.details(UserActor(1,'a'),1),{'id':1})
        self.assertEqual(reader.mine(UserActor(1,'a')),[])
        self.assertEqual(repo.details.call_count,1);self.assertEqual(repo.own_leagues.call_count,1)
        engine.begin.assert_not_called()

    def test_supplied_connection_reads_reuse_connection_and_scope(self):
        engine=MagicMock();repo=MagicMock();conn=object();reader=LeagueReadService(engine,repo)
        reader.details_in_transaction(conn,2,1);reader.mine_in_transaction(conn,1,'ACTIVE',[2])
        repo.details.assert_called_once_with(conn,2,1)
        repo.own_leagues.assert_called_once_with(conn,1,'active',[2])
        engine.connect.assert_not_called();engine.begin.assert_not_called()

class ScopedQueriesTests(unittest.TestCase):
    def setup_service(self, candidates=(3,1,3), states=None, authorized=True):
        from endpoints.league.lifecycle.query_service import LeagueLifecycleQueryService
        engine=MagicMock();conn=engine.connect.return_value.__enter__.return_value
        conn.execution_options.return_value=conn
        repo=MagicMock();repo.candidate_ids.return_value=list(candidates)
        repo.lock_state.side_effect=lambda c,i:(states or {}).get(i,True)
        repo.lock_league.return_value=True;repo.state_exists.return_value=False;repo.authorized.return_value=authorized
        reader=MagicMock();reader.details_in_transaction.return_value={'id':1};reader.mine_in_transaction.return_value=[]
        return LeagueLifecycleQueryService(engine,repo,reader),engine,conn,repo,reader

    def test_candidate_lock_authorize_phase_read_commit_sequence(self):
        svc,engine,conn,repo,reader=self.setup_service()
        events=[]
        for name in ('candidate_ids','lock_state','lock_league','authorized','mark_pre_draft','mark_drafting','mark_post_draft','mark_in_season','mark_completed'):
            method=getattr(repo,name);old=method.side_effect;value=method.return_value
            method.side_effect=lambda *a,n=name,old=old,value=value,**kw:(events.append((n,a[1:])),old(*a,**kw) if old else value)[1]
        reader.mine_in_transaction.side_effect=lambda *a:events.append(('read',a[1:])) or []
        conn.begin.return_value.__exit__.side_effect=lambda *a:events.append(('commit',()))
        svc.mine(UserActor(2,'b'),'completed')
        self.assertEqual([e[0] for e in events],['candidate_ids','lock_state','lock_league','authorized','lock_state','lock_league','authorized','mark_pre_draft','mark_drafting','mark_post_draft','mark_in_season','mark_completed','read','commit'])
        self.assertEqual([events[i][1][0] for i in (1,4)],[1,3])
        reader.mine_in_transaction.assert_called_once_with(conn,2,'completed',[1,3])
        repo.mark_drafting.assert_called_once_with(conn,[1,3],2,True)
        conn.execution_options.assert_called_once_with(isolation_level='READ COMMITTED')

    def test_empty_denied_and_missing_have_no_updates(self):
        for candidates,auth,exists in [((),True,True),((1,),False,True),((1,),True,False)]:
            svc,engine,conn,repo,reader=self.setup_service(candidates,authorized=auth);repo.lock_league.return_value=exists
            self.assertIsNone(svc.details(UserActor(2,'b'),1))
            repo.mark_pre_draft.assert_not_called();reader.details_in_transaction.assert_not_called()
        svc,*_=self.setup_service()
        with self.assertRaises(TypeError):svc.mine(2)

    def test_first_state_appearance_restarts_once_then_conflicts(self):
        from endpoints.league.lifecycle.query_service import LifecycleRefreshConflict
        svc,engine,conn,repo,reader=self.setup_service((1,),states={1:False});repo.state_exists.side_effect=[True,False]
        self.assertEqual(svc.details(UserActor(2,'b'),1),{'id':1})
        self.assertEqual(repo.candidate_ids.call_count,2);repo.mark_completed.assert_called_once()
        svc,engine,conn,repo,reader=self.setup_service((1,),states={1:False});repo.state_exists.return_value=True
        with self.assertRaises(LifecycleRefreshConflict):svc.details(UserActor(2,'b'),1)
        self.assertEqual(repo.candidate_ids.call_count,2);repo.mark_pre_draft.assert_not_called()

    def test_failures_propagate_without_retry_or_return(self):
        for name in ('mark_pre_draft','mark_drafting','mark_post_draft','mark_in_season','mark_completed'):
            svc,engine,conn,repo,reader=self.setup_service();getattr(repo,name).side_effect=RuntimeError('phase')
            with self.assertRaises(RuntimeError):svc.mine(UserActor(2,'b'))
            self.assertEqual(repo.candidate_ids.call_count,1);reader.mine_in_transaction.assert_not_called()
        svc,engine,conn,repo,reader=self.setup_service();conn.begin.return_value.__exit__.side_effect=RuntimeError('commit')
        with self.assertRaises(RuntimeError):svc.mine(UserActor(2,'b'))
        svc,engine,conn,repo,reader=self.setup_service();reader.mine_in_transaction.side_effect=RuntimeError('read')
        with self.assertRaises(RuntimeError):svc.mine(UserActor(2,'b'))

    def test_removed_members_are_excluded_before_phases(self):
        svc,engine,conn,repo,reader=self.setup_service((1,2));repo.authorized.side_effect=[False,True]
        svc.mine(UserActor(2,'b'),'active');repo.mark_pre_draft.assert_called_once_with(conn,[2],2,True)
        reader.mine_in_transaction.assert_called_once_with(conn,2,'active',[2])


class ScopedPolicyTests(unittest.TestCase):
    def test_scoped_phases_preserve_policy_and_leave_other_ids_untouched(self):
        from test_league_lifecycle_service import LifecycleDatabase,EXPECTED
        from endpoints.league.lifecycle.repository import LeagueLifecycleRepository,LOCAL_TODAY
        from sqlalchemy.dialects.sqlite import dialect
        db=LifecycleDatabase();self.addCleanup(db.connection.close)
        db.connection.executescript('ALTER TABLE "League" ADD commissioner INTEGER; CREATE TABLE "LeagueMember" ("leagueId" INTEGER,"userId" INTEGER); INSERT INTO "LeagueMember" SELECT id,2 FROM "League" WHERE id<=7;')
        class ScopedConnection:
            def execute(self,statement,params):
                compiled=statement.params(**params).compile(dialect=dialect(paramstyle='named'),compile_kwargs={'render_postcompile':True})
                sql=str(compiled).replace(LOCAL_TODAY,'date(now())').replace('UPDATE "League" l','UPDATE "League" AS l').replace('ss."seasonStart"::date','date(ss."seasonStart")').replace('ss."seasonEnd"::date','date(ss."seasonEnd")')
                return db.connection.execute(sql,compiled.params)
        conn=ScopedConnection();repo=LeagueLifecycleRepository();before=db.rows()
        for method in ('mark_pre_draft','mark_drafting','mark_post_draft','mark_in_season','mark_completed'):getattr(repo,method)(conn,list(range(1,14)),2,True)
        after=db.rows();self.assertEqual({r['id']:r['status'] for r in after[:7]},{i:EXPECTED[i] for i in range(1,8)})
        self.assertEqual(after[7:],before[7:])
        for method in ('mark_pre_draft','mark_drafting','mark_post_draft','mark_in_season','mark_completed'):getattr(repo,method)(conn,[],2,True)
        self.assertEqual(db.rows(),after)
