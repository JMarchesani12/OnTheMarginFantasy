# MOD022 — shared scoreboard ingestion for active leagues

## Intent, decisions and alternatives

Stop fetching/applying the same scoreboard once per same-season league in the live ingest cron. Preserve per-league processed/failure reporting, existing date selection and committed partial progress. User selected **later valid payload wins; identical duplicates skip writes**, and requested design/implementation plan together. These documents await combined review before product changes.

Recommended approach: a new invocation-local coordinator shares a season/date outcome across leagues, processes ordered group units once, and delegates each actual game write to existing ingestion helpers. Alternatives: directly switch to ingest_season_for_job (rejected: first-wins dedup/raw-event counts/fetch wrappers differ); buffer all groups and publish atomically (deferred: loses existing committed partial progress and needs a larger failure contract). No transport retry/bootstrap/checkpoint redesign.

## Current call graph and boundaries

cronIngestScoreboard.main owns the existing job_gate, configured-engine fallback and safe logging. In America/Chicago it processes today, then yesterday if before03:00; for each date it queries active leagues and calls ingest_league_for_job per league. SportSeason calendar bounds and League.status determine active selection. Preserve selection SQL, date/order/timezone, report envelope, gate skip/exit behavior and safe_event redaction.

League ingestion resolves league sport, sport API config and season, fetches configured groups in order, counts all raw events, parses and independently commits each upsert. A later duplicate can overwrite an earlier game. Season ingestion instead skips duplicate IDs after the first parsed game, counts distinct valid events and wraps fetch failures. It also serves refresh/bootstrap callers; leave those entry points unchanged in this batch.

Existing _insert_or_update_game resolves team/phase facts and uses repository reference SHARE locks on the upsert connection. Preserve it, parser/client, provider limit500/timeout10, API URL selection, phase overrides/conference logic, per-game commit and database correction identity.

## Coordinator lifetime and identity

Instantiate one new SharedScoreboardIngestionService per cron main invocation after the gate is acquired; never store it globally/on engine/long-lived ScheduleIngestionService. It consumes the existing ingestion service and a gate-check callback. Unit results, config snapshots and last-applied payloads are only local to this invocation and discarded afterward. A new invocation always refetches/revalidates, including after failures.

For each date, consume leagues in the exact active-league query order, resolving each league's own sport/season using existing helpers. Validate before associating a league with shared work. Invalid/missing metadata fails only that league; valid unrelated leagues continue. Recheck metadata for each league rather than inferring sport/season from another league. Cache normalized Sport API configuration once per sport for this invocation; effective base is service.espn_base_url (do not switch to currently ignored baseUrlName). Configuration changes are picked up next run.

Outcome key: (sportId,sportSeasonId,targetDate,effectiveBaseUrl,apiKeyword,orderedUniqueGroups). Logical fetch key adds groupId. Different seasons/sports/dates/config identities never share results even if external event IDs match. Group order is first-occurrence configured order; repeated group IDs are processed once. This deliberately treats repeated configuration as one logical request, with eventsSeen counting unique group responses rather than duplicate config occurrences. No group cache crosses runs.

On first league for a key, execute the season/date unit. Later leagues with that key receive its completed success/failure, not another attempt. Iterate/report in original league order (A1,B1,A2 stays A1,B1,A2), not grouped-bucket order. No cross-date dedup; today/yesterday order remains, including existing possibility of a later sweep correcting a row.

## Ordered parsing and duplicate conflict policy

Fetch/parse groups sequentially in normalized order. Count every raw event yielded, including skipped invalid/unparseable events, for the shared league-compatible eventsSeen. Use actual client iteration/extraction; preserve current empty/missing-events response behavior instead of adding schema/retry policy. A parsed game must have a truthy externalGameId; otherwise skip it as invalid, still counted raw. Canonical event identity is exact str(externalGameId) within this sport/season/date unit, matching database identity; no whitespace/case normalization.

For each valid parsed game, compare its full parsed mapping to a defensive deep copy of the **last successfully applied** mapping for that ID. Include date/TBD/teams/scores/names/broadcast and every phase-affecting field, including seasonType/tournament labels/IDs. Dictionary equality is sufficient; avoid an incomplete persisted-fields fingerprint or hashing lossy JSON conversions.

If identical to the last applied mapping, skip the duplicate upsert. Otherwise call _insert_or_update_game; record the new copy only after successful commit. Thus Aold→Anew→Aold performs3writes and finishesold; an ever-seen fingerprint set would be wrong. Identical consecutive revisions perform1write. Later parsed-invalid records cannot undo a valid record. An upsert/validation exception fails the unit immediately; do not continue to later records hoping to repair it or mark success.

Each actual write resolves current mappings/phases and validates references as before. Skipping an identical parsed duplicate intentionally does not re-resolve a concurrent metadata edit within that unit; the next nonidentical payload or next job run does. This is invocation-level dedup, not a snapshot/history guarantee or cross-job cache.

## Failure, reporting and gate contract

Successful shared unit: every associated valid league receives its existing processed {leagueId,date} entry. Per-league unit_completed logs retain raw eventsSeen for normal unique group configurations; it is shared logical observation, not a count of writes performed for that league. Internal summary may add gamesUpserted/duplicateSkips for tests, but public cron processed/failures envelope and key shapes remain unchanged.

Any fetch, iteration/parsing exception, reference/upsert/commit failure makes the shared outcome failed. Every associated valid league/date reports failure, including later leagues reached after the failure; no automatic same-run retry. Prior committed writes remain. Other sport-seasons/dates continue. Preserve original exception safe-event category handling; never log raw exception text/payload/SQL or wrap every error into a new undifferentiated type. Cached failure objects/categories are in-memory only and are not serialized into reports.

A fresh main invocation retries from the beginning (no durable checkpoint). Successful identical rows from a prior failed run are revalidated/upserted once again; stable GameResult identity must persist. Logical dedup is distinct from HTTP attempts; no new timeout/backoff/retry/Retry-After behavior.

Call gate.check before date discovery, each league association/report, every new group fetch and actual game upsert, and the existing final boundary. GateLost propagates to the outer cron failure path and stops all further work; do not cache it as a normal shared-unit failure and continue. A loss during network/DB work can only stop the next boundary, not roll back an already committed game. Preserve earlier processed entries and existing outer {leagueId:None} failure convention. No new global gate registration.

## Verification and measured acceptance

- Cron/job-gate/timezone safe-report tests run actual main with injected engine/service/clock, not configured runtime. Same-season leagues share work; original report order/raw counts retained; metadata-only failures and other seasons continue; shared failure fans out; GateLost stops all new work; busy gate starts no provider work.
- Unit RED→GREEN exact counts: groups10:A,B,invalid;20:A,C across16leagues →2fetches/3writes, each successful league eventsSeen5. Conflict laterA revision →4writes/final later revision; Aold→Anew→Aold →3writes. Include metadata-only phase inputs, duplicate configured groups, missing IDs, reversed group order, multiple sports/seasons/dates, copied/mutated parser outputs and write failures before memo update.
- Failure/rerun: group20 fails after committed A/B; all dependent leagues fail, unrelated season succeeds. Next explicit invocation fetches all groups and converges to A/B/C with stable IDs. Upsert/mapping/phase/reference/commit failures preserve prior progress and never produce false completion.
- Owned PostgreSQL fixtures with actual parser, mapping/phase selection/reference locks/upsert. Compare all persisted fields and identities against a pinned pre-change league path for overlap, conflicting corrections, phase metadata and dates; preserve allowed intentional raw-count/duplicate-config/invalid-ID differences. Fresh source hashes and strict SQL/provider/write counts; no production latency promise.
- Update ingestion runner's inherited status facts before reuse (actual prepared100active/0completed, not old67/33). Version measurements; immutable historical raw. Test invocation-local cleanup, network-deny transport, no checkpoint/tier/output writes, exact owned DB/container removal. Full guarded backend and relevant audit suite; no frontend/browser/provider calls.

## Scope and release limits

Only live cron gains the coordinator. Existing league/season ingestion wrappers, refresh cron, bootstrap/checkpoint and client transport semantics remain unchanged. Do not broaden to ingestion repository batching, SQL indexes, generic reference caches, retries, season completion or scheduled changes. Builder chooses small internal result types/method names and test fixtures; no unknown external-consumer guarantee. Per-run config/duplicate snapshots and failure fanout are deliberate policy, not full metadata/provider consistency. Local synthetic acceptance does not establish production quotas/outages/concurrency/RLS.

Status: selected duplicate policy, combined design/plan requested; fresh builder check found no important unanswered questions; plan self-reviewed. User approved combined design/plan; implementation and scoped review completed. No product implementation.
