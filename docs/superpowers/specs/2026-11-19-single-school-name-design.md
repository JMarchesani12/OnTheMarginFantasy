# One canonical school name

User wants School.shortName and SportTeam.displayName removed now that SchoolAlias exists. School.name becomes the single school/team display source; SchoolAlias retains alternate names and abbreviations. User selected shorter school names, such as Northern Iowa. Use vetted provider school labels when uniquely mapped to an existing school; preserve existing names and flag unmapped/ambiguous cases for review rather than guessing.

Update draft history, rosters, search/catalog, league rules, transaction summaries, and ingestion helpers to read School.name via SportTeam.schoolId. Preserve API field names where necessary to avoid breaking clients; an API property named displayName does not require a database column of that name. Keep User.displayName and conference display labels because they describe different entities. Keep provider-supplied GameResult home/away names for unlinked opponents and stored game-source records; prefer canonical names for linked teams where the app renders them.

Preserve every old short/team name in SchoolAlias before dropping columns. Do not infer current names from arbitrary aliases. Update the seed importer so future runs work without the removed fields. Frozen baselines/historical migrations/snapshots remain historical; current schema and maintained tools/tests use School.name.

Rollout order: verify alias preservation and dependencies; deploy code that no longer reads or writes either column; then execute a bounded, transaction-owned drop migration without CASCADE. The original deployed app read SportTeam.displayName, so column removal was deferred until the user confirmed the compatible deployment. Rollback-only checks verified the new reads before the final committed drop.

Alternatives considered: retain a sport-specific override (user declined); hide old fields without removing them (useful only during deployment transition); selected School.name plus aliases with staged column removal.


The configured target now has the 336 approved canonical-name changes applied,
with all 2,079 aliases preserved. Both legacy columns were removed after the user confirmed compatible API/job
deployment; the committed migration and fresh database/API postflight passed.
The one unmapped school (347) is left unchanged; all 365 schools with teams have
unambiguous provider mappings. See the rollout and read-only postflight receipts.
