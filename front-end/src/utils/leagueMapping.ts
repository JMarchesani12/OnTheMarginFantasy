import type { League, SingleLeague } from "../types/league";

export const normalizeLeaguesResponse = (response: unknown): League[] => {
  if (Array.isArray(response)) {
    return response as League[];
  }

  if (
    response &&
    typeof response === "object" &&
    Array.isArray((response as { leagues?: League[] }).leagues)
  ) {
    return (response as { leagues: League[] }).leagues;
  }

  return [];
};

export const normalizeLeagueSettings = (value: unknown) => {
  if (!value) return undefined;
  if (typeof value === "string") {
    try {
      return JSON.parse(value) as League["settings"];
    } catch {
      return undefined;
    }
  }
  return value as League["settings"];
};

export const mapLeagueFromResponse = (
  payload: SingleLeague | League | { league?: SingleLeague | League }
): League => {
  const data =
    (payload as { league?: SingleLeague | League }).league ?? payload;

  if ((data as League).leagueId) {
    const leagueData = data as League;
    return {
      ...leagueData,
      settings: normalizeLeagueSettings(leagueData.settings) ?? leagueData.settings,
    };
  }

  const single = data as SingleLeague;
  const status = single.status ?? "Pre-Draft";
  const commissionerId =
    (single as { commissionerId?: number }).commissionerId ??
    (single as { commissioner?: number }).commissioner ??
    0;

  return {
    leagueId: single.id,
    leagueCreatedAt: single.createdAt,
    leagueName: single.name,
    sport: String(single.sport),
    maxPlayersToHaveMaxRounds: 0,
    numPlayers: single.numPlayers,
    status,
    settings: normalizeLeagueSettings(single.settings) ?? {
      bonuses: {},
      transactions: { tradeVeto: { enabled: false, requiredVetoCount: 0 } },
      draft: {
        draftType: "SNAKE",
        selectionTime: 60,
        numberOfRounds: 0,
        timeoutAction: "AUTO-SKIP",
        graceSeconds: 0,
      },
    },
    updatedAt: single.updatedAt ?? single.createdAt,
    draftDate: single.draftDate,
    tradeDeadline: single.tradeDeadline,
    freeAgentDeadline: single.freeAgentDeadline,
    seasonYear: single.seasonYear,
    commissionerId,
    commissionerDisplayName:
      (single as { commissionerDisplayName?: string })
        .commissionerDisplayName ?? "",
    memberId: 0,
    teamName: null,
    draftOrder: null,
    seasonPoints: null,
    currentWeekEndDate: null,
    currentWeekId: null,
    currentWeekNumber: null,
    currentWeekStartDate: null,
  };
};
