# MOD-039 — Backend integer-parser pilot

## Intent and selected approach

User selected the backend integer-parser pilot: reuse the existing request-validation
implementation in draft pick and control HTTP handling, preserving defaults/errors/
authorization. This is a small behavior-preserving extraction, not a validation or
security-policy change. Work in the existing audit checkout and leave uncommitted.

## Inventory and alternatives

| Candidate | Finding and decision |
| --- | --- |
| Draft create_pick and _draft_control_response local integer functions | Both exactly match requestValidation._integer_value. Select these two real consumer paths. |
| Existing integer_field/integer_list_field consumers | Transaction, roster, scoring, league settings and socket boundaries already reuse the shared validators. Preserve existing interfaces and list ceilings. |
| League admission/member actor parsing | Similar coercion but different missing/invalid messages and identity-mismatch handling. Do not fold into this pilot. |
| Read/ownership authorization helpers | Commissioner-or-member read policy differs from member-only draft scope and owned-member mutations. Do not unify distinct access or transaction rules. |
| Frontend mapping/date/API helpers | Many already shared; remaining context freshness/persistence and feedback semantics belong to MOD029/028B or a separate frontend pilot. |
| Ownership/conference rule consolidation | Domain ownership remains MOD033, not a generic utility extraction. |

The alternative frontend pilot would require additional semantic decisions; the
selected backend duplication is exact and already has an appropriate owner. No
new generic utility module, base controller/repository or global rewrite.

## Change

Expose the existing scalar parser as integer_value(value, field) in
api/utils/requestValidation.py. Keep integer_field and integer_list_field behavior,
calling the same implementation. Replace the two identical local draft functions
with imports/calls to integer_value; keep scalar-value calls for optional/defaulted
fields and per-element draft-order parsing. Do not replace domain list validation
with a new ceiling or alter nonempty/permutation/positive-ID decisions.

Integers and integer strings retain Python int semantics, including whitespace,
signs and supported digit forms. Bools, floats, containers, missing/null scalar
values and invalid strings retain ValueError('<field> must be an integer'). No
new positive/range/length rule; existing downstream resource bounds remain owned
by their callers. Missing-field messages and error precedence remain unchanged.
Default weekNumber0 remains distinct from explicit null. Optional actingUserId
is still only a compatibility assertion against the verified principal.

No I/O/actor lookup/auth decision/transaction/commit/notification moves into the
helper. Principal resolution, requested-league ownership, commissioner checks,
HTTP status/error envelope, disabled manual route and post-commit delivery remain
in their existing boundaries. No SQL/frontend/schema/dependency/deployment change.

## Verification and completion

Characterize actual consumer behavior before extraction: accepted integer/string
inputs and optional/default handling; rejected bool/float/null/container/string
inputs; required-field/error precedence; order elements and actor mismatches.
Reuse existing actual JWT/endpoint/domain fixtures rather than test a mirrored
parser. Add focused shared-scalar coverage and prove the real consumers use the
public helper. Existing helper callers/list ceilings and full isolated backend
suite must remain green. No configured DB/runtime/provider is used. Native database
reruns are unnecessary for this pure boundary extraction with no SQL changes.
Fresh independent review and recorded inventory/deliberate non-extractions complete
this first bounded MOD039 pilot; broader helper inventory/extractions remain scoped
follow-ups rather than an implied utility rewrite.
