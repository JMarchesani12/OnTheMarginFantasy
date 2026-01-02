import type { Sport } from "../types/sport";
import { apiFetch, API_BASE_URL } from "./client";

export async function getSports(): Promise<Sport[]> {

  const res = await apiFetch(`${API_BASE_URL}/api/sports`, {
    method: "GET"
  });

  if (!res.ok) {
    throw new Error(`Failed to get sports: ${res.status}`);
  }

  const data = (await res.json()) as Sport[];
  return data;
}
