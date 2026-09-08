export type SeasonLabel = `${number}-${string}`;

export type ConferenceOverrides = Record<string, Record<string, string>>;

export type WarningCode =
  | "duplicate_event_id"
  | "duplicate_game"
  | "unresolved_conference"
  | "unmatched_override"
  | "ambiguous_override"
  | "conflicting_override"
  | "missing_score"
  | "invalid_score"
  | "same_team"
  | "unknown_conference_name"
  | "empty_date_range"
  | "low_game_count"
  | "invalid_espn_response"
  | "tie_game"
  | "same_conference";

export interface WarningItem {
  code: WarningCode;
  message: string;
  season?: string;
  eventId?: string;
  dateRange?: string;
}

export interface WarningCollector {
  add: (warning: WarningItem) => void;
  all: () => WarningItem[];
}

export interface SeasonRange {
  label: SeasonLabel;
  start: string;
  end: string;
}

export interface DateRange {
  start: string;
  end: string;
}

export interface EspnTeamInfo {
  id: string;
  displayName: string;
  shortDisplayName?: string;
  abbreviation?: string;
  conference?: string | null;
}

export interface OverrideMatchWarning {
  season: string;
  teamName: string;
  conference: string;
}

export interface ResolvedConferenceInput {
  season: string;
  teamId: string;
  espnConference: string | null;
}

export interface ConferenceResolver {
  resolveConference: (input: ResolvedConferenceInput) => string | null;
  unmatchedOverrides: OverrideMatchWarning[];
  ambiguousOverrides: Array<OverrideMatchWarning & { matchedTeamIds: string[] }>;
  unknownConferenceNames: string[];
  overrideTeamIdsBySeason: Map<string, Map<string, string>>;
}

export interface NormalizedTeamGame {
  id: string;
  name: string;
  conference: string;
  score: number;
}

export interface NormalizedGame {
  season: string;
  date: string;
  espnEventId: string;
  teamA: NormalizedTeamGame;
  teamB: NormalizedTeamGame;
  winnerTeamId: string;
  loserTeamId: string;
  margin: number;
  neutralSite: boolean | null;
}

export interface StatLine {
  conference: string;
  opponent?: string;
  wins: number;
  losses: number;
  games: number;
  pointsFor: number;
  pointsAgainst: number;
  totalMargin: number;
  winPercentage: number;
  averageMargin: number;
}

export interface AnalysisResult {
  aggregate: Map<string, StatLine>;
  vsConference: Map<string, Map<string, StatLine>>;
  bySeason: Map<string, Map<string, StatLine>>;
  vsConferenceBySeason: Map<string, Map<string, Map<string, StatLine>>>;
}

export interface CliOptions {
  seasons: SeasonRange[];
  rangeDays: number;
  cacheDir: string;
  outputDir: string;
  overridesPath: string;
}

export interface RawEspnEvent {
  id?: unknown;
  date?: unknown;
  status?: unknown;
  competitions?: unknown;
}

export interface ParsedEspnTeam {
  id: string;
  name: string;
  shortName: string | null;
  abbreviation: string | null;
  conference: string | null;
  score: number | null;
}

export interface ParsedEspnGame {
  season: string;
  date: string;
  espnEventId: string;
  completed: boolean;
  neutralSite: boolean | null;
  competitors: [ParsedEspnTeam, ParsedEspnTeam] | null;
  statusDescription: string | null;
}
