# Database-owned school aliases

User approved moving team aliases into the database. SchoolAlias belongs to School; aliases shared across sports, unique by (schoolId, normalizedAlias), never globally unique. Keep displayed names/IDs and typo rules. Seed existing schools using SportTeam.externalId -> provider IDs, never equate provider/school IDs. Skip absent schools, reject ambiguous mappings, preserve existing aliases on replay.

Runtime Python matching receives aliases from the lookup SQL. A public metadata-only catalog endpoint supplies teamId/schoolId/name/aliases to a shared browser cache (five minutes, deduplicated loads). Each search surface consumes that index by team ID; name fallback only for an unambiguous exact displayed name. No bundled alias JSON or guessed school identity in runtime. JSON remains seed/test data only. Existing league authorization and ownership/search result shapes remain intact. Loading/failure of aliases does not disable direct name/typo search; report failure with retry. Stale/unmounted hook requests cannot publish.

Create an additive RLS-enabled SchoolAlias table with no browser direct grants; the backend serves public school metadata. Import current names/short names and vetted provider aliases transactionally, idempotently, without updating School, SportTeam, ownership, scores, or settings. Prepare, test, then apply to the configured project authorized by this request and verify counts/UNI across sports. No application deployment requested.

Preflight confirmed configured project fingerprint 4ecd426e8efadd29: 366 schools, 631 teams, 365 schools represented by teams, no ambiguous provider IDs. Northern Iowa School.id=369, provider ID=2460; basketball/football SportTeam IDs differ. Existing table absent.

Alternatives: keep JSON cache source (requires deployments for edits); enrich every roster/schedule payload (many contract changes); selected one cached metadata endpoint and explicit aliases in backend lookup SQL.
