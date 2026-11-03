# MOD-004 browser privilege proposal

These two SQL files are **unapplied review artifacts**, tested only in a disposable
database. They are not part of baseline installation or an automatic migration.

The observed source browser client needs authenticated own-User SELECT. Flask,
trusted jobs and the listener use server database connections. Proposed changes:

| Boundary | Observed | Proposed |
| --- | --- | --- |
| anon public tables/sequences | Broad object privileges; RLS filters row access | No table/sequence privileges |
| authenticated public tables/sequences | Broad object privileges; own-User SELECT policy | SELECT on User only, still subject to the existing policy |
| Future public tables/sequences by postgres/supabase_admin | Broad browser defaults | No browser defaults; later features grant explicitly |
| service_role/backend/owners | Existing server privileges | Preserved |
| Auth/storage schemas, functions, JWT, API authorization | Existing platform/application contracts | Preserved |

`mod004_browser_privileges.sql` checks inherited browser roles, privileged browser
flags, explicit column grants, schema CREATE privilege and global table/sequence
default grants that schema-scoped revokes cannot remove safely. Unexpected states
reject for review. It revokes direct PUBLIC/browser table/sequence grants, retains
authenticated User SELECT, and adjusts the two observed creators' public defaults.
It does not grant new backend credentials/roles, alter a policy or change RLS.

Before deployment, confirm external consumers beyond this checkout, actual API/
listener/job DSNs/roles, Supabase platform ownership/defaults and an actor authorized
to alter both creators' defaults. The real local provider test confirms postgres cannot change supabase_admin
defaults (SQLSTATE42501); the full file rolls back without partial changes.
The configured hosted actor is also NOSUPERUSER and not a supabase_admin member;
no hosted mutation probe was performed. Do not partially apply the file or bypass that
boundary by broadening server privileges. Use a fresh catalog check and an approved
actor/transaction; these checks are not a substitute for consumer review.

Execute any approved change in one transaction (for example, psql --single-transaction
--set ON_ERROR_STOP=1 with the reviewed SQL file). Review the transaction's result
and verify effective privileges and own-profile reads before release. No production
command/DSN is supplied here.

`mod004_browser_privileges_recovery.sql` restores the previously observed browser
ACL/default grants **only for this exact starting baseline and proposal**, provided
no unrelated grants/schema changes occurred. It deliberately reintroduces broad
privileges; do not treat it as a universal rollback or ACL backup. Take a fresh
metadata ACL snapshot before any approved deployment and use it when restoring a
changed starting state. Policy/RLS and service/backend access remain unchanged.

Local tests verify proposal/recovery, future table grants, preserved own-profile
reads and service access. Replaying the frozen observed baseline verifier while
hardening is active correctly reports drift; recovery returns to the observed
reference. An approved hardening release will need its own versioned transition/
expected state and ledger entry before rollout.


Real-provider HTTP tests now confirm profile isolation and service reads before,
during and after the proposal. The full file was tested with the existing local
supabase_admin maintenance account, not by elevating postgres. Do not infer that
a customer Render service or hosted SQL editor has that maintenance capability.
Before a hosted rollout, choose an authorized platform-maintenance path or review
a narrower application-owner-only change that explicitly leaves provider defaults
outside its guarantee. No narrower scope is silently substituted by this proposal.
