# MOD-040 / MOD-030 — Shared Bonuses Editor move

## Intent and selected approach

User selected the mechanical Bonuses Editor move as the next MOD040 frontend
structural pilot, also satisfying MOD030. Planned backend domain extraction is
already complete. Move existing shared UI into component ownership without mixing
content extraction or behavior changes. Preserve both uncommitted MOD039 pilots.

The alternative larger Manage draft-order extraction would change component/state
boundaries and requires its own MOD031B review. It is not part of this move.

## Exact move and import map

Move front-end/src/screens/CreateLeague/BonusesEditor.tsx to
front-end/src/components/League/BonusesEditor.tsx with byte-identical contents.
Keep BonusesEditor, BONUS_TEMPLATES and exported types unchanged.

| Consumer | Before | After |
| --- | --- | --- |
| screens/CreateLeague/CreateLeague.tsx | ./BonusesEditor | ../../components/League/BonusesEditor |
| screens/League/ManageLeaguePage.tsx | ../CreateLeague/BonusesEditor | ../../components/League/BonusesEditor |

Current component imports only React, so no internal relative import adjustment
is needed. No paired editor CSS file exists; both screens keep their current CSS
imports and class names. Do not move/extract styles, change templates/local IDs,
state/callback/validation behavior, payload assembly, labels, gates or routes.
No new facade/re-export at the old path: repository search found only these two
source consumers, both migrated together. This is internal source ownership, not
a public module/API path. Preserve historical audit evidence rather than rewriting
its former-path findings; update current status/import-map documentation only.

## Verification and completion

Capture source bytes/hash before moving and prove the new file matches exactly.
Verify the diff consists of that move and two import strings (aside from docs).
Resolve both consumers with TypeScript/production build and run the current full
frontend suite. Perform a source-level literal-relative TS/TSX import graph scan
(including type/lazy literal imports) for unresolved modules/cycles and remaining
old-path consumers; document exclusions for computed/package/CSS edges. If a scan
finds pre-existing issues, distinguish them from new edges rather than silently
repairing unrelated modules.

MOD030 explicitly calls for import/type/build verification and no mirrored unit
test. This mechanical move adds no algorithm tests; existing component behavior is
preserved by byte equality, unchanged consumers/props/styles and type/build checks.
No browser visual/E2E comparison is claimed; perform it only if a concrete styling
or resolution concern emerges. No backend/native reruns, configured app/provider,
schema/dependency/deployment/commit/push. Fresh independent review, source-hashed
evidence and status updates complete this bounded MOD040 frontend ownership pilot
and MOD030; other frontend content extraction remains separate scoped work.
