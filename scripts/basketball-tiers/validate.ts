import type { NormalizedGame, StatLine, WarningCollector } from "./types.ts";

export function validateGames(games: NormalizedGame[], warnings: WarningCollector): NormalizedGame[] {
  const seenEvents = new Set<string>();
  const seenGameKeys = new Set<string>();
  const valid: NormalizedGame[] = [];

  for (const game of games) {
    if (seenEvents.has(game.espnEventId)) {
      warnings.add({
        code: "duplicate_event_id",
        message: `Duplicate ESPN event ID ${game.espnEventId}`,
        season: game.season,
        eventId: game.espnEventId,
      });
      continue;
    }
    seenEvents.add(game.espnEventId);

    const gameKey = [
      game.date,
      [game.teamA.id, game.teamB.id].sort().join("-"),
      [game.teamA.score, game.teamB.score].join("-"),
    ].join(":");
    if (seenGameKeys.has(gameKey)) {
      warnings.add({
        code: "duplicate_game",
        message: `Duplicate game detected for ${game.teamA.name} vs ${game.teamB.name} on ${game.date}`,
        season: game.season,
        eventId: game.espnEventId,
      });
      continue;
    }
    seenGameKeys.add(gameKey);

    valid.push(game);
  }

  return valid;
}

export function validateStatLines(stats: Iterable<StatLine>, label: string): string[] {
  const errors: string[] = [];
  for (const stat of stats) {
    if (stat.wins + stat.losses !== stat.games) {
      errors.push(`${label} ${stat.conference}${stat.opponent ? ` vs ${stat.opponent}` : ""} wins + losses does not equal games`);
    }
  }
  return errors;
}

export function validateVsConferenceSymmetry(stats: Map<string, Map<string, StatLine>>): string[] {
  const errors: string[] = [];
  const checked = new Set<string>();

  for (const [conference, opponents] of stats.entries()) {
    for (const [opponent, stat] of opponents.entries()) {
      const key = [conference, opponent].sort().join("::");
      if (checked.has(key)) {
        continue;
      }
      checked.add(key);

      const inverse = stats.get(opponent)?.get(conference);
      if (!inverse) {
        errors.push(`${conference} vs ${opponent} missing inverse perspective`);
        continue;
      }

      if (stat.games !== inverse.games) {
        errors.push(`${conference} vs ${opponent} games mismatch: ${stat.games} !== ${inverse.games}`);
      }
      if (stat.wins !== inverse.losses || stat.losses !== inverse.wins) {
        errors.push(`${conference} vs ${opponent} wins/losses mismatch: ${stat.wins}-${stat.losses} !== inverse ${inverse.losses}-${inverse.wins}`);
      }
      if (stat.pointsFor !== inverse.pointsAgainst) {
        errors.push(`${conference} vs ${opponent} points for mismatch: ${stat.pointsFor} !== inverse ${inverse.pointsAgainst}`);
      }
      if (stat.pointsAgainst !== inverse.pointsFor) {
        errors.push(`${conference} vs ${opponent} points against mismatch: ${stat.pointsAgainst} !== inverse ${inverse.pointsFor}`);
      }
      if (stat.totalMargin !== -inverse.totalMargin) {
        errors.push(`${conference} vs ${opponent} total margin mismatch: ${stat.totalMargin} !== inverse ${-inverse.totalMargin}`);
      }
      if (Math.abs(stat.averageMargin + inverse.averageMargin) > 0.000001) {
        errors.push(`${conference} vs ${opponent} average margin mismatch: ${stat.averageMargin} !== inverse ${-inverse.averageMargin}`);
      }
    }
  }

  return errors;
}
