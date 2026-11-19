import { useEffect, useState } from "react";
import { getTeamPerformance } from "../api/teamPerformance";
import type { TeamPerformance } from "../types/teamPerformance";

const EMPTY: Record<number, TeamPerformance> = {};
export function useTeamPerformance(leagueId: number, weekNumber: number, identity: unknown = leagueId) {
  const [result, setResult] = useState<{
    leagueId: number; weekNumber: number; identity: unknown;
    teams: Record<number, TeamPerformance>; failed: boolean;
  } | null>(null);
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    let cancelled = false;
    getTeamPerformance(leagueId, weekNumber, controller.signal).then(data => {
      if (!cancelled) setResult({ leagueId, weekNumber, identity,
        teams: Object.fromEntries(data.teams.map(team => [team.teamId, team])), failed: false });
    }).catch(() => {
      if (!cancelled) setResult({ leagueId, weekNumber, identity, teams: EMPTY, failed: true });
    });
    return () => { cancelled = true; controller.abort(); };
  }, [leagueId, weekNumber, identity, revision]);
  const current = result?.leagueId === leagueId && result.weekNumber === weekNumber && result.identity === identity ? result : null;
  return { teams: current?.teams ?? EMPTY, loading: !current, failed: current?.failed ?? false,
    retry: () => { setResult(null); setRevision(value => value + 1); } };
}
