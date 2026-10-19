// src/components/League/LeagueScheduleTabs.tsx
import { useEffect, useMemo, useState } from "react";
import type { LeagueMember } from "../../types/leagueMember";
import type { MemberWeekSchedule } from "../../types/schedule";
import { getScheduleForMemberForWeek } from "../../api/schedule";
import {
  buildDateHeadersFromWeek,
  getLocalDateKeyForGame,
  formatLocalTime,
  type DateHeader,
} from "../../utils/scheduleTable";
import { safeLocalStorage } from "../../utils/safeStorage";
import { MIN_SCHEDULE_WEEK_NUMBER } from "../../utils/weekCutoff";
import { selectDailyTotals, getTeamGamePointDiff } from "../../utils/leagueScheduleDailyTotals";
import {
  getOpponentTierDisplayTone,
  type TierDisplayTone,
} from "../../utils/scheduleTierDisplay";
import { groupTeamsByTier } from "../../utils/teamTierGroups";
import "./LeagueScheduleTabs.css";

type LeagueScheduleTabsProps = {
  leagueId: number;
  members: LeagueMember[];
  currentMemberId: number;      // league.memberId
  initialWeekNumber?: number;
  maxWeekNumber?: number;       // NEW: optional cap, e.g. 18
  timeZone?: string | null;
};

type ScheduleCell = {
  explanation: string | null;
  opponentName: string;
  opponentTierDisplayTone: TierDisplayTone;
  isHome: boolean;
  teamScore: number;
  opponentScore: number;
  memberPointDiff: number;
  broadcast: string | null;
  time: string | null;
};

type TeamRow = {
  tier?: number | null;
  teamId: number;
  teamName: string;
  conferenceName: string | null;
  cellsByDate: Record<string, ScheduleCell[]>;
};

export const LeagueScheduleTabs = ({
  leagueId,
  members,
  currentMemberId,
  initialWeekNumber = MIN_SCHEDULE_WEEK_NUMBER,
  maxWeekNumber,
  timeZone
}: LeagueScheduleTabsProps) => {
  const [activeMemberId, setActiveMemberId] = useState<number | null>(
    currentMemberId || (members[0]?.id ?? null)
  );
  const [weekNumber, setWeekNumber] = useState(initialWeekNumber);
  const [weekInputValue, setWeekInputValue] = useState(String(initialWeekNumber));
  const storageKey = `league-schedule-collapsed:${leagueId}:${currentMemberId}`;
  const [isCollapsed, setIsCollapsed] = useState(false);

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
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : "Failed to load schedule");
      } finally {
        setLoading(false);
      }
    };

    loadSchedule();
  }, [activeMemberId, weekNumber, leagueId]);

  useEffect(() => {
    if (!currentMemberId) return;
    try {
      const stored = safeLocalStorage.getItem(storageKey);
      if (stored === null) return;
      setIsCollapsed(stored === "true");
    } catch {
      // ignore storage errors
    }
  }, [storageKey, currentMemberId]);

  useEffect(() => {
    if (!currentMemberId) return;
    try {
      safeLocalStorage.setItem(storageKey, String(isCollapsed));
    } catch {
      // ignore storage errors
    }
  }, [storageKey, currentMemberId, isCollapsed]);

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
      { tier?: number | null; teamName: string; conferenceName: string | null; cellsByDate: Record<string, ScheduleCell[]> }
    >();

    // 1) Seed map with ALL owned teams so they always get a row
    for (const t of ownedTeams) {
      teamMap.set(t.teamId, {
        tier: t.tier,
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
      opponentTierDisplayTone: TierDisplayTone,
      isHome: boolean,
      teamScore: number,
      opponentScore: number,
      memberPointDiff: number,
      broadcast: string | null,
      time: string | null,
      explanation: string | null,
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
        explanation,
        opponentName,
        opponentTierDisplayTone,
        isHome,
        teamScore,
        opponentScore,
        memberPointDiff,
        broadcast,
        time,
      });
    };

    // 2) Group games into rows by league-local calendar date
    for (const g of games) {
      const dateKey = getLocalDateKeyForGame(g.date);
      const time = formatLocalTime(g.date);

      if (g.ownsHome) {
        addOwnedGame(
          g.homeTeamId,
          g.homeTeamName,
          dateKey,
          g.awayTeamName,
          getOpponentTierDisplayTone(g.tierAdjustment),
          true,
          g.homeScore,
          g.awayScore,
          getTeamGamePointDiff(g, true),
          g.broadcast,
          time,
          g.tierAdjustment?.applied ? g.tierAdjustment.explanation : null,
        );
      }

      if (g.ownsAway) {
        addOwnedGame(
          g.awayTeamId,
          g.awayTeamName,
          dateKey,
          g.homeTeamName,
          getOpponentTierDisplayTone(g.tierAdjustment),
          false,
          g.awayScore,
          g.homeScore,
          getTeamGamePointDiff(g, false),
          g.broadcast,
          time,
          g.tierAdjustment?.applied ? g.tierAdjustment.explanation : null,
        );
      }
    }

    // 3) Build headers from the league's Week row so sport-specific windows apply.
    const dateHeaders: DateHeader[] =
      week != null
        ? buildDateHeadersFromWeek(week.startDate, week.endDate)
        : [];

    // 4) Convert map to sorted array of TeamRow
    const teamRows: TeamRow[] = Array.from(teamMap.entries())
      .map(([teamId, { tier, teamName, conferenceName, cellsByDate }]) => ({
        tier,
        teamId,
        teamName,
        conferenceName,
        cellsByDate
      }))
      .sort((a, b) => {
        const aConference = a.conferenceName ?? "Independent";
        const bConference = b.conferenceName ?? "Independent";
        const conferenceMatch = aConference.localeCompare(bConference);
        if (conferenceMatch !== 0) {
          return conferenceMatch;
        }
        return a.teamName.localeCompare(b.teamName);
      });

    const tierGroups = groupTeamsByTier(teamRows);
    return { dateHeaders, teamRows: tierGroups.length > 1
      ? tierGroups.flatMap((group) => group.teams)
      : teamRows };
  }, [schedule]);

  const todayKey = useMemo(() => {
    const formatter = new Intl.DateTimeFormat("en-CA", {
      timeZone: timeZone ?? undefined,
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    });
    const parts = formatter.formatToParts(new Date());
    const year = parts.find((p) => p.type === "year")?.value ?? "0000";
    const month = parts.find((p) => p.type === "month")?.value ?? "00";
    const day = parts.find((p) => p.type === "day")?.value ?? "00";
    return `${year}-${month}-${day}`;
  }, [timeZone]);

  const activeMemberDailyTotals = useMemo(() => {
    const totals: Record<string, number> = {};
    const member = members.find((item) => item.id === activeMemberId);
    (member?.dailyPointDifferentials ?? []).forEach((entry) => {
      if (!entry?.date) {
        return;
      }
      totals[entry.date] = (totals[entry.date] ?? 0) + (entry.pointDifferential ?? 0);
    });
    return totals;
  }, [members, activeMemberId]);

  const dailyTotals = useMemo(() => {
    return selectDailyTotals({
      dateHeaders,
      todayKey,
      activeMemberDailyTotals,
      isViewingCurrentWeek: weekNumber === initialWeekNumber,
      teamRows,
    });
  }, [dateHeaders, teamRows, activeMemberDailyTotals, todayKey, weekNumber, initialWeekNumber]);

  const tierSections = useMemo(() => {
    const groups = groupTeamsByTier(teamRows);
    return groups.length > 1 ? groups : [{ tier: null, label: null, teams: teamRows }];
  }, [teamRows]);
  const hasMultipleTiers = tierSections.length > 1;

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
    const next = Math.max(MIN_SCHEDULE_WEEK_NUMBER, weekNumber - 1);
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
    if (next < MIN_SCHEDULE_WEEK_NUMBER) next = MIN_SCHEDULE_WEEK_NUMBER;
    if (maxWeekNumber != null && next > maxWeekNumber) {
      next = maxWeekNumber;
    }

    setWeekNumber(next);
  };


  return (
    <div className="league-schedule">
      <h2 className="league-schedule__title">Weekly Performance</h2>
      <div className="league-schedule__rules-summary">
        {schedule?.rules && <p>{schedule.rules.summary}</p>}
      </div>
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
          <button
            type="button"
            className="league-schedule__toggle"
            onClick={() => setIsCollapsed((prev) => !prev)}
            aria-expanded={!isCollapsed}
            aria-controls="league-schedule-body"
          >
            {isCollapsed ? "Show Schedule" : "Hide Schedule"}
          </button>
          <button
            type="button"
            onClick={handlePrevWeek}
            disabled={weekNumber <= MIN_SCHEDULE_WEEK_NUMBER}
          >
            ‹
          </button>

          <label className="league-schedule__week-label">
            Week
            <input
              type="number"
              min={MIN_SCHEDULE_WEEK_NUMBER}
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
      {!isCollapsed && (
        <div className="league-schedule__body" id="league-schedule-body">
        {loading && <p>Loading schedule…</p>}
        {error && <p className="league-schedule__error">{error}</p>}

        {!loading && !error && dateHeaders.length === 0 && (
          <p>No games for this week.</p>
        )}

        {!loading && !error && dateHeaders.length > 0 && (
          <>
            {tierSections.map((section) => (
              <section
                className={hasMultipleTiers ? "league-schedule__tier-card" : undefined}
                key={section.tier ?? "all"}
                aria-label={section.label ?? "Team schedule"}
              >
                {section.label && <h3 className="league-schedule__tier-title">{section.label}</h3>}
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
                {section.teams.map((row) => (
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
                                <div
                                  className={`league-schedule__cell-opponent league-schedule__cell-opponent--${c.opponentTierDisplayTone}`}
                                >
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
                                {c.explanation && (
                                  <p className="league-schedule__adjustment">{c.explanation}</p>
                                )}
                                {(c.time != null || c.broadcast != null) && (
                                  <div className="league-schedule__cell-meta">
                                    {c.time != null && (
                                      <div className="league-schedule__cell-time">
                                        {c.time}
                                      </div>
                                    )}
                                    <br/>
                                    {c.broadcast != null && (
                                      <div className="league-schedule__cell-broadcast">
                                        {c.broadcast}
                                      </div>
                                    )}
                                  </div>
                                )}
                              </div>
                            );
                          })}
                        </td>
                      );
                    })}
                  </tr>
                ))}
                {!hasMultipleTiers && (
                <tr className="league-schedule__summary-row">
                  <td className="league-schedule__team-col">
                    <span className="league-schedule__summary-label">
                      Daily diff
                    </span>
                  </td>
                  {dateHeaders.map((d) => {
                    const total = dailyTotals[d.key];
                    const className =
                      typeof total !== "number"
                        ? "is-neutral"
                        : total > 0
                        ? "is-positive"
                        : total < 0
                        ? "is-negative"
                        : "is-neutral";
                    return (
                      <td key={`summary-open-${d.key}`}>
                        <span
                          className={`league-schedule__summary-value ${className}`}
                        >
                          {typeof total === "number"
                            ? `${total > 0 ? "+" : ""}${total}`
                            : "--"}
                        </span>
                      </td>
                    );
                  })}
                </tr>
                )}
              </tbody>
                  </table>
                </div>
              </section>
            ))}
            {hasMultipleTiers && (
              <section className="league-schedule__tier-card" aria-label="Overall daily totals">
                <h3 className="league-schedule__tier-title">Overall daily totals</h3>
                <div className="league-schedule__table-wrapper">
                  <table className="league-schedule__table">
              <thead>
                <tr>
                  <th className="league-schedule__team-col">Date</th>
                  {dateHeaders.map((d) => (
                    <th key={d.key}>{d.label}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                <tr className="league-schedule__summary-row">
                  <td className="league-schedule__team-col">
                    <span className="league-schedule__summary-label">
                      Daily diff
                    </span>
                  </td>
                  {dateHeaders.map((d) => {
                    const total = dailyTotals[d.key];
                    const className =
                      typeof total !== "number"
                        ? "is-neutral"
                        : total > 0
                        ? "is-positive"
                        : total < 0
                        ? "is-negative"
                        : "is-neutral";
                    return (
                      <td key={`summary-open-${d.key}`}>
                        <span
                          className={`league-schedule__summary-value ${className}`}
                        >
                          {typeof total === "number"
                            ? `${total > 0 ? "+" : ""}${total}`
                            : "--"}
                        </span>
                      </td>
                    );
                  })}
                </tr>
              </tbody>
                  </table>
                </div>
              </section>
            )}
          </>
        )}
        </div>
      )}

      {isCollapsed && (
        <div className="league-schedule__body league-schedule__body--collapsed" id="league-schedule-body">
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
                    <th className="league-schedule__team-col">Date</th>
                    {dateHeaders.map((d) => (
                      <th key={`collapsed-${d.key}`}>{d.label}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  <tr className="league-schedule__summary-row">
                    <td className="league-schedule__team-col">
                      <span className="league-schedule__summary-label">
                        Daily diff
                      </span>
                    </td>
                    {dateHeaders.map((d) => {
                      const total = dailyTotals[d.key];
                      const className =
                        typeof total !== "number"
                          ? "is-neutral"
                          : total > 0
                          ? "is-positive"
                          : total < 0
                          ? "is-negative"
                          : "is-neutral";
                      return (
                        <td key={`summary-${d.key}`}>
                          <span
                            className={`league-schedule__summary-value ${className}`}
                          >
                            {typeof total === "number"
                              ? `${total > 0 ? "+" : ""}${total}`
                              : "--"}
                          </span>
                        </td>
                      );
                    })}
                  </tr>
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
