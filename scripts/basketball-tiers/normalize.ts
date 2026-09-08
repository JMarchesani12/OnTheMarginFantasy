import type {
  ConferenceResolver,
  NormalizedGame,
  ParsedEspnGame,
  WarningCollector,
} from "./types.ts";

export function normalizeGames(
  games: ParsedEspnGame[],
  resolver: ConferenceResolver,
  warnings: WarningCollector,
): { inspected: number; crossConferenceGames: NormalizedGame[] } {
  const crossConferenceGames: NormalizedGame[] = [];

  for (const game of games) {
    if (!game.completed) {
      continue;
    }
    if (!game.competitors) {
      warnings.add({
        code: "invalid_espn_response",
        message: `Completed ESPN event ${game.espnEventId} did not have exactly two competitors`,
        season: game.season,
        eventId: game.espnEventId,
      });
      continue;
    }

    const [teamA, teamB] = game.competitors;
    if (teamA.id === teamB.id) {
      warnings.add({
        code: "same_team",
        message: `ESPN event ${game.espnEventId} has the same team on both sides`,
        season: game.season,
        eventId: game.espnEventId,
      });
      continue;
    }

    if (teamA.score === null || teamB.score === null) {
      warnings.add({
        code: "missing_score",
        message: `Completed ESPN event ${game.espnEventId} is missing a final score`,
        season: game.season,
        eventId: game.espnEventId,
      });
      continue;
    }
    if (!Number.isInteger(teamA.score) || !Number.isInteger(teamB.score) || teamA.score < 0 || teamB.score < 0) {
      warnings.add({
        code: "invalid_score",
        message: `Completed ESPN event ${game.espnEventId} has invalid score ${teamA.score}-${teamB.score}`,
        season: game.season,
        eventId: game.espnEventId,
      });
      continue;
    }
    if (teamA.score === teamB.score) {
      warnings.add({
        code: "tie_game",
        message: `Completed ESPN event ${game.espnEventId} ended in a tie`,
        season: game.season,
        eventId: game.espnEventId,
      });
      continue;
    }

    const teamAConference = resolver.resolveConference({
      season: game.season,
      teamId: teamA.id,
      espnConference: teamA.conference,
    });
    const teamBConference = resolver.resolveConference({
      season: game.season,
      teamId: teamB.id,
      espnConference: teamB.conference,
    });

    if (!teamAConference || !teamBConference) {
      warnings.add({
        code: "unresolved_conference",
        message: `ESPN event ${game.espnEventId} has unresolved conference: ${teamA.name}=${teamAConference ?? "unknown"}, ${teamB.name}=${teamBConference ?? "unknown"}`,
        season: game.season,
        eventId: game.espnEventId,
      });
      continue;
    }

    if (teamAConference === teamBConference) {
      continue;
    }

    const teamAWon = teamA.score > teamB.score;
    crossConferenceGames.push({
      season: game.season,
      date: game.date,
      espnEventId: game.espnEventId,
      teamA: {
        id: teamA.id,
        name: teamA.name,
        conference: teamAConference,
        score: teamA.score,
      },
      teamB: {
        id: teamB.id,
        name: teamB.name,
        conference: teamBConference,
        score: teamB.score,
      },
      winnerTeamId: teamAWon ? teamA.id : teamB.id,
      loserTeamId: teamAWon ? teamB.id : teamA.id,
      margin: Math.abs(teamA.score - teamB.score),
      neutralSite: game.neutralSite,
    });
  }

  return { inspected: games.length, crossConferenceGames };
}
