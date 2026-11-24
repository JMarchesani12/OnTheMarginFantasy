import type { SeasonStandings } from '../types/scoring.ts';

export function applySeasonStandings<T extends { memberId: number; totalPoints: number }>(rows: readonly T[], standings: SeasonStandings | null) {
  const members = new Map(standings?.members.map(member => [member.memberId, member]));
  return rows.map(row => {
    const member = members.get(row.memberId);
    const available = !!member && Number.isFinite(member.totalPoints) && Number.isFinite(member.bonusPoints);
    return { ...row,
      totalPoints: available ? member.totalPoints : row.totalPoints,
      bonusPoints: available ? member.bonusPoints : 0,
      seasonTotalAvailable: available,
    };
  });
}
