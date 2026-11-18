import { safeResponse, safeJson, READ_ERROR } from "./safeError";
import type { Sport } from "../types/sport";
import { apiFetch, API_BASE_URL } from "./client";

export async function getSports(): Promise<Sport[]> {

  const res = await safeResponse(apiFetch(`${API_BASE_URL}/api/sports`, {
    method: "GET"
  }), READ_ERROR);

  const data = (await safeJson(res, READ_ERROR)) as Sport[];
  return data;
}
