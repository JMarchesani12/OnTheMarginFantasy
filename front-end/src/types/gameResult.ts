export type GameResult = {
  awayScore: number;
  awayTeamId: number;
  awayTeamName: string;
  date: string; // ISO/string from API
  externalGameId: string;
  homeScore: number;
  homeTeamId: number;
  homeTeamName: string;
  id: number;
  memberPointDiff: number;
  ownsAway: boolean;
  ownsHome: boolean;
  broadcast: string | null;
};
