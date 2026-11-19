import type { TeamSearchCatalog } from "../types/teamSearch.ts";

export function createTeamSearchCatalogCache(load: () => Promise<TeamSearchCatalog>, now = Date.now) {
  let cached: TeamSearchCatalog | null = null;
  let expiresAt = 0;
  let pending: Promise<TeamSearchCatalog> | null = null;
  return {
    read(force = false): Promise<TeamSearchCatalog> {
      if (!force && cached && now() < expiresAt) return Promise.resolve(cached);
      if (pending) return pending;
      pending = load().then(value => {
        cached = value;
        expiresAt = now() + 300_000;
        pending = null;
        return value;
      }, error => {
        pending = null;
        throw error;
      });
      return pending;
    },
  };
}
