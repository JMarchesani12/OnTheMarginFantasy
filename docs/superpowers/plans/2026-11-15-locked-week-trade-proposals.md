# Locked-week trade proposals implementation plan

> Execute inline with superpowers:executing-plans and test-driven development.

**Goal:** Queue proposals submitted against a locked week for the next unlocked week, as approved by the user.

**Architecture:** Reuse the workflow's existing league-scoped next-unlocked-week lookup. Validate ownership and conference limits for the resolved week and store its ID on the proposal. Keep authorization, deadline checks, proposal status, and acceptance/application behavior intact. Proposing must not transfer any teams. The existing trade panel displays the stored week number.

**Tech stack:** Python/Flask/SQLAlchemy; isolated SQL-backed unittest fixtures. The frontend error display fix and regression tests from the preceding turn remain included.

### Task 1: Resolve locked-week proposals

- [x] Add failing HTTP regression tests in `api/tests/test_trade_proposal_authorization.py`: successful forwarding without roster mutation; skip locked weeks and other leagues; no future week; effective-week ownership and conference/deadline enforcement.
- [x] Run `python3 api/tests/run_isolated.py test_trade_proposal_authorization.py` and confirm the new success cases fail on the old locked-week rejection.
- [x] Update `TransactionWorkflowService.propose_trade` in `api/endpoints/transaction/workflow_service.py` to resolve the next unlocked week and use its ID and number.
- [x] Run the proposal suite, then the full isolated backend suite and frontend tests/build. Inspect the diff for unintended changes. No live trades, roster updates, or deployment.

**Verification:** All 17 proposal tests, 600 isolated backend tests, and 67 frontend tests pass. `npm run build` and `git diff --check` pass. Independent review found no material issues. Tests use synthetic fixtures; PostgreSQL concurrency and hosted deployment were not exercised.
