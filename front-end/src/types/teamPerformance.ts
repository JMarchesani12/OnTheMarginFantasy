export type TeamPerformance = {
  teamId: number;
  weekDifferential: number;
  seasonDifferential: number;
  averageDifferential: number | null;
  weekGamesPlayed: number;
  gamesPlayed: number;
  unconfirmedGames: number;
};

export type TeamPerformanceResponse = { weekNumber: number; teams: TeamPerformance[] };
