// src/api/schedule.ts
import type { ConferenceSchedule, MemberWeekSchedule, TeamSeasonSchedule } from "../types/schedule";

const API_BASE_URL = import.meta.env.API_BASE_URL ?? "http://127.0.0.1:5050";

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

  console.log(API_BASE_URL)

  const res = await fetch(`${API_BASE_URL}/api/schedule/all`, {
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

  const res = await fetch(`${API_BASE_URL}/api/schedule/conferenceGamesByWeek`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    throw new Error(`Failed to get schedules for conference: ${res.status}`);
  }

  const data = (await res.json()) as ConferenceSchedule;
  console.log(data)
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

  console.log(API_BASE_URL);

  const res = await fetch(`${API_BASE_URL}/api/schedule/teamGamesBySeason`, {
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
