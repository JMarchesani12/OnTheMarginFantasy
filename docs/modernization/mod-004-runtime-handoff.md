# MOD-004 runtime and rollout handoff — 2026-10-29

Maintainer reports Render hosting, with the separate draft-listener service
intentionally suspended to save cost. That suspension is an operating preference,
not a defect to repair. No Render service was restarted, deployed or changed.

## What is established

| Boundary | Evidence | Conclusion |
| --- | --- | --- |
| Application database definitions | Frozen baseline and read-only Supabase verifier | Observed public schema/access reference matches configured database. |
| Configured database actor | Read-only pg_roles | postgres is NOSUPERUSER, BYPASSRLS, not a member of supabase_admin. This is the repository-configured connection, not a verified Render environment mapping. |
| Fresh provider setup | Real local Supabase Auth/PostgREST acceptance | Baseline initializes without role elevation; real JWT profile isolation, historical upgrades/adoption and recovery pass. |
| Full proposal authority | Real local normal-postgres attempt | Supabase rejects changing supabase_admin defaults with42501; the entire attempt rolls back. Existing local maintenance actor can test full proposal/recovery without granting postgres extra powers. |
| Render listener suspension | Maintainer report | Preserve suspension. Service ID/type/start command/active revision have not been inspected. |
| Source API lifecycle | api/wsgi.py → create_app → api/api.py:68 | API factory itself starts start_draft_notify_listener. The suspended service's name does not establish whether the active web command starts this code too. |
| Connection configuration | api/db.py and startDraftNotifyListener.py | Models/jobs use SUPABASE_DB_URL; notification connection reads DATABASE_URL. Different endpoints/users may still target the same project. Compare privately, never print either DSN. |
| Current activity | Aggregate read-only pg_stat_activity snapshot | Zero sessions with a last command exactly matching source LISTEN at collection time. This neither proves no listeners nor attributes connections to Render services. |

No raw application rows, SQL text, client addresses, credentials or generated Auth
tokens were exported. Evidence: [runtime assessment](evidence/runtime-role-assessment-2026-10-29.json)
and [real provider run](evidence/supabase-provider-verification-2026-10-29.json).

## Remaining Render verification

A Render integration was discovered but is not installed/connected in this session.
Read-only service inspection can continue once that connection is available. No
additional permission is needed to repeat the already authorized read-only review;
service mutations/restarts remain outside scope.

Inspect service IDs/types, suspended state, active commit, root directory,
start commands and scheduled invocation configuration. Inventory environment
variable names; compare DSN project/role targets internally and record only the
comparison result. Do not save environment values, logs with query parameters,
passwords or tokens. Map the web process, suspended worker/listener and scoring/
ingestion schedules to actual repository entry points. In particular, distinguish
notification LISTEN from draft-timeout worker and scheduled jobs.

Do not change listener startup behavior as part of this metadata check. If runtime
mapping confirms a lifecycle/config defect, scope a separate MOD-024/034 repair
with the owner's intentional suspension preserved.

## Rollout choices still require review

The tested full browser-privilege proposal includes defaults owned by both
postgres and supabase_admin. A normal application/Render connection is not an
appropriate substitute for a platform maintenance actor. No actor was elevated.
Either identify an authorized platform path for the full proposal or explicitly
review a narrower current-object/postgres-creator proposal with provider defaults
left as a documented limitation. Do not partially apply the full file, silently
weaken its coverage, or mark all future browser access restricted.

A hardening rollout must have its own versioned transition/expected state and
ledger/recovery plan. Current code only implements the frozen baseline ledger.
Verify external consumers and actual service roles before selecting that transition.
No hosted baseline adoption, policy/grant change, restart or deployment is done.

MOD-004 remains open for these runtime/rollout decisions. MOD-005's documented
repository baseline and supported-provider acceptance are complete; that is not
permission to adopt the baseline or apply hardening on the hosted project.
