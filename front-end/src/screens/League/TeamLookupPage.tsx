import { useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import { getLeague, getLeaguesForUser } from "../../api/leagues";
import { searchTeamsForLeague } from "../../api/schedule";
import { useCurrentUser } from "../../context/currentUserContext";
import type { League } from "../../types/league";
import type { TeamSearchResult } from "../../types/schedule";
import {
  mapLeagueFromResponse,
  normalizeLeaguesResponse,
} from "../../utils/leagueMapping";
import "./TeamLookupPage.css";

type LocationState = {
  league?: League;
};

const ownerLabelFor = (team: TeamSearchResult) =>
  team.ownerTeamName ?? team.ownerDisplayName ?? null;

const TeamLookupPage = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { league_id } = useParams();
  const state = location.state as LocationState | null;
  const { userId: currentUserId } = useCurrentUser();
  const [league, setLeague] = useState<League | null>(state?.league ?? null);
  const [leagueLoading, setLeagueLoading] = useState(false);
  const [leagueError, setLeagueError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<TeamSearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const leagueId = league?.leagueId ?? (league_id ? Number(league_id) : null);
  const trimmedQuery = useMemo(() => query.trim(), [query]);

  useEffect(() => {
    if (state?.league) {
      setLeague(mapLeagueFromResponse(state.league));
    }
  }, [state?.league]);

  useEffect(() => {
    if (league || !league_id || !currentUserId) {
      return;
    }

    let isMounted = true;

    const loadLeague = async () => {
      try {
        setLeagueLoading(true);
        setLeagueError(null);
        const response = await getLeaguesForUser(currentUserId, "all");
        if (!isMounted) return;
        const matches = normalizeLeaguesResponse(response);
        const found = matches.find(
          (item) => item.leagueId === Number(league_id)
        );
        if (found) {
          setLeague(mapLeagueFromResponse(found));
          return;
        }

        const fallback = await getLeague(Number(league_id));
        if (isMounted) {
          setLeague(mapLeagueFromResponse(fallback));
        }
      } catch (err: any) {
        if (isMounted) {
          setLeagueError(err?.message ?? "Failed to load league details.");
        }
      } finally {
        if (isMounted) {
          setLeagueLoading(false);
        }
      }
    };

    loadLeague();

    return () => {
      isMounted = false;
    };
  }, [league, league_id, currentUserId]);

  useEffect(() => {
    if (!leagueId || trimmedQuery.length < 2) {
      setResults([]);
      setError(null);
      return;
    }

    let isCancelled = false;

    const timer = window.setTimeout(async () => {
      try {
        setLoading(true);
        setError(null);
        const data = await searchTeamsForLeague(leagueId, trimmedQuery);
        if (!isCancelled) {
          setResults(data.teams);
        }
      } catch (err: any) {
        if (!isCancelled) {
          setResults([]);
          setError(err?.message ?? "Failed to search teams.");
        }
      } finally {
        if (!isCancelled) {
          setLoading(false);
        }
      }
    }, 250);

    return () => {
      isCancelled = true;
      window.clearTimeout(timer);
    };
  }, [leagueId, trimmedQuery]);

  const openTeam = (team: TeamSearchResult) => {
    if (!league) return;
    navigate(`/leagues/${league.leagueId}/teams/${team.teamId}`, {
      state: {
        league,
        teamName: team.teamName,
        ownerTeamName: team.ownerTeamName,
        ownerDisplayName: team.ownerDisplayName,
      },
    });
  };

  if (!league || !leagueId) {
    return (
      <div className="team-lookup">
        <button
          type="button"
          className="team-lookup__back"
          onClick={() => navigate(-1)}
        >
          ← Back
        </button>
        {leagueLoading ? (
          <p>Loading league details…</p>
        ) : (
          <p>
            {leagueError ??
              "Missing league context. Please open this page from your league."}
          </p>
        )}
      </div>
    );
  }

  return (
    <div className="team-lookup">
      <button
        type="button"
        className="team-lookup__back"
        onClick={() => navigate(-1)}
      >
        ← Back to League
      </button>

      <header className="team-lookup__header">
        <div>
          <h1>Find Team</h1>
          <p>
            {league.leagueName} · Season {league.seasonYear}
          </p>
        </div>
      </header>

      <section className="team-lookup__search">
        <label htmlFor="team-lookup-search">Team</label>
        <input
          id="team-lookup-search"
          type="text"
          placeholder="Search Iowa State, iowa st, Duke..."
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          autoComplete="off"
        />
      </section>

      {error && <p className="team-lookup__error">{error}</p>}
      {trimmedQuery.length > 0 && trimmedQuery.length < 2 && (
        <p className="team-lookup__hint">Enter at least two characters.</p>
      )}
      {loading && <p className="team-lookup__hint">Searching teams…</p>}
      {!loading && trimmedQuery.length >= 2 && results.length === 0 && !error && (
        <p className="team-lookup__hint">No teams match that search.</p>
      )}

      {results.length > 0 && (
        <section className="team-lookup__results" aria-label="Team search results">
          {results.map((team) => {
            const ownerLabel = ownerLabelFor(team);
            return (
              <button
                key={team.teamId}
                type="button"
                className="team-lookup__result"
                onClick={() => openTeam(team)}
              >
                <span className="team-lookup__result-main">
                  <span className="team-lookup__team-name">{team.teamName}</span>
                  <span className="team-lookup__meta">
                    {team.conferenceName ?? "Independent"}
                  </span>
                </span>
                <span
                  className={`team-lookup__owner ${
                    ownerLabel ? "" : "team-lookup__owner--empty"
                  }`}
                >
                  {ownerLabel ? `Owned by ${ownerLabel}` : "Unowned"}
                </span>
              </button>
            );
          })}
        </section>
      )}
    </div>
  );
};

export default TeamLookupPage;
