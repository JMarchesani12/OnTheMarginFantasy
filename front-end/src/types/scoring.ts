export type ScoreWeek = {
  endDate: string;
  memberId: number;
  pointDifferential: number;
  pointsAwarded: number;
  rank: number;
  startDate: string;
  teamName: string;
  weekNumber: number;
};

export type WeekStandings = {
    results: ScoreWeek[];
    weekNumbers: number[];
}
