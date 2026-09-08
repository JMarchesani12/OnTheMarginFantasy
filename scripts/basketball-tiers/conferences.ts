import type {
  ConferenceOverrides,
  ConferenceResolver,
  EspnTeamInfo,
  OverrideMatchWarning,
} from "./types.ts";

const TEAM_ALIASES: Record<string, string> = {
  jaxstate: "jax state",
  "jacksonville state": "jax state",
  "jacksonville state gamecocks": "jax state",
  "abilene chrstn": "abilene christian",
  "bethune": "bethune cookman",
  "c arkansas": "central arkansas",
  "e kentucky": "eastern kentucky",
  "sf austin": "stephen f austin",
  "chicago st": "chicago state",
  "murray st": "murray state",
  "nc a and t": "north carolina a&t",
  "nc a t": "north carolina a&t",
  "north carolina a and t": "north carolina a&t",
  "new mexico st": "new mexico state",
  "w illinois": "western illinois",
  "arizona st": "arizona state",
  "oregon st": "oregon state",
  "washington st": "washington state",
  "seattle u": "seattle",
  "s indiana": "southern indiana",
  "kennesaw st": "kennesaw state",
  "missouri st": "missouri state",
  "boise st": "boise state",
  "ca baptist": "cal baptist",
  "california baptist": "cal baptist",
  "colorado st": "colorado state",
  "fresno st": "fresno state",
  "hawai i": "hawaii",
  "n illinois": "northern illinois",
  "sacramento st": "sacramento state",
  "san diego st": "san diego state",
  "texas st": "texas state",
  "ut rio grande": "utrgv",
  "east texas a and m": "texas a&m commerce",
  "sam houston state": "sam houston",
  "sam houston state bearkats": "sam houston",
  "texas a m commerce": "texas a&m commerce",
  "texas a and m commerce": "texas a&m commerce",
  "st thomas mn": "st thomas",
  "st thomas minnesota": "st thomas",
  "ut rio grande valley": "utrgv",
  "texas rio grande valley": "utrgv",
  "dixie state": "utah tech",
};

const CONFERENCE_ALIASES: Record<string, string> = {
  acc: "ACC",
  "atlantic coast": "ACC",
  "atlantic coast conference": "ACC",
  a10: "A10",
  "a 10": "A10",
  "atlantic 10": "A10",
  "atlantic 10 conference": "A10",
  asun: "ASUN",
  "asun conference": "ASUN",
  american: "American",
  "american athletic": "American",
  "american athletic conference": "American",
  "america east": "America East",
  "america east conference": "America East",
  "big 12": "Big 12",
  "big 12 conference": "Big 12",
  "big east": "Big East",
  "big east conference": "Big East",
  "big sky": "Big Sky",
  "big sky conference": "Big Sky",
  "big south": "Big South",
  "big south conference": "Big South",
  "big ten": "Big Ten",
  "big ten conference": "Big Ten",
  "big west": "Big West",
  "big west conference": "Big West",
  caa: "CAA",
  "colonial athletic association": "CAA",
  cusa: "CUSA",
  "conference usa": "CUSA",
  horizon: "Horizon",
  "horizon league": "Horizon",
  independent: "Independent",
  independents: "Independent",
  "division 2": "Division 2",
  "division ii": "Division 2",
  ivy: "Ivy",
  "ivy league": "Ivy",
  maac: "MAAC",
  mac: "MAC",
  meac: "MEAC",
  mvc: "MVC",
  "missouri valley": "MVC",
  "missouri valley conference": "MVC",
  mwc: "MWC",
  "mountain west": "MWC",
  "mountain west conference": "MWC",
  nec: "NEC",
  "northeast conference": "NEC",
  ovc: "OVC",
  "ohio valley": "OVC",
  "ohio valley conference": "OVC",
  "pac 12": "Pac-12",
  "pac 12 conference": "Pac-12",
  "pac-12": "Pac-12",
  patriot: "Patriot",
  "patriot league": "Patriot",
  sec: "SEC",
  "southeastern conference": "SEC",
  socon: "SoCon",
  "southern conference": "SoCon",
  southland: "Southland",
  "southland conference": "Southland",
  swac: "SWAC",
  summit: "Summit",
  "summit league": "Summit",
  "sun belt": "Sun Belt",
  "sun belt conference": "Sun Belt",
  uac: "UAC",
  wac: "WAC",
  "western athletic conference": "WAC",
  wcc: "WCC",
  "west coast": "WCC",
  "west coast conference": "WCC",
};

const MASCOT_SUFFIXES = [
  "bearkats",
  "blue devils",
  "gamecocks",
  "tommies",
];

export function createConferenceResolver(
  overrides: ConferenceOverrides,
  teams: EspnTeamInfo[],
): ConferenceResolver {
  const teamIndex = buildTeamIndex(teams);
  const overrideTeamIdsBySeason = new Map<string, Map<string, string>>();
  const unmatchedOverrides: OverrideMatchWarning[] = [];
  const ambiguousOverrides: Array<OverrideMatchWarning & { matchedTeamIds: string[] }> = [];
  const unknownConferenceNames = new Set<string>();

  for (const [season, seasonOverrides] of Object.entries(overrides)) {
    const seasonMap = new Map<string, string>();
    const seenTeamIds = new Map<string, string>();

    for (const [teamName, conferenceName] of Object.entries(seasonOverrides)) {
      const normalizedConference = normalizeConferenceName(conferenceName);
      if (!normalizedConference) {
        unknownConferenceNames.add(conferenceName);
        continue;
      }

      const key = normalizeTeamNameForMatch(teamName);
      const matches = teamIndex.get(key) ?? [];
      if (matches.length === 0) {
        unmatchedOverrides.push({ season, teamName, conference: conferenceName });
        continue;
      }
      if (matches.length > 1) {
        ambiguousOverrides.push({
          season,
          teamName,
          conference: conferenceName,
          matchedTeamIds: matches.map((match) => match.id),
        });
        continue;
      }

      const teamId = matches[0].id;
      const previousConference = seenTeamIds.get(teamId);
      if (previousConference && previousConference !== normalizedConference) {
        unmatchedOverrides.push({ season, teamName, conference: conferenceName });
        continue;
      }
      seenTeamIds.set(teamId, normalizedConference);
      seasonMap.set(teamId, normalizedConference);
    }
    overrideTeamIdsBySeason.set(season, seasonMap);
  }

  return {
    unmatchedOverrides,
    ambiguousOverrides,
    unknownConferenceNames: [...unknownConferenceNames].sort(),
    overrideTeamIdsBySeason,
    resolveConference(input) {
      const override = overrideTeamIdsBySeason.get(input.season)?.get(input.teamId);
      if (override) {
        return override;
      }
      return normalizeConferenceName(input.espnConference);
    },
  };
}

export function normalizeConferenceName(raw: string | null | undefined): string | null {
  if (!raw) {
    return null;
  }
  const key = raw.trim().toLowerCase().replaceAll("&", "and").replace(/[^a-z0-9]+/g, " ").trim();
  return CONFERENCE_ALIASES[key] ?? null;
}

export function normalizeTeamNameForMatch(raw: string): string {
  let normalized = raw
    .toLowerCase()
    .replaceAll("&", " and ")
    .replace(/[^a-z0-9]+/g, " ")
    .replace(/\bsaint\b/g, "st")
    .replace(/\bst\b/g, "st")
    .replace(/\buniversity\b/g, "")
    .replace(/\s+/g, " ")
    .trim();

  for (const suffix of MASCOT_SUFFIXES) {
    if (normalized.endsWith(` ${suffix}`)) {
      normalized = normalized.slice(0, -suffix.length).trim();
    }
  }

  return TEAM_ALIASES[normalized] ?? normalized;
}

function buildTeamIndex(teams: EspnTeamInfo[]): Map<string, EspnTeamInfo[]> {
  const index = new Map<string, EspnTeamInfo[]>();

  for (const team of teams) {
    const names = [
      team.displayName,
      team.shortDisplayName,
      team.abbreviation,
    ].filter((name): name is string => Boolean(name));

    for (const name of names) {
      const key = normalizeTeamNameForMatch(name);
      const existing = index.get(key) ?? [];
      if (!existing.some((entry) => entry.id === team.id)) {
        existing.push(team);
      }
      index.set(key, existing);
    }
  }

  return index;
}
