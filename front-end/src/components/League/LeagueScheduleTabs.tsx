import { useTeamPerformance } from "../../hooks/useTeamPerformance";
import { TeamPerformanceStats } from "../TeamPerformance/TeamPerformanceStats";
import { safeErrorMessage, READ_ERROR } from "../../api/safeError";
// src/components/League/LeagueScheduleTabs.tsx
import { useEffect, useMemo, useState, type CSSProperties } from "react";
import type { LeagueMember } from "../../types/leagueMember";
import type { MemberWeekSchedule } from "../../types/schedule";
import { getScheduleForMemberForWeek } from "../../api/schedule";
import {
  buildDateHeadersFromWeek,
  LEAGUE_TIME_ZONE,
  getLocalDateKeyForGame,
  formatLocalTime,
  type DateHeader,
} from "../../utils/scheduleTable";
import { buildSchedulePages, getSchedulePageIndex, moveSchedulePage } from "../../utils/schedulePagination";
import { MIN_SCHEDULE_WEEK_NUMBER } from "../../utils/weekCutoff";
import { selectDailyTotals, getTeamGamePointDiff } from "../../utils/leagueScheduleDailyTotals";
import {
  getOpponentTierDisplayTone,
  getMatchupHoverExplanation,
  type TierDisplayTone,
} from "../../utils/scheduleTierDisplay";
import { groupTeamsByTier } from "../../utils/teamTierGroups";
import "./LeagueScheduleTabs.css";

type LeagueScheduleTabsProps = {
  sport?: string | number;
  leagueId: number;
  members: LeagueMember[];
  currentMemberId: number;      // league.memberId
  initialWeekNumber?: number;
  maxWeekNumber?: number;       // NEW: optional cap, e.g. 18
  timeZone?: string | null;
};

type ScheduleCell = {
  hoverExplanation: string | null;
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
  sport,
  leagueId,
  members,
  currentMemberId,
  initialWeekNumber = MIN_SCHEDULE_WEEK_NUMBER,
  maxWeekNumber,
  timeZone
}: LeagueScheduleTabsProps) => {
  const sportName = String(sport ?? "").toLowerCase();
  const minWeekNumber = sportName === "1" || sportName.includes("basketball") ? 1 : MIN_SCHEDULE_WEEK_NUMBER;
  const startingWeekNumber = Math.max(minWeekNumber, initialWeekNumber);
  const [activeMemberId, setActiveMemberId] = useState<number | null>(
    currentMemberId || (members[0]?.id ?? null)
  );
  const [weekNumber, setWeekNumber] = useState(startingWeekNumber);
  const performance = useTeamPerformance(leagueId, weekNumber);
  const [weekInputValue, setWeekInputValue] = useState(String(startingWeekNumber));
  const [requestedPageIndex, setRequestedPageIndex] = useState<number | null>(null);
  const scheduleTimeZone = timeZone ?? LEAGUE_TIME_ZONE;
  const [viewMode, setViewMode] = useState<"day" | "week">(() =>
    window.matchMedia("(max-width: 800px)").matches ? "day" : "week");
  const [schedule, setSchedule] = useState<MemberWeekSchedule | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Fetch schedule when member/week changes
  useEffect(() => {
    if (!activeMemberId) return;

    let cancelled = false;
    const loadSchedule = async () => {
      try {
        setLoading(true);
        setError(null);

        const data = await getScheduleForMemberForWeek(
          activeMemberId,
          weekNumber,
          leagueId
        );

        if (!cancelled) setSchedule(data);
      } catch (err: unknown) {
        if (!cancelled) setError(safeErrorMessage(err, READ_ERROR));
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    loadSchedule();
    return () => { cancelled = true; };
  }, [activeMemberId, weekNumber, leagueId]);

  // Build headers + rows from schedule
  const { dateHeaders: periodDateHeaders, teamRows } = useMemo(() => {
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
      tierAdjustment: Parameters<typeof getMatchupHoverExplanation>[1],
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
        hoverExplanation: getMatchupHoverExplanation(opponentTierDisplayTone, tierAdjustment),
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
      const dateKey = getLocalDateKeyForGame(g.date, scheduleTimeZone);
      const time = formatLocalTime(g.date, g.timeTBD);

      if (g.ownsHome) {
        addOwnedGame(
          g.homeTeamId,
          g.homeTeamName,
          dateKey,
          g.awayTeamName,
          getOpponentTierDisplayTone(g.tierAdjustment, g.homeTeamTier, g.awayTeamTier,
            g.sportId === 1 && !g.ownsAway && g.awayTeamUnranked === true,
            g.ownsHome && g.ownsAway),
          true,
          g.homeScore,
          g.awayScore,
          getTeamGamePointDiff(g, true),
          g.broadcast,
          time,
          g.tierAdjustment,
        );
      }

      if (g.ownsAway) {
        addOwnedGame(
          g.awayTeamId,
          g.awayTeamName,
          dateKey,
          g.homeTeamName,
          getOpponentTierDisplayTone(g.tierAdjustment, g.awayTeamTier, g.homeTeamTier,
            g.sportId === 1 && !g.ownsHome && g.homeTeamUnranked === true,
            g.ownsHome && g.ownsAway),
          false,
          g.awayScore,
          g.homeScore,
          getTeamGamePointDiff(g, false),
          g.broadcast,
          time,
          g.tierAdjustment,
        );
      }
    }

    // 3) Build headers from the league's Week row so sport-specific windows apply.
    const dateHeaders: DateHeader[] =
      week != null
        ? buildDateHeadersFromWeek(week.startDate, week.endDate, scheduleTimeZone)
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
        const aConference = a.conferenceName ?? "Conference unavailable";
        const bConference = b.conferenceName ?? "Conference unavailable";
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
  }, [schedule, scheduleTimeZone]);

  const todayKey = useMemo(() => {
    const formatter = new Intl.DateTimeFormat("en-CA", {
      timeZone: scheduleTimeZone,
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    });
    const parts = formatter.formatToParts(new Date());
    const year = parts.find((p) => p.type === "year")?.value ?? "0000";
    const month = parts.find((p) => p.type === "month")?.value ?? "00";
    const day = parts.find((p) => p.type === "day")?.value ?? "00";
    return `${year}-${month}-${day}`;
  }, [scheduleTimeZone]);

  const datePages = useMemo(() => buildSchedulePages(periodDateHeaders, viewMode === "day"), [periodDateHeaders, viewMode]);
  const pageIndex = getSchedulePageIndex(datePages, requestedPageIndex, todayKey);
  const dateHeaders = useMemo(() => datePages[pageIndex] ?? [], [datePages, pageIndex]);
  const calendarPages = useMemo(() => buildSchedulePages(periodDateHeaders), [periodDateHeaders]);
  const calendarIndex = getSchedulePageIndex(calendarPages, null, dateHeaders[0]?.key ?? todayKey);
  const calendarDates = calendarPages[calendarIndex] ?? [];
  const visibleDateLabel = viewMode === "day" ? dateHeaders[0]?.label
    : dateHeaders.length ? `${dateHeaders[0].label} – ${dateHeaders[dateHeaders.length - 1].label}` : undefined;
  const navigationLoading = loading || schedule?.week?.weekNumber !== weekNumber;

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
    const groups = groupTeamsByTier(teamRows, sport);
    return groups.length > 1 ? groups : [{ tier: null, label: null, teams: teamRows }];
  }, [teamRows, sport]);
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

  const navigateDates = (direction: -1 | 1) => {
    const next = moveSchedulePage(weekNumber, pageIndex, datePages.length,
      direction, minWeekNumber, maxWeekNumber);
    setRequestedPageIndex(next.pageIndex);
    setWeekNumber(next.weekNumber);
    setWeekInputValue(String(next.weekNumber));
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
    if (next < minWeekNumber) next = minWeekNumber;
    if (maxWeekNumber != null && next > maxWeekNumber) {
      next = maxWeekNumber;
    }

    setRequestedPageIndex(0);
    setWeekNumber(next);
  };


  return (
    <div className={`league-schedule league-schedule--${viewMode}`}>
      <div className="league-schedule__toolbar">
        <div className="league-schedule__toolbar-top">
          <label className="league-schedule__member-picker">Fantasy team
            <select value={activeMemberId ?? ""} onChange={event => setActiveMemberId(Number(event.target.value))}>
              {sortedMembers.map(member => <option key={member.id} value={member.id}>{member.teamName ?? `Team ${member.id}`}</option>)}
            </select>
          </label>
          <label className="league-schedule__period-picker">Scoring week
            <input type="number" min={minWeekNumber} max={maxWeekNumber ?? undefined}
              value={weekInputValue} onChange={handleWeekInputChange} />
          </label>
          <div className="league-schedule__view-toggle" role="group" aria-label="Schedule view">
            {(["day", "week"] as const).map(mode => <button key={mode} type="button"
              aria-pressed={viewMode === mode} onClick={() => {
                const anchor = dateHeaders.find(date => date.key === todayKey)?.key ?? dateHeaders[0]?.key ?? todayKey;
                const pages = buildSchedulePages(periodDateHeaders, mode === "day");
                setRequestedPageIndex(getSchedulePageIndex(pages, null, anchor));
                setViewMode(mode);
              }}>{mode === "day" ? "Day" : "Week"}</button>)}
          </div>
        </div>
        <div className="league-schedule__date-nav">
          <button type="button" className="league-schedule__date-arrow"
            onClick={() => navigateDates(-1)}
            aria-label={viewMode === "day" ? "Previous day" : "Previous week"}
            title={viewMode === "day" ? "Previous day" : "Previous week"}
            disabled={navigationLoading || (weekNumber <= minWeekNumber && pageIndex === 0)}>‹</button>
          <div className="league-schedule__date-heading" aria-live="polite">
            <span>{viewMode === "day" ? "Daily schedule" : "Weekly schedule"}</span>
            <h2 className="league-schedule__title">{visibleDateLabel ?? "Loading dates…"}</h2>
          </div>
          <button type="button" className="league-schedule__date-arrow"
            onClick={() => navigateDates(1)}
            aria-label={viewMode === "day" ? "Next day" : "Next week"}
            title={viewMode === "day" ? "Next day" : "Next week"}
            disabled={navigationLoading || (maxWeekNumber != null && weekNumber >= maxWeekNumber && pageIndex >= datePages.length - 1)}>›</button>
          <button type="button" className="league-schedule__today" disabled={navigationLoading}
            onClick={() => { setWeekNumber(startingWeekNumber); setWeekInputValue(String(startingWeekNumber)); setRequestedPageIndex(null); }}>Current week</button>
        </div>
        {viewMode === "day" && calendarDates.length > 0 && <div className="league-schedule__date-strip" role="group" aria-label="Choose a day">
          {calendarDates.map(date => {
            const parsed = new Date(`${date.key}T12:00:00Z`);
            return <button key={date.key} type="button" disabled={navigationLoading}
              aria-label={date.label} aria-pressed={date.key === dateHeaders[0]?.key}
              onClick={() => setRequestedPageIndex(getSchedulePageIndex(datePages, null, date.key))}>
              <span>{parsed.toLocaleDateString("en-US", { weekday: "short", timeZone: "UTC" })}</span>
              <strong>{parsed.getUTCDate()}</strong>
              {date.key === todayKey && <span className="league-schedule__today-dot" aria-label="Today" />}
            </button>;
          })}
        </div>}
      </div>
      <div className="league-schedule__rules-summary">
        {schedule?.rules && <p>{schedule.rules.summary}</p>}
      </div>

      {performance.failed && <p className="league-schedule__rules-summary">Team performance is unavailable. <button type="button" onClick={performance.retry}>Retry team stats</button></p>}
      {/* Body */}
      {(
        <div className="league-schedule__body" id="league-schedule-body">
        {loading && <p>Loading schedule…</p>}
        {error && <p className="league-schedule__error">{error}</p>}

        {!loading && !error && dateHeaders.length === 0 && (
          <p>No games for this week.</p>
        )}

        {!loading && !error && dateHeaders.length > 0 && (
          <>
            {hasMultipleTiers && (
              <section className="league-schedule__tier-card" aria-label="Overall daily totals">
                <h3 className="league-schedule__tier-title">Overall daily totals</h3>
                <div className="league-schedule__table-wrapper">
                  <table className="league-schedule__table" style={{ "--schedule-days": dateHeaders.length } as CSSProperties}>
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
                      <td data-date={d.label} key={`summary-open-${d.key}`}>
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
            {tierSections.map((section) => (
              <section
                className={hasMultipleTiers ? "league-schedule__tier-card" : undefined}
                key={section.tier ?? "all"}
                aria-label={section.label ?? "Team schedule"}
              >
                {section.label && <h3 className="league-schedule__tier-title">{section.label}</h3>}
                <div className="league-schedule__table-wrapper">
                  <table className="league-schedule__table" style={{ "--schedule-days": dateHeaders.length } as CSSProperties}>
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
                          {row.conferenceName ?? "Conference unavailable"}
                        </div>
                        <div className="league-schedule__team-name">
                          {row.teamName}
                        </div>
                        <TeamPerformanceStats stats={performance.teams[row.teamId]} />
                      </div>
                    </td>
                    {dateHeaders.map((d) => {
                      const cells = row.cellsByDate[d.key];
                      if (!cells || cells.length === 0) {
                        return (
                          <td data-date={d.label}
                            key={d.key}
                            className="league-schedule__cell league-schedule__cell--empty"
                          >
                            —
                          </td>
                        );
                      }

                      return (
                        <td data-date={d.label} key={d.key} className="league-schedule__cell">
                          {cells.map((c, idx) => {
                            const showScore =
                              !(c.teamScore === 0 && c.opponentScore === 0);
                            const tooltipId = `matchup-game-${leagueId}-${row.teamId}-${d.key}-${idx}`;

                            return (
                              <div
                                key={idx}
                                className="league-schedule__cell-game"
                                tabIndex={c.hoverExplanation ? 0 : undefined}
                                aria-describedby={c.hoverExplanation ? tooltipId : undefined}
                              >
                                <div
                                  className={`league-schedule__cell-opponent league-schedule__cell-opponent--${c.opponentTierDisplayTone}`}
                                >
                                  {c.isHome ? "vs " : "@ "}
                                  {c.opponentName}
                                </div>
                                {c.hoverExplanation && (
                                  <span id={tooltipId} role="tooltip" className={`league-schedule__matchup-tooltip league-schedule__matchup-tooltip--${c.opponentTierDisplayTone}`}>
                                    {c.hoverExplanation}
                                  </span>
                                )}
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
                                {(c.time != null || c.broadcast != null) && (
                                  <div className="league-schedule__cell-meta">
                                    {c.time != null && (
                                      <div className="league-schedule__cell-time">
                                        {c.time}
                                      </div>
                                    )}
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
                      <td data-date={d.label} key={`summary-open-${d.key}`}>
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

          </>
        )}
        </div>
      )}

    </div>
  );
};
