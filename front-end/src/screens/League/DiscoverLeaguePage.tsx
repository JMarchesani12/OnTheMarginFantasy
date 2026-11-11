import { useEffect, useMemo, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useRequestScope } from "../../hooks/useRequestScope";
import type { LeagueMemberPreview } from "../../types/leagueMember";
import {
  getLeaguePreview,
  type LeaguePreview,
  getMemberPreviewsOfLeague,
  requestToJoinLeague,
} from "../../api/leagues";
import { getSports } from "../../api/sport";
import type { Sport } from "../../types/sport";
import { useCurrentUser } from "../../context/currentUserContext";
import "./DiscoverLeaguePage.css";

const ownerPreviewError = (error: unknown) => {
  const status = (error as { status?: number })?.status;
  return status === 404 ? "League is unavailable or no longer discoverable." : status === 401 || status === 403 ? "You do not have access to this league preview." : "Could not load league details. Please retry.";
};

const DiscoverLeaguePage = () => {
  const { league_id } = useParams();
  const profile = useCurrentUser();
  const navigate = useNavigate();
  const id = league_id && /^[1-9]\d*$/.test(league_id) ? Number(league_id) : NaN;
  const valid = Number.isSafeInteger(id) && id > 0;
  if (!valid || !profile.userId) return <main className="discover-league">
    <button type="button" onClick={() => navigate("/leagues")}>← Back to Leagues</button>
    <p role="status">{!valid ? "Invalid league URL." : "Sign in and load your profile to view this league."}</p>
  </main>;
  return <DiscoverResolver key={`${league_id}:${profile.identityKey}`} leagueId={id} isCurrent={profile.isCurrentIdentity} />;
};

const DiscoverResolver = ({ leagueId, isCurrent }: { leagueId: number; isCurrent: () => boolean }) => {
  const navigate = useNavigate();
  const scope = useRequestScope(isCurrent);
  const [league, setLeague] = useState<LeaguePreview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    const current = scope.capture("preview");
    getLeaguePreview(leagueId, current.signal).then(data => {
      if (!current()) return;
      if (!data || data.id !== leagueId || typeof data.name !== "string" || !Number.isSafeInteger(data.sport) || data.sport <= 0 || !(data.commissionerDisplayName == null || typeof data.commissionerDisplayName === "string")) throw new Error("Invalid preview");
      setLeague(data);
    }).catch(error => { if (current()) setError(ownerPreviewError(error)); });
    return current.cancel;
  }, [leagueId, attempt, scope]);
  if (league) return <DiscoverLeagueView league={league} isCurrent={isCurrent} />;
  return <main className="discover-league">
    <button type="button" onClick={() => navigate("/leagues")}>← Back to Leagues</button>
    <p role={error ? "alert" : "status"}>{error ?? "Loading league details…"}</p>
    {error && <button type="button" onClick={() => { if (scope.isCurrent()) { setError(null); setAttempt(value => value + 1); } }}>Retry</button>}
  </main>;
};

const DiscoverLeagueView = ({ league, isCurrent }: { league: LeaguePreview; isCurrent: () => boolean }) => {
  const navigate = useNavigate();
  const { userId } = useCurrentUser();
  const scope = useRequestScope(isCurrent);
  const [sports, setSports] = useState<Sport[]>([]);
  const [sportsLoading, setSportsLoading] = useState(false);
  const [sportsError, setSportsError] = useState<string | null>(null);
  const [members, setMembers] = useState<LeagueMemberPreview[]>([]);
  const [membersLoading, setMembersLoading] = useState(false);
  const [membersError, setMembersError] = useState<string | null>(null);
  const [requestStatus, setRequestStatus] = useState<
    "idle" | "submitting" | "success" | "error"
  >("idle");
  const [teamName, setTeamName] = useState("");
  const [requestError, setRequestError] = useState<string | null>(null);

  useEffect(() => {
    if (!league) {
      return;
    }

    let isCancelled = false;
    const current = scope.capture("members");

    const loadMembers = async () => {
      setMembersLoading(true);
      setMembersError(null);

      try {
        const data = await getMemberPreviewsOfLeague(league.id, current.signal);
        if (!isCancelled && current()) {
          setMembers(data);
        }
      } catch (error: any) {
        if (!isCancelled && current()) {
          setMembersError(error?.message ?? "Failed to load league members");
        }
      } finally {
        if (!isCancelled && current()) {
          setMembersLoading(false);
        }
      }
    };

    loadMembers();

    return () => {
      isCancelled = true;
      current.cancel();
    };
  }, [league, scope]);

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

  const commissionerName = league.commissionerDisplayName ?? "Unknown";
  const sportLabel = sportLabelById.get(league.sport) ??
    (sportsLoading ? "Loading sport…" : "Unknown sport");

  const handleRequestJoin = async () => {
    if (!scope.isCurrent() || requestStatus === "submitting" || requestStatus === "success") return;
    const current = scope.capture();
    if (!userId) {
      setRequestStatus("error");
      setRequestError("You must be signed in to request a spot.");
      return;
    }

    if (!teamName.trim()) {
      setRequestStatus("error");
      setRequestError("Team name is required.");
      return;
    }

    setRequestStatus("submitting");
    setRequestError(null);

    try {
      await requestToJoinLeague(league.id, userId, undefined, teamName.trim());
      if (current()) setRequestStatus("success");
    } catch (error: any) {
      if (!current()) return;
      setRequestStatus("error");
      setRequestError(error?.message ?? "Failed to submit join request.");
    }
  };

  return (
    <main className="discover-league">
      <button
        className="discover-league__back"
        type="button"
        onClick={() => navigate("/leagues")}
      >
        ← Back to Leagues
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
        <form className="discover-league__cta" onSubmit={(event) => {
          event.preventDefault();
          void handleRequestJoin();
        }}>
          <label htmlFor="join-team-name">Your Team Name</label>
          <input id="join-team-name" type="text" required placeholder="My Team"
            value={teamName} onChange={(event) => setTeamName(event.target.value)}
            disabled={requestStatus === "submitting" || requestStatus === "success"} />
          <button
            type="submit"
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
        </form>
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
              (member.displayName ?? "Unnamed team");

            return (
              <li key={member.id}>
                <span>{displayName}</span>
              </li>
            );
          })}
        </ul>
      </section>
    </main>
  );
};

export default DiscoverLeaguePage;
