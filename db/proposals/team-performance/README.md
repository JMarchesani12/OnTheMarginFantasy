# Real-world team performance rollout

1. Apply `001_game_completion.sql` before deploying ingestion code. It only adds a nullable completion flag; it does not guess historical game status or change scoring.
2. Deploy the API and frontend together. The authenticated `/api/roster/teamPerformance` read uses the league's sport, season, week bounds, tier rules and tournament multipliers. It returns all teams in one request rather than fetching each team's season separately.
3. Refresh historical schedules with the existing season bootstrap for each relevant season, using `--force` once to refresh already-ingested dates. See `api/startSeasonJobs/README.md` for the configured bootstrap command, operational gate prerequisites, checkpoints, and interruption/resume rules. If interrupted, resume without `--force`. Do not run another bootstrap concurrently.
4. Verify historical `GameResult.isCompleted` is populated by the provider. Scheduled and live games are excluded; unknown historical results remain visibly marked as awaiting confirmation. Do not backfill completion from nonzero scores or elapsed time.

Weekly stats cover the selected scoring week. Season stats cover confirmed completed games in that sport season through the present, even before the current manager acquired a team. Each real-world team is scored from its own perspective, with league tier adjustments and phase rules. Ownership-specific cancellation when a manager owns both opponents is intentionally not applied to these team-level comparison stats; those stats are not a reconstruction of the manager's earned total.

Average = adjusted season differential / completed games, including zero-differential games. Teams with no completed games show an em dash rather than a misleading average of zero. Historical stats can be partial until the refresh completes.

The migration and historical refresh have not been applied by the implementation task.
