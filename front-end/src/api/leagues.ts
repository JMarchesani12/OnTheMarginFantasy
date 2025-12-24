import type { CreateLeaguePayload, GetConferences, League } from "../types/league";
import type { LeagueMember } from "../types/leagueMember";

const API_BASE_URL =
  import.meta.env.API_BASE_URL ?? "http://127.0.0.1:5050";

export async function createLeague(
  payload: CreateLeaguePayload
): Promise<unknown> {
  const res = await fetch(`${API_BASE_URL}/api/league/create`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    throw new Error(`Failed to create league: ${res.status}`);
  }

  return res.json();
}

export async function getLeaguesForUser(
  userId: number | null, type: string
): Promise<League[]> {
    const body = {
        "userId": userId,
        "type": type
    }
  const res = await fetch(`${API_BASE_URL}/api/league/byUser`, {
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
  const res = await fetch(`${API_BASE_URL}/api/league/${leagueId}/members`, {
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
  const res = await fetch(`${API_BASE_URL}/api/league/${leagueId}/conferences`, {
    method: "GET",
  });

  if (!res.ok) {
    throw new Error(`Failed to get conferences: ${res.status}`);
  }

  return res.json();
}