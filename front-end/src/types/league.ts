export type LeagueStatus = 'Pre-Draft' | 'Drafting' | 'In-Season' | 'Completed';

export type SportCode = "NCAA_MENS_BASKETBALL" | "FBC_FOOTBALL" | "FCS_FOOTBALL";

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
  transactionsApplyOn: string; // e.g. "nextMonday"
  tradeVeto: {
    enabled: boolean;
    requiredVetoCount: number;
  };
}

export interface LeagueSettings {
  bonuses: LeagueBonuses;
  transactions: LeagueSettingsTransactions;
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
  commissioner: number;
  seasonYear: number;
}

export type League = {
  leagueId: number;
  leagueCreatedAt: string;
  leagueName: string;
  sport: string;
  numPlayers: number;
  status: LeagueStatus;
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
