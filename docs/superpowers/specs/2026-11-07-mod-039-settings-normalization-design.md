# MOD-039 — Frontend settings-normalization pilot

## Inventory result and recommendation

Following the approved inventory continuation, one further exact active helper
match is selected for recommendation: ManageLeaguePage's local
normalizeLeagueSettings matches the exported function in utils/leagueMapping.ts.
The existing shared league mapper and Manage League's local mapper are two real
consumers. Reuse the existing export; introduce no new abstraction or behavior.
This frontend batch stays separate from the already implemented integer pilot.

| Candidate | Result |
| --- | --- |
| ManageLeaguePage.normalizeLeagueSettings vs shared leagueMapping export | Exact runtime behavior. Recommended small second pilot. |
| Whole Manage League mapper vs shared mapper | Different currentWeek fields: local sets null, shared retains response values. Do not consolidate. |
| Home league-list normalizer vs shared normalizer | Home logs unexpected payloads; shared helper is silent. Leave diagnostic policy unchanged. |
| Scoring/transaction/calendar settings parsing | Different missing/invalid JSON handling, exception identities, dictionary requirements and connection ownership. Leave separate. |
| League actor assertion parsing | Similar numeric coercion but caller-specific required/error/mismatch contracts; not selected in this batch. |
| ESPN/NCAA example parser files | Exact placeholder copies but no active external consumers found by repository search. Not a live-consumer extraction; retain for separate cleanup/provenance work. |
| API error handling and authorization | Status/error/fallback/refresh or role/transaction semantics differ. Coordinate MOD028B/029/033 instead of generic consolidation. |

The alternative is to stop after the first pilot. The settings parser is a small,
demonstrated duplication worth removing; broader mapping cleanup would change
behavior and belongs to its own scope.

## Proposed change

Import normalizeLeagueSettings from ../../utils/leagueMapping in ManageLeaguePage
and remove its identical nested definition. Keep its existing mapLeagueFromResponse
and every default/property, initial navigation-state handling, effect dependency,
fetch, form-state initialization and save behavior unchanged. Keep shared utility
behavior unchanged; no new helper signatures/options/diagnostics.

Falsy inputs return undefined. String input uses JSON.parse and returns undefined
on parse failure. Non-string truthy values retain identity through the existing
TypeScript assertion. Valid JSON primitive/array/null behavior also remains as-is;
this helper does not become a schema validator. Caller nullish fallback distinctions
remain unchanged, including fallback to original malformed settings on the
already-mapped League branch versus defaults on the SingleLeague branch.

No request caching/freshness/auth/storage/role/API/backend/SQL changes, no merging
of larger mappers, no date/rule normalization and no third-party dependencies.
Preserve the existing uncommitted integer pilot and its evidence.

## Verification and delivery

Characterize shared helper values and actual Manage League mapping before extraction:
object and JSON-string settings, malformed/falsy/null/primitive values, caller
fallbacks and currentWeek null policy. Use the real component module with controlled
React/transport dependencies or extracted actual AST functions, never a handwritten
copy of its algorithm. Prove Manage League uses the exported helper after removal;
existing shared mapper callers must keep their behavior. Full frontend tests and
TypeScript/production build pass; backend unchanged by this batch. Fresh independent
review and source-hashed evidence. Leave uncommitted/undeployed; no configured runtime,
provider or native database operations.
