# Real Supabase provider acceptance

This suite validates the observed baseline with real Supabase Auth and PostgREST,
not SQL substitutes. Supported test versions: CLI 2.90.0, PostgreSQL image
17.6.1.084 (server17.6), GoTrue2.188.1 and PostgREST14.4. It uses a separate
project ID and local ports; never reuse a linked/hosted project or another local
project's containers/volumes. No .env is read by the harness.

## Disposable setup

These commands initialize a new project under /private/tmp. Generated local keys
remain in private temporary files and are never copied into repository evidence.
The default local password is synthetic; no hosted credentials are supplied.

```sh
mkdir -p /private/tmp/otm-mod004005-supabase-20261029
chmod 700 /private/tmp/otm-mod004005-supabase-20261029
supabase init --workdir /private/tmp/otm-mod004005-supabase-20261029 --yes
python3 - <<'PY'
from pathlib import Path
import re
p=Path('/private/tmp/otm-mod004005-supabase-20261029/supabase/config.toml')
s=p.read_text()
for old,new in [(54321,55441),(54322,55442),(54323,55443),(54324,55444),
                (54320,55440),(54329,55449),(54327,55447)]:
    s=s.replace(str(old),str(new))
for section in ('realtime','studio','storage','edge_runtime','analytics','db.seed'):
    pattern=r'(\['+re.escape(section)+r'\][\s\S]*?\benabled = )true'
    s=re.sub(pattern,r'\1false',s,count=1)
p.write_text(s)
PY
supabase start --workdir /private/tmp/otm-mod004005-supabase-20261029 \
  --exclude realtime,storage-api,imgproxy,studio,edge-runtime,logflare,vector,supavisor,postgres-meta \
  > /private/tmp/otm-mod004005-supabase-20261029/start.log 2>&1
supabase status --workdir /private/tmp/otm-mod004005-supabase-20261029 --output json \
  > /private/tmp/otm-mod004005-supabase-20261029/status.json
chmod 600 /private/tmp/otm-mod004005-supabase-20261029/status.json
docker exec supabase_db_otm-mod004005-supabase-20261029 \
  psql -U postgres -d postgres \
  -c "COMMENT ON DATABASE postgres IS 'otm-supabase-provider-assessment-20261029';"
python3 scripts/modernization/assess_supabase.py
# Stop/remove ONLY this disposable project and its synthetic data.
supabase stop --project-id otm-mod004005-supabase-20261029 --no-backup \
  --workdir /private/tmp/otm-mod004005-supabase-20261029
```

Do not use `supabase stop --all` or a different project ID. Run from the repository
root; inspect failures without printing status.json tokens. The harness requires
the exact loopback API/DB ports and database marker before mutations. It initializes
the explicit pg_trgm prerequisite and uses the immutable baseline runner. It does
not create fake auth.users, auth.uid or platform roles.

## Assertions and evidence

- A clean provider initializes the baseline as real postgres (NOSUPERUSER,
  BYPASSRLS); Supabase's existing platform support permits the observed event
  trigger. Baseline replay preserves synthetic Auth/profile rows.
- Real Auth signup issues two tokens; PostgREST unfiltered own-profile reads,
  foreign-profile filters, anonymous denial, no-policy table denial, browser
  write denial and service-role reads are verified before/proposal/after recovery.
- Two separate schema-only restore databases use actual exported auth/public
  definitions, then simulate precisely supported historical states: subdivision
  absent and either old-only esasonStart or correct-only seasonStart. Historical
  SQL converges; verified adoption/replay preserves a pre-existing School row.
- Schema-selected pg_dump does not include pg_trgm installation or database event
  triggers and assumes the original public schema's initial USAGE privilege.
  Restore fixtures explicitly supply those prerequisites, and register ensure_rls
  as postgres (the observed function owner). They do not infer application DDL.
  Restore uses the existing local maintenance account; no role is granted extra
  permissions. The restore fixture is not a production data backup/restore test.
- Full hardening attempted as normal postgres rejects with SQLSTATE42501 when it
  reaches supabase_admin defaults. The probe always rolls back, even if provider
  capabilities unexpectedly change, and state verification proves no partial
  privileges remain. The full proposal and recovery are then tested using the
  existing disposable supabase_admin maintenance account, without altering role
  powers. Recovery preserves profile values and the observed catalog reference.

The result records versions, input hashes and verdicts, not keys/tokens/user IDs,
in docs/modernization/evidence/supabase-provider-verification-2026-10-29.json.
On an ordinary failure, created users and uniquely named restore databases are
cleaned up. Always stop the owned project afterward to remove its containers,
volumes, baseline and any interrupted fixture leftovers. Other projects remain.

The existing 16-test PostgreSQL unit/integration suite remains the regression gate
for baseline drift/checksum/ledger/savepoint behavior. This provider suite adds
actual service and platform acceptance; it does not exercise a browser UI, Render
process lifecycle, hosted privilege changes, arbitrary historical schemas, or
production disaster recovery. Hosted rollout remains separately authorized.
