import { apiFetch, API_BASE_URL } from "./client";
import { safeResponse, safeJson, READ_ERROR } from "./safeError";
import { createTeamSearchCatalogCache } from "../lib/teamSearchCatalogCache";
import type { TeamSearchCatalog } from "../types/teamSearch";

const cache = createTeamSearchCatalogCache(async () => {
  const response = await safeResponse(apiFetch(`${API_BASE_URL}/api/team-search/catalog`, { method: "GET", cache: "no-store" }), READ_ERROR);
  const data = await safeJson(response, READ_ERROR) as TeamSearchCatalog;
  if (!Array.isArray(data.teams) || data.teams.some(team => !Number.isInteger(team.teamId)
    || !Number.isInteger(team.schoolId) || typeof team.teamName !== "string"
    || !Array.isArray(team.aliases) || team.aliases.some(alias => typeof alias !== "string"))) {
    throw new Error("Invalid team search names response");
  }
  return data;
});

export const getTeamSearchCatalog = (force = false) => cache.read(force);
