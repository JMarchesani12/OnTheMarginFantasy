"""Database identity, alias import replay and public metadata boundary."""
import unittest
from flask import Flask
from authMiddleware import install_auth_middleware
from endpoints.sport.routes import setup_routes
from test_league_read_authorization import ReadDatabase


class SchoolAliasDatabaseTests(unittest.TestCase):
    def setUp(self):
        self.db=ReadDatabase(); self.addCleanup(self.db.connection.close)
        self.db.connection.executescript('''
            CREATE TABLE "School" (id INTEGER PRIMARY KEY,name TEXT,"shortName" TEXT);
            CREATE TABLE "SchoolAlias" ("schoolId" INTEGER,alias TEXT,"normalizedAlias" TEXT,source TEXT,
                UNIQUE("schoolId","normalizedAlias"));
            CREATE TABLE "SportTeam" (id INTEGER PRIMARY KEY,"schoolId" INTEGER,"sportId" INTEGER,"displayName" TEXT,"externalId" TEXT);
            INSERT INTO "School" VALUES (369,'University of Northern Iowa','UNI'),(400,'Ohio State','OSU'),(401,'Oregon State','OSU');
            INSERT INTO "SportTeam" VALUES (369,369,1,'UNI','2460'),(525,369,2,'UNI','2460'),(600,400,1,'Ohio State','194'),(601,401,1,'Oregon State','204');
            INSERT INTO "SchoolAlias" VALUES (369,'Northern Iowa','northern iowa','manual'),(400,'OSU','osu','manual'),(401,'OSU','osu','manual');
        ''')
        app=Flask(__name__);app.config['TESTING']=True
        install_auth_middleware(app,public_paths={'/api/team-search/catalog'})
        setup_routes(app,self.db); self.client=app.test_client()

    def test_catalog_uses_actual_school_identity_across_sports(self):
        response=self.client.get('/api/team-search/catalog')
        self.assertEqual(response.status_code,200)
        teams=response.json['teams']
        northern=[row for row in teams if row['schoolId']==369]
        self.assertEqual([row['teamId'] for row in northern],[369,525])
        self.assertTrue(all(row['aliases']==['Northern Iowa'] for row in northern))
        self.assertEqual([row['schoolId'] for row in teams if row['aliases']==['OSU']],[400,401])
        self.assertTrue(all(set(row)=={'teamId','schoolId','teamName','aliases'} for row in teams))

    def test_database_alias_edits_appear_without_catalog_rebuild(self):
        self.db.connection.execute('INSERT INTO "SchoolAlias" VALUES (369,\'Panther Country\',\'panther country\',\'manual\')')
        self.db.connection.commit()
        response=self.client.get('/api/team-search/catalog')
        self.assertEqual(response.status_code,200)
        self.assertIn('Panther Country',response.json['teams'][0]['aliases'])
        self.assertNotIn('source',response.get_data(as_text=True))

    def test_seed_uses_external_ids_not_school_or_team_ids(self):
        from utils.school_alias_seed import plan_school_aliases
        schools=[{'id':369,'name':'University of Northern Iowa','shortName':'UNI'}]
        teams=[{'schoolId':369,'externalId':'2460','displayName':'UNI'}]
        rows=plan_school_aliases(schools,teams,{'groups':[{'id':'2460','names':['UNI','Northern Iowa']}]})
        self.assertEqual({row['schoolId'] for row in rows},{369})
        self.assertIn('Northern Iowa',{row['alias'] for row in rows})
        self.assertEqual(len([row for row in rows if row['normalizedAlias']=='uni']),1)

    def test_ambiguous_provider_mapping_blocks_seed(self):
        from utils.school_alias_seed import plan_school_aliases
        with self.assertRaisesRegex(ValueError,'Ambiguous'):
            plan_school_aliases([], [{'schoolId':369,'externalId':'2460','displayName':'UNI'},
                                     {'schoolId':400,'externalId':'2460','displayName':'Other'}],{'groups':[]})

    def test_import_replay_preserves_manual_alias_source(self):
        from utils.school_alias_seed import import_school_aliases
        catalog={'groups':[{'id':'2460','names':['UNI','Northern Iowa']}]}
        with self.db.begin() as conn:
            import_school_aliases(conn,catalog)
            import_school_aliases(conn,catalog)
        rows=self.db.connection.execute('SELECT * FROM "SchoolAlias" WHERE "schoolId"=369').fetchall()
        self.assertEqual(len({row['normalizedAlias'] for row in rows}),len(rows))
        self.assertEqual(next(row for row in rows if row['alias']=='Northern Iowa')['source'],'manual')
