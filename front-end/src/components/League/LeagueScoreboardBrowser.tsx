import SearchableSelect from "../SearchableSelect";
import { useTeamSearchCatalog } from "../../hooks/useTeamSearchCatalog";
import { useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import type { League } from "../../types/league";
import type { TeamSearchResult } from "../../types/schedule";
import type { DailyScoreboardGame, DailyScoreboardResponse } from "../../types/dailyScoreboard";
import { getDailyScoreboard } from "../../api/dailyScoreboard";
import { searchTeamsForLeague } from "../../api/schedule";
import { safeErrorMessage, READ_ERROR } from "../../api/safeError";
import { filterDailyGames, shiftScoreboardDate, isScoreboardDate, getScoreboardTimezone } from "../../utils/dailyScoreboard";
import "./LeagueScoreboardBrowser.css";

function localToday(timezone: string) {
  const parts = new Intl.DateTimeFormat("en-US", { timeZone: timezone, year: "numeric", month: "2-digit", day: "2-digit" }).formatToParts(new Date());
  return ["year", "month", "day"].map(type => parts.find(part => part.type === type)!.value).join("-");
}

export default function LeagueScoreboardBrowser({ league }: { league: League }) {
  const navigate = useNavigate();
  const teamSearch = useTeamSearchCatalog();
  const [params, setParams] = useSearchParams();
  const timezone = getScoreboardTimezone(league.settings);
  const today = localToday(timezone);
  const [mode, setMode] = useState<"games" | "teams">(() => params.get("browse") === "teams" ? "teams" : "games");
  const [date, setDate] = useState(() => isScoreboardDate(params.get("date")) ? params.get("date")! : today);
  const [conference, setConference] = useState(() => params.get("conference") ?? "");
  const [gameQuery, setGameQuery] = useState(() => params.get("game") ?? "");
  const [teamQuery, setTeamQuery] = useState(() => params.get("q") ?? "");
  const [revision, setRevision] = useState(0);
  const [result, setResult] = useState<{ date: string; leagueId: number; data?: DailyScoreboardResponse; error?: string } | null>(null);
  const [teamResult, setTeamResult] = useState<{ leagueId: number; query: string; teams?: TeamSearchResult[]; error?: string } | null>(null);
  const search = teamQuery.trim();

  useEffect(() => {
    if (mode !== "games") return;
    const controller = new AbortController();
    let cancelled = false;
    getDailyScoreboard(league.leagueId, date, controller.signal).then(data => {
      if (!cancelled) setResult({ date, leagueId: league.leagueId, data });
    }).catch(error => {
      if (!cancelled) setResult({ date, leagueId: league.leagueId, error: safeErrorMessage(error, READ_ERROR) });
    });
    return () => { cancelled = true; controller.abort(); };
  }, [league.leagueId, date, mode, revision]);

  useEffect(() => {
    if (mode !== "teams" || search.length < 2) return;
    let cancelled = false;
    const timer = window.setTimeout(() => {
      searchTeamsForLeague(league.leagueId, search, 50).then(data => {
        if (!cancelled) setTeamResult({ leagueId: league.leagueId, query: search, teams: data.teams });
      }).catch(error => {
        if (!cancelled) setTeamResult({ leagueId: league.leagueId, query: search, error: safeErrorMessage(error, READ_ERROR) });
      });
    }, 250);
    return () => { cancelled = true; window.clearTimeout(timer); };
  }, [league.leagueId, mode, search, revision]);

  const current = result?.date === date && result.leagueId === league.leagueId ? result : null;
  const games = current?.data?.games;
  const conferences = useMemo(() => [...new Set((games ?? []).flatMap(game => [game.homeConferenceName, game.awayConferenceName]).filter((name): name is string => !!name))].sort(), [games]);
  const filtered = filterDailyGames(games ?? [], conference, gameQuery, teamSearch.index);
  const currentTeams = teamResult?.query === search && teamResult.leagueId === league.leagueId ? teamResult : null;
  const saveBrowseParam = (key: string, value: string) => setParams(previous => {
    const next = new URLSearchParams(previous); next.set(key, value); return next;
  }, { replace: true });
  const chooseDate = (value: string) => { setDate(value); saveBrowseParam("date", value); };
  const chooseMode = (value: "games" | "teams") => { setMode(value); saveBrowseParam("browse", value); };
  const openTeam = (teamId: number | null, teamName: string, ownerTeamName: string | null, ownerDisplayName: string | null) => {
    if (teamId == null) return;
    navigate(`/leagues/${league.leagueId}/teams/${teamId}`, { state: { league, teamName, ownerTeamName, ownerDisplayName } });
  };
  const ownerLabel = (game: DailyScoreboardGame, side: "home" | "away") => {
    if (game.ownershipWeekNumber == null) return "Outside league scoring weeks";
    const memberId = game[`${side}OwnerMemberId`];
    if (memberId == null) return "Unowned";
    const name = game[`${side}OwnerTeamName`] ?? game[`${side}OwnerDisplayName`] ?? `Member ${memberId}`;
    return memberId === league.memberId ? `You · ${name}` : `Owned by ${name}`;
  };

  return <section className="league-browser" aria-label="League-wide scoreboard and teams">
    <header className="league-browser__header">
      <div><h2>Scoreboard</h2><p>Every game. Every team. Your league’s ownership.</p></div>
      <div className="league-browser__modes" role="group" aria-label="Browse league">
        <button type="button" aria-pressed={mode === "games"} onClick={() => chooseMode("games")}>Daily games</button>
        <button type="button" aria-pressed={mode === "teams"} onClick={() => chooseMode("teams")}>Find team</button>
      </div>
    </header>
    {mode === "games" ? <>
      <div className="league-browser__toolbar">
        <div className="league-browser__date-nav">
          <button type="button" aria-label="Previous day" onClick={() => chooseDate(shiftScoreboardDate(date, -1))}>‹</button>
          <label>Game date<input type="date" value={date} onChange={event => { if (isScoreboardDate(event.target.value)) chooseDate(event.target.value); }} /></label>
          <button type="button" aria-label="Next day" onClick={() => chooseDate(shiftScoreboardDate(date, 1))}>›</button>
          <div className="league-browser__date-actions">
            <button type="button" onClick={() => chooseDate(today)}>Today</button>
            <button type="button" onClick={() => { setResult(null); setRevision(value => value + 1); }}>Refresh</button>
          </div>
        </div>
        <div className="league-browser__filters">
          <div><label htmlFor="scoreboard-conference">Conference</label>
            <SearchableSelect id="scoreboard-conference" value={conference}
              onChange={value => { setConference(value); saveBrowseParam("conference", value); }}
              options={[{ value: "", label: "All conferences" },
                ...[...new Set([...(conference ? [conference] : []), ...conferences])].map(name => ({ value: name, label: name }))]} />
          </div>
          <label>Find a game<input type="search" aria-describedby="league-game-search-help" value={gameQuery} placeholder="Name or abbreviation (e.g. UNI)" maxLength={120} onChange={event => { setGameQuery(event.target.value); saveBrowseParam("game", event.target.value); }} /></label>
        </div>
      </div>
      {teamSearch.error && <p role="status">Alternate names could not load. <button type="button" onClick={teamSearch.retry}>Retry search names</button></p>}
      <p id="league-game-search-help" className="league-browser__hint">Search by name or abbreviation; minor typos work too.</p>
      <p className="league-browser__hint">Times in {current?.data?.timezone ?? timezone}. Ownership shown for each game’s scoring week.</p>
      {!current && <p role="status">Loading daily games…</p>}
      {current?.error && <p role="alert">{current.error} <button type="button" onClick={() => { setResult(null); setRevision(value => value + 1); }}>Retry games</button></p>}
      {games && <>
        <p className="league-browser__count">{filtered.length} {filtered.length === 1 ? "game" : "games"}{conference ? ` · ${conference}` : " · All conferences"}</p>
        {filtered.length === 0 && <p>{games.length ? "No games match these filters." : "No games scheduled for this date."}</p>}
        <div className="league-browser__games">
          {filtered.map(game => <article className="league-browser__game" key={game.id} aria-label={`${game.awayTeamName} at ${game.homeTeamName}`}>
            <div className="league-browser__game-meta">
              <span>{game.isCompleted ? "Final" : game.timeTBD ? "Time TBD" : new Date(game.date).toLocaleTimeString(undefined, { timeZone: current?.data?.timezone ?? timezone, hour: "numeric", minute: "2-digit" })}</span>
              <span>{game.broadcast}</span>
            </div>
            {(["away", "home"] as const).map(side => <div className="league-browser__team" key={side}>
              <div className="league-browser__team-main">
                <button type="button" className="league-browser__team-name" disabled={game[`${side}TeamId`] == null} onClick={() => openTeam(game[`${side}TeamId`], game[`${side}TeamName`], game[`${side}OwnerTeamName`], game[`${side}OwnerDisplayName`])}>{game[`${side}TeamName`]}</button>
                <span className="league-browser__conference">{side === "home" ? "Home" : "Away"}{game[`${side}ConferenceName`] ? ` · ${game[`${side}ConferenceName`]}` : ""}</span>
                <span className={`league-browser__owner${game[`${side}OwnerMemberId`] === league.memberId ? " league-browser__owner--you" : ""}`}>{ownerLabel(game, side)}</span>
              </div>
              <strong className="league-browser__score">{game.isCompleted || game.homeScore !== 0 || game.awayScore !== 0 ? game[`${side}Score`] : "—"}</strong>
            </div>)}
          </article>)}
        </div>
      </>}
    </> : <div className="league-browser__team-search">
      <label>Find any team<input type="search" aria-describedby="league-team-search-help" value={teamQuery} placeholder="Name or abbreviation (e.g. UNI)" maxLength={120} onChange={event => { setTeamQuery(event.target.value); saveBrowseParam("q", event.target.value); }} /></label>
      <p className="league-browser__hint">Find teams even when they aren’t playing today. Ownership here is current; select a team to see its season schedule.</p>
      {search.length < 2 && <p>Enter at least two characters.</p>}
      <p id="league-team-search-help" className="league-browser__hint">Search by name or abbreviation; minor typos work too.</p>
      {search.length >= 2 && !currentTeams && <p role="status">Searching teams…</p>}
      {currentTeams?.error && <p role="alert">{currentTeams.error} <button type="button" onClick={() => { setTeamResult(null); setRevision(value => value + 1); }}>Retry search</button></p>}
      {currentTeams?.teams?.length === 0 && <p>No teams match that search.</p>}
      <div className="league-browser__team-results">
        {currentTeams?.teams?.map(team => <button type="button" className="league-browser__team-result" key={team.teamId} onClick={() => openTeam(team.teamId, team.teamName, team.ownerTeamName, team.ownerDisplayName)}>
          <strong>{team.teamName}</strong><span>{team.conferenceName ?? "Conference unavailable"}</span>
          <span className="league-browser__owner">{team.ownerMemberId == null ? "Unowned" : `Owned by ${team.ownerTeamName ?? team.ownerDisplayName ?? `Member ${team.ownerMemberId}`}`}</span>
        </button>)}
      </div>
      {currentTeams?.teams?.length === 50 && <p className="league-browser__hint">Showing the first 50 matches. Refine your search to narrow the results.</p>}
    </div>}
  </section>;
}
