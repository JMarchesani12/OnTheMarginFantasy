// src/api/schedule.ts
import type { ConferenceSchedule, MemberWeekSchedule, TeamSeasonSchedule } from "../types/schedule";
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

  const res = await apiFetch(`${API_BASE_URL}/api/schedule/all`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    throw new Error(`Failed to get schedule for member: ${res.status}`);
  }

  const data = (await res.json()) as MemberWeekSchedule;
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

  const res = await apiFetch(`${API_BASE_URL}/api/schedule/conferenceGamesByWeek`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    throw new Error(`Failed to get schedules for conference: ${res.status}`);
  }

  const data = (await res.json()) as ConferenceSchedule;
  return data;
}

export async function getScheduleForTeam(
  seasonYear: number,
  sportTeamId: number
): Promise<TeamSeasonSchedule> {
  const payload = {
    seasonYear,
    sportTeamId,
  };

  const res = await apiFetch(`${API_BASE_URL}/api/schedule/teamGamesBySeason`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    throw new Error(`Failed to get schedule for teams: ${res.status}`);
  }

  const data = (await res.json()) as TeamSeasonSchedule;
  return data;
}
