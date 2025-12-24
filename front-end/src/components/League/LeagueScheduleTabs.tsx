// src/components/League/LeagueScheduleTabs.tsx
import { useEffect, useMemo, useState } from "react";
import type { LeagueMember } from "../../types/leagueMember";
import type { MemberWeekSchedule } from "../../types/schedule";
import { getScheduleForMemberForWeek } from "../../api/schedule";
import {
  buildDateHeadersFromWeek,
  getLocalDateKeyForGame,
  type DateHeader,
} from "../../utils/scheduleTable";
import "./LeagueScheduleTabs.css";

type LeagueScheduleTabsProps = {
  leagueId: number;
  members: LeagueMember[];
  currentMemberId: number;      // league.memberId
  initialWeekNumber?: number;   // default 1
  maxWeekNumber?: number;       // NEW: optional cap, e.g. 18
};

type ScheduleCell = {
  opponentName: string;
  isHome: boolean;
  teamScore: number;
  opponentScore: number;
  memberPointDiff: number;
  broadcast: string | null;
};

type TeamRow = {
  teamId: number;
  teamName: string;
  conferenceName: string | null;
  cellsByDate: Record<string, ScheduleCell[]>;
};

export const LeagueScheduleTabs = ({
  leagueId,
  members,
  currentMemberId,
  initialWeekNumber = 1,
  maxWeekNumber
}: LeagueScheduleTabsProps) => {
  const [activeMemberId, setActiveMemberId] = useState<number | null>(
    currentMemberId || (members[0]?.id ?? null)
  );
  const [weekNumber, setWeekNumber] = useState(initialWeekNumber);
  const [weekInputValue, setWeekInputValue] = useState(String(initialWeekNumber));

  const [schedule, setSchedule] = useState<MemberWeekSchedule | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Fetch schedule when member/week changes
  useEffect(() => {
    if (!activeMemberId) return;

    const loadSchedule = async () => {
      try {
        setLoading(true);
        setError(null);

        const data = await getScheduleForMemberForWeek(
          activeMemberId,
          weekNumber,
          leagueId
        );

        setSchedule(data);
      } catch (err: any) {
        setError(err?.message ?? "Failed to load schedule");
      } finally {
        setLoading(false);
      }
    };

    loadSchedule();
  }, [activeMemberId, weekNumber, leagueId]);

  // Build headers + rows from schedule
  const { dateHeaders, teamRows } = useMemo(() => {
    if (!schedule) {
      return { dateHeaders: [] as DateHeader[], teamRows: [] as TeamRow[] };
    }

    const week = schedule.week ?? null;
    const games = schedule.games ?? [];
    const ownedTeams = schedule.ownedTeams ?? [];

    // Map from teamId -> { teamName, cellsByDate }
    const teamMap = new Map<
      number,
      { teamName: string; conferenceName: string | null; cellsByDate: Record<string, ScheduleCell[]> }
    >();

    // 1) Seed map with ALL owned teams so they always get a row
    for (const t of ownedTeams) {
      teamMap.set(t.teamId, {
        teamName: t.teamName,
        conferenceName: t.conferenceName ?? null,
        cellsByDate: {},
      });
    }

    // Helper to add a game into the appropriate team row
    const addOwnedGame = (
      teamId: number,
      fallbackTeamName: string,
      dateKey: string,
      opponentName: string,
      isHome: boolean,
      teamScore: number,
      opponentScore: number,
      memberPointDiff: number,
      broadcast: string | null,
    ) => {
      let row = teamMap.get(teamId);
      if (!row) {
        // In case an owned team wasn't in the list (defensive)
        row = {
          teamName: fallbackTeamName,
          conferenceName: null,
          cellsByDate: {},
        };
        teamMap.set(teamId, row);
      }

      const cellsByDate = row.cellsByDate;
      if (!cellsByDate[dateKey]) {
        cellsByDate[dateKey] = [];
      }

      cellsByDate[dateKey].push({
        opponentName,
        isHome,
        teamScore,
        opponentScore,
        memberPointDiff,
        broadcast
      });
    };

    // 2) Group games into rows by league-local calendar date
    for (const g of games) {
      const dateKey = getLocalDateKeyForGame(g.date);

      if (g.ownsHome) {
        addOwnedGame(
          g.homeTeamId,
          g.homeTeamName,
          dateKey,
          g.awayTeamName,
          true,
          g.homeScore,
          g.awayScore,
          g.memberPointDiff,
          g.broadcast
        );
      }

      if (g.ownsAway) {
        addOwnedGame(
          g.awayTeamId,
          g.awayTeamName,
          dateKey,
          g.homeTeamName,
          false,
          g.awayScore,
          g.homeScore,
          g.memberPointDiff,
          g.broadcast
        );
      }
    }

    // 3) Build headers from Week row (Mon–Sun, using our earlier helpers)
    const dateHeaders: DateHeader[] =
      week != null
        ? buildDateHeadersFromWeek(week.startDate, week.endDate)
        : [];

    // 4) Convert map to sorted array of TeamRow
    const teamRows: TeamRow[] = Array.from(teamMap.entries())
      .map(([teamId, { teamName, conferenceName, cellsByDate }]) => ({
        teamId,
        teamName,
        conferenceName,
        cellsByDate
      }))
      .sort((a, b) => a.teamName.localeCompare(b.teamName));

    return { dateHeaders, teamRows };
  }, [schedule]);


  const sortedMembers = useMemo(
    () =>
      [...members].sort((a, b) => {
        const aOrder = a.draftOrder ?? Number.MAX_SAFE_INTEGER;
        const bOrder = b.draftOrder ?? Number.MAX_SAFE_INTEGER;
        if (aOrder === bOrder) {
          return (a.teamName ?? "").localeCompare(b.teamName ?? "");
        }
        return aOrder - bOrder;
      }),
    [members]
  );

  const handlePrevWeek = () => {
    const next = Math.max(1, weekNumber - 1);
    setWeekNumber(next);
    setWeekInputValue(String(next));
  };

  const handleNextWeek = () => {
    const next = maxWeekNumber != null
      ? Math.min(maxWeekNumber, weekNumber + 1)
      : weekNumber + 1;

    setWeekNumber(next);
    setWeekInputValue(String(next));
  };

  const handleWeekInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const raw = e.target.value;

    // Always update the input value, even if it's invalid/empty
    setWeekInputValue(raw);

    // If empty, do not update weekNumber yet
    if (raw.trim() === "") return;

    // Try parsing a number
    const parsed = Number(raw);

    // If not a number, don’t update weekNumber yet
    if (Number.isNaN(parsed)) return;

    // Clamp to valid range
    let next = parsed;
    if (next < 1) next = 1;
    if (maxWeekNumber != null && next > maxWeekNumber) {
      next = maxWeekNumber;
    }

    setWeekNumber(next);
  };


  return (
    <div className="league-schedule">
      {/* Tabs + week controls header */}
      <div className="league-schedule__header">
        <div className="league-schedule__tabs">
          {sortedMembers.map((m) => (
            <button
              key={m.id}
              type="button"
              className={`league-schedule__tab ${
                m.id === activeMemberId ? "league-schedule__tab--active" : ""
              }`}
              onClick={() => setActiveMemberId(m.id)}
            >
              {m.teamName ?? `Team ${m.id}`}
            </button>
          ))}
        </div>

        <div className="league-schedule__week-controls">
          <button type="button" onClick={handlePrevWeek} disabled={weekNumber <= 1}>
            ‹
          </button>

          <label className="league-schedule__week-label">
            Week
            <input
              type="number"
              min={1}
              max={maxWeekNumber ?? undefined}
              value={weekInputValue}
              onChange={handleWeekInputChange}
              className="league-schedule__week-input"
            />
          </label>

          <button
            type="button"
            onClick={handleNextWeek}
            disabled={maxWeekNumber != null && weekNumber >= maxWeekNumber}
          >
            ›
          </button>
        </div>
      </div>

      {/* Body */}
      <div className="league-schedule__body">
        {loading && <p>Loading schedule…</p>}
        {error && <p className="league-schedule__error">{error}</p>}

        {!loading && !error && dateHeaders.length === 0 && (
          <p>No games for this week.</p>
        )}

        {!loading && !error && dateHeaders.length > 0 && (
          <div className="league-schedule__table-wrapper">
            <table className="league-schedule__table">
              <thead>
                <tr>
                  <th className="league-schedule__team-col">Team</th>
                  {dateHeaders.map((d) => (
                    <th key={d.key}>{d.label}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {teamRows.map((row) => (
                  <tr key={row.teamId}>
                    <td className="league-schedule__team-col">
                      <div className="league-schedule__team-col-content">
                        <div className="league-schedule__team-conf">
                          {row.conferenceName ?? "Independent"}
                        </div>
                        <div className="league-schedule__team-name">
                          {row.teamName}
                        </div>
                      </div>
                    </td>
                    {dateHeaders.map((d) => {
                      const cells = row.cellsByDate[d.key];
                      if (!cells || cells.length === 0) {
                        return (
                          <td
                            key={d.key}
                            className="league-schedule__cell league-schedule__cell--empty"
                          >
                            —
                          </td>
                        );
                      }

                      return (
                        <td key={d.key} className="league-schedule__cell">
                          {cells.map((c, idx) => {
                            const showScore =
                              !(c.teamScore === 0 && c.opponentScore === 0);

                            return (
                              <div
                                key={idx}
                                className="league-schedule__cell-game"
                              >
                                <div className="league-schedule__cell-opponent">
                                  {c.isHome ? "vs " : "@ "}
                                  {c.opponentName}
                                </div>
                                {showScore && (
                                  <>
                                    <div className="league-schedule__cell-score">
                                      {c.teamScore}–{c.opponentScore}
                                    </div>
                                    <div className="league-schedule__cell-pd">
                                      {c.memberPointDiff > 0
                                        ? `+${c.memberPointDiff}`
                                        : c.memberPointDiff}
                                    </div>
                                  </>
                                )}
                                {c.broadcast != null ? c.broadcast : ""}
                              </div>
                            );
                          })}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
