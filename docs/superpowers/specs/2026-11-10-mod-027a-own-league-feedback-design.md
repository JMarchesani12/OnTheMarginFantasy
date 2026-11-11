# MOD-027A: own-league loading, empty, failure and retry

## Intent and scope

Distinguish pending, successfully empty and failed primary league requests on Home. The user selected local Home state with immediate hiding of previous account/stage results and Retry for the current selection. This is a small change, following MOD-026 at commit f3175c5.

## Approaches

Chosen: keep the primary request state in Home, keyed to the profile identity generation, numeric user ID and selected stage. This fits the existing effects and avoids adding infrastructure. A shared fetching hook adds unnecessary scope for one resource. Keeping previous cards during a stage request can misrepresent them as belonging to the selected stage and was not selected.

## Behavior

For a ready profile, show “Loading your leagues…” while its selected stage is pending. Show cards only from a successful matching request. A successful empty response shows “You have no active leagues.”, “You have no completed leagues.” or “You have no leagues yet.” for Active, Completed or All respectively. Retain the existing Create League action.

A failed request shows a fixed, safe “Could not load your leagues. Please retry.” message and a “Retry leagues” button. Retry immediately enters loading and fetches the current account/stage; do not replay an obsolete captured selection. Use status/alert semantics for feedback. Keep stage selection usable during requests. Only an explicitly successful empty result may display the empty message.

Render-time matching must hide old results and errors immediately on account/stage changes, before effects run. Guard completions with the existing current-identity check, request disposal and cancellation; late results or errors must not replace a newer selection or attempt, including Active→Completed→Active. Abort on replacement/unmount. Retry must not publish after its identity becomes obsolete. Avoid automatic retry loops.

When no numeric profile user ID is available, do not fetch or show a league-empty/error outcome; existing ProfileStatus owns profile loading/error/retry. A same-identity profile refresh must not revive stale list work after its effect is disposed.

Builder call: retain the existing array and {leagues: array} response shapes. For the primary resource, an unrecognized successful payload is a request failure rather than a fabricated empty result. This is a narrow container check, not comprehensive league-row schema validation. Preserve current stage filtering.

## Boundaries

Do not redesign Home or add caching, dependencies, API/schema changes, global error parsing or a shared query system. Preserve the separate all-membership read used by discovery filtering, public search, sports, overview and profile behavior. Its separate normalization/error policy stays unchanged. No Docker, database or live-provider work is needed. Use existing styles with minimal local additions if needed; this is feedback within the current list area, not a layout redesign.

## Verification

Use the existing actual-Home module test harness with controlled requests. Cover initial pending/success/empty/failure, each stage's empty wording, retry pending/success/repeated failure, malformed payload failure, preserved accepted response shapes/filtering, stage replacement before effects, out-of-order success/error, stage round trips, account changes/logout/unmount and profile-not-ready behavior. Assert obsolete requests cannot publish and retry uses the current account/stage. Keep MOD-026 profile/discovery tests green.

Run the complete frontend suite, production build, frontend import verifier and diff checks. Record exact evidence and coverage limits: the controlled hook harness is not a real browser/React runtime. Leave changes uncommitted and undeployed per the established workflow; update only MOD-027A's audit status after verification. Remaining MOD-027 cards are separate work.
