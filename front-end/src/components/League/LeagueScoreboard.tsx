import { useEffect, useRef, useState, type CSSProperties, type FC } from "react";
import { getLeagueRank } from "../../utils/leagueDetailCalculations";
import "./LeagueScoreboard.css";

export type ScoreboardRow = {
  memberId: number;
  teamName: string;
  totalPoints: number;
  bonusPoints?: number;
  seasonTotalAvailable?: boolean;
  weeklyPoints: Record<number, number | null | undefined>;
  weeklyDifferentials: Record<number, number | null | undefined>;
};

type LeagueScoreboardProps = {
  weekNumbers: number[];
  rows: ScoreboardRow[];
  currentWeekNumber: number | null;
  currentMemberId?: number | null;
  showBonuses?: boolean;
  loading: boolean;
  error: string | null;
};

const LeagueScoreboard: FC<LeagueScoreboardProps> = ({
  weekNumbers,
  rows,
  currentMemberId,
  loading,
  error,
  showBonuses = false,
}) => {
  const [view, setView] = useState<"latest" | "all">("latest");
  const tableRef = useRef<HTMLDivElement>(null);
  const latestWeek = weekNumbers.length ? Math.max(...weekNumbers) : null;
  const sortedWeeks = [...weekNumbers].sort((a, b) => a - b);
  const visibleWeeks = view === "all" ? sortedWeeks : latestWeek == null ? [] : [latestWeek];
  const rankedRows = [...rows].sort((a, b) => b.totalPoints - a.totalPoints);
  const standings = rankedRows.filter(row => row.seasonTotalAvailable !== false).map(row => ({ memberId: row.memberId, points: row.totalPoints }));
  useEffect(() => {
    if (view === "all" && tableRef.current) {
      tableRef.current.scrollLeft = tableRef.current.scrollWidth;
    }
  }, [view, latestWeek, loading, error]);
  const jumpToWeek = (edge: "first" | "latest") => {
    const table = tableRef.current;
    if (table) table.scrollTo({ left: edge === "first" ? 0 : table.scrollWidth });
  };

  if (!weekNumbers.length && !loading && !error) {
    return null;
  }

  return (
    <section className={`league-scoreboard league-scoreboard--${view}`}>
      <header className="league-scoreboard__header">
        <div>
          <p className="league-scoreboard__eyebrow">League competition</p>
          <h2>Standings</h2>
          <p className="league-scoreboard__subhead">
            Latest scoring week {latestWeek ?? "-"}
          </p>
        </div>
      </header>

      {weekNumbers.length > 0 && <div className="league-scoreboard__controls">
        <div className="league-scoreboard__view-toggle" role="group" aria-label="Standings view">
          <button type="button" aria-pressed={view === "latest"} onClick={() => setView("latest")}>Latest week</button>
          <button type="button" aria-pressed={view === "all"} onClick={() => setView("all")}>All weeks</button>
        </div>
        {view === "all" && <div className="league-scoreboard__shortcuts" role="group" aria-label="Jump to scoring week">
          <button type="button" onClick={() => jumpToWeek("first")}>First week</button>
          <button type="button" onClick={() => jumpToWeek("latest")}>Latest week</button>
        </div>}
      </div>}
      {view === "all" && <p className="league-scoreboard__scroll-hint">Scroll sideways to compare weeks. Teams are ranked by season points.</p>}
      {loading && <p className="league-scoreboard__loading">Loading scoreboard…</p>}
      {error && <p className="league-scoreboard__error">{error}</p>}

      {!loading && !error && weekNumbers.length > 0 && (
        <div
          className="league-scoreboard__table"
          ref={tableRef}
          role="region"
          tabIndex={view === "all" ? 0 : undefined}
          aria-label={view === "all" ? "All weekly standings, scroll horizontally" : "Latest week standings"}
          style={{ "--week-count": visibleWeeks.length } as CSSProperties}
        >
          <div className="league-scoreboard__row league-scoreboard__row--header">
            <span>Rank / Team</span>
            {visibleWeeks.map((week) => (
              <span key={`header-week-${week}`}>Week {week}</span>
            ))}
            <span>Season</span>
          </div>
          {rankedRows.map((row) => (
            <div className={`league-scoreboard__row${row.memberId === currentMemberId ? " league-scoreboard__row--yours" : ""}`} key={`member-${row.memberId}`}>
              <span className="league-scoreboard__team">
                <span className="league-scoreboard__rank">{getLeagueRank(standings, row.memberId)?.rank ?? "—"}.</span> {row.teamName}
                {row.memberId === currentMemberId && <span className="league-scoreboard__you">You</span>}
              </span>
              {visibleWeeks.map((week) => {
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
              <span className="league-scoreboard__total">
                {row.seasonTotalAvailable === false ? "—" : row.totalPoints}
                {showBonuses && !!row.bonusPoints && <small> ({row.bonusPoints > 0 ? "+" : ""}{row.bonusPoints} bonus)</small>}
              </span>
            </div>
          ))}
        </div>
      )}

    </section>
  );
};

export default LeagueScoreboard;
