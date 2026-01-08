export type DraftSettings = {
  numberOfRounds: number;
  selectionTime: number;
  graceSeconds: number;
  draftType: string;
};

export type DraftState = {
  leagueId: number;
  status: string | null;
  currentOverallPickNumber: number | null;
  currentMemberId: number | null;
  onDeck?: DraftTurnSlot | null;
  inTheHole?: DraftTurnSlot | null;
  expiresAt: string | null;
  lastPickAt: string | null;
  updatedAt: string | null;
};

export type DraftTurnSlot = {
  overallPickNumber: number;
  memberId: number;
  memberTeamName?: string | null;
};

export type DraftMember = {
  memberId: number;
  userId: string;
  teamName: string | null;
  draftOrder: number | null;
};

export type DraftSummaryPick = {
  id: number;
  createdAt: string;
  overallPickNumber: number;
  roundNumber: number;
  pickInRound: number;
  memberId: number;
  memberTeamName?: string | null;
  sportTeamId: number;
  sportTeamName?: string | null;
};

export type DraftSnapshot = {
  leagueId: number;
  draftSettings?: DraftSettings;
  serverNow?: string;
  state?: DraftState;
  onDeck?: DraftTurnSlot | null;
  inTheHole?: DraftTurnSlot | null;
  members?: DraftMember[];
  picks?: DraftSummaryPick[];
  availableTeams?: unknown[];
  recentPicks?: unknown[];
  draftSelections?: unknown[];
};
