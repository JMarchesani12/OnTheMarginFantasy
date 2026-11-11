import { safeResponse, safeJson, READ_ERROR } from "./safeError";
// src/api/schedule.ts
import type {
  ConferenceSchedule,
  MemberWeekSchedule,
  TeamSearchResponse,
  TeamSeasonSchedule,
} from "../types/schedule";
import { apiFetch, API_BASE_URL } from "./client";

export async function getScheduleForMemberForWeek(
  memberId: number,
  weekNumber: number,
  leagueId: number
): Promise<MemberWeekSchedule> {
  const payload = {
    "leagueId": leagueId,
    "weekNumber": weekNumber,
    "memberId": memberId,
  };

  const res = await safeResponse(apiFetch(`${API_BASE_URL}/api/schedule/all`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  }), READ_ERROR);

  const data = (await safeJson(res, READ_ERROR)) as MemberWeekSchedule;
  return data;
}

export async function getScheduleForConferenceForWeek(
  weekNumber: number,
  leagueId: number,
  seasonYear: number,
  sportConferenceId: number
): Promise<ConferenceSchedule> {
  const payload = {
    "leagueId": leagueId,
    "weekNumber": weekNumber,
    "seasonYear": seasonYear,
    "sportConferenceId": sportConferenceId
  };

  const res = await safeResponse(apiFetch(`${API_BASE_URL}/api/schedule/conferenceGamesByWeek`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  }), READ_ERROR);

  const data = (await safeJson(res, READ_ERROR)) as ConferenceSchedule;
  return data;
}

export async function getScheduleForTeam(
  seasonYear: number,
  sportTeamId: number,
  leagueId?: number
): Promise<TeamSeasonSchedule> {
  const payload = {
    seasonYear,
    sportTeamId,
    ...(leagueId ? { leagueId } : {}),
  };

  const res = await safeResponse(apiFetch(`${API_BASE_URL}/api/schedule/teamGamesBySeason`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  }), READ_ERROR);

  const data = (await safeJson(res, READ_ERROR)) as TeamSeasonSchedule;
  return data;
}

export async function searchTeamsForLeague(
  leagueId: number,
  query: string,
  limit = 20
): Promise<TeamSearchResponse> {
  const res = await safeResponse(apiFetch(`${API_BASE_URL}/api/schedule/teamSearch`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ leagueId, query, limit }),
  }), READ_ERROR);

  const data = (await safeJson(res, READ_ERROR)) as TeamSearchResponse;
  return data;
}
