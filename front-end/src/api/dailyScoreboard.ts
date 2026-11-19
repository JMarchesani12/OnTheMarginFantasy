import { apiFetch, API_BASE_URL } from "./client";
import { safeResponse, safeJson, READ_ERROR } from "./safeError";
import type { DailyScoreboardResponse } from "../types/dailyScoreboard";

export async function getDailyScoreboard(leagueId: number, date: string, signal?: AbortSignal): Promise<DailyScoreboardResponse> {
  const response = await safeResponse(apiFetch(`${API_BASE_URL}/api/schedule/dailyScoreboard`, {
    method: "POST", signal, headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ leagueId, date }),
  }), READ_ERROR);
  return await safeJson(response, READ_ERROR) as DailyScoreboardResponse;
}
