# Season setup and basketball tournaments

Run SQL migration `api/migrations/20261023_basketball_tournament_rules.sql` before deploying the updated API or running basketball setup. It adds `SeasonPhase.rules` JSONB. It does not rewrite existing seasons or leagues. No new subdivisions or tournament-specific tables are needed.

## Configuration

`configs/ncaa-mens-basketball-2026.json` includes D1 and the four national postseason tournaments. Its dates are illustrative and must be confirmed. Add the actual conference tournament entries before running it. `configs/ncaa-mens-basketball-2026.example.json` shows ACC and Big Ten entries alongside the four national tournaments; its conference IDs **101/102 are placeholders**, and its dates and source-label aliases are examples, not verified 2027 schedules. Copy the shape for every basketball conference. The script rejects missing conference entries.

Find the real IDs and any existing tournament codes using:

```sql
SELECT sc.id AS "sportConferenceId", c.name, td.code AS "existingTournamentCode"
FROM "SportConference" sc
JOIN "Conference" c ON c.id = sc."conferenceId"
LEFT JOIN "TournamentDefinition" td ON td."sportConferenceId" = sc.id AND td.scope = 'Conference'
WHERE sc."sportId" = 1
ORDER BY c.name;
```

Example entry (replace the ID, verify dates and matchers):

```json
{
  "code": "ACC_TOURNEY",
  "name": "ACC Tournament",
  "scope": "Conference",
  "sportConferenceId": 101,
  "startDate": "2027-03-09",
  "endDate": "2027-03-13",
  "rules": {
    "positiveOnly": true,
    "marginMultiplier": 1,
    "primaryPostseason": false,
    "sourceLabels": ["ACC Tournament", "ACC Championship"]
  }
}
```

Use the existing stable code when a TournamentDefinition already exists. For a new code the script creates its definition, after validating the sport/conference. A rerun refreshes names, phase dates, and phase rules. An existing code cannot be reassigned to a different conference/scope. Definitions are reusable; phases carry each season's dates and rules. `has_conference_tournaments` alone no longer supplies basketball tournament setup: basketball opts into explicit manifest tournaments through SportConfig.

Dates in JSON are inclusive in the top-level `timezone` (the examples use `America/New_York`). The script stores half-open intervals from local midnight through midnight after the final date, so late-evening games and daylight-saving time are handled correctly. UTC is the default when timezone is omitted. D1's regular/postseason dates remain broad subdivision metadata; conference phase dates classify individual tournaments. For basketball the final-period phase dates determine week generation, so a gap between D1's regularSeasonEnd and postseasonStart does not drop conference games.

## Scoring and periods

| Competition | Margin scoring | Period |
| --- | --- | --- |
| Regular season | Existing signed tier-adjusted margin | Normal weekly period |
| Conference tournaments | Positive adjusted margin only, 1x | Normal weekly period |
| NCAA (`NCAA_TOURNEY`) | Positive adjusted margin only, 2x | Shared final period |
| NIT | Positive adjusted margin only, 1x | Shared final period |
| Crown (`CROWN`) | Positive adjusted margin only, 1x | Shared final period |
| CBI | Positive adjusted margin only, 0.5x | Shared final period |

Tournament multipliers apply **after existing tier adjustments**, separately for each game. Odd half margins round upward, matching existing integer scoring: adjusted CBI +21 becomes +11. Losses and both-owned games contribute zero in tournament phases. The normal N-to-1 ranking points are awarded once after the shared final period ends; ranking points themselves are not doubled. The final period covers the earliest start through the latest end of the four national tournaments, expressed in the league timezone. Regular weekly windows continue through the preceding day without a gap. Ownership remains fixed to the league's scoring week, including its extended final week.

`primaryPostseason: true` belongs only to NCAA, so NIT/CBI/Crown do not compete with NCAA bracket depth in primary-postseason tiebreakers/bonuses. `priority` remains a legacy phase-selection tie breaker for sports without manifest rules; basketball matching and scoring do not infer meaning from it.

## Game assignment

The ESPN adapter retains tournament labels from event/competition notes and tournament objects, tournament object IDs, and event season type. Configure `rules.sourceLabels` against actual payload labels. Matching ignores capitalization/punctuation and accepts complete phrases in longer labels, such as `ACC Tournament - Quarterfinal`.

Optional `rules.sourceIds` matches tournament object IDs. Optional `rules.eventIds` lists ESPN event IDs as explicit, dated overrides when upstream labels are missing or ambiguous. Prefer source identity over dates; an event ID override is a deliberate administrator correction.

Conference source matches must also agree with both teams' season-specific conference membership (falling back to current membership only if no season-scoped membership exists). Overlapping national tournaments require distinct source matchers; dates alone never choose a tournament. Unknown or ambiguous postseason events fail ingestion visibly. A recognized tournament label, source ID, or event override outside its configured dates also fails, so date errors and postponements cannot silently become regular-season games. During a conference's configured tournament window, a same-conference game without a valid match also fails rather than silently receiving signed regular-season scoring. Missing source fields may require adding aliases or an event override. The sample aliases are not a substitute for checking real ESPN payloads.

## Running

From `api`, after applying the migration and completing/confirming the config:

```sh
PYTHONPATH=. python3 startSeasonJobs/startSeason.py --config startSeasonJobs/configs/ncaa-mens-basketball-2026.json
```

Use `--max-days 3` for limited ingestion; partial ingestion is not marked fully bootstrapped. A failed fetch or unclassified tournament leaves the bootstrap incomplete and the command exits with an error after printing its summary. Fix the dates/matchers and rerun. Use `--force` to reingest an already bootstrapped season, including updating existing GameResult phase assignments after changing rules/matchers.

## Interruptions and resume

Bootstrap saves a local checkpoint after each fully successful date, including dates with no games. If interrupted, rerun the same command **without `--force`** to skip completed dates and retry unfinished or failed dates. At most the interrupted date is replayed; existing games are updated rather than duplicated. `--max-days N` now processes the next N pending dates, so repeated limited runs advance through the season.

Checkpoints live under `api/.cache/season-bootstrap/` (already ignored by Git), independently for each database/season. The script prints the checkpoint path and progress after each successful date; its final summary includes `daysSkipped`. Use `--checkpoint-file /path/to/progress.json` to choose a durable location. Keep that file on the machine running the script, and run one bootstrap per season at a time. No database migration is required for checkpoints.

Files are saved with atomic replacement. A corrupt file produces an explicit error rather than silently restarting. `--force` deliberately discards checkpoints and refreshes all dates; if that forced run is interrupted, resume it **without `--force`**. Relevant phase rules/dates or ESPN API keyword/group changes invalidate a partial checkpoint so stale assignments are reprocessed. Routine metadata timestamps/names do not invalidate it. After a fully completed season, use `--force` when changing configuration or refreshing schedules. Force a refresh after changing team/conference membership mappings, too.

This only tracks dates processed by the updated script. Work from a run started before checkpoint support has no reliable day-level checkpoint and cannot automatically be skipped. An already-running Python process does not pick up this code change; finish that run or restart with the updated script.

## Existing leagues

Season setup changes global metadata, not existing Week rows. New leagues use the new merged final period. Existing leagues must deliberately rebuild periods and rescore after reclassifying their games; split final periods are rejected by the scorer. The existing rebuild utility now shares ScheduleModel's week builder and requires an explicit season year:

```sh
PYTHONPATH=. python3 scripts/rebuild_weeks_and_rescore.py --season-year 2026 --league-id 123
```

This utility changes weeks and deletes/recomputes scores for the selected league. Review ownership acquiredWeek/droppedWeek values, transactions linked to old weeks, and lock state before using it for an active league: changing week numbering is not an ownership/transaction migration. Omitting `--league-id` targets every league in the requested season. No database migration, season ingestion, or league rebuild was executed as part of this code change.
