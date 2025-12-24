export type WeekInfo = {
  id: number;
  createdAt: string;
  leagueId: number;
  weekNumber: number;
  startDate: string;
  endDate: string;
  isLocked: boolean;
  scoringComplete: boolean;
};