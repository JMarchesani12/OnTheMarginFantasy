-- REVIEW PROPOSAL ONLY. Run in one caller-owned transaction after fresh preflight.
-- Covers public tables/sequences and defaults of the two observed creators.
-- No role, policy, owner, backend DSN, service-role or auth/storage changes.
DO $guard$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_default_acl d CROSS JOIN LATERAL aclexplode(d.defaclacl) a
      WHERE d.defaclnamespace=0 AND d.defaclobjtype IN ('r','S') AND a.grantee IN
        (0,(SELECT oid FROM pg_roles WHERE rolname='anon'),
           (SELECT oid FROM pg_roles WHERE rolname='authenticated'))) THEN
    RAISE EXCEPTION 'Review global default grants before schema-scoped hardening';
  END IF;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname IN ('anon','authenticated')
      AND (rolsuper OR rolbypassrls)) THEN
    RAISE EXCEPTION 'Review privileged browser roles before hardening';
  END IF;
  IF EXISTS (SELECT 1 FROM pg_auth_members WHERE member IN
      (SELECT oid FROM pg_roles WHERE rolname IN ('anon','authenticated'))) THEN
    RAISE EXCEPTION 'Review inherited browser-role privileges before hardening';
  END IF;
  IF EXISTS (SELECT 1 FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid
      JOIN pg_namespace n ON n.oid=c.relnamespace
      WHERE n.nspname='public' AND a.attacl IS NOT NULL AND NOT a.attisdropped) THEN
    RAISE EXCEPTION 'Review explicit column grants before hardening';
  END IF;
  IF has_schema_privilege('anon','public','CREATE') OR
     has_schema_privilege('authenticated','public','CREATE') THEN
    RAISE EXCEPTION 'Review public schema CREATE privileges before hardening';
  END IF;
END;
$guard$;
REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public FROM PUBLIC, anon, authenticated;
REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public FROM PUBLIC, anon, authenticated;
GRANT SELECT ON public."User" TO authenticated;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
  REVOKE ALL ON TABLES FROM PUBLIC, anon, authenticated;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
  REVOKE ALL ON SEQUENCES FROM PUBLIC, anon, authenticated;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA public
  REVOKE ALL ON TABLES FROM PUBLIC, anon, authenticated;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA public
  REVOKE ALL ON SEQUENCES FROM PUBLIC, anon, authenticated;
