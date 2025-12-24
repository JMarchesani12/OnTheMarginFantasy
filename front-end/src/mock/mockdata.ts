// mockData.ts
// Mock data for Sicko Basketball UI development without an API

// --- Types ---
export interface User {
  id: string;
  displayName: string;
}

export interface LeagueMember {
  id: string;
  userId: string;
  teamName: string;
  draftOrder: number;
  seasonPoints: number;
}

export interface Conference {
  id: string;
  name: string;
  tier: "POWER_4" | "OTHER";
  maxTeamsPerOwner: number;
}

export interface RealTeam {
  id: string;
  name: string;
  conferenceId: string;
}

export interface LeagueTeamSlot {
  id: string;
  memberId: string;
  realTeamId: string;
  acquiredWeek: number;
  droppedWeek?: number;
}

export interface WeekScore {
  memberId: string;
  pointDifferential: number;
  rank: number;
  pointsAwarded: number;
}

// --- Mock Users ---
export const mockUsers: User[] = [
  { id: "u1", displayName: "Haylee" },
  { id: "u2", displayName: "Dylan" },
  { id: "u3", displayName: "Mitch" },
  { id: "u4", displayName: "Cole" },
  { id: "u5", displayName: "Sarah" },
  { id: "u6", displayName: "Tyler" },
  { id: "u7", displayName: "Jordan" }
];

// --- Mock League Members ---
export const mockLeagueMembers: LeagueMember[] = [
  { id: "m1", userId: "u1", teamName: "Haylee Hoopers", draftOrder: 1, seasonPoints: 12 },
  { id: "m2", userId: "u2", teamName: "Dylan Dunkers", draftOrder: 2, seasonPoints: 14 },
  { id: "m3", userId: "u3", teamName: "Mitch Madness", draftOrder: 3, seasonPoints: 10 },
  { id: "m4", userId: "u4", teamName: "Cole Crushers", draftOrder: 4, seasonPoints: 8 },
  { id: "m5", userId: "u5", teamName: "Sarah Swish", draftOrder: 5, seasonPoints: 16 },
  { id: "m6", userId: "u6", teamName: "Tyler Tip-Offs", draftOrder: 6, seasonPoints: 9 },
  { id: "m7", userId: "u7", teamName: "Jordan Jumpshots", draftOrder: 7, seasonPoints: 11 }
];

// --- Mock Conferences ---
export const mockConferences: Conference[] = [
  { id: "c1", name: "ACC", tier: "POWER_4", maxTeamsPerOwner: 2 },
  { id: "c2", name: "A-10", tier: "POWER_4", maxTeamsPerOwner: 2 },
  { id: "c3", name: "Big Ten", tier: "POWER_4", maxTeamsPerOwner: 2 },
  { id: "c4", name: "Big 12", tier: "POWER_4", maxTeamsPerOwner: 2 },
  { id: "c5", name: "Missouri Valley", tier: "OTHER", maxTeamsPerOwner: 1 },
  { id: "c6", name: "Mountain West", tier: "OTHER", maxTeamsPerOwner: 1 }
];

// --- Mock Real Teams ---
export const mockRealTeams: RealTeam[] = [
  { id: "t1", name: "Iowa State", conferenceId: "c4" },
  { id: "t2", name: "Kansas", conferenceId: "c4" },
  { id: "t3", name: "Duke", conferenceId: "c1" },
  { id: "t4", name: "Dayton", conferenceId: "c2" },
  { id: "t5", name: "Drake", conferenceId: "c5" },
  { id: "t6", name: "Boise State", conferenceId: "c6" }
];

// --- Mock Draft / Roster Ownership ---
export const mockLeagueTeamSlots: LeagueTeamSlot[] = [
  { id: "s1", memberId: "m1", realTeamId: "t1", acquiredWeek: 1 },
  { id: "s2", memberId: "m1", realTeamId: "t5", acquiredWeek: 1 },
  { id: "s3", memberId: "m2", realTeamId: "t2", acquiredWeek: 1 },
  { id: "s4", memberId: "m3", realTeamId: "t3", acquiredWeek: 1 },
  { id: "s5", memberId: "m4", realTeamId: "t4", acquiredWeek: 1 },
  { id: "s6", memberId: "m5", realTeamId: "t6", acquiredWeek: 1 }
];

// --- Mock Weekly Scores for UI Pages ---
export const mockWeeklyScores: Record<number, WeekScore[]> = {
  1: [
    { memberId: "m5", pointDifferential: 55, rank: 1, pointsAwarded: 7 },
    { memberId: "m2", pointDifferential: 42, rank: 2, pointsAwarded: 6 },
    { memberId: "m1", pointDifferential: 30, rank: 3, pointsAwarded: 5 },
    { memberId: "m7", pointDifferential: 12, rank: 4, pointsAwarded: 4 },
    { memberId: "m3", pointDifferential: 8, rank: 5, pointsAwarded: 3 },
    { memberId: "m6", pointDifferential: -5, rank: 6, pointsAwarded: 2 },
    { memberId: "m4", pointDifferential: -18, rank: 7, pointsAwarded: 1 }
  ],
  2: [
    { memberId: "m2", pointDifferential: 60, rank: 1, pointsAwarded: 7 },
    { memberId: "m5", pointDifferential: 48, rank: 2, pointsAwarded: 6 },
    { memberId: "m3", pointDifferential: 22, rank: 3, pointsAwarded: 5 },
    { memberId: "m6", pointDifferential: 10, rank: 4, pointsAwarded: 4 },
    { memberId: "m1", pointDifferential: 4, rank: 5, pointsAwarded: 3 },
    { memberId: "m7", pointDifferential: -9, rank: 6, pointsAwarded: 2 },
    { memberId: "m4", pointDifferential: -20, rank: 7, pointsAwarded: 1 }
  ]
};

// --- Convenience helpers for UI ---
export const getMemberName = (memberId: string): string => {
  const member = mockLeagueMembers.find((m) => m.id === memberId);
  const user = mockUsers.find((u) => u.id === member?.userId);
  return user?.displayName ?? "Unknown";
};

export const getTeamById = (teamId: string): RealTeam | undefined =>
  mockRealTeams.find((t) => t.id === teamId);

export const getConferenceById = (confId: string): Conference | undefined =>
  mockConferences.find((c) => c.id === confId);
