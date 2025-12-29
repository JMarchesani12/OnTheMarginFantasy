import type { DraftPickResponse } from "../types/roster";

const API_BASE_URL = import.meta.env.API_BASE_URL ?? "http://127.0.0.1:5050";

type CreateDraftPickBody = {
  leagueId: number
  memberId: number;
  sportTeamId: number;
};

export async function createDraftPick(
  memberId: number,
  leagueId: number,
  sportTeamId: number
): Promise<DraftPickResponse> {
  const payload: CreateDraftPickBody = {
    leagueId,
    memberId,
    sportTeamId,
  };

  const res = await fetch(`${API_BASE_URL}/api/draft/pick`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    throw new Error(`Failed to submit draft pick: ${res.status}`);
  }

  const data = (await res.json()) as DraftPickResponse;
  return data;
}

export async function getSportRounds(sportId: number) {
  const res = await fetch(`${API_BASE_URL}/api/draft/rounds/${sportId}`)
  if (!res.ok) {
    throw new Error(`Failed to submit draft pick: ${res.status}`);
  }

  const data = (await res.json());
  return data['rounds'];
}