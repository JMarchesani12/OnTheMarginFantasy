# MOD-011 verification plan

**Goal:** Close the outstanding native PostgreSQL acceptance for existing denial/cancellation repairs without reimplementing them.
**Scope:** Current baseline + kickoff + identity migration on owned marked disposable PostgreSQL; no hosted admission writes or new product behavior.

- [x] Initialize actual baseline/status CHECK/FKs and apply current additive migrations.
- [x] Verify PENDING→DENIED/CANCELLED exact response fields; repeat, approved, foreign-owner/commissioner and wrong-league rejection without mutation.
- [x] Verify lowercase status CHECK rejection, post-write and deferred-commit rollback, competing denial/cancellation lock waits.
- [x] Rerun existing native admission suites and isolated backend; fresh review of verification/evidence.
- [x] Record evidence, update MOD-006 applied database status and MOD-011 completion; clean owned test DB/container.

## Ledger

User explicitly authorized running MOD-006 SQL now and continuing Priority5 if appropriate. Configured aggregate preflight:14 profiles,0 unlinked,0 duplicate groups. Guarded MOD-006 migration applied and catalog-verified; counts unchanged. Evidence mod-006-rollout-2026-11-04.json. No account mutation, backend deployment or other hosted SQL performed.

MOD-011 is a small independent outstanding acceptance check with existing code; proceed ahead of larger MOD-008 design/constraints, without changing the roadmap dependencies for MOD-012.

- Native verifier PASS against actual schema plus both migrations. CHECK rejection explicitly verifies23514; same pending request denial/cancellation races observe lock waits and exactly one transition. Previous suites rerun without modifying their historical reports.
- Full backend623/623; independent code/evidence review no material findings; eight source hashes match. No product code edits. Final diff check clean.
- MOD-008 source inspection: week generation uses check/read then separate insert transactions; score replacement is atomic but has no period serialization. Preserve week0/final-period semantics when designing that separate task; no MOD-008 migration or behavior change started here.

Cleanup verified: owned random native-test database dropped; task-owned PostgreSQL container stopped/auto-removed and temporary storage discarded. All evidence source hashes match. Configured database retains the authorized MOD-006 constraint.
