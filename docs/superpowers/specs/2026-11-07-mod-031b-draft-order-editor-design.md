# MOD-031B — Presentational draft-order editor extraction

## Intent and selected approach

User selected MOD031B as the next bounded MOD040 frontend content extraction:
move the draft-order UI out of ManageLeaguePage while parent state, saving and
role/status gates stay in that screen. This gives the list/actions a focused
component owner without changing draft behavior. Preserve both MOD039 pilots and
the MOD030 BonusesEditor move already uncommitted in this checkout.

The alternative draft-clock hook extraction affects timer/countdown lifecycle and
will be reviewed separately under MOD031A. Moving draft state and API orchestration
into the editor would expand this pilot and is excluded.

## Component boundary

Create front-end/src/components/League/DraftOrderEditor.tsx. Extract only the
existing div.ml-draft-order subtree: heading/randomize button, loading/errors,
ordered member rows, rank/name/displayName, remove/self-disabled state and drag
handlers/hint. No new wrapper DOM, CSS, markup, labels, sorting, keyboard controls,
local state/effects, fetches, dialogs or API imports in this component.

Typed props convey orderedMembers, memberCount, membersLoading, membersError,
memberActionError, draggingMemberId and currentUserId, plus onRandomize,
onRemoveMember(member), onDragStart(memberId), onDragOver(memberId), onDragEnd.
Reuse LeagueMember; do not fix unrelated existing type declarations. Use the
original member count for randomize-disabled and list-presence conditions rather
than substituting orderedMembers.length: the arrays can differ during loading/
parent reconciliation. Keep nullish name fallback and direct displayName rendering.

Render the component at the former subtree location, inside the existing parent
commissioner/Pre-Draft gates. The self-removal disabled/title UI remains the same
comparison with currentUserId; the parent handler retains its independent guard.
Pass the same existing handlers. Drag-over still calls event.preventDefault before
forwarding the target ID; randomize/remove/start/end forward the same arguments.
Do not add a saving disable rule or change drag/key/button semantics in this pass.

## Parent-owned state and operations

Keep all member loading/reconciliation, orderedMemberIds/orderedMembers,
draggingMemberId, draftOrderState, shuffleMembers and randomization, reorder/splice,
member removal/confirmation, errors, saving and status/role logic in ManageLeaguePage.
The new component does not hide a second source of truth or become an auth boundary.

Keep settings/date/type/round/timeout/grace inputs and both Save/Save and Start Draft
buttons outside the extracted component. Preserve existing updateLeague → optional
setDraftOrder → getLeague sequence, payloads, parent refresh/forms/messages and
failure handling. The currently displayed Save and Start Draft behavior/message is
not implemented or corrected as part of this extraction. No admission/moderation,
leave/delete, settings, request lifecycle, account freshness, API/schema/backend,
provider or draft-scaling change.

ManageLeaguePage.css and imported CreateLeague.css remain parent-owned and unchanged;
new component uses the existing ml-/cl- class names. No stylesheet relocation or
new dependency. Parent→component→types import flow, no component→screen edge.

## Verification

Characterize actual parent rendering/actions before extraction using controlled
React/transport dependencies: exact role/status visibility, empty/loading/error
branches, row order/ranks/names, dragging class, self-remove disable/title, randomize
and drag actions, removal confirmation/payload/reload, and order-save arguments.
Cover an ordered list whose length differs from member count. Tests execute actual
production component/handler code, not a copied reordering algorithm. Preserve
existing API failure/error behavior and both save action arguments.

After extraction test actual child callback forwarding (including preventDefault)
and parent integration with the same scenarios. Full frontend tests, TypeScript/
production build and source import graph must pass. Graph scan's documented inline
ImportTypeNode exclusion remains; use normal type imports and do not broaden this
pilot into scanner cleanup. No browser DOM/E2E claim unless actually run; controlled
JSX/component tests cover this code boundary. No backend/native/configured runtime,
provider, schema/dependency/deployment/commit/push. Fresh independent final review,
source-hashed evidence and scope/status documentation complete MOD031B's bounded
presentation extraction, not the other Priority7 cards.

## Builder discretion

Exact prop interface spelling, test harness/fixtures and formatting may be chosen
without adding behavior. Keep callback/data ownership and observable markup/action
contracts above. If characterization exposes a pre-existing bug, record it as a
separate behavior-change follow-up rather than silently fixing it in this extraction.
