# MOD-040 League Subfolder Organization Plan

> Use superpowers:executing-plans inline, import compatibility tests first and one independent final review.

**Goal:** Group completed league implementation into cohesive subpackages without behavior changes.
**Spec:** [Approved hybrid](../specs/2026-10-29-mod-038-layering-design.md), prior user discussion of league subfolders and authorization to move on.
**Architecture:** Canonical admission/{service,repository,contracts}, members/{service,repository}, administration/{service,repository}, reads/{service,repository}, lifecycle/{service,repository}. Routes/endpoints/model remain at package root. Old flat modules become module aliases to canonical implementation, preserving old imports/identity/globals/patch targets and exception compatibility.

## Constraints

- Current checkout, preserve prior work, uncommitted; no behavior/API/schema/dependencies/deployment/hosted changes.
- Move code verbatim except relative imports. Packages have lightweight __init__, no model/transport imports from service/repository. Facade/adapter composition imports canonical paths.
- Preserve legacy modules, class/exception identity and module-global patch behavior. No duplicate definitions/re-export implementations.
- Keep historical native evidence intact; new report hashes canonical sources AND compatibility aliases. Existing baseline runners still work through aliases.

## Task 1

- [x] RED import compatibility tests (old/canonical module identity, legacy patch target composition, exception load/identity).
- [x] Move implementation/create packages, relative import fixes, legacy module aliases and canonical adapter/model imports; GREEN focused/full backend.
- [x] AST compare all non-import definitions to captured sources and untouched facade/adapter method bodies; dependency checks.

## Task 2

- [x] Rerun complete native league verification through existing legacy harness imports; record complete package/source manifest in new evidence.
- [x] One independent review, final full backend, docs/folder README/current hash/link/diff checks, owned DB/container cleanup.

## Ledger

- Ruling: Use true module aliases (sys.modules points to canonical module) rather than class re-exports to preserve legacy patch targets and shared globals, without duplicate implementation.
- Pre-flight: Admission contracts move with its service; old contracts path aliases the exact same exception module. Remaining domain modules import only canonical siblings/shared policy.

- Task 1 complete: baseline 486/486; RED missing canonical packages across 3 tests (13 subtest/errors), GREEN 3/3. Full backend 489/489. All 11 canonical non-import AST definitions identical to snapshot; model/endpoint definitions identical to pre-move git version. Canonical dependency boundaries verified.
- Task 2 complete: [native evidence](../../modernization/evidence/mod-040-league-folders-postgres-2026-10-30.json) PASS for every prior league/member/admission/lifecycle slice through legacy imports. New 50-file manifest includes canonical modules, aliases and initializers. Old reports retained, source hashes superseded.
- Independent final review no findings; reviewer compatibility suite 3/3; no fixes needed. Final backend 489/489; source manifest, links and diff checked. Owned resources removed; current checkout uncommitted. No API/behavior/schema/hosted/frontend/dependency/startup/deployment changes.
- League extraction and folder pass complete; other domains/frontend and correctness remain separate broader MOD-040 work.
