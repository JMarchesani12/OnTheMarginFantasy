export type TierAdjustment = {
  rawMargin: number;
  adjustedMargin: number;
  tierGap: number | null;
  minimumTierGap: number;
  applied: boolean;
  multiplier: number;
  tone: "neutral" | "red" | "green";
  explanation: string | null;
};
export type RuleSummary = {
  version: string;
  summary: string;
  tierAdjustment: { minimumTierGap: number };
};
export type LeagueRules = RuleSummary & {
  leagueId: number;
  leagueName: string;
  sportId: number;
  sportName: string;
  seasonYear: number;
  sections: { heading: string; paragraphs: string[] }[];
  settings: Record<string, unknown>;
  tiers: { tier: number; teams: { teamId: number; teamName: string; tier: number }[] }[];
  examples: TierAdjustment[];
};
