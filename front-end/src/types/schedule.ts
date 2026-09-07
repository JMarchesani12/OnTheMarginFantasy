import type { GameResult } from "./gameResult";
import type { WeekInfo } from "./week";

export type OwnedTeam = {
  teamId: number;
  teamName: string;
  conferenceName: string | null
}

export type TeamSearchResult = {
  teamId: number;
  teamName: string;
  conferenceName: string | null;
  ownerMemberId: number | null;
  ownerTeamName: string | null;
  ownerDisplayName: string | null;
};

export type TeamSearchResponse = {
  leagueId: number;
  query: string;
  teams: TeamSearchResult[];
};

export type MemberWeekSchedule = {
  ownedTeams: OwnedTeam[];
  week: WeekInfo | null;
  games: GameResult[];
};

type ConferenceGame = {
  id: number;
  externalGameId: string;

  sport: number;
  sportSeasonId: number;
  seasonPhaseId: number | null;
  roundOrder: number | null;

  date: string;

  homeTeamId: number;
  homeTeamName: string;
  homeScore: number;
  homeInConference: boolean;
  homeOwnerMemberId: number | null;
  homeOwnerTeamName: string | null;
  homeOwnerDisplayName: string | null;

  awayTeamId: number;
  awayTeamName: string;
  awayScore: number;
  awayInConference: boolean;
  awayOwnerMemberId: number | null;
  awayOwnerTeamName: string | null;
  awayOwnerDisplayName: string | null;

  broadcast: string | null;
}

export type ConferenceSchedule = {
  games: ConferenceGame[];
}

type TeamGameView = {
  id: number;
  externalGameId: string;

  sport: number;
  sportSeasonId: number;
  seasonPhaseId: number | null;
  roundOrder: number | null;

  date: string;

  homeTeamId: number;
  homeTeamName: string;
  homeScore: number;

  awayTeamId: number;
  awayTeamName: string;
  awayScore: number;

  isHome: boolean;
  opponentTeamId: number;
  opponentTeamName: string;
  ownerMemberId: number | null;
  ownerTeamName: string | null;
  ownerDisplayName: string | null;

  broadcast: string | null;
};

export type TeamSeasonSchedule = {
  games: TeamGameView[];
}
