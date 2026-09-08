import { mkdir, readFile, writeFile } from "node:fs/promises";
import { existsSync } from "node:fs";
import { join } from "node:path";

import { formatEspnDateRange } from "./seasons.ts";
import type {
  DateRange,
  ParsedEspnGame,
  ParsedEspnTeam,
  RawEspnEvent,
  SeasonRange,
  WarningCollector,
} from "./types.ts";

const ESPN_SCOREBOARD_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/scoreboard";
const DIVISION_I_GROUP = "50";
const SCOREBOARD_LIMIT = "1000";

const ESPN_CONFERENCE_ID_NAMES: Record<string, string> = {
  "1": "America East",
  "2": "ACC",
  "3": "A10",
  "4": "Big East",
  "5": "Big Sky",
  "6": "Big South",
  "7": "Big Ten",
  "8": "Big 12",
  "9": "Big West",
  "10": "CAA",
  "11": "CUSA",
  "12": "Ivy",
  "13": "MAAC",
  "14": "MAC",
  "16": "MEAC",
  "18": "MVC",
  "19": "NEC",
  "20": "OVC",
  "21": "Pac-12",
  "22": "Patriot",
  "23": "SEC",
  "24": "SoCon",
  "25": "Southland",
  "26": "SWAC",
  "27": "Sun Belt",
  "29": "WCC",
  "30": "WAC",
  "43": "Independent",
  "44": "MWC",
  "45": "Horizon",
  "46": "ASUN",
  "49": "Summit",
  "62": "American",
};

export async function loadSeasonScoreboards(
  seasons: SeasonRange[],
  rangesBySeason: Map<string, DateRange[]>,
  cacheDir: string,
  warnings: WarningCollector,
  rangeDays: number,
): Promise<unknown[]> {
  const responses: unknown[] = [];
  await mkdir(cacheDir, { recursive: true });

  for (const season of seasons) {
    const ranges = rangesBySeason.get(season.label) ?? [];
    for (const range of ranges) {
      const dateRange = formatEspnDateRange(range);
      const cachePath = join(cacheDir, `${season.label}-${dateRange}.json`);
      const response = await loadCachedOrFetch(cachePath, dateRange, warnings, season.label);
      responses.push(response);

      const events = getEvents(response);
      if (!events) {
        warnings.add({
          code: "invalid_espn_response",
          message: `ESPN response did not contain an events array for ${dateRange}`,
          season: season.label,
          dateRange,
        });
      } else if (events.length === 0 && rangeDays > 1) {
        warnings.add({
          code: "empty_date_range",
          message: `ESPN returned no events for ${dateRange}`,
          season: season.label,
          dateRange,
        });
      } else if (events.length < 3 && rangeDays > 1 && isLikelyRegularSeasonRange(range)) {
        warnings.add({
          code: "low_game_count",
          message: `ESPN returned only ${events.length} events for ${dateRange}`,
          season: season.label,
          dateRange,
        });
      }
    }
  }

  return responses;
}

export function parseEspnGames(response: unknown, season: string, warnings: WarningCollector): ParsedEspnGame[] {
  const events = getEvents(response);
  if (!events) {
    return [];
  }

  return events.map((event) => parseEvent(event, season, warnings)).filter((game): game is ParsedEspnGame => Boolean(game));
}

export function collectEspnTeams(games: ParsedEspnGame[]): Array<{
  id: string;
  displayName: string;
  shortDisplayName?: string;
  abbreviation?: string;
  conference?: string | null;
}> {
  const teams = new Map<string, {
    id: string;
    displayName: string;
    shortDisplayName?: string;
    abbreviation?: string;
    conference?: string | null;
  }>();

  for (const game of games) {
    if (!game.competitors) {
      continue;
    }
    for (const competitor of game.competitors) {
      const existing = teams.get(competitor.id);
      teams.set(competitor.id, {
        id: competitor.id,
        displayName: existing?.displayName ?? competitor.name,
        shortDisplayName: existing?.shortDisplayName ?? competitor.shortName ?? undefined,
        abbreviation: existing?.abbreviation ?? competitor.abbreviation ?? undefined,
        conference: existing?.conference ?? competitor.conference,
      });
    }
  }

  return [...teams.values()];
}

async function loadCachedOrFetch(
  cachePath: string,
  dateRange: string,
  warnings: WarningCollector,
  season: string,
): Promise<unknown> {
  if (existsSync(cachePath)) {
    return JSON.parse(await readFile(cachePath, "utf8")) as unknown;
  }

  const url = new URL(ESPN_SCOREBOARD_URL);
  url.searchParams.set("dates", dateRange);
  url.searchParams.set("groups", DIVISION_I_GROUP);
  url.searchParams.set("limit", SCOREBOARD_LIMIT);

  const response = await fetch(url);
  if (!response.ok) {
    warnings.add({
      code: "invalid_espn_response",
      message: `ESPN request failed for ${dateRange}: ${response.status} ${response.statusText}`,
      season,
      dateRange,
    });
    return { events: [] };
  }

  const body = await response.text();
  await writeFile(cachePath, body, "utf8");
  return JSON.parse(body) as unknown;
}

function parseEvent(event: RawEspnEvent, season: string, warnings: WarningCollector): ParsedEspnGame | null {
  const eventId = valueToString(event.id);
  if (!eventId) {
    warnings.add({ code: "invalid_espn_response", message: "ESPN event missing id", season });
    return null;
  }

  const date = valueToString(event.date)?.slice(0, 10);
  if (!date) {
    warnings.add({ code: "invalid_espn_response", message: `ESPN event ${eventId} missing date`, season, eventId });
    return null;
  }

  const competitions = Array.isArray(event.competitions) ? event.competitions : [];
  const competition = asRecord(competitions[0]);
  const competitorsRaw = Array.isArray(competition?.competitors) ? competition.competitors : [];
  const competitors = competitorsRaw.map(parseCompetitor).filter((team): team is ParsedEspnTeam => Boolean(team));
  const status = asRecord(event.status);
  const statusType = asRecord(status?.type);
  const completed = Boolean(statusType?.completed);

  return {
    season,
    date,
    espnEventId: eventId,
    completed,
    neutralSite: typeof competition?.neutralSite === "boolean" ? competition.neutralSite : null,
    competitors: competitors.length === 2 ? [competitors[0], competitors[1]] : null,
    statusDescription: valueToString(statusType?.description) ?? valueToString(statusType?.name),
  };
}

function parseCompetitor(raw: unknown): ParsedEspnTeam | null {
  const competitor = asRecord(raw);
  const team = asRecord(competitor?.team);
  const id = valueToString(team?.id);
  const name = valueToString(team?.displayName) ?? valueToString(team?.name) ?? valueToString(team?.shortDisplayName);

  if (!id || !name) {
    return null;
  }

  return {
    id,
    name,
    shortName: valueToString(team?.shortDisplayName),
    abbreviation: valueToString(team?.abbreviation),
    conference: team ? extractConferenceName(team) : null,
    score: parseScore(competitor?.score),
  };
}

function extractConferenceName(team: Record<string, unknown>): string | null {
  const conferenceId = valueToString(team.conferenceId);
  const candidates = [
    valueToString(asRecord(team.conference)?.name),
    valueToString(asRecord(team.conference)?.shortName),
    valueToString(asRecord(team.group)?.name),
    valueToString(asRecord(team.groups)?.name),
    valueToString(team.conferenceName),
    conferenceNameFromId(conferenceId),
  ];
  return candidates.find((candidate): candidate is string => Boolean(candidate)) ?? (conferenceId ? null : "Division 2");
}

function conferenceNameFromId(conferenceId: string | null): string | null {
  return conferenceId ? ESPN_CONFERENCE_ID_NAMES[conferenceId] ?? null : null;
}

function parseScore(raw: unknown): number | null {
  if (typeof raw === "number" && Number.isFinite(raw)) {
    return raw;
  }
  if (typeof raw === "string" && raw.trim() !== "") {
    const parsed = Number(raw);
    return Number.isFinite(parsed) ? parsed : null;
  }
  const record = asRecord(raw);
  if (record) {
    return parseScore(record.value ?? record.displayValue ?? record.score);
  }
  return null;
}

function getEvents(response: unknown): RawEspnEvent[] | null {
  const record = asRecord(response);
  if (!record || !Array.isArray(record.events)) {
    return null;
  }
  return record.events.filter((event): event is RawEspnEvent => Boolean(asRecord(event)));
}

function isLikelyRegularSeasonRange(range: DateRange): boolean {
  return range.start.slice(5, 7) !== "04";
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return typeof value === "object" && value !== null ? value as Record<string, unknown> : null;
}

function valueToString(value: unknown): string | null {
  if (typeof value === "string" && value.trim() !== "") {
    return value.trim();
  }
  if (typeof value === "number") {
    return String(value);
  }
  return null;
}
