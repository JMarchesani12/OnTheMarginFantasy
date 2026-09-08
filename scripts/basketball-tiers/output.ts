import { mkdir, writeFile } from "node:fs/promises";
import { join } from "node:path";

import type { AnalysisResult, NormalizedGame, StatLine, WarningItem } from "./types.ts";
import { summarizeWarnings } from "./warnings.ts";

type CsvValue = string | number | boolean | null | undefined;
type CsvRow = Record<string, CsvValue>;

export function rowsToCsv(headers: string[], rows: CsvRow[]): string {
  return [
    headers.join(","),
    ...rows.map((row) => headers.map((header) => escapeCsvValue(row[header])).join(",")),
  ].join("\n") + "\n";
}

export async function writeOutputs(
  outputDir: string,
  seasons: string[],
  games: NormalizedGame[],
  analysis: AnalysisResult,
  warnings: WarningItem[],
): Promise<string[]> {
  await mkdir(outputDir, { recursive: true });

  const files = [
    await writeCsv(outputDir, "conference-summary.csv", summaryRows(analysis.aggregate)),
    await writeCsv(outputDir, "conference-vs-conference.csv", vsRows(analysis.vsConference)),
    await writeCsv(outputDir, "season-summary.csv", seasonSummaryRows(analysis.bySeason)),
    await writeCsv(outputDir, "season-vs-conference.csv", seasonVsRows(analysis.vsConferenceBySeason)),
    await writeCsv(outputDir, "games-used.csv", gameRows(games)),
    await writeCsv(outputDir, "warnings.csv", warningRows(warnings)),
    await writeMarkdownReport(outputDir, seasons, games, analysis, warnings),
  ];

  return files;
}

export function summaryRows(stats: Map<string, StatLine>): CsvRow[] {
  return [...stats.values()]
    .sort(sortStats)
    .map(statToRow);
}

export function vsRows(stats: Map<string, Map<string, StatLine>>): CsvRow[] {
  return [...stats.values()]
    .flatMap((opponents) => [...opponents.values()])
    .sort((a, b) => a.conference.localeCompare(b.conference) || (a.opponent ?? "").localeCompare(b.opponent ?? ""))
    .map(statToRow);
}

function seasonSummaryRows(stats: Map<string, Map<string, StatLine>>): CsvRow[] {
  return [...stats.entries()]
    .flatMap(([season, seasonStats]) => summaryRows(seasonStats).map((row) => ({ season, ...row })));
}

function seasonVsRows(stats: Map<string, Map<string, Map<string, StatLine>>>): CsvRow[] {
  return [...stats.entries()]
    .flatMap(([season, seasonStats]) => vsRows(seasonStats).map((row) => ({ season, ...row })));
}

function gameRows(games: NormalizedGame[]): CsvRow[] {
  return games.map((game) => ({
    season: game.season,
    date: game.date,
    team_a: game.teamA.name,
    team_a_id: game.teamA.id,
    team_a_conference: game.teamA.conference,
    team_a_score: game.teamA.score,
    team_b: game.teamB.name,
    team_b_id: game.teamB.id,
    team_b_conference: game.teamB.conference,
    team_b_score: game.teamB.score,
    margin: game.margin,
    neutral_site: game.neutralSite,
    espn_event_id: game.espnEventId,
  }));
}

function warningRows(warnings: WarningItem[]): CsvRow[] {
  return warnings.map((warning) => ({
    code: warning.code,
    season: warning.season,
    event_id: warning.eventId,
    date_range: warning.dateRange,
    message: warning.message,
  }));
}

function statToRow(stat: StatLine): CsvRow {
  return {
    conference: stat.conference,
    ...(stat.opponent ? { opponent: stat.opponent } : {}),
    wins: stat.wins,
    losses: stat.losses,
    games: stat.games,
    win_percentage: round(stat.winPercentage, 3),
    points_for: stat.pointsFor,
    points_against: stat.pointsAgainst,
    total_margin: stat.totalMargin,
    average_margin: round(stat.averageMargin, 2),
  };
}

async function writeCsv(outputDir: string, filename: string, rows: CsvRow[]): Promise<string> {
  const headers = csvHeadersForFile(filename);
  const path = join(outputDir, filename);
  await writeFile(path, rowsToCsv(headers, rows), "utf8");
  return path;
}

async function writeMarkdownReport(
  outputDir: string,
  seasons: string[],
  games: NormalizedGame[],
  analysis: AnalysisResult,
  warnings: WarningItem[],
): Promise<string> {
  const lines: string[] = [
    "# NCAA Men's Basketball Conference Analysis",
    "",
    `Seasons: ${seasons.join(", ")}`,
    `Cross-conference games analyzed: ${games.length}`,
    "",
    "## Aggregate Overview",
    "",
    "| Conference | W | L | Win % | Avg Margin |",
    "|------------|---|---|-------|------------|",
    ...summaryRows(analysis.aggregate).map((row) => `| ${row.conference} | ${row.wins} | ${row.losses} | ${formatPercent(Number(row.win_percentage))} | ${formatMargin(Number(row.average_margin))} |`),
    "",
  ];

  for (const conference of [...analysis.aggregate.keys()].sort()) {
    const stat = analysis.aggregate.get(conference);
    if (!stat) {
      continue;
    }
    lines.push(
      `## ${conference}`,
      "",
      "Overall:",
      `Record: ${stat.wins}-${stat.losses}`,
      `Win %: ${formatPercent(stat.winPercentage)}`,
      `Average Margin: ${formatMargin(stat.averageMargin)}`,
      "",
      "### Against Conferences",
      "",
      "| Opponent | W | L | Win % | Avg Margin |",
      "|----------|---|---|-------|------------|",
    );

    const opponents = [...(analysis.vsConference.get(conference)?.values() ?? [])].sort(sortStats);
    lines.push(...opponents.map((row) => `| ${row.opponent} | ${row.wins} | ${row.losses} | ${formatPercent(row.winPercentage)} | ${formatMargin(row.averageMargin)} |`));

    lines.push(
      "",
      "### By Season",
      "",
      "| Season | W | L | Win % | Avg Margin |",
      "|--------|---|---|-------|------------|",
    );

    for (const [season, seasonStats] of [...analysis.bySeason.entries()].sort()) {
      const seasonStat = seasonStats.get(conference);
      if (seasonStat) {
        lines.push(`| ${season} | ${seasonStat.wins} | ${seasonStat.losses} | ${formatPercent(seasonStat.winPercentage)} | ${formatMargin(seasonStat.averageMargin)} |`);
      }
    }
    lines.push("");
  }

  lines.push("## Warning Summary", "");
  const summary = summarizeWarnings(warnings);
  if (summary.size === 0) {
    lines.push("No warnings.");
  } else {
    for (const [code, count] of [...summary.entries()].sort()) {
      lines.push(`- ${code}: ${count}`);
    }
  }

  const path = join(outputDir, "report.md");
  await writeFile(path, `${lines.join("\n")}\n`, "utf8");
  return path;
}

function escapeCsvValue(value: CsvValue): string {
  if (value === null || value === undefined) {
    return "";
  }
  const stringValue = String(value);
  if (/[",\n\r]/.test(stringValue)) {
    return `"${stringValue.replaceAll('"', '""')}"`;
  }
  return stringValue;
}

function csvHeadersForFile(filename: string): string[] {
  switch (filename) {
    case "conference-summary.csv":
      return ["conference", "wins", "losses", "games", "win_percentage", "points_for", "points_against", "total_margin", "average_margin"];
    case "conference-vs-conference.csv":
      return ["conference", "opponent", "wins", "losses", "games", "win_percentage", "points_for", "points_against", "total_margin", "average_margin"];
    case "season-summary.csv":
      return ["season", "conference", "wins", "losses", "games", "win_percentage", "points_for", "points_against", "total_margin", "average_margin"];
    case "season-vs-conference.csv":
      return ["season", "conference", "opponent", "wins", "losses", "games", "win_percentage", "points_for", "points_against", "total_margin", "average_margin"];
    case "games-used.csv":
      return ["season", "date", "team_a", "team_a_id", "team_a_conference", "team_a_score", "team_b", "team_b_id", "team_b_conference", "team_b_score", "margin", "neutral_site", "espn_event_id"];
    case "warnings.csv":
      return ["code", "season", "event_id", "date_range", "message"];
    default:
      throw new Error(`No CSV headers configured for ${filename}`);
  }
}

function sortStats(a: StatLine | CsvRow, b: StatLine | CsvRow): number {
  const aWin = Number("winPercentage" in a ? a.winPercentage : a.win_percentage);
  const bWin = Number("winPercentage" in b ? b.winPercentage : b.win_percentage);
  const aMargin = Number("averageMargin" in a ? a.averageMargin : a.average_margin);
  const bMargin = Number("averageMargin" in b ? b.averageMargin : b.average_margin);
  const aConference = String(a.conference);
  const bConference = String(b.conference);
  return bWin - aWin || bMargin - aMargin || aConference.localeCompare(bConference);
}

function round(value: number, places: number): number {
  const multiplier = 10 ** places;
  return Math.round(value * multiplier) / multiplier;
}

function formatPercent(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

function formatMargin(value: number): string {
  return `${value >= 0 ? "+" : ""}${value.toFixed(1)}`;
}
