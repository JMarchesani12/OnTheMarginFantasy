import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import LeagueCard from "../../components/LeagueCard/LeagueCard";
import { getLeaguesForUser } from "../../api/leagues";
import type { League } from "../../types/league";
import { supabase } from "../../lib/supabaseClient";
import "./Home.css";

const stageOptions = [
  { value: "active", label: "Active" },
  { value: "all", label: "All" },
  { value: "completed", label: "Completed" },
] as const;

type StageValue = (typeof stageOptions)[number]["value"];

const Home = () => {
  const navigate = useNavigate();
  const [userId, setUserId] = useState<number | null>(null);
  const [displayName, setDisplayName] = useState<string | null>(null);
  const [email, setEmail] = useState<string | null>(null);
  const [stage, setStage] = useState<StageValue>("active");
  const [leagues, setLeagues] = useState<League[]>([]);

  useEffect(() => {
    let isMounted = true;

    const fetchSession = async () => {
      try {
        const { data: { session } } = await supabase.auth.getSession();
        if (!isMounted) return;

        const authUuid = session?.user?.id;
        if (!authUuid) {
          console.warn("Missing auth session");
          return;
        }

        // Look up your internal numeric user id
        const { data: userRow } = await supabase
          .from("User")
          .select('id, email, "displayName"')
          .eq("uuid", authUuid)
          .maybeSingle();

        if (!userRow) return;

        setUserId(userRow.id);
        setEmail(userRow.email);
        setDisplayName(userRow.displayName);
      } catch (e) {
        console.error("Failed to fetch auth session", e);
      }
    };


    fetchSession();

    return () => {
      isMounted = false;
    };
  }, []);

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

  const welcomeName =
    (displayName ?? "").trim() ||
    (email ?? "").trim()
  
  return (
    <main className="home">
      <header className="home__header">
        <div>
          <p className="home__eyebrow">Welcome back {welcomeName}</p>
          <h1>Your Leagues</h1>
          <p className="home__subtitle">
            Manage current leagues or spin up a new competition for the season.
          </p>
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
        </div>
        <div className="home__actions">
          <button
            className="home__signout-btn"
            type="button"
            onClick={() => navigate("/")}
          >
            Sign Out
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

      <section className="home__leagues" aria-label="Your leagues">
        {leagues.map((league) => (
          <LeagueCard key={league.leagueId} league={league} />
        ))}
      </section>
    </main>
  );
};

export default Home;
