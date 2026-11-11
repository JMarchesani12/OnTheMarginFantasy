import { safeResponse, safeJson, WRITE_UNCERTAIN, READ_ERROR } from "./safeError";
import type { DraftPickResponse } from "../types/roster";
import type { DraftSnapshot } from "../types/draft";
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

  const res = await safeResponse(apiFetch(`${API_BASE_URL}/api/draft/pick`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  }), WRITE_UNCERTAIN);

  const data = (await safeJson(res, WRITE_UNCERTAIN)) as DraftPickResponse;
  return data;
}

export async function getSportRounds(sportId: number) {
  const res = await safeResponse(apiFetch(`${API_BASE_URL}/api/draft/rounds/${sportId}`), READ_ERROR)

  const data = (await safeJson(res, READ_ERROR));
  return data['rounds'];
}

export async function setDraftOrder(leagueId: number, memberIdsInOrder: number[]) {
  const payload = {
    "memberIdsInOrder": memberIdsInOrder
  }
  const res = await safeResponse(apiFetch(`${API_BASE_URL}/api/league/${leagueId}/draft/order`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  }), WRITE_UNCERTAIN)

  const data = (await safeJson(res, WRITE_UNCERTAIN));
  return data;
}

export async function startDraft(leagueId: number): Promise<DraftSnapshot> {
  const payload = {
    "leagueId": leagueId
  }
  const res = await safeResponse(apiFetch(`${API_BASE_URL}/api/draft/start`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  }), WRITE_UNCERTAIN)

  const data = (await safeJson(res, WRITE_UNCERTAIN)) as DraftSnapshot;
  return data;
}

export async function pauseDraft(leagueId: number): Promise<DraftSnapshot> {
  const payload = {
    "leagueId": leagueId
  }
  const res = await safeResponse(apiFetch(`${API_BASE_URL}/api/draft/pause`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  }), WRITE_UNCERTAIN)

  const data = (await safeJson(res, WRITE_UNCERTAIN)) as DraftSnapshot;
  return data;
}

export async function resumeDraft(leagueId: number): Promise<DraftSnapshot> {
  const payload = {
    "leagueId": leagueId
  }
  const res = await safeResponse(apiFetch(`${API_BASE_URL}/api/draft/resume`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  }), WRITE_UNCERTAIN)

  const data = (await safeJson(res, WRITE_UNCERTAIN)) as DraftSnapshot;
  return data;
}

export async function finalizeDraft(
  leagueId: number,
  actingUserId: number
): Promise<{ draftComplete: boolean; leagueId: number; leagueStatus: string | null }> {
  const payload = {
    leagueId,
    actingUserId,
  };
  const res = await safeResponse(apiFetch(`${API_BASE_URL}/api/draft/finalize`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  }), WRITE_UNCERTAIN);

  return await safeJson(res, WRITE_UNCERTAIN);
}

export async function getDraftState(leagueId: number, signal?: AbortSignal): Promise<DraftSnapshot> {
  const res = await safeResponse(apiFetch(`${API_BASE_URL}/api/draft/state/${leagueId}`, { signal }), READ_ERROR)

  const data = (await safeJson(res, READ_ERROR)) as DraftSnapshot;
  return data;
}
