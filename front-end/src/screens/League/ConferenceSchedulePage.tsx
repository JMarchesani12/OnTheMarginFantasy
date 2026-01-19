import { useEffect, useMemo, useState, type ChangeEvent } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import type { League, LeagueConference } from "../../types/league";
import type { ConferenceSchedule } from "../../types/schedule";
import type { WeekInfo } from "../../types/week";
import {
  getScheduleForConferenceForWeek,
  getScheduleForMemberForWeek,
} from "../../api/schedule";
import { getConferences } from "../../api/leagues";
import {
  buildDateHeadersFromWeek,
  formatLocalTime,
  getLocalDateKeyForGame,
  type DateHeader,
} from "../../utils/scheduleTable";
import { getEffectiveWeekNumber } from "../../utils/weekCutoff";
import "./ConferenceSchedulePage.css";

type LocationState = {
  league?: League;
};

type ScheduleCell = {
  opponentName: string;
  isHome: boolean;
  teamScore: number;
  opponentScore: number;
  broadcast: string | null;
  time: string | null;
};

type TeamRow = {
  teamId: number;
  teamName: string;
  cellsByDate: Record<string, ScheduleCell[]>;
};

const buildFallbackHeaders = (games: ConferenceSchedule["games"]): DateHeader[] => {
  const formatter = new Intl.DateTimeFormat(undefined, {
    weekday: "short",
    month: "short",
    day: "numeric",
  });

  const uniqueDays = Array.from(
    new Set(games.map((game) => getLocalDateKeyForGame(game.date)))
  ).sort();

  return uniqueDays.map((key) => {
    const [year, month, day] = key.split("-").map((part) => Number(part));
    const displayDate = new Date(year, (month ?? 1) - 1, day ?? 1);
    return { key, label: formatter.format(displayDate) };
  });
};

const ConferenceSchedulePage = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { league_id } = useParams();
  const state = location.state as LocationState | null;
  const league = state?.league;

  const leagueId = league?.leagueId ?? (league_id ? Number(league_id) : null);
  const memberId = league?.memberId ?? null;

  const initialWeekNumber = useMemo(
    () =>
      getEffectiveWeekNumber({
        currentWeekNumber: league?.currentWeekNumber ?? null,
        currentWeekStartDate: league?.currentWeekStartDate ?? null,
        timeZone: league?.settings?.timezone ?? null,
      }) ?? 1,
    [league?.currentWeekNumber, league?.currentWeekStartDate, league?.settings?.timezone]
  );
  const [weekNumber, setWeekNumber] = useState(initialWeekNumber);
  const [weekInfo, setWeekInfo] = useState<WeekInfo | null>(null);
  const [weekInfoLoading, setWeekInfoLoading] = useState(false);

  const [conferences, setConferences] = useState<LeagueConference[]>([]);
  const [conferencesLoading, setConferencesLoading] = useState(false);
  const [conferencesError, setConferencesError] = useState<string | null>(null);
  const [activeConferenceId, setActiveConferenceId] = useState<number | null>(null);

  const [schedule, setSchedule] = useState<ConferenceSchedule | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [searchTerm, setSearchTerm] = useState("");

  const storageKey =
    typeof window !== "undefined" && leagueId
      ? `conferenceSelection:${leagueId}`
      : null;

  useEffect(() => {
    setWeekNumber(initialWeekNumber);
  }, [initialWeekNumber]);

  useEffect(() => {
    if (!storageKey) {
      return;
    }
    const saved = window.localStorage.getItem(storageKey);
    if (saved) {
      const parsed = Number(saved);
      if (!Number.isNaN(parsed)) {
        setActiveConferenceId(parsed);
      }
    }
  }, [storageKey]);

  useEffect(() => {
    if (!leagueId) {
      return;
    }

    let isCancelled = false;
    const loadConferences = async () => {
      try {
        setConferencesLoading(true);
        setConferencesError(null);

        const response = await getConferences(leagueId);
        const sorted = [...response.conferences].sort((a, b) =>
          a.displayName.localeCompare(b.displayName)
        );

        if (!isCancelled) {
          setConferences(sorted);
        }
      } catch (err: any) {
        if (!isCancelled) {
          setConferencesError(err?.message ?? "Failed to load conferences");
        }
      } finally {
        if (!isCancelled) {
          setConferencesLoading(false);
        }
      }
    };

    loadConferences();
    return () => {
      isCancelled = true;
    };
  }, [leagueId]);

  useEffect(() => {
    if (!leagueId || !memberId) {
      return;
    }

    let isCancelled = false;
    const loadWeekInfo = async () => {
      try {
        setWeekInfoLoading(true);
        const data = await getScheduleForMemberForWeek(memberId, weekNumber, leagueId);
        if (!isCancelled) {
          setWeekInfo(data.week);
        }
      } catch (err) {
        console.error(err);
        if (!isCancelled) {
          setWeekInfo(null);
        }
      } finally {
        if (!isCancelled) {
          setWeekInfoLoading(false);
        }
      }
    };

    loadWeekInfo();
    return () => {
      isCancelled = true;
    };
  }, [leagueId, memberId, weekNumber]);

  useEffect(() => {
    if (!leagueId || !league || !activeConferenceId) {
      return;
    }

    let isCancelled = false;
    const loadConferenceSchedule = async () => {
      try {
        setLoading(true);
        setError(null);
        const data = await getScheduleForConferenceForWeek(
          weekNumber,
          leagueId,
          league.seasonYear,
          activeConferenceId
        );
        if (!isCancelled) {
          setSchedule(data);
        }
      } catch (err: any) {
        if (!isCancelled) {
          setSchedule(null);
          setError(err?.message ?? "Failed to load conference schedule");
        }
      } finally {
        if (!isCancelled) {
          setLoading(false);
        }
      }
    };

    loadConferenceSchedule();
    return () => {
      isCancelled = true;
    };
  }, [activeConferenceId, leagueId, league, weekNumber]);

  const { dateHeaders, teamRows } = useMemo(() => {
    if (!schedule) {
      return { dateHeaders: [] as DateHeader[], teamRows: [] as TeamRow[] };
    }

    const headers =
      weekInfo && weekInfo.startDate && weekInfo.endDate
        ? buildDateHeadersFromWeek(weekInfo.startDate, weekInfo.endDate)
        : buildFallbackHeaders(schedule.games);

    const teamMap = new Map<
      number,
      { teamName: string; cellsByDate: Record<string, ScheduleCell[]> }
    >();

    const addGame = (
      teamId: number,
      teamName: string,
      dateKey: string,
      opponentName: string,
      isHome: boolean,
      teamScore: number,
      opponentScore: number,
      broadcast: string | null,
      time: string | null
    ) => {
      const entry = teamMap.get(teamId) ?? {
        teamName,
        cellsByDate: {},
      };

      if (!entry.cellsByDate[dateKey]) {
        entry.cellsByDate[dateKey] = [];
      }

      entry.cellsByDate[dateKey].push({
        opponentName,
        isHome,
        teamScore,
        opponentScore,
        broadcast,
        time,
      });

      teamMap.set(teamId, entry);
    };

    schedule.games.forEach((game) => {
      const dateKey = getLocalDateKeyForGame(game.date);
      const time = formatLocalTime(game.date);

      if (game.homeInConference) {
        addGame(
          game.homeTeamId,
          game.homeTeamName,
          dateKey,
          game.awayTeamName,
          true,
          game.homeScore,
          game.awayScore,
          game.broadcast,
          time
        );
      }

      if (game.awayInConference) {
        addGame(
          game.awayTeamId,
          game.awayTeamName,
          dateKey,
          game.homeTeamName,
          false,
          game.awayScore,
          game.homeScore,
          game.broadcast,
          time
        );
      }
    });

    const rows: TeamRow[] = Array.from(teamMap.entries())
      .map(([teamId, value]) => ({
        teamId,
        teamName: value.teamName,
        cellsByDate: value.cellsByDate,
      }))
      .sort((a, b) => a.teamName.localeCompare(b.teamName));

    return { dateHeaders: headers, teamRows: rows };
  }, [schedule, weekInfo]);

  const filteredRows = useMemo(() => {
    if (!searchTerm) {
      return teamRows;
    }
    return teamRows.filter((row) =>
      row.teamName.toLowerCase().includes(searchTerm.toLowerCase())
    );
  }, [teamRows, searchTerm]);

  const activeConference = useMemo(
    () =>
      conferences.find((conf) => conf.sportConferenceId === activeConferenceId) ?? null,
    [conferences, activeConferenceId]
  );

  const handleConferenceChange = (evt: ChangeEvent<HTMLSelectElement>) => {
    const raw = evt.target.value;
    if (raw === "") {
      setActiveConferenceId(null);
      return;
    }
    const nextId = Number(raw);
    const resolved = Number.isNaN(nextId) ? null : nextId;
    setActiveConferenceId(resolved);
    if (storageKey && typeof window !== "undefined") {
      if (resolved === null) {
        window.localStorage.removeItem(storageKey);
      } else {
        window.localStorage.setItem(storageKey, String(resolved));
      }
    }
  };

  const handleTeamClick = (teamId: number, teamName: string) => {
    if (!league) return;
    navigate(`/leagues/${league.leagueId}/teams/${teamId}`, {
      state: {
        league,
        teamName,
        fromConferenceId: activeConferenceId,
        fromWeekNumber: weekNumber,
        fromWeekStartDate: weekInfo?.startDate ?? null,
        fromWeekEndDate: weekInfo?.endDate ?? null,
      },
    });
  };

  const updateWeek = (delta: number) => {
    setWeekNumber((prev) => Math.max(1, prev + delta));
  };

  if (!league || !leagueId) {
    return (
      <div className="conference-schedule">
        <button
          className="conference-schedule__back"
          type="button"
          onClick={() => navigate(-1)}
        >
          ← Back
        </button>
        <p>League context missing. Re-open this page from your league dashboard.</p>
      </div>
    );
  }

  return (
    <div className="conference-schedule">
      <button
        className="conference-schedule__back"
        type="button"
        onClick={() => navigate(-1)}
      >
        ← Back to League
      </button>

      <header className="conference-schedule__header">
        <div>
          <h1>Conference Scoreboard</h1>
          <p>
            Season {league.seasonYear} • Week {weekNumber}
          </p>
        </div>
        {activeConference && (
          <div className="conference-schedule__active">
            Viewing {activeConference.displayName}
          </div>
        )}
      </header>

      <section className="conference-schedule__controls">
        <div className="conference-schedule__form">
          <label htmlFor="conference-select">Conference</label>
          <select
            id="conference-select"
            className="conference-schedule__select"
            value={activeConferenceId ?? ""}
            onChange={handleConferenceChange}
            disabled={conferencesLoading || conferences.length === 0}
          >
            {conferences.length === 0 && <option value="">No conferences available</option>}
            {conferences.length > 0 && <option value="">Select conference…</option>}
            {conferences.map((conf) => (
              <option key={conf.sportConferenceId} value={conf.sportConferenceId}>
                {conf.displayName ?? `Conference ${conf.conferenceId}`}
              </option>
            ))}
          </select>
        </div>

        <div className="conference-schedule__week">
          <button type="button" onClick={() => updateWeek(-1)} disabled={weekNumber <= 1}>
            ‹
          </button>
          <span>Week {weekNumber}</span>
          <button type="button" onClick={() => updateWeek(1)}>
            ›
          </button>
        </div>
      </section>

      <div className="conference-schedule__filters">
        <label>
          Filter teams
          <input
            type="text"
            placeholder="Search by team name"
            value={searchTerm}
            onChange={(evt) => setSearchTerm(evt.target.value)}
          />
        </label>
        {weekInfoLoading && <span className="conference-schedule__hint">Syncing week…</span>}
      </div>

      {conferencesError && <p className="conference-schedule__error">{conferencesError}</p>}
      {error && <p className="conference-schedule__error">{error}</p>}
      {!activeConferenceId && (
        <p className="conference-schedule__hint">
          Select a conference above to view that week&apos;s slate.
        </p>
      )}

      {loading && <p className="conference-schedule__hint">Loading games…</p>}

      {!loading && activeConferenceId && filteredRows.length === 0 && (
        <p className="conference-schedule__hint">
          {teamRows.length === 0
            ? "No games for that conference this week."
            : "No teams match your search."}
        </p>
      )}

      {!loading && filteredRows.length > 0 && (
        <div className="conference-schedule__table-wrapper">
          <table className="conference-schedule__table">
            <thead>
              <tr>
                <th className="conference-schedule__team-col">Team</th>
                {dateHeaders.map((header) => (
                  <th key={header.key}>{header.label}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filteredRows.map((row) => (
                <tr key={row.teamId}>
                  <td className="conference-schedule__team-col">
                    <button
                      type="button"
                      className="conference-schedule__team-link"
                      onClick={() => handleTeamClick(row.teamId, row.teamName)}
                    >
                      {row.teamName}
                    </button>
                  </td>

                  {dateHeaders.map((header) => {
                    const cells = row.cellsByDate[header.key];
                    if (!cells || cells.length === 0) {
                      return (
                        <td
                          key={header.key}
                          className="conference-schedule__cell conference-schedule__cell--empty"
                        >
                          —
                        </td>
                      );
                    }

                    return (
                      <td key={header.key} className="conference-schedule__cell">
                        {cells.map((cell, idx) => {
                          // ESPN often uses 0-0 as "scheduled" in your API shape
                          const hasScore = !(cell.teamScore === 0 && cell.opponentScore === 0);

                          // Build HOME-on-top, AWAY-on-bottom display (regardless of which row we're on)
                          const homeName = cell.isHome ? row.teamName : cell.opponentName;
                          const awayName = cell.isHome ? cell.opponentName : row.teamName;

                          const homeScore = cell.isHome ? cell.teamScore : cell.opponentScore;
                          const awayScore = cell.isHome ? cell.opponentScore : cell.teamScore;

                          // Winner flags (bold ONLY the winning row)
                          const homeWon = hasScore && homeScore > awayScore;
                          const awayWon = hasScore && awayScore > homeScore;

                          return (
                            <div
                              key={`${row.teamId}-${header.key}-${idx}`}
                              className="conference-schedule__cell-game"
                            >
                              {/* Removed the old "vs/@ opponent" line above the score box */}

                              <div className="conference-schedule__cell-score">
                                {/* HOME (top) */}
                                <div
                                  className={`conference-schedule__score-line ${
                                    homeWon ? "is-winner" : ""
                                  }`}
                                >
                                  <span className="conference-schedule__score-name">
                                    {homeName}
                                  </span>
                                  <span className="conference-schedule__score-value">
                                    {hasScore ? homeScore : "—"}
                                  </span>
                                </div>

                                {/* @ row */}
                                <div className="conference-schedule__at-row">
                                  <span className="conference-schedule__at">@</span>
                                </div>

                                {/* AWAY (bottom) */}
                                <div
                                  className={`conference-schedule__score-line ${
                                    awayWon ? "is-winner" : ""
                                  }`}
                                >
                                  <span className="conference-schedule__score-name">
                                    {awayName}
                                  </span>
                                  <span className="conference-schedule__score-value">
                                    {hasScore ? awayScore : "—"}
                                  </span>
                                </div>

                                {!hasScore && (
                                  <span className="conference-schedule__score-status">
                                    Scheduled
                                  </span>
                                )}

                                {(cell.time || cell.broadcast) && (
                                  <div className="conference-schedule__cell-meta">
                                    {cell.time && (
                                      <span className="conference-schedule__cell-time">
                                        {cell.time}
                                      </span>
                                    )}
                                    {cell.broadcast && (
                                      <span className="conference-schedule__cell-broadcast">
                                        {cell.broadcast}
                                      </span>
                                    )}
                                  </div>
                                )}
                              </div>
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
  );
};

export default ConferenceSchedulePage;
