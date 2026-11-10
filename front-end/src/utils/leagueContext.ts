import { getLeague, getLeaguesForUser } from "../api/leagues";
import { mapLeagueFromResponse, normalizeLeaguesResponse } from "./leagueMapping";

/** Shared list/find/fallback policy. A fallback read never establishes membership. */
export async function resolveLeagueContext(leagueId: number, userId: number, signal: AbortSignal) {
  const response = await getLeaguesForUser(userId, "all", signal);
  signal.throwIfAborted();
  const found = normalizeLeaguesResponse(response).find(item => item.leagueId === leagueId);
  const league = mapLeagueFromResponse(found ?? await getLeague(leagueId, signal));
  signal.throwIfAborted();
  if (league.leagueId !== leagueId) throw new Error("League response does not match the requested league.");
  const isMember = !!found && Number.isSafeInteger(league.memberId) && league.memberId > 0;
  return { league: isMember ? league : { ...league, memberId: 0 }, isMember };
}
