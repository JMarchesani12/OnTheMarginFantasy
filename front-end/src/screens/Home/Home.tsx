import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import LeagueCard from "../../components/LeagueCard/LeagueCard";
import { getLeaguesForUser, searchLeagues } from "../../api/leagues";
import { getSports } from "../../api/sport";
import type { League, LeagueSearchResult } from "../../types/league";
import type { Sport } from "../../types/sport";
import "./Home.css";
import { useCurrentUser } from "../../context/currentUserContext";
import { useAuth } from "../../context/AuthContext";

const stageOptions = [
  { value: "active", label: "Active" },
  { value: "all", label: "All" },
  { value: "completed", label: "Completed" },
] as const;

type StageValue = (typeof stageOptions)[number]["value"];

type HomeTab = "leagues" | "search";

const SEARCH_LIMIT = 6;

const Home = () => {
  const navigate = useNavigate();
  const [tab, setTab] = useState<HomeTab>("leagues");
  const [stage, setStage] = useState<StageValue>("active");
  const [leagues, setLeagues] = useState<League[]>([]);
  const [sports, setSports] = useState<Sport[]>([]);
  const [sportsLoading, setSportsLoading] = useState(false);
  const [sportsError, setSportsError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [sportId, setSportId] = useState("all");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [searchResults, setSearchResults] = useState<LeagueSearchResult[]>([]);
  const [searchLoading, setSearchLoading] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [page, setPage] = useState(0);
  const [hasMore, setHasMore] = useState(false);

  const { userId, displayName, email } = useCurrentUser();

  console.log(userId)

  const { signOut } = useAuth();

  useEffect(() => {
    if (!userId) {
      return;
    }

    let isMounted = true;

    async function loadLeagues() {
      try {
        const response = await getLeaguesForUser(userId, stage);

        if (!isMounted) {
          return;
        }

        console.log(response)

        if (Array.isArray(response)) {
          setLeagues(response as League[]);
        } else if (
          response &&
          typeof response === "object" &&
          Array.isArray((response as { leagues?: League[] }).leagues)
        ) {
          setLeagues((response as { leagues: League[] }).leagues);
        } else {
          console.warn("Unexpected leagues payload", response);
          setLeagues([]);
        }
      } catch (error) {
        console.error("Failed to load leagues", error);
      }
    }

    loadLeagues();

    return () => {
      isMounted = false;
    };
  }, [userId, stage]);

  useEffect(() => {
    let isMounted = true;

    const loadSports = async () => {
      setSportsLoading(true);
      setSportsError(null);

      try {
        const data = await getSports();
        if (!isMounted) {
          return;
        }
        setSports(data);
      } catch (error: any) {
        if (isMounted) {
          setSportsError(error?.message ?? "Failed to load sports");
        }
      } finally {
        if (isMounted) {
          setSportsLoading(false);
        }
      }
    };

    loadSports();

    return () => {
      isMounted = false;
    };
  }, []);

  useEffect(() => {
    const timeout = window.setTimeout(() => {
      setDebouncedQuery(query.trim());
    }, 400);

    return () => {
      window.clearTimeout(timeout);
    };
  }, [query]);

  useEffect(() => {
    if (!debouncedQuery) {
      setSearchResults([]);
      setHasMore(false);
      setSearchLoading(false);
      setSearchError(null);
      return;
    }

    let isCancelled = false;

    const loadSearchResults = async () => {
      setSearchLoading(true);
      setSearchError(null);

      try {
        const results = await searchLeagues({
          query: debouncedQuery,
          sportId: sportId === "all" ? undefined : Number(sportId),
          limit: SEARCH_LIMIT,
          offset: page * SEARCH_LIMIT,
        });

        if (!isCancelled) {
          setSearchResults(results);
          setHasMore(results.length === SEARCH_LIMIT);
        }
      } catch (error: any) {
        if (!isCancelled) {
          setSearchError(error?.message ?? "Failed to search leagues");
        }
      } finally {
        if (!isCancelled) {
          setSearchLoading(false);
        }
      }
    };

    loadSearchResults();

    return () => {
      isCancelled = true;
    };
  }, [debouncedQuery, sportId, page]);

  const sportLabelById = useMemo(() => {
    const map = new Map<number, string>();
    sports.forEach((sport) => {
      map.set(sport.id, sport.name);
    });
    return map;
  }, [sports]);

  const welcomeName =
    (displayName ?? "").trim() ||
    (email ?? "").trim()
  
  return (
    <main className="home">
      <header className="home__header">
        <div>
          <p className="home__eyebrow">Welcome back {welcomeName}</p>
          <h1>{tab === "leagues" ? "Your Leagues" : "Discover Leagues"}</h1>
          <p className="home__subtitle">
            {tab === "leagues"
              ? "Manage current leagues or spin up a new competition for the season."
              : "Search for discoverable leagues to join by name or sport."}
          </p>
          {tab === "leagues" && (
            <div className="home__stage-filter">
              <label htmlFor="league-stage">View</label>
              <select
                id="league-stage"
                value={stage}
                onChange={(event) =>
                  setStage(event.target.value as StageValue)
                }
              >
                {stageOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>
          )}
        </div>
        <div className="home__actions">
          <button
            className="home__signout-btn"
            type="button"
            onClick={async () => {
              await signOut();
              navigate("/");
            }}
          >
            Sign Out
          </button>
          <button
            className="home__settings-btn"
            type="button"
            onClick={() => navigate("/settings")}
          >
            Settings
          </button>
          <button
            className="home__create-btn"
            type="button"
            onClick={() => navigate("/leagues/new")}
          >
            Create League
          </button>
        </div>
      </header>

      <div className="home__tabs" role="tablist" aria-label="League tabs">
        <button
          className={`home__tab ${tab === "leagues" ? "home__tab--active" : ""}`}
          type="button"
          role="tab"
          aria-selected={tab === "leagues"}
          onClick={() => setTab("leagues")}
        >
          Your Leagues
        </button>
        <button
          className={`home__tab ${tab === "search" ? "home__tab--active" : ""}`}
          type="button"
          role="tab"
          aria-selected={tab === "search"}
          onClick={() => setTab("search")}
        >
          Search Leagues
        </button>
      </div>

      {tab === "leagues" ? (
        <section className="home__leagues" aria-label="Your leagues">
          {leagues.map((league) => (
            <LeagueCard key={league.leagueId} league={league} />
          ))}
        </section>
      ) : (
        <section className="home__search" aria-label="Search leagues">
          <div className="home__search-controls">
            <div className="home__search-field">
              <label htmlFor="league-search">Search by league name</label>
              <input
                id="league-search"
                type="search"
                placeholder="Try “Conference Clash”"
                value={query}
                onChange={(event) => {
                  setQuery(event.target.value);
                  setPage(0);
                }}
              />
            </div>
            <div className="home__search-field">
              <label htmlFor="league-sport">Sport (optional)</label>
              <select
                id="league-sport"
                value={sportId}
                onChange={(event) => {
                  setSportId(event.target.value);
                  setPage(0);
                }}
                disabled={sportsLoading}
              >
                <option value="all">All sports</option>
                {sports.map((sport) => (
                  <option key={sport.id} value={String(sport.id)}>
                    {sport.name}
                  </option>
                ))}
              </select>
              {sportsError && (
                <span className="home__search-error">{sportsError}</span>
              )}
            </div>
          </div>

          {searchLoading && (
            <p className="home__search-status">Searching leagues…</p>
          )}
          {searchError && (
            <p className="home__search-error">{searchError}</p>
          )}

          {!searchLoading && debouncedQuery && searchResults.length === 0 && (
            <p className="home__search-status">No leagues match that search.</p>
          )}

          {!debouncedQuery && (
            <p className="home__search-status">
              Start typing to search discoverable leagues.
            </p>
          )}

          <div className="home__search-results">
            {searchResults.map((result) => {
              const sportLabel =
                sportLabelById.get(result.sport) ?? "Unknown sport";
              const commissionerName =
                result.commissionerDisplayName ?? "Unknown commissioner";

              return (
                <article key={result.id} className="home__search-card">
                  <div>
                    <h2>{result.name}</h2>
                    <p className="home__search-meta">
                      {sportLabel} · Commissioner: {commissionerName}
                    </p>
                  </div>
                  <button
                    className="home__search-action"
                    type="button"
                    onClick={() =>
                      navigate(`/leagues/discover/${result.id}`, {
                        state: { league: result },
                      })
                    }
                  >
                    View League
                  </button>
                </article>
              );
            })}
          </div>

          {debouncedQuery && searchResults.length > 0 && (
            <div className="home__pagination">
              <button
                type="button"
                disabled={page === 0 || searchLoading}
                onClick={() => setPage((prev) => Math.max(0, prev - 1))}
              >
                Previous
              </button>
              <span>Page {page + 1}</span>
              <button
                type="button"
                disabled={!hasMore || searchLoading}
                onClick={() => setPage((prev) => prev + 1)}
              >
                Next
              </button>
            </div>
          )}
        </section>
      )}
    </main>
  );
};

export default Home;
