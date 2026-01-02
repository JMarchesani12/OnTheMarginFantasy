// src/api/schedule.ts
import type { WeekStandings } from "../types/scoring";
import { apiFetch, API_BASE_URL } from "./client";

export async function getScoresForWeek(
  weekNumbers: number[],
  leagueId: number
): Promise<WeekStandings> {

const payload = {
    "weekNumbers": weekNumbers
};

  const res = await apiFetch(`${API_BASE_URL}/api/league/${leagueId}/pointsAwarded`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });

  if (!res.ok) {
    throw new Error(`Failed to get schedule for member: ${res.status}`);
  }

  const data = (await res.json()) as WeekStandings;
  return data;
}
