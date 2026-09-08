import type { AnalysisResult, NormalizedGame, StatLine } from "./types.ts";

export function calculateAnalysis(games: NormalizedGame[]): AnalysisResult {
  const aggregate = new Map<string, StatLine>();
  const vsConference = new Map<string, Map<string, StatLine>>();
  const bySeason = new Map<string, Map<string, StatLine>>();
  const vsConferenceBySeason = new Map<string, Map<string, Map<string, StatLine>>>();

  for (const game of games) {
    applyPerspective(aggregate, game.teamA.conference, game.teamA.conference, "", game.teamA.score, game.teamB.score);
    applyPerspective(aggregate, game.teamB.conference, game.teamB.conference, "", game.teamB.score, game.teamA.score);

    applyNestedPerspective(vsConference, game.teamA.conference, game.teamB.conference, game.teamA.score, game.teamB.score);
    applyNestedPerspective(vsConference, game.teamB.conference, game.teamA.conference, game.teamB.score, game.teamA.score);

    const seasonStats = getMap(bySeason, game.season);
    applyPerspective(seasonStats, game.teamA.conference, game.teamA.conference, "", game.teamA.score, game.teamB.score);
    applyPerspective(seasonStats, game.teamB.conference, game.teamB.conference, "", game.teamB.score, game.teamA.score);

    const seasonVs = getMap(vsConferenceBySeason, game.season);
    applyNestedPerspective(seasonVs, game.teamA.conference, game.teamB.conference, game.teamA.score, game.teamB.score);
    applyNestedPerspective(seasonVs, game.teamB.conference, game.teamA.conference, game.teamB.score, game.teamA.score);
  }

  finalizeStatMap(aggregate);
  finalizeNestedStatMap(vsConference);

  for (const seasonStats of bySeason.values()) {
    finalizeStatMap(seasonStats);
  }
  for (const seasonVs of vsConferenceBySeason.values()) {
    finalizeNestedStatMap(seasonVs);
  }

  return { aggregate, vsConference, bySeason, vsConferenceBySeason };
}

function applyNestedPerspective(
  stats: Map<string, Map<string, StatLine>>,
  conference: string,
  opponent: string,
  pointsFor: number,
  pointsAgainst: number,
): void {
  applyPerspective(getMap(stats, conference), opponent, conference, opponent, pointsFor, pointsAgainst);
}

function applyPerspective(
  stats: Map<string, StatLine>,
  key: string,
  conference: string,
  opponent: string,
  pointsFor: number,
  pointsAgainst: number,
): void {
  const stat = getStatLine(stats, key, conference, opponent);
  stat.games += 1;
  stat.pointsFor += pointsFor;
  stat.pointsAgainst += pointsAgainst;
  stat.totalMargin += pointsFor - pointsAgainst;
  if (pointsFor > pointsAgainst) {
    stat.wins += 1;
  } else if (pointsFor < pointsAgainst) {
    stat.losses += 1;
  }
}

function getStatLine(stats: Map<string, StatLine>, key: string, conference: string, opponent: string): StatLine {
  const existing = stats.get(key);
  if (existing) {
    return existing;
  }

  const created: StatLine = {
    conference,
    ...(opponent === "" ? {} : { opponent }),
    wins: 0,
    losses: 0,
    games: 0,
    pointsFor: 0,
    pointsAgainst: 0,
    totalMargin: 0,
    winPercentage: 0,
    averageMargin: 0,
  };
  stats.set(key, created);
  return created;
}

function finalizeNestedStatMap(stats: Map<string, Map<string, StatLine>>): void {
  for (const opponentStats of stats.values()) {
    finalizeStatMap(opponentStats);
  }
}

function finalizeStatMap(stats: Map<string, StatLine>): void {
  for (const stat of stats.values()) {
    stat.winPercentage = stat.games === 0 ? 0 : stat.wins / stat.games;
    stat.averageMargin = stat.games === 0 ? 0 : stat.totalMargin / stat.games;
  }
}

function getMap<K, V>(map: Map<K, Map<string, V>>, key: K): Map<string, V> {
  const existing = map.get(key);
  if (existing) {
    return existing;
  }
  const created = new Map<string, V>();
  map.set(key, created);
  return created;
}
