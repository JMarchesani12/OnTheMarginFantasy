# Model facade retirement implementation plan

> Execute inline using superpowers:executing-plans. User authorized the existing checkout and caller migration; leave changes uncommitted.

**Goal:** Retire redundant Model modules after moving their first-party consumers to existing canonical services.
**Spec:** User request on 2026-11-02 plus the approved incremental hybrid architecture in docs/modernization/architecture.md.
**Architecture:** Change callers, not canonical business logic. Tests that only assert obsolete wrapper translations become direct domain-contract tests. Preserve substantive SQL, authorization, rollback, helper override and disabled HTTP coverage. Never create replacement compatibility facades merely to delete filenames.
**Constraints:** No configured database, provider calls, app/job startup, dependencies, schema, push or deployment. Preserve the league exception pickle shim. Native checks use only marked disposable loopback PostgreSQL.

## Tasks
- [x] Audit eight modules and first-party imports, baseline isolated suite.
- [x] Retire user and sport: migrate tests and native harnesses to UserService/SportService and domain exceptions.
- [x] Retire inherited transaction and schedule facades: canonical imports, helper tests and source manifests.
- [x] Retire scoring and roster: migrate operational scoring script and tests; remove redundant roster HTTP construction.
- [x] Evaluate remaining league/draft bridges individually; migrate only when substantive coverage can be retained without recreating a facade.
- [x] Run isolated suite, native checks for changed operational/composition paths, import/source-manifest audit and fresh final review. Update status/evidence.

## Review focus
- Trusted/job calls remain explicit; HTTP actor checks do not weaken.
- Existing transaction scopes and helper overrides survive canonical constructors.
- Retired error translation assertions must be replaced by domain failure assertions, not discarded wholesale.
- Disabled HTTP tests patch services actually used by adapters.
- Native verification manifests reference existing files; historical evidence stays historical.

## Ledger
- Baseline: clean corrected branch; isolated suite 564 tests passes (see /tmp/model-retirement-baseline.log).
- User and sport have no runtime consumers. Transaction/schedule are inherited facades with existing canonical equivalents. League/draft carry multi-service bridges requiring individual review.

- All eight retired; first-party runtime calls now use canonical services. No replacement facade or canonical business-logic change introduced.
- RED: six initial retired-import subtests failed while modules existed; remaining draft expectation also failed before removal. GREEN: all eight unavailable, full suite 565/565. Existing 564 test methods retained; wrapper error checks now assert canonical domain failures.
- Ruling: retire Model-only constructor bypass/export/built-in error translation contracts alongside their import paths — these internal interfaces are explicitly being retired; canonical services keep their domain contracts — outside-repo Python consumers must migrate.
- League native initial RED: old wrapper ValueError expectation, actual canonical AdmissionRejected. Updated only the expected domain type; all real lock/replay operations retained and rerun passes.
- Final review and final source evidence pending; no commit or deployment.

- Final: fixed Important standalone verification bootstrap ordering — fresh interpreter import regression failed for all three scripts with ModuleNotFoundError, then passed after removing duplicate admission imports and moving rules import after assess_postgres. Full suite 566/566. No other review findings; no re-review required.
- Native: seven complete domain harnesses PASS after caller migration (user, roster, transaction, scoring, league, draft, schedule); all harness-owned databases removed. Sport remains guarded SQLite coverage.
- Source audit: 216 Python files compile; no first-party imports of retired Model modules; all literal source-manifest targets exist; 40 canonical service/repository/contract ASTs unchanged excluding documentation.
- Evidence: all historical reports preserved byte-for-byte; seven fresh 2026-11-02 native reports and aggregate mod-035-model-facade-retirement-2026-11-02.json contain matching source captures. Exception pickle shim retained.
- Complete in current checkout, uncommitted; no push/deployment. No deferred review minors.
