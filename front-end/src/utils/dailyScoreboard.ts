import { filterTeamSearch, type TeamSearchIndex } from "./teamSearch.ts";
import type { DailyScoreboardGame } from "../types/dailyScoreboard";

export function getScoreboardTimezone(settings: unknown): string {
  let value = settings;
  if (typeof value === "string") {
    try { value = JSON.parse(value); } catch { return "UTC"; }
  }
  if (!value || typeof value !== "object") return "UTC";
  const config = value as Record<string, unknown>;
  const schedule = config.schedule && typeof config.schedule === "object"
    ? config.schedule as Record<string, unknown> : {};
  const timezone = schedule.timezone || schedule.timeZone || config.timezone || config.timeZone || "UTC";
  if (typeof timezone !== "string") return "UTC";
  try { new Intl.DateTimeFormat("en-US", { timeZone: timezone }); return timezone; }
  catch { return "UTC"; }
}

export function isScoreboardDate(value: string | null): value is string {
  if (!value || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const parsed = new Date(`${value}T12:00:00Z`);
  return !Number.isNaN(parsed.getTime()) && parsed.toISOString().slice(0, 10) === value;
}

export function shiftScoreboardDate(date: string, direction: number): string {
  const value = new Date(`${date}T12:00:00Z`);
  value.setUTCDate(value.getUTCDate() + direction);
  return value.toISOString().slice(0, 10);
}

export function filterDailyGames(games: DailyScoreboardGame[], conference: string, query: string, index?: TeamSearchIndex) {
  const eligible = games.filter(game => !conference || game.homeConferenceName === conference || game.awayConferenceName === conference);
  return filterTeamSearch(eligible, query, game => [{teamId: game.homeTeamId, teamName: game.homeTeamName}, {teamId: game.awayTeamId, teamName: game.awayTeamName}], index);
}
