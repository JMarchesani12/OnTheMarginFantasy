import type { OwnedTeam } from "../types/schedule";

export type RawOwnedTeam = Partial<OwnedTeam> & {
  id?: number | string;
  sportTeamId?: number | string;
  name?: string;
  displayName?: string | null;
  conferenceDisplayName?: string | null;
};

export const normalizeOwnedTeams = (teams: RawOwnedTeam[]): OwnedTeam[] =>
  teams.map((team, index) => {
    const resolvedId = team.teamId ?? team.sportTeamId ?? team.id;
    const numericId = Number(resolvedId);
    const fallbackId = -(index + 1);

    return {
      teamId: Number.isFinite(numericId) ? numericId : fallbackId,
      teamName:
        team.teamName ??
        team.displayName ??
        team.name ??
        `Team ${Number.isFinite(numericId) ? numericId : index + 1}`,
      conferenceName: team.conferenceName ?? team.conferenceDisplayName ?? null,
    };
  });
