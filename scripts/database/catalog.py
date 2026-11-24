"""Read-only public-schema metadata queries used by schema snapshots."""

QUERIES={
 'tables': "SELECT c.relname AS table_name,pg_get_userbyid(c.relowner) AS owner,c.relrowsecurity AS rls_enabled,c.relforcerowsecurity AS rls_forced FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relkind IN ('r','p') ORDER BY c.relname",
 'columns': "SELECT table_name,column_name,data_type,udt_name,is_nullable,column_default,is_identity,identity_generation FROM information_schema.columns WHERE table_schema='public' ORDER BY table_name,ordinal_position",
 'constraints': "SELECT c.relname AS table_name,k.conname,k.contype,pg_get_constraintdef(k.oid) AS definition FROM pg_constraint k JOIN pg_class c ON c.oid=k.conrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' ORDER BY c.relname,k.conname",
 'indexes': "SELECT tablename,indexname,indexdef FROM pg_indexes WHERE schemaname='public' ORDER BY tablename,indexname",
 'policies': "SELECT schemaname,tablename,policyname,permissive,roles,cmd,qual,with_check FROM pg_policies WHERE schemaname='public' ORDER BY tablename,policyname",
 'sequence_grants': "SELECT c.relname,pg_get_userbyid(c.relowner) AS owner,c.relacl::text AS acl FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relkind='S' ORDER BY c.relname",
 'table_acl': "SELECT c.relname,c.relacl::text AS acl FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relkind IN ('r','p') ORDER BY c.relname",
 'precise_columns': "SELECT c.relname,a.attname,format_type(a.atttypid,a.atttypmod) AS type,coll.collname,a.attgenerated FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid JOIN pg_namespace n ON n.oid=c.relnamespace LEFT JOIN pg_collation coll ON coll.oid=a.attcollation WHERE n.nspname='public' AND c.relkind IN ('r','p') AND a.attnum>0 AND NOT a.attisdropped ORDER BY c.relname,a.attname",
 'sequence_options': "SELECT schemaname,sequencename,data_type,start_value,min_value,max_value,increment_by,cycle,cache_size FROM pg_sequences WHERE schemaname='public' ORDER BY sequencename",
 'default_grants': "SELECT pg_get_userbyid(d.defaclrole) AS owner,n.nspname,d.defaclobjtype,d.defaclacl::text AS acl FROM pg_default_acl d LEFT JOIN pg_namespace n ON n.oid=d.defaclnamespace WHERE n.nspname='public' OR d.defaclnamespace=0 ORDER BY 1,2,3",
 'schema_acl': "SELECT nspname,pg_get_userbyid(nspowner) AS owner,nspacl::text AS acl FROM pg_namespace WHERE nspname='public'",
 'role_flags': "SELECT rolname,rolsuper,rolinherit,rolcanlogin,rolbypassrls FROM pg_roles WHERE rolname IN ('anon','authenticated','service_role') ORDER BY rolname",
 'role_membership': "SELECT parent.rolname AS granted_role,child.rolname AS member,m.admin_option FROM pg_auth_members m JOIN pg_roles parent ON parent.oid=m.roleid JOIN pg_roles child ON child.oid=m.member WHERE child.rolname IN ('anon','authenticated','service_role') ORDER BY 1,2",
 'custom_routines': "SELECT n.nspname,p.proname,pg_get_function_identity_arguments(p.oid) AS arguments,pg_get_userbyid(p.proowner) AS owner,p.prosecdef AS security_definer,p.proacl::text AS acl FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='public' AND NOT EXISTS (SELECT 1 FROM pg_depend d WHERE d.classid='pg_proc'::regclass AND d.objid=p.oid AND d.deptype='e') ORDER BY p.proname,arguments",
 'column_acl': "SELECT c.relname,a.attname,a.attacl::text AS acl FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND a.attacl IS NOT NULL AND NOT a.attisdropped ORDER BY c.relname,a.attname",
 'triggers': "SELECT c.relname AS table_name,t.tgname,t.tgenabled,n2.nspname AS function_schema,p.proname AS function_name FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid JOIN pg_namespace n ON n.oid=c.relnamespace JOIN pg_proc p ON p.oid=t.tgfoid JOIN pg_namespace n2 ON n2.oid=p.pronamespace WHERE n.nspname='public' AND NOT t.tgisinternal ORDER BY c.relname,t.tgname",
 'views': "SELECT c.relname,c.relkind,c.reloptions,pg_get_userbyid(c.relowner) AS owner,c.relacl::text AS acl FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relkind IN ('v','m') ORDER BY c.relname",
 'internal_triggers': "SELECT c.relname AS table_name,k.conname AS constraint_name,owning.relname AS constraint_table,t.tgtype,t.tgenabled,t.tgdeferrable,t.tginitdeferred,n2.nspname AS function_schema,p.proname AS function_name FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid JOIN pg_namespace n ON n.oid=c.relnamespace JOIN pg_proc p ON p.oid=t.tgfoid JOIN pg_namespace n2 ON n2.oid=p.pronamespace LEFT JOIN pg_constraint k ON k.oid=t.tgconstraint LEFT JOIN pg_class owning ON owning.oid=k.conrelid WHERE n.nspname='public' AND t.tgisinternal ORDER BY c.relname,k.conname,t.tgtype,p.proname",
 'relation_durability': "SELECT c.relname,c.relkind,c.relpersistence FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relkind IN ('r','p','S','m') ORDER BY c.relname",
 'event_trigger': "SELECT e.evtname,e.evtevent,e.evtenabled,e.evttags,n.nspname AS function_schema,p.proname AS function_name FROM pg_event_trigger e JOIN pg_proc p ON p.oid=e.evtfoid JOIN pg_namespace n ON n.oid=p.pronamespace WHERE e.evtname='ensure_rls'",
}

def snapshot_catalog(conn):
    return [dict(r) for r in conn.exec_driver_sql('''SELECT i.oid::bigint AS oid,i.relname AS name,ns.nspname AS schema,t.relname AS table_name,
      am.amname AS method,x.indisunique AS unique,x.indisprimary AS primary,x.indisexclusion AS exclusion,
      x.indisvalid AS valid,x.indisready AS ready,x.indnullsnotdistinct AS nulls_not_distinct,
      ARRAY(SELECT pg_get_indexdef(i.oid,k,true) FROM generate_series(1,x.indnkeyatts) k) AS key_definitions,
      ARRAY(SELECT pg_get_indexdef(i.oid,k,true) FROM generate_series(x.indnkeyatts+1,x.indnatts) k) AS includes,
      x.indclass::text AS operator_classes,x.indcollation::text AS collations,x.indoption::text AS options,
      pg_get_expr(x.indpred,x.indrelid) AS predicate,
      ARRAY(SELECT c.conname FROM pg_constraint c WHERE c.conindid=i.oid ORDER BY c.conname) AS constraints,
      pg_get_indexdef(i.oid) AS definition,pg_relation_size(i.oid) AS bytes
      FROM pg_index x JOIN pg_class i ON i.oid=x.indexrelid JOIN pg_class t ON t.oid=x.indrelid
      JOIN pg_namespace ns ON ns.oid=t.relnamespace JOIN pg_am am ON am.oid=i.relam
      WHERE ns.nspname='public' ORDER BY t.relname,i.relname''').mappings()]
