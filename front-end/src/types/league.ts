export type LeagueStatus = 'Pre-Draft' | 'Drafting' | 'Post-Draft' | 'In-Season' | 'Completed';

export type ScoringSystem =
  | "POINT_DIFFERENTIAL"
  | "TEAM_WINS"
  | "HEAD_TO_HEAD";

export type PointSystem =
  | "WINNER_GETS_POINT"
  | "RANKED_POINTS";

export interface BonusPlacementDTO {
  label: string;
  points: number;
}

export interface BonusDTO {
  name: string;
  placements: BonusPlacementDTO[];
}

export type LeagueBonuses = Record<string, Record<string, number>>;

export interface LeagueSettingsTransactions {
  tradeVeto: {
    enabled: boolean;
    requiredVetoCount: number;
  };
}

export type DraftType = "SNAKE" | "STRAIGHT"
export type TimeoutAction = "AUTO-SKIP" | "AUTO-PICK"

export interface DraftMeta {
  draftType: DraftType;
  selectionTime: number;
  numberOfRounds: number;
  timeoutAction: TimeoutAction;
  graceSeconds: number;
}

export interface LeagueSettings {
  bonuses: LeagueBonuses;
  timezone?: string;
  transactions: LeagueSettingsTransactions;
  draft: DraftMeta;
}

export interface CreateLeaguePayload {
  name: string;
  sport: number;
  numPlayers: number;
  status: string; // e.g. "Pre-Draft"
  settings: LeagueSettings;
  draftDate: string | null;
  freeAgentDeadline: string | null;
  tradeDeadline: string | null;
  commissioner: number | null;
  seasonYear: number;
  isDiscoverable: boolean;
}

export type League = {
  leagueId: number;
  leagueCreatedAt: string;
  leagueName: string;
  sport: string;
  maxPlayersToHaveMaxRounds: number;
  numPlayers: number;
  status: LeagueStatus;
  settings: LeagueSettings;
  updatedAt: string;
  draftDate: string | null;
  tradeDeadline: string | null;
  freeAgentDeadline: string | null;
  seasonYear: number;
  commissionerId: number;
  commissionerDisplayName: string;
  memberId: number;
  teamName: string | null;
  draftOrder: number | null;
  seasonPoints: number | null;
  currentWeekEndDate: Date | null;
  currentWeekId: number | null;
  currentWeekNumber: number | null;
  currentWeekStartDate: Date | null;
};


export type LeagueConference = {
  conferenceId: number;
  displayName: string;
  maxTeamsPerOwner: number;
  sportConferenceId: number;
  teamsInConference: number;
}

export type GetConferences = {
  conferences: LeagueConference[];
  leagueId: number;
  seasonYear: string;
  sportId: number;
}

export type UpdateLeague = {
  name?: string;
  numPlayers?: number;
  status?: string;
  settings?: LeagueSettings;
  draftDate?: string | null;
  tradeDeadline?: string | null;
  freeAgentDeadline?: string | null;
}

export interface LeagueSearchResult {
  id: number;
  name: string;
  sport: number;
  numPlayers: number;
  status: string;
  draftDate: string | null;
  isDiscoverable: boolean;
  commissioner: number;
  commissionerEmail: string;
  commissionerDisplayName: string | null;
}

export interface RequestResponse {
  id: number;
  createdAt: string;
  leagueId: number;
  userId: number;
  status: string;
  message?: string;
  resolvedAt: string;
  resolvedByUserId: number;
}

export type NewMember = {
  id: number;
  leagueId: number;
  userId: number;
  teamName: string;
  seasonPoints: number;
  createdAt: string;
}

export interface ApproveRequestResponse {
  request: RequestResponse;
  member?: NewMember;
}

export interface GetRequestResponse {
  id: number;
  createdAt: string;
  leagueId: number;
  userId: number;
  status: string;
  message?: string;
  resolvedAt: string | null;
  resolvedByUserId: number | null;
  userEmail: string;
  userDisplayName: string;
}

export type SingleLeague = {
  commissioner: number;
  createdAt: string;
  draftDate: string | null;
  freeAgentDeadline: string | null;
  id: number;
  isDiscoverable: boolean;
  name: string;
  numPlayers: number;
  seasonYear: number;
  settings: LeagueSettings;
  sport: number;
  status: LeagueStatus;
  tradeDeadline: string | null;
  updatedAt: string | null;
}
