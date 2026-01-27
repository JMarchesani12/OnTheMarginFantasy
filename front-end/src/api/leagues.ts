import type { ApproveRequestResponse, CreateLeaguePayload, GetConferences, GetRequestResponse, League, LeagueSearchResult, RequestResponse, SingleLeague, UpdateLeague } from "../types/league";
import type { LeagueMember, UpdateLeagueMember } from "../types/leagueMember";
import { apiFetch, API_BASE_URL } from "./client";

export async function getLeague(leagueId: number): Promise<SingleLeague> {
  const res = await apiFetch(`${API_BASE_URL}/api/league/${leagueId}`, {
    method: "GET"
  });

  if (!res.ok) {
    throw new Error(`Failed to get league: ${res.status}`);
  }

  return res.json();
}

export async function createLeague(
  payload: CreateLeaguePayload
): Promise<unknown> {
  const res = await apiFetch(`${API_BASE_URL}/api/league/create`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    throw new Error(`Failed to create league: ${res.status}`);
  }

  return res.json();
}

export async function updateLeague(
  payload: UpdateLeague,
  leagueId: number
): Promise<UpdateLeague> {
  const res = await apiFetch(`${API_BASE_URL}/api/league/${leagueId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    throw new Error(`Failed to update league: ${res.status}`);
  }

  return res.json() as UpdateLeague;
}

export async function getLeaguesForUser(
  userId: number | null, type: string
): Promise<League[]> {
    const body = {
        "userId": userId,
        "type": type
    }
  const res = await apiFetch(`${API_BASE_URL}/api/league/byUser`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    throw new Error(`Failed to get leagues: ${res.status}`);
  }

  return res.json();
}

export async function getMembersOfLeague(
  leagueId: number
): Promise<LeagueMember[]> {
  const res = await apiFetch(`${API_BASE_URL}/api/league/${leagueId}/members`, {
    method: "GET",
  });

  if (!res.ok) {
    throw new Error(`Failed to get league members: ${res.status}`);
  }

  return res.json();
}

export async function getConferences(
  leagueId: number
): Promise<GetConferences> {
  const res = await apiFetch(`${API_BASE_URL}/api/league/${leagueId}/conferences`, {
    method: "GET",
  });

  if (!res.ok) {
    throw new Error(`Failed to get conferences: ${res.status}`);
  }

  return res.json();
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
  const res = await apiFetch(`${API_BASE_URL}/api/league/${leagueId}/joinRequest`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    throw new Error(`Failed to submit request: ${res.status}`);
  }

  return res.json();
}

export async function approveRequestToJoinLeague(
  leagueId: number,
  requestId: number,
  userId: number,
): Promise<ApproveRequestResponse> {
  const body = {
        "actingUserId": userId
    }
  const res = await apiFetch(`${API_BASE_URL}/api/league/${leagueId}/joinRequests/${requestId}/approve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    throw new Error(`Failed to approve request: ${res.status}`);
  }

  return res.json();
}

export async function denyRequestToJoinLeague(
  leagueId: number,
  requestId: number,
  userId: number,
): Promise<RequestResponse> {
  const body = {
        "actingUserId": userId
    }
  const res = await apiFetch(`${API_BASE_URL}/api/league/${leagueId}/joinRequests/${requestId}/deny`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    throw new Error(`Failed to deny request: ${res.status}`);
  }

  return res.json();
}

export async function cancelRequestToJoinLeague(
  leagueId: number,
  requestId: number,
  userId: number,
): Promise<RequestResponse> {
  const body = {
        "userId": userId
    }
  const res = await apiFetch(`${API_BASE_URL}/api/league/${leagueId}/joinRequests/${requestId}/cancel`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    throw new Error(`Failed to cancel request: ${res.status}`);
  }

  return res.json();
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
  const res = await apiFetch(`${API_BASE_URL}/api/league/${leagueId}/joinRequests`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    throw new Error(`Failed to get requests: ${res.status}`);
  }

  return res.json();
}

export async function removeLeagueMember(
  leagueId: number,
  memberId: number,
  actingUserId: number
) {
  const res = await apiFetch(`${API_BASE_URL}/api/league/${leagueId}/members/${memberId}`, {
    method: "DELETE",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ actingUserId, shiftDraftOrder: true }),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => null);
    throw new Error(err?.message ?? `Failed to remove member: ${res.status}`);
  }

  return res.json();
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

  const res = await apiFetch(url.toString());

  if (!res.ok) {
    throw new Error(`Failed to get leagues: ${res.status}`);
  }

  return res.json();
}

export async function deleteLeague(
  leagueId: number,
  actingUserId: number
) {
  const res = await apiFetch(`${API_BASE_URL}/api/league/${leagueId}`, {
    method: "DELETE",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ actingUserId }),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => null);
    throw new Error(err?.message ?? `Failed to delete league`);
  }

  return res.json();
}

export async function updateLeagueMember(
  memberId: number,
  teamName?: string,
  draftOrder?: number,
  seasonPoints?: number
) {

  const payload: UpdateLeagueMember = {
    teamName: teamName,
    draftOrder: draftOrder,
    seasonPoints: seasonPoints
  }
  const res = await apiFetch(`${API_BASE_URL}/api/league/leagueMember/${memberId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => null);
    throw new Error(err?.message ?? `Failed to update league member`);
  }

  return res.json();
}
