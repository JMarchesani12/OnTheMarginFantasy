# MOD-006 profile identity rollout

The local implementation preserves nullable legacy/job `User.uuid` and existing
unique `User.email`. The new `User_uuid_key` allows at most one linked profile per
non-null auth subject. Multiple unlinked rows remain valid; they do not resolve
as interactive principals. No accounts are merged, deleted or linked by this work.

## Review before an operational rollout

1. Establish the target and a role permitted to see the complete profile table.
   Run [the read-only aggregate preflight](20261104_user_identity.sql) only with
   authorized database access. It reports total/unlinked profiles, duplicate
   subject groups and affected profile counts, never UUIDs, emails or names.
   `row_security=off` deliberately errors when RLS would filter the query; it
   does not bypass RLS or confer access. Statement timeout is 30 seconds.
2. If duplicate groups are nonzero, stop. A maintainer must review the relevant
   account ownership and dependent references under appropriate private access,
   decide the canonical mapping and approve a separate remediation. Do not pick
   the oldest/smallest row automatically, cascade-delete profiles, overwrite email,
   merge auth accounts or infer identity from matching email. Keep a reversible
   mapping/audit record through the approved process; rerun aggregate preflight.
   Null UUID counts are informational and do not block this nullable policy.
3. Obtain operational approval and choose a low-contention window. Run
   [20261104_user_identity_unique.sql](../../api/migrations/20261104_user_identity_unique.sql)
   as one complete transaction, stopping on error. It takes a write-conflicting
   table lock, rechecks duplicates, validates the existing named constraint on
   replay and adds uniqueness only when ready. Lock timeout is 5 seconds and
   statement timeout 60 seconds. A busy/dirty/drifted database aborts unchanged;
   investigate and schedule a new attempt rather than removing timeouts or
   skipping the guard. Ordinary readers can also delay the DDL lock upgrade.
4. Verify the installed nondeferrable `UNIQUE(uuid)` uses null-distinct semantics
   and is valid/ready; rerun preflight. Deploy the reviewed backend through its
   normal process. The backend maps concurrent same-subject creation to the
   existing 409 response after rollback and one subject lookup; email collisions
   across subjects remain safe 400 rejections. No session can acquire another
   profile by email and no profile values are overwritten.

No hosted preflight, constraint installation, remediation or deployment has been
performed by this task. Repository and disposable-test results do not establish
production readiness. Existing UUID FK/auth cascade and unique-email policy are
unchanged. Browser provider consolidation remains MOD-026.

## Initialization and recovery

Keep the frozen October 29 baseline unchanged. Fresh supported databases apply
the baseline, then the October 30 kickoff migration, then this November 4 identity
migration. The frozen baseline runner verifies its historical schema only and
must not be used to adopt or verify the upgraded schema as if it were unchanged.
`db/tables.sql` describes the intended upgraded schema, not proof of hosted state.

Migration replay validates the named unique key instead of silently accepting
an unrelated key, a deferred key, an invalid index or NULLS NOT DISTINCT semantics.
Duplicates cause transaction rollback before the constraint is added.

If an installed constraint must be removed, review/approve that operational
rollback separately. The only introduced object is the `User_uuid_key` unique
constraint (and its backing index). Dropping that constraint preserves rows and
email/FK rules but reopens duplicate linked-profile creation for all writers.
Coordinate writes/rollout and recheck aggregate counts before reinstalling. Do
not drop existing email/FK constraints or modify historical baseline checksums.
The application change itself is compatible with the previous schema but cannot
guarantee uniqueness until the new constraint is installed.

## Local evidence

[Guarded native verifier](../../scripts/modernization/verify_mod006.py) uses only
the existing marked, owned loopback PostgreSQL harness on port 55439. It creates
and drops a random test database; it accepts no DSN and reads no `.env`.
[Recorded results](../../docs/modernization/evidence/mod-006-postgres-2026-11-04.json)
cover baseline upgrade/replay, dirty/shape/RLS refusal, nullable legacy rows,
email/FK policies, actual unique-lock waits and same-/different-email races.
