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

export type SeasonStandings = {
  leagueId: number;
  members: { memberId: number; teamName: string; weeklyPoints: number; bonusPoints: number; totalPoints: number }[];
  bonusStatus?: { state: 'ready' | 'pending'; components: Record<string, 'ready' | 'pending'>; snapshotIds: number[] };
};
