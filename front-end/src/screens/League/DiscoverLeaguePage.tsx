import { useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import type { LeagueSearchResult } from "../../types/league";
import type { LeagueMember } from "../../types/leagueMember";
import {
  getMembersOfLeague,
  requestToJoinLeague,
} from "../../api/leagues";
import { getSports } from "../../api/sport";
import type { Sport } from "../../types/sport";
import { useCurrentUser } from "../../context/currentUserContext";
import "./DiscoverLeaguePage.css";

type LocationState = {
  league?: LeagueSearchResult;
};

const DiscoverLeaguePage = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const state = location.state as LocationState | null;
  const league = state?.league;
  const { userId, displayName, email } = useCurrentUser();

  const [sports, setSports] = useState<Sport[]>([]);
  const [sportsLoading, setSportsLoading] = useState(false);
  const [sportsError, setSportsError] = useState<string | null>(null);
  const [members, setMembers] = useState<LeagueMember[]>([]);
  const [membersLoading, setMembersLoading] = useState(false);
  const [membersError, setMembersError] = useState<string | null>(null);
  const [requestStatus, setRequestStatus] = useState<
    "idle" | "submitting" | "success" | "error"
  >("idle");
  const [requestError, setRequestError] = useState<string | null>(null);

  useEffect(() => {
    if (!league) {
      return;
    }

    let isCancelled = false;

    const loadMembers = async () => {
      setMembersLoading(true);
      setMembersError(null);

      try {
        const data = await getMembersOfLeague(league.id);
        if (!isCancelled) {
          setMembers(data);
        }
      } catch (error: any) {
        if (!isCancelled) {
          setMembersError(error?.message ?? "Failed to load league members");
        }
      } finally {
        if (!isCancelled) {
          setMembersLoading(false);
        }
      }
    };

    loadMembers();

    return () => {
      isCancelled = true;
    };
  }, [league]);

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

  const sportLabelById = useMemo(() => {
    const map = new Map<number, string>();
    sports.forEach((sport) => map.set(sport.id, sport.name));
    return map;
  }, [sports]);

  if (!league) {
    return (
      <main className="discover-league">
        <button
          className="discover-league__back"
          type="button"
          onClick={() => navigate(-1)}
        >
          ← Back
        </button>
        <p>League data is not available. Please open this page from search.</p>
      </main>
    );
  }

  const commissionerName = league.commissionerDisplayName ?? "Unknown";
  const sportLabel = sportLabelById.get(league.sport) ??
    (sportsLoading ? "Loading sport…" : "Unknown sport");

  const handleRequestJoin = async () => {
    if (!userId) {
      setRequestStatus("error");
      setRequestError("You must be signed in to request a spot.");
      return;
    }

    const fallbackName =
      displayName?.trim() ||
      email?.split("@")[0] ||
      "My";
    const teamName = `${fallbackName}'s Team`;

    setRequestStatus("submitting");
    setRequestError(null);

    try {
      await requestToJoinLeague(league.id, userId, undefined, teamName);
      setRequestStatus("success");
    } catch (error: any) {
      setRequestStatus("error");
      setRequestError(error?.message ?? "Failed to submit join request.");
    }
  };

  return (
    <main className="discover-league">
      <button
        className="discover-league__back"
        type="button"
        onClick={() => navigate(-1)}
      >
        ← Back
      </button>

      <section className="discover-league__hero">
        <div>
          <h1>{league.name}</h1>
          <p className="discover-league__meta">
            {sportLabel} · Commissioner: {commissionerName}
          </p>
          {sportsError && (
            <p className="discover-league__error">{sportsError}</p>
          )}
        </div>
        <div className="discover-league__cta">
          <button
            type="button"
            onClick={handleRequestJoin}
            disabled={requestStatus === "submitting" || requestStatus === "success"}
          >
            {requestStatus === "success" ? "Request Sent" : "Request to Join"}
          </button>
          {requestError && (
            <p className="discover-league__error">{requestError}</p>
          )}
          {requestStatus === "success" && (
            <p className="discover-league__success">
              Request submitted. The commissioner will review it shortly.
            </p>
          )}
        </div>
      </section>

      <section className="discover-league__members">
        <div className="discover-league__members-header">
          <h2>League Members</h2>
          <span>{members.length} total</span>
        </div>

        {membersLoading && (
          <p className="discover-league__status">Loading members…</p>
        )}
        {membersError && (
          <p className="discover-league__error">{membersError}</p>
        )}

        {!membersLoading && !membersError && members.length === 0 && (
          <p className="discover-league__status">
            No members yet. Be the first to join.
          </p>
        )}

        <ul className="discover-league__member-list">
          {members.map((member) => {
            const displayName =
              member.teamName?.trim() ||
              String(member.displayName ?? `User ${member.userId}`);

            return (
              <li key={member.id}>
                <span>{displayName}</span>
                <span className="discover-league__member-meta">
                  Draft #{member.draftOrder ?? "TBD"}
                </span>
              </li>
            );
          })}
        </ul>
      </section>
    </main>
  );
};

export default DiscoverLeaguePage;
