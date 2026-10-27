import type { TierAdjustment } from "./leagueRules";
export type GameResult = {
  tierAdjustment?: TierAdjustment;
  homeTeamUnranked?: boolean;
  awayTeamUnranked?: boolean;
  awayScore: number;
  awayTeamTier: number | null;
  awayTeamId: number;
  awayTeamName: string;
  date: string; // ISO/string from API
  externalGameId: string;
  homeScore: number;
  homeTeamTier: number | null;
  homeTeamId: number;
  homeTeamName: string;
  id: number;
  memberPointDiff: number;
  ownsAway: boolean;
  ownsHome: boolean;
  sportId: number;
  broadcast: string | null;
};
