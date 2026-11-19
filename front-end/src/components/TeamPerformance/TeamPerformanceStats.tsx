import type { TeamPerformance } from "../../types/teamPerformance";
import "./TeamPerformanceStats.css";

export function TeamPerformanceStats({ stats }: { stats?: TeamPerformance }) {
  if (!stats) return null;
  const signed = (value: number) => `${value > 0 ? "+" : ""}${value}`;
  return <span className="team-performance" aria-label="League-adjusted team performance">
    <span>Week <strong>{stats.weekGamesPlayed ? signed(stats.weekDifferential) : "—"}</strong></span>
    <span>Season <strong>{stats.gamesPlayed ? signed(stats.seasonDifferential) : "—"}</strong></span>
    <span>Avg/game <strong>{stats.averageDifferential == null ? "—" : `${stats.averageDifferential > 0 ? "+" : ""}${stats.averageDifferential.toFixed(1)}`}</strong></span>
    <span>{stats.gamesPlayed} played</span>
    {stats.unconfirmedGames > 0 && <span className="team-performance__pending">{stats.unconfirmedGames} result{stats.unconfirmedGames === 1 ? "" : "s"} awaiting confirmation</span>}
  </span>;
}
