import type { CSSProperties, FC } from "react";
import "./LeagueScoreboard.css";

export type ScoreboardRow = {
  memberId: number;
  teamName: string;
  totalPoints: number;
  weeklyPoints: Record<number, number | null | undefined>;
  weeklyDifferentials: Record<number, number | null | undefined>;
};

type LeagueScoreboardProps = {
  weekNumbers: number[];
  rows: ScoreboardRow[];
  weeklyDifferentialTotals?: Record<number, number>;
  currentWeekNumber: number | null;
  loading: boolean;
  error: string | null;
};

const LeagueScoreboard: FC<LeagueScoreboardProps> = ({
  weekNumbers,
  rows,
  weeklyDifferentialTotals,
  currentWeekNumber,
  loading,
  error,
}) => {
  const throughWeek =
    typeof currentWeekNumber === "number" && currentWeekNumber > 1
      ? currentWeekNumber - 1
      : null;

  if (!weekNumbers.length && !loading && !error) {
    return null;
  }

  return (
    <section className="league-scoreboard">
      <header className="league-scoreboard__header">
        <div>
          <p className="league-scoreboard__eyebrow">Scoreboard</p>
          <h2>Weekly Performance</h2>
          <p className="league-scoreboard__subhead">
            Through week {throughWeek ?? "-"}
          </p>
        </div>
      </header>

      {loading && <p className="league-scoreboard__loading">Loading scoreboard…</p>}
      {error && <p className="league-scoreboard__error">{error}</p>}

      {!loading && !error && weekNumbers.length > 0 && (
        <div
          className="league-scoreboard__table"
          role="region"
          aria-label="Weekly scores"
          style={{ "--week-count": weekNumbers.length } as CSSProperties}
        >
          <div className="league-scoreboard__row league-scoreboard__row--header">
            <span>Team</span>
            {weekNumbers.map((week) => (
              <span key={`header-week-${week}`}>Week {week}</span>
            ))}
            <span>Total</span>
          </div>
          {rows.map((row) => (
            <div className="league-scoreboard__row" key={`member-${row.memberId}`}>
              <span className="league-scoreboard__team">{row.teamName}</span>
              {weekNumbers.map((week) => {
                const points = row.weeklyPoints[week];
                const differential = row.weeklyDifferentials[week];
                return (
                  <span
                    key={`cell-${row.memberId}-${week}`}
                    className="league-scoreboard__cell"
                  >
                    <span className="league-scoreboard__cell-value">
                      {typeof points === "number" ? `${points} pts` : "--"}
                    </span>
                    {typeof differential === "number" && (
                      <span
                        className={`league-scoreboard__diff ${
                          differential > 0
                            ? "is-positive"
                            : differential < 0
                            ? "is-negative"
                            : "is-neutral"
                        }`}
                      >
                        {`${differential > 0 ? "+" : ""}${differential}`}
                      </span>
                    )}
                  </span>
                );
              })}
              <span className="league-scoreboard__total">{row.totalPoints}</span>
            </div>
          ))}
          {weeklyDifferentialTotals && (
            <div className="league-scoreboard__row league-scoreboard__row--footer">
              <span>Week diff</span>
              {weekNumbers.map((week) => {
                const total = weeklyDifferentialTotals[week];
                const className =
                  typeof total !== "number"
                    ? "is-neutral"
                    : total > 0
                    ? "is-positive"
                    : total < 0
                    ? "is-negative"
                    : "is-neutral";
                return (
                  <span
                    key={`diff-total-${week}`}
                    className={`league-scoreboard__diff-total ${className}`}
                  >
                    {typeof total === "number"
                      ? `${total > 0 ? "+" : ""}${total}`
                      : "--"}
                  </span>
                );
              })}
              <span className="league-scoreboard__diff-total league-scoreboard__diff-total--spacer">
                —
              </span>
            </div>
          )}
        </div>
      )}

    </section>
  );
};

export default LeagueScoreboard;
