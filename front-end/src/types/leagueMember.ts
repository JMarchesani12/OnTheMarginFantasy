// src/types/leagueMember.ts
export type LeagueMember = {
  id: number;
  createdAt: string;
  draftOrder: number | null;
  leagueId: number;
  seasonPoints: number | null;
  teamName: string | null;
  userId: number;
  displayName: number;
  currentWeekPointDifferential: number;
};

export type UpdateLeagueMember = {
  teamName?: string;
  draftOrder?: number;
  seasonPoints?: number;
}
