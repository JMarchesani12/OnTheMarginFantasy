# Capacity-based draft rounds

Approved behavior from the draft-rules discussion: no conference is mandatory. Each owner may draft any available team within the conference's existing per-owner cap. A legal pick is never blocked to preserve someone else's future options. Owners with no legal picks lose their remaining opportunities and may finish with smaller rosters.

Rounds equal `min(sport.maxDraftRounds, floor(sum(min(season conference team count, owner count * conference cap)) / owner count))`. Membership count comes from actual league members. Reject starting a draft if even one full round is impossible; do not manufacture capacity by flooring to one.

Recalculate before the draft starts and when membership changes before drafting. Creation uses the same policy. Never resize a live or completed draft. Preserve season-specific conference membership and current fallback behavior. Existing maximum-player metadata no longer controls rounds.

## Approaches

The discussion considered protecting future roster completion versus allowing unrestricted valid picks. The user selected unrestricted picks and accepts unequal final rosters. Use existing DraftTurn numbering and omit ineligible owners from upcoming turns; do not add fake DraftPick or roster rows. Existing skipped timeout behavior remains distinct from having no legal choices.

No schema migration or hosted data mutation is required. Surface the maximum-roster/skip rule in the draft screen. Verify sizing, season mapping, start, live and timeout advancement, completion, and unaffected authorization.


The timeout worker must discover already-stuck live turns even when their clock is unexpired or absent. Normal pick advancement skips immediately; the existing worker polling bound is 30 seconds for externally altered or preexisting stuck state. Validate stored conference caps before automatic advancement so malformed configuration cannot be mistaken for exhaustion.
