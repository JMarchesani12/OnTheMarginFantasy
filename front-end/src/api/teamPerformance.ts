import { apiFetch, API_BASE_URL } from "./client";
import { safeResponse, safeJson, READ_ERROR } from "./safeError";
import type { TeamPerformanceResponse } from "../types/teamPerformance";

export async function getTeamPerformance(leagueId: number, weekNumber: number, signal?: AbortSignal): Promise<TeamPerformanceResponse> {
  const response = await safeResponse(apiFetch(`${API_BASE_URL}/api/roster/teamPerformance`, {
    method: "POST", signal, headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ leagueId, weekNumber }),
  }), READ_ERROR);
  return await safeJson(response, READ_ERROR) as TeamPerformanceResponse;
}
