type DisplayedSeasonPointsInput = {
  scoreboardTotalPoints: number | null | undefined;
  hasScoreboardScores: boolean;
  memberSeasonPoints: number | null | undefined;
  leagueSeasonPoints: number | null | undefined;
};

export const getScoreboardThroughWeek = (
  currentWeekNumber: number | null
): number | null => {
  if (currentWeekNumber === null) {
    return null;
  }

  if (currentWeekNumber <= 0) {
    return 0;
  }

  return currentWeekNumber - 1;
};

export const getDisplayedSeasonPoints = ({
  scoreboardTotalPoints,
  hasScoreboardScores,
  memberSeasonPoints,
  leagueSeasonPoints,
}: DisplayedSeasonPointsInput): number => {
  if (hasScoreboardScores && typeof scoreboardTotalPoints === "number") {
    return scoreboardTotalPoints;
  }

  if (typeof memberSeasonPoints === "number") {
    return memberSeasonPoints;
  }

  if (typeof leagueSeasonPoints === "number") {
    return leagueSeasonPoints;
  }

  return 0;
};
