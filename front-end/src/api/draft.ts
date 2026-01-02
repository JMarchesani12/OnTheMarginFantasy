import type { DraftPickResponse } from "../types/roster";
import { apiFetch, API_BASE_URL } from "./client";

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

  const res = await apiFetch(`${API_BASE_URL}/api/draft/pick`, {
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
  const res = await apiFetch(`${API_BASE_URL}/api/draft/rounds/${sportId}`)
  if (!res.ok) {
    throw new Error(`Failed to submit draft pick: ${res.status}`);
  }

  const data = (await res.json());
  return data['rounds'];
}

export async function setDraftOrder(leagueId: number, memberIdsInOrder: number[]) {
  const payload = {
    "memberIdsInOrder": memberIdsInOrder
  }
  const res = await apiFetch(`${API_BASE_URL}/api/league/${leagueId}/draft/order`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    throw new Error(`Failed to set draft order: ${res.status}`);
  }

  const data = (await res.json());
  return data;
}

export async function startDraft(leagueId: number) {
  const payload = {
    "leagueId": leagueId
  }
  const res = await apiFetch(`${API_BASE_URL}/api/draft/start`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    throw new Error(`Failed to start draft: ${res.status}`);
  }

  const data = (await res.json());
  return data;
}

export async function pauseDraft(leagueId: number) {
  const payload = {
    "leagueId": leagueId
  }
  const res = await apiFetch(`${API_BASE_URL}/api/draft/pause`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    throw new Error(`Failed to start draft: ${res.status}`);
  }

  const data = (await res.json());
  return data;
}

export async function resumeDraft(leagueId: number) {
  const payload = {
    "leagueId": leagueId
  }
  const res = await apiFetch(`${API_BASE_URL}/api/draft/resume`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    throw new Error(`Failed to start draft: ${res.status}`);
  }

  const data = (await res.json());
  return data;
}

export async function getDraftState(leagueId: number) {
  const res = await apiFetch(`${API_BASE_URL}/api/draft/state/${leagueId}`)
  if (!res.ok) {
    throw new Error(`Failed to start draft: ${res.status}`);
  }

  const data = (await res.json());
  return data;
}
