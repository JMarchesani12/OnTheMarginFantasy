// src/types/leagueMember.ts
export type LeagueMember = {
  id: number;
  createdAt: string;
  draftOrder: number | null;
  leagueId: number;
  seasonPoints: number | null;
  teamName: string | null;
  userId: number;
};
