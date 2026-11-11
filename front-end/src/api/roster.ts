import { safeResponse, safeJson, READ_ERROR } from "./safeError";
// src/api/schedule.ts
import type { OwnedTeam } from "../types/schedule";
import { apiFetch, API_BASE_URL } from "./client";

export async function getMemberTeams(
  memberId: number,
  weekNumber: number,
  leagueId: number,
  signal?: AbortSignal
): Promise<OwnedTeam[]> {
  const payload = {
    "leagueId": leagueId,
    "weekNumber": weekNumber,
    "memberId": memberId,
  };

  const res = await safeResponse(apiFetch(`${API_BASE_URL}/api/roster/memberTeams`, {
    signal,
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  }), READ_ERROR);

  const data = (await safeJson(res, READ_ERROR)) as OwnedTeam[];
  return data;
}

export async function getAvailableTeams(
  weekNumber: number,
  leagueId: number,
  signal?: AbortSignal
): Promise<OwnedTeam[]> {
  const payload = {
    "leagueId": leagueId,
    "weekNumber": weekNumber,
  };

  const res = await safeResponse(apiFetch(`${API_BASE_URL}/api/roster/availableTeams`, {
    signal,
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  }), READ_ERROR);

  const data = (await safeJson(res, READ_ERROR)) as OwnedTeam[];
  return data;
}
