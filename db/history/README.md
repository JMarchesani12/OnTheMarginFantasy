# Applied database changes

Immutable execution receipts for the observed application database. A receipt records a past approved operation, not authorization to replay it on another target. File contents/hashes were preserved when these records were moved to descriptive names.

| Record | Applied change |
| --- | --- |
| [20261104_profile_identity.json](20261104_profile_identity.json) | Nullable legacy UUIDs preserved; linked-profile uniqueness |
| [20261104_week_score_identity.json](20261104_week_score_identity.json) | Week/member-score identity and same-league references |
| [20261104_ownership_integrity.json](20261104_ownership_integrity.json) | Ownership references, valid intervals and overlap exclusion |
| [20261117_ownership_index.json](20261117_ownership_index.json) | Member-led ownership index |
| [20261117_seasonal_references.json](20261117_seasonal_references.json) | Same-sport season/conference/game references |
| [20261118_browser_privileges.json](20261118_browser_privileges.json) | Current browser table/sequence grants and postgres defaults removed |

[Browser privilege starting catalog](20261118_browser_privileges_before.json) preserves the package's input evidence. Its original hash still matches the versioned manifest. The [change package](../changes/README.md) preserves exact SQL/state/recovery bytes. [Snapshots](../snapshots/README.md) retain before/after schemas and catalog checksums.

Paths recorded inside historical JSON describe the checkout at execution time. The former docs/modernization/evidence directory is retired; its six rollout receipts and privilege starting catalog are now here. The former db/proposals/mod004-owner-v1 package is now db/changes/20261118_browser_privileges. Snapshot directories now use descriptive ownership-index, seasonal-references and browser-privileges suffixes. Old source/receipt paths are provenance, not current runnable commands. Do not change receipt contents to make historical paths look current.

## School search and canonical names — November 19, 2026

- [school-alias-rollout-2026-11-19.json](school-alias-rollout-2026-11-19.json)
- [school-alias-runtime-2026-11-19.json](school-alias-runtime-2026-11-19.json)
- [school-name-column-drop-2026-11-19.json](school-name-column-drop-2026-11-19.json)
- [school-name-column-drop-postflight-2026-11-19.json](school-name-column-drop-postflight-2026-11-19.json)
- [school-name-deployment-check-2026-11-19.json](school-name-deployment-check-2026-11-19.json)
- [school-name-dry-run-2026-11-19.json](school-name-dry-run-2026-11-19.json)
- [school-name-plan-2026-11-19.json](school-name-plan-2026-11-19.json)
- [school-name-postflight-2026-11-19.json](school-name-postflight-2026-11-19.json)
- [school-name-rollout-2026-11-19.json](school-name-rollout-2026-11-19.json)
