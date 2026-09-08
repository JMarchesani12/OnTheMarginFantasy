import test from "node:test";
import assert from "node:assert/strict";

import { calculateAnalysis } from "./analyze.ts";
import type { NormalizedGame } from "./types.ts";

const games: NormalizedGame[] = [
  {
    season: "2025-26",
    date: "2025-11-10",
    espnEventId: "1",
    teamA: { id: "100", name: "SEC Team", conference: "SEC", score: 80 },
    teamB: { id: "200", name: "Big Ten Team", conference: "Big Ten", score: 72 },
    winnerTeamId: "100",
    loserTeamId: "200",
    margin: 8,
    neutralSite: true,
  },
  {
    season: "2025-26",
    date: "2025-11-11",
    espnEventId: "2",
    teamA: { id: "300", name: "Big 12 Team", conference: "Big 12", score: 68 },
    teamB: { id: "101", name: "SEC Team 2", conference: "SEC", score: 70 },
    winnerTeamId: "101",
    loserTeamId: "300",
    margin: 2,
    neutralSite: false,
  },
  {
    season: "2024-25",
    date: "2024-12-01",
    espnEventId: "3",
    teamA: { id: "201", name: "Big Ten Team 2", conference: "Big Ten", score: 61 },
    teamB: { id: "301", name: "Big 12 Team 2", conference: "Big 12", score: 65 },
    winnerTeamId: "301",
    loserTeamId: "201",
    margin: 4,
    neutralSite: null,
  },
];

test("calculateAnalysis uses signed scoring margin from each conference perspective", () => {
  const analysis = calculateAnalysis(games);

  assert.deepEqual(analysis.aggregate.get("SEC"), {
    conference: "SEC",
    wins: 2,
    losses: 0,
    games: 2,
    pointsFor: 150,
    pointsAgainst: 140,
    totalMargin: 10,
    winPercentage: 1,
    averageMargin: 5,
  });

  assert.deepEqual(analysis.aggregate.get("Big Ten"), {
    conference: "Big Ten",
    wins: 0,
    losses: 2,
    games: 2,
    pointsFor: 133,
    pointsAgainst: 145,
    totalMargin: -12,
    winPercentage: 0,
    averageMargin: -6,
  });
});

test("calculateAnalysis emits both conference-vs-conference perspectives symmetrically", () => {
  const analysis = calculateAnalysis(games);
  const secVsBigTen = analysis.vsConference.get("SEC")?.get("Big Ten");
  const bigTenVsSec = analysis.vsConference.get("Big Ten")?.get("SEC");

  assert.deepEqual(secVsBigTen, {
    conference: "SEC",
    opponent: "Big Ten",
    wins: 1,
    losses: 0,
    games: 1,
    pointsFor: 80,
    pointsAgainst: 72,
    totalMargin: 8,
    winPercentage: 1,
    averageMargin: 8,
  });

  assert.deepEqual(bigTenVsSec, {
    conference: "Big Ten",
    opponent: "SEC",
    wins: 0,
    losses: 1,
    games: 1,
    pointsFor: 72,
    pointsAgainst: 80,
    totalMargin: -8,
    winPercentage: 0,
    averageMargin: -8,
  });
});

test("calculateAnalysis keeps season-specific conference summaries", () => {
  const analysis = calculateAnalysis(games);

  assert.equal(analysis.bySeason.get("2024-25")?.get("Big 12")?.wins, 1);
  assert.equal(analysis.bySeason.get("2024-25")?.get("Big 12")?.averageMargin, 4);
  assert.equal(analysis.bySeason.get("2025-26")?.get("SEC")?.wins, 2);
  assert.equal(analysis.bySeason.get("2025-26")?.get("SEC")?.averageMargin, 5);
});
