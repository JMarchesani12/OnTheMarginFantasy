import { safeResponse, safeJson, READ_ERROR, CREATE_LEAGUE_UNCERTAIN, WRITE_UNCERTAIN, JOIN_LEAGUE_UNCERTAIN } from "./safeError";

import type { LeagueRules } from "../types/leagueRules";
import type { ApproveRequestResponse, CreateLeaguePayload, GetConferences, GetRequestResponse, League, LeagueSearchResult, RequestResponse, SingleLeague, UpdateLeague } from "../types/league";
import type { LeagueMember, LeagueMemberPreview, UpdateLeagueMember } from "../types/leagueMember";
import { apiFetch, API_BASE_URL } from "./client";

export type LeaguePreview = Pick<LeagueSearchResult, "id" | "name" | "sport" | "commissionerDisplayName">;

export async function getLeaguePreview(leagueId: number, signal?: AbortSignal): Promise<LeaguePreview> {
  const res = await safeResponse(apiFetch(`${API_BASE_URL}/api/league/${leagueId}?view=preview`, { method: "GET", signal }), READ_ERROR);

  return safeJson(res, READ_ERROR);
}

export async function getLeague(leagueId: number, signal?: AbortSignal): Promise<SingleLeague> {
  const res = await safeResponse(apiFetch(`${API_BASE_URL}/api/league/${leagueId}?view=full`, {
    method: "GET",
    signal,
  }), READ_ERROR);

  return safeJson(res, READ_ERROR);
}

export async function createLeague(
  payload: CreateLeaguePayload
): Promise<unknown> {
  const res = await safeResponse(apiFetch(`${API_BASE_URL}/api/league/create`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  }), CREATE_LEAGUE_UNCERTAIN);

  return safeJson(res, CREATE_LEAGUE_UNCERTAIN);
}

export async function updateLeague(
  payload: UpdateLeague,
  leagueId: number
): Promise<UpdateLeague> {
  const res = await safeResponse(apiFetch(`${API_BASE_URL}/api/league/${leagueId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  }), WRITE_UNCERTAIN);

  return safeJson(res, WRITE_UNCERTAIN) as UpdateLeague;
}

export async function getLeaguesForUser(
  userId: number | null, type: string, signal?: AbortSignal
): Promise<League[]> {
    const body = {
        "userId": userId,
        "stage": type
    }
  const res = await safeResponse(apiFetch(`${API_BASE_URL}/api/league/byUser`, {
    method: "POST",
    signal,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  }), READ_ERROR);

  return safeJson(res, READ_ERROR);
}

export async function getMembersOfLeague(
  leagueId: number,
  signal?: AbortSignal
): Promise<LeagueMember[]> {
  const res = await safeResponse(apiFetch(`${API_BASE_URL}/api/league/${leagueId}/members?view=full`, {
    signal,
    method: "GET",
  }), READ_ERROR);

  return safeJson(res, READ_ERROR);
}

export async function getMemberPreviewsOfLeague(
  leagueId: number,
  signal?: AbortSignal
): Promise<LeagueMemberPreview[]> {
  const res = await safeResponse(apiFetch(`${API_BASE_URL}/api/league/${leagueId}/members?view=preview`, { signal }), READ_ERROR);

  return safeJson(res, READ_ERROR);
}

export async function getConferences(
  leagueId: number
): Promise<GetConferences> {
  const res = await safeResponse(apiFetch(`${API_BASE_URL}/api/league/${leagueId}/conferences`, {
    method: "GET",
  }), READ_ERROR);

  return safeJson(res, READ_ERROR);
}

export async function requestToJoinLeague(
  leagueId: number,
  userId: number,
  message?: string,
  teamName?: string
): Promise<RequestResponse> {
  const body = {
        "userId": userId,
        "message": message,
        "teamName": teamName
    }
  const res = await safeResponse(apiFetch(`${API_BASE_URL}/api/league/${leagueId}/joinRequest`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  }), JOIN_LEAGUE_UNCERTAIN);

  return safeJson(res, JOIN_LEAGUE_UNCERTAIN);
}

export async function approveRequestToJoinLeague(
  leagueId: number,
  requestId: number,
  userId: number,
): Promise<ApproveRequestResponse> {
  const body = {
        "actingUserId": userId
    }
  const res = await safeResponse(apiFetch(`${API_BASE_URL}/api/league/${leagueId}/joinRequests/${requestId}/approve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  }), WRITE_UNCERTAIN);

  return safeJson(res, WRITE_UNCERTAIN);
}

export async function denyRequestToJoinLeague(
  leagueId: number,
  requestId: number,
  userId: number,
): Promise<RequestResponse> {
  const body = {
        "actingUserId": userId
    }
  const res = await safeResponse(apiFetch(`${API_BASE_URL}/api/league/${leagueId}/joinRequests/${requestId}/deny`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  }), WRITE_UNCERTAIN);

  return safeJson(res, WRITE_UNCERTAIN);
}

export async function cancelRequestToJoinLeague(
  leagueId: number,
  requestId: number,
  userId: number,
): Promise<RequestResponse> {
  const body = {
        "userId": userId
    }
  const res = await safeResponse(apiFetch(`${API_BASE_URL}/api/league/${leagueId}/joinRequests/${requestId}/cancel`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  }), WRITE_UNCERTAIN);

  return safeJson(res, WRITE_UNCERTAIN);
}

export async function getRequestsToJoinLeague(
  leagueId: number,
  userId: number,
  status?: string
): Promise<GetRequestResponse[]> {
  const body = {
        "actingUserId": userId,
        "status": status
    }
  const res = await safeResponse(apiFetch(`${API_BASE_URL}/api/league/${leagueId}/joinRequests`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  }), READ_ERROR);

  return safeJson(res, READ_ERROR);
}

export async function removeLeagueMember(
  leagueId: number,
  memberId: number,
  actingUserId: number
) {
  const res = await safeResponse(apiFetch(`${API_BASE_URL}/api/league/${leagueId}/members/${memberId}`, {
    method: "DELETE",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ actingUserId, shiftDraftOrder: true }),
  }), WRITE_UNCERTAIN);

  return safeJson(res, WRITE_UNCERTAIN);
}

export async function searchLeagues(params: {
  query: string;
  sportId?: number;
  limit?: number;
  offset?: number;
}): Promise<LeagueSearchResult[]> {
  const { query, sportId, limit = 20, offset = 0 } = params;

  const url = new URL(`${API_BASE_URL}/api/leagues/search`);
  url.searchParams.set("q", query);
  url.searchParams.set("limit", String(limit));
  url.searchParams.set("offset", String(offset));

  if (sportId !== undefined) {
    url.searchParams.set("sportId", String(sportId));
  }

  const res = await safeResponse(apiFetch(url.toString()), READ_ERROR);

  return safeJson(res, READ_ERROR);
}

export async function deleteLeague(
  leagueId: number,
  actingUserId: number
) {
  const res = await safeResponse(apiFetch(`${API_BASE_URL}/api/league/${leagueId}`, {
    method: "DELETE",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ actingUserId }),
  }), WRITE_UNCERTAIN);

  return safeJson(res, WRITE_UNCERTAIN);
}

export async function updateLeagueMember(
  memberId: number,
  teamName: string
) {

  const payload: UpdateLeagueMember = {
    teamName: teamName
  }
  const res = await safeResponse(apiFetch(`${API_BASE_URL}/api/league/leagueMember/${memberId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  }), WRITE_UNCERTAIN);

  return safeJson(res, WRITE_UNCERTAIN);
}

export async function getLeagueRules(leagueId: number): Promise<LeagueRules> {
  const res = await safeResponse(apiFetch(`${API_BASE_URL}/api/league/${leagueId}/rules`), READ_ERROR);

  return safeJson(res, READ_ERROR);
}
