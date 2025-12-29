import type { GameResult } from "./gameResult";
import type { WeekInfo } from "./week";

export type OwnedTeam = {
  teamId: number;
  teamName: string;
  conferenceName: string | null
}

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

  awayTeamId: number;
  awayTeamName: string;
  awayScore: number;
  awayInConference: boolean;

  broadcast: string | null;
  time: string | null;
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

  broadcast: string | null;
  time: string | null;
};

export type TeamSeasonSchedule = {
  games: TeamGameView[];
}