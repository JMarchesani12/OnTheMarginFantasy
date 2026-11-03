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
  dailyPointDifferentials?: {
    date: string;
    pointDifferential: number;
  }[];
};

export type UpdateLeagueMember = {
  teamName: string;
}

export type LeagueMemberPreview = {
  id: number;
  teamName: string | null;
  displayName: string | null;
};
