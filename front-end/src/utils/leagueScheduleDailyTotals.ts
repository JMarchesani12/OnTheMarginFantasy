import type { GameResult } from "../types/gameResult";
import type { DateHeader } from "./scheduleTable";

export type DailyTotalsTeamRow = {
  cellsByDate: Record<string, { memberPointDiff?: number | null }[]>;
};

type SelectDailyTotalsArgs = {
  dateHeaders: DateHeader[];
  todayKey: string;
  activeMemberDailyTotals: Record<string, number>;
  isViewingCurrentWeek: boolean;
  teamRows: DailyTotalsTeamRow[];
};

export function selectDailyTotals({
  dateHeaders,
  todayKey,
  activeMemberDailyTotals,
  isViewingCurrentWeek,
  teamRows,
}: SelectDailyTotalsArgs): Record<string, number> {
  const totals: Record<string, number> = {};
  const canUseApiDailyTotals =
    isViewingCurrentWeek && Object.keys(activeMemberDailyTotals).length > 0;

  dateHeaders.forEach((header) => {
    const isFuture = header.key > todayKey;
    const totalFromApi = activeMemberDailyTotals[header.key];
    totals[header.key] = isFuture
      ? 0
      : canUseApiDailyTotals
      ? totalFromApi ?? 0
      : 0;
  });

  if (canUseApiDailyTotals) {
    return totals;
  }

  teamRows.forEach((row) => {
    Object.entries(row.cellsByDate).forEach(([dateKey, cells]) => {
      if (dateKey > todayKey) {
        totals[dateKey] = 0;
        return;
      }

      let sum = totals[dateKey] ?? 0;
      cells.forEach((cell) => {
        if (typeof cell.memberPointDiff === "number") {
          sum += cell.memberPointDiff;
        }
      });
      totals[dateKey] = sum;
    });
  });

  return totals;
}

// Show each team's raw margin when both sides are owned; their rows cancel out.
// Single-owned games keep the backend's tier-adjusted scoring contribution.
export function getTeamGamePointDiff(
  game: Pick<GameResult, "ownsHome" | "ownsAway" | "homeScore" | "awayScore" | "memberPointDiff">,
  isHome: boolean,
): number {
  if (game.ownsHome && game.ownsAway) {
    return isHome ? game.homeScore - game.awayScore : game.awayScore - game.homeScore;
  }
  return game.memberPointDiff;
}
