// src/api/schedule.ts
import type { OwnedTeam } from "../types/schedule";
import { apiFetch, API_BASE_URL } from "./client";

export async function getMemberTeams(
  memberId: number,
  weekNumber: number,
  leagueId: number
): Promise<OwnedTeam[]> {
  const payload = {
    "leagueId": leagueId,
    "weekNumber": weekNumber,
    "memberId": memberId,
  };

  const res = await apiFetch(`${API_BASE_URL}/api/roster/memberTeams`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    throw new Error(`Failed to get member teams: ${res.status}`);
  }

  const data = (await res.json()) as OwnedTeam[];
  return data;
}

export async function getAvailableTeams(
  weekNumber: number,
  leagueId: number
): Promise<OwnedTeam[]> {
  const payload = {
    "leagueId": leagueId,
    "weekNumber": weekNumber,
  };

  const res = await apiFetch(`${API_BASE_URL}/api/roster/availableTeams`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    throw new Error(`Failed to get available teams: ${res.status}`);
  }

  const data = (await res.json()) as OwnedTeam[];
  return data;
}
