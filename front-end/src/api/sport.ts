import type { Sport } from "../types/sport";

const API_BASE_URL = import.meta.env.API_BASE_URL ?? "http://127.0.0.1:5050";

export async function getSports(): Promise<Sport[]> {

  const res = await fetch(`${API_BASE_URL}/api/sports`, {
    method: "GET"
  });

  if (!res.ok) {
    throw new Error(`Failed to get sports: ${res.status}`);
  }

  const data = (await res.json()) as Sport[];
  return data;
}