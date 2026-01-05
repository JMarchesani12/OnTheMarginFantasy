import { useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import type { League } from "../../types/league";
import type { TeamSeasonSchedule } from "../../types/schedule";
import { getScheduleForTeam } from "../../api/schedule";
import { LEAGUE_TIME_ZONE } from "../../utils/scheduleTable";
import "./TeamSchedulePage.css";

type LocationState = {
  league?: League;
  teamName?: string;
  fromConferenceId?: number | null;
  fromWeekNumber?: number;
  fromWeekStartDate?: string | null;
  fromWeekEndDate?: string | null;
};

const dateFormatter = new Intl.DateTimeFormat(undefined, {
  timeZone: LEAGUE_TIME_ZONE,
  weekday: "short",
  month: "short",
  day: "numeric",
});

const weekRangeFormatter = new Intl.DateTimeFormat(undefined, {
  timeZone: LEAGUE_TIME_ZONE,
  month: "short",
  day: "numeric",
});

const timeFormatter = new Intl.DateTimeFormat(undefined, {
  hour: "numeric",
  minute: "2-digit",
  hour12: true,
});

const formatLocalTime = (dateStr: string | null | undefined) => {
  if (!dateStr) return null;
  const date = new Date(dateStr);
  if (Number.isNaN(date.getTime())) return null;
  return timeFormatter.format(date);
};

const TeamSchedulePage = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { league_id, team_id } = useParams();
  const state = location.state as LocationState | null;
  const league = state?.league;

  const teamId = team_id ? Number(team_id) : null;
  const teamLabel = state?.teamName ?? (teamId ? `Team ${teamId}` : "Team");

  const [schedule, setSchedule] = useState<TeamSeasonSchedule | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!league || !teamId) return;
    let isCancelled = false;

    const loadSchedule = async () => {
      try {
        setLoading(true);
        setError(null);
        const data = await getScheduleForTeam(league.seasonYear, teamId);
        if (!isCancelled) {
          setSchedule(data);
        }
      } catch (err: any) {
        if (!isCancelled) {
          setError(err?.message ?? "Failed to load team schedule");
        }
      } finally {
        if (!isCancelled) {
          setLoading(false);
        }
      }
    };

    loadSchedule();
    return () => {
      isCancelled = true;
    };
  }, [league, teamId]);

  const record = useMemo(() => {
    if (!schedule) {
      return { wins: 0, losses: 0, pending: 0 };
    }
    return schedule.games.reduce((acc, game) => {
      const teamScore = game.isHome ? game.homeScore : game.awayScore;
      const opponentScore = game.isHome ? game.awayScore : game.homeScore;
      const hasScore = !(teamScore === 0 && opponentScore === 0);

      if (!hasScore) {
        acc.pending += 1;
        return acc;
      }

      if (teamScore > opponentScore) {
        acc.wins += 1;
      } else if (teamScore < opponentScore) {
        acc.losses += 1;
      } else {
        acc.pending += 1;
      }
      return acc;
    }, { wins: 0, losses: 0, pending: 0 });
  }, [schedule]);

  if (!league || !league_id || !teamId) {
    return (
      <div className="team-schedule">
        <button
          type="button"
          className="team-schedule__back"
          onClick={() => navigate(-1)}
        >
          ← Back
        </button>
        <p>Missing team or league context. Please open this page from your league.</p>
      </div>
    );
  }

  return (
    <div className="team-schedule">
      <button
        type="button"
        className="team-schedule__back"
        onClick={() => navigate(-1)}
      >
        ← Back
      </button>
      <header className="team-schedule__header">
        <div>
          <h1>{teamLabel}</h1>
          <p>Season {league.seasonYear}</p>
        </div>
        {state?.fromConferenceId && state?.fromWeekNumber && (
          <div className="team-schedule__badge">
            <span className="team-schedule__badge-week">
              Week {state.fromWeekNumber}
              {state.fromWeekStartDate || state.fromWeekEndDate ? (
                <>
                  {" • "}
                  {[
                    state.fromWeekStartDate
                      ? weekRangeFormatter.format(new Date(state.fromWeekStartDate))
                      : null,
                    state.fromWeekEndDate
                      ? weekRangeFormatter.format(new Date(state.fromWeekEndDate))
                      : null,
                  ]
                    .filter(Boolean)
                    .join(" – ")}
                </>
              ) : null}
            </span>
          </div>
        )}
      </header>

      <div className="team-schedule__record">
        Record: {record.wins}-{record.losses}
      </div>

      {error && <p className="team-schedule__error">{error}</p>}
      {loading && <p className="team-schedule__hint">Loading team games…</p>}

      {!loading && schedule && (
        <div className="team-schedule__list">
          {schedule.games.map((game) => {
            const teamScore = game.isHome ? game.homeScore : game.awayScore;
            const opponentScore = game.isHome ? game.awayScore : game.homeScore;
            const hasScore = !(teamScore === 0 && opponentScore === 0);
            const localTime = formatLocalTime(game.date);

            let result: "win" | "loss" | "pending" = "pending";
            if (hasScore) {
              if ((teamScore ?? 0) > (opponentScore ?? 0)) {
                result = "win";
              } else if ((teamScore ?? 0) < (opponentScore ?? 0)) {
                result = "loss";
              }
            }

            return (
              <article key={game.id} className="team-schedule__game">
                <div className="team-schedule__game-header">
                  <span>{dateFormatter.format(new Date(game.date))}</span>
                  <span>{game.isHome ? "vs " : "@ "}{game.opponentTeamName}</span>
                  {localTime && <span>{localTime}</span>}
                  {game.broadcast && <span>{game.broadcast}</span>}
                </div>
                <div className={`team-schedule__score team-schedule__score--${result}`}>
                  {hasScore ? (
                    <>
                      {game.homeScore}–{game.awayScore}
                      <span className="team-schedule__score-label">
                        {result === "win" ? "Win" : result === "loss" ? "Loss" : "TBD"}
                      </span>
                    </>
                  ) : (
                    <span className="team-schedule__score-label">TBD</span>
                  )}
                </div>
              </article>
            );
          })}
        </div>
      )}
    </div>
  );
};

export default TeamSchedulePage;
