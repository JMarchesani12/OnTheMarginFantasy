import { safeResponse, safeJson, READ_ERROR } from "./safeError";
// src/api/schedule.ts
import type { WeekStandings } from "../types/scoring";
import { apiFetch, API_BASE_URL } from "./client";

export async function getScoresForWeek(
  weekNumbers: number[],
  leagueId: number,
  signal?: AbortSignal
): Promise<WeekStandings> {

const payload = {
    "weekNumbers": weekNumbers
};

  const res = await safeResponse(apiFetch(`${API_BASE_URL}/api/league/${leagueId}/pointsAwarded`, {
    signal,
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  }), READ_ERROR);

  const data = (await safeJson(res, READ_ERROR)) as WeekStandings;
  return data;
}
