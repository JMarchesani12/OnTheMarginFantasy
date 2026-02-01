import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import { io, type Socket } from "socket.io-client";
import type { League } from "../../types/league";
import type { OwnedTeam } from "../../types/schedule";
import type {
  DraftMember,
  DraftSnapshot,
  DraftSummaryPick,
  DraftState,
  DraftTurnSlot,
} from "../../types/draft";
import { getAvailableTeams } from "../../api/roster";
import { createDraftPick, getDraftState, pauseDraft, resumeDraft, startDraft } from "../../api/draft";
import { getConferences, getLeague, getLeaguesForUser } from "../../api/leagues";
import { useAuth } from "../../context/AuthContext";
import { useCurrentUser } from "../../context/currentUserContext";
import { normalizeOwnedTeams, type RawOwnedTeam } from "../../utils/teams";
import { safeLocalStorage } from "../../utils/safeStorage";
import {
  mapLeagueFromResponse,
  normalizeLeaguesResponse,
} from "../../utils/leagueMapping";
import "./LeagueDraftPage.css";

type LocationState = {
  league?: League;
  autoJoin?: boolean;
};

type GroupedTeams = [string, OwnedTeam[]][];

const LeagueDraftPage = () => {
  const navigate = useNavigate();
  const { league_id } = useParams();
  const location = useLocation();
  const state = location.state as LocationState | null;
  const [league, setLeague] = useState<League | null>(state?.league ?? null);
  const [leagueLoading, setLeagueLoading] = useState(false);
  const [leagueError, setLeagueError] = useState<string | null>(null);
  const { session } = useAuth();
  const { userId: currentUserId } = useCurrentUser();

  const leagueId = league?.leagueId ?? (league_id ? Number(league_id) : null);

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

  const [availableTeams, setAvailableTeams] = useState<OwnedTeam[]>([]);
  const [selectedTeam, setSelectedTeam] = useState<OwnedTeam | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState("");
  const [conferenceFilter, setConferenceFilter] = useState("all");
  const [draftSelections, setDraftSelections] = useState<OwnedTeam[]>([]);
  const [draftState, setDraftState] = useState<DraftState | null>(null);
  const [draftMembers, setDraftMembers] = useState<DraftMember[]>([]);
  const [draftActionLoading, setDraftActionLoading] = useState(false);
  const [draftSummaryPicks, setDraftSummaryPicks] = useState<DraftSummaryPick[]>([]);
  const [draftSummaryLoading, setDraftSummaryLoading] = useState(false);
  const [showDraftComplete, setShowDraftComplete] = useState(false);
  const [hasJoinedDraft, setHasJoinedDraft] = useState(false);
  const [nowMs, setNowMs] = useState(() => Date.now());
  const [clockOffsetMs, setClockOffsetMs] = useState(0);
  const [onDeckSlot, setOnDeckSlot] = useState<DraftTurnSlot | null>(null);
  const [inTheHoleSlot, setInTheHoleSlot] = useState<DraftTurnSlot | null>(null);
  const [conferenceLimits, setConferenceLimits] = useState<Map<string, number>>(
    new Map()
  );
  const teamMetaRef = useRef<Map<number, OwnedTeam>>(new Map());
  const draftWeekNumber = 1;
  const socketRef = useRef<Socket | null>(null);
  const previousDraftStatusRef = useRef<string | null>(null);
  const joinQueuedRef = useRef(false);
  const pausedSnapshotLoadedRef = useRef(false);
  const initialSnapshotLoadedRef = useRef(false);
  const resolveConferenceName = useCallback(
    (conferenceName: string | null) => {
      if (conferenceName) {
        return conferenceName;
      }
      if (conferenceLimits.has("Independent")) {
        return "Independent";
      }
      return "Unassigned";
    },
    [conferenceLimits]
  );

  const isBrowser = typeof window !== "undefined";
  const storageKey =
    leagueId && league?.memberId
      ? `draftSelections:${leagueId}:${league.memberId}`
      : null;
  const socketUrl =
    import.meta.env.VITE_SOCKET_URL ??
    import.meta.env.VITE_API_BASE_URL ??
    "http://127.0.0.1:5050";

  const loadTeams = useCallback(async () => {
    if (!leagueId) {
      return;
    }

    try {
      setLoading(true);
      setError(null);

      const data = await getAvailableTeams(draftWeekNumber, leagueId);
      const normalized = normalizeOwnedTeams(data as RawOwnedTeam[]);
      setAvailableTeams(normalized);
    } catch (err: any) {
      setError(err?.message ?? "Failed to load available teams");
    } finally {
      setLoading(false);
    }
  }, [leagueId, draftWeekNumber]);

  useEffect(() => {
    let cancelled = false;
    loadTeams();

    if (!leagueId || session?.access_token) {
      return () => {
        cancelled = true;
      };
    }

    const interval = window.setInterval(() => {
      if (!cancelled) {
        loadTeams();
      }
    }, 10000);

    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, [loadTeams, leagueId, session?.access_token]);

  useEffect(() => {
    if (!leagueId) {
      return;
    }

    let isCancelled = false;

    const loadConferences = async () => {
      try {
        const data = await getConferences(leagueId);
        if (isCancelled || !data?.conferences) {
          return;
        }
        const next = new Map<string, number>();
        data.conferences.forEach((conf) => {
          next.set(conf.displayName, conf.maxTeamsPerOwner);
        });
        setConferenceLimits(next);
      } catch (err) {
        console.warn("Failed to load conferences for draft table.", err);
      }
    };

    loadConferences();

    return () => {
      isCancelled = true;
    };
  }, [leagueId]);

  useEffect(() => {
    if (!storageKey || !isBrowser) {
      return;
    }

    try {
      const stored = safeLocalStorage.getItem(storageKey);
      if (stored) {
        const parsed = JSON.parse(stored) as RawOwnedTeam[];
        setDraftSelections(normalizeOwnedTeams(parsed));
      }
    } catch (err) {
      console.warn("Failed to load draft selections", err);
    }
  }, [storageKey]);

  const persistSelections = useCallback(
    (teams: OwnedTeam[]) => {
      if (!storageKey || !isBrowser) {
        return;
      }

      try {
        safeLocalStorage.setItem(storageKey, JSON.stringify(teams));
      } catch (err) {
        console.warn("Failed to persist draft selections", err);
      }
    },
    [isBrowser, storageKey]
  );

  const applyDraftSnapshot = useCallback(
    (payload: unknown) => {
      const snapshot =
        payload && typeof payload === "object" && "snapshot" in payload
          ? (payload as { snapshot?: unknown }).snapshot
          : payload;

      if (!snapshot || typeof snapshot !== "object") {
        void loadTeams();
        return;
      }

      const data = snapshot as DraftSnapshot;
      const available = data.availableTeams;
      const recent = data.recentPicks ?? data.draftSelections ?? data.picks;
      const state = data.state;
      const members = data.members;
      const picks = data.picks;
      const serverNow = data.serverNow;
      const onDeck = data.onDeck ?? data.state?.onDeck ?? null;
      const inTheHole = data.inTheHole ?? data.state?.inTheHole ?? null;

      if (Array.isArray(available)) {
        const normalizedAvailable = normalizeOwnedTeams(available as RawOwnedTeam[]);
        setAvailableTeams(normalizedAvailable);
        normalizedAvailable.forEach((team) => {
          teamMetaRef.current.set(team.teamId, team);
        });
      } else {
        void loadTeams();
      }

      if (Array.isArray(recent)) {
        if (!Array.isArray(picks)) {
          const normalized = normalizeOwnedTeams(
            (recent as RawOwnedTeam[]).map((team) => ({
              ...team,
              teamId:
                typeof team.teamId === "number"
                  ? team.teamId
                  : typeof (team as Record<string, unknown>).sportTeamId === "number"
                  ? ((team as Record<string, unknown>).sportTeamId as number)
                  : team.teamId,
              teamName:
                typeof team.teamName === "string"
                  ? team.teamName
                  : typeof (team as Record<string, unknown>).sportTeamName === "string"
                  ? ((team as Record<string, unknown>).sportTeamName as string)
                  : team.teamName,
            }))
          );
          setDraftSelections(normalized);
          persistSelections(normalized);
        }
      }

      if (state && typeof state === "object") {
        setDraftState(state as DraftState);
      }

      if (Array.isArray(members)) {
        setDraftMembers(members as DraftMember[]);
      }

      if (Array.isArray(picks)) {
        const normalizedPicks = picks as DraftSummaryPick[];
        setDraftSummaryPicks(normalizedPicks);
        const memberId = league?.memberId ?? null;
        if (memberId == null) {
          return;
        }
        const userPicks = normalizedPicks.filter((pick) => pick.memberId === memberId);
        setDraftSelections((current) => {
          const currentById = new Map(current.map((team) => [team.teamId, team]));
          const pickedTeams = userPicks.map((pick) => {
            const known =
              teamMetaRef.current.get(pick.sportTeamId) ??
              currentById.get(pick.sportTeamId);
            if (known) {
              return known;
            }
            return {
              teamId: pick.sportTeamId,
              teamName: pick.sportTeamName ?? `Team ${pick.sportTeamId}`,
              conferenceName:
                (pick as DraftSummaryPick & { conferenceName?: string | null })
                  .conferenceName ?? null,
            };
          });
          persistSelections(pickedTeams);
          return pickedTeams;
        });
        const pickedIds = new Set(normalizedPicks.map((pick) => pick.sportTeamId));
        setAvailableTeams((current) =>
          current.filter((team) => !pickedIds.has(team.teamId))
        );
      }

      setOnDeckSlot(onDeck ?? null);
      setInTheHoleSlot(inTheHole ?? null);

      if (serverNow) {
        const serverMs = Date.parse(serverNow);
        if (!Number.isNaN(serverMs)) {
          setClockOffsetMs(serverMs - Date.now());
        }
      }
    },
    [loadTeams, persistSelections]
  );

  useEffect(() => {
    if (!leagueId || !session?.access_token) {
      return;
    }
    const socket = io(socketUrl, {
      auth: { token: session.access_token },
    });

    socketRef.current = socket;

    socket.on("connect", () => {
      setError(null);
    });

    socket.on("draft:snapshot", (payload) => {
      applyDraftSnapshot(payload);
    });

    socket.on("draft:updated", (payload) => {
      applyDraftSnapshot(payload);
    });

    socket.on("draft:error", (payload) => {
      const message =
        typeof payload === "string"
          ? payload
          : (payload as { message?: string } | null)?.message;
      setError(message ?? "Draft socket error");
    });

    socket.on("connect_error", (err) => {
      setError(err?.message ?? "Failed to connect to draft socket");
    });

    if (!joinQueuedRef.current) {
      socket.emit("draft:join", { leagueId });
      joinQueuedRef.current = true;
      setHasJoinedDraft(true);
    }

    return () => {
      if (hasJoinedDraft) {
        socket.emit("draft:leave", { leagueId });
      }
      socket.disconnect();
      socketRef.current = null;
      joinQueuedRef.current = false;
    };
  }, [applyDraftSnapshot, hasJoinedDraft, leagueId, session?.access_token, socketUrl]);

  const groupTeams = (teams: OwnedTeam[]): GroupedTeams => {
    const map = new Map<string, OwnedTeam[]>();

    teams.forEach((team) => {
      const key = resolveConferenceName(team.conferenceName);
      const current = map.get(key) ?? [];
      current.push(team);
      map.set(key, current);
    });

    return Array.from(map.entries()).sort(([a], [b]) => a.localeCompare(b));
  };

  const uniqueConferences = useMemo(() => {
    const all = availableTeams
      .map((team) => resolveConferenceName(team.conferenceName))
      .filter(Boolean);
    return Array.from(new Set(all)).sort((a, b) => a.localeCompare(b));
  }, [availableTeams, resolveConferenceName]);

  const applyFilters = (teams: OwnedTeam[]) =>
    teams.filter((team) => {
      const matchesSearch = team.teamName
        .toLowerCase()
        .includes(searchTerm.toLowerCase());
      const matchesConference =
        conferenceFilter === "all" ||
        resolveConferenceName(team.conferenceName) === conferenceFilter;
      return matchesSearch && matchesConference;
    });

  const groupedAvailable = useMemo(
    () => groupTeams(applyFilters(availableTeams)),
    [availableTeams, searchTerm, conferenceFilter]
  );
  const isCommissioner =
    currentUserId != null && league?.commissionerId === currentUserId;

  const loadDraftSummary = useCallback(async () => {
    if (!leagueId) {
      return;
    }

    try {
      setDraftSummaryLoading(true);
      const data = await getDraftState(leagueId);
      if (data && typeof data === "object") {
        if (Array.isArray(data.picks)) {
          const normalizedPicks = data.picks as DraftSummaryPick[];
          setDraftSummaryPicks(normalizedPicks);
          const memberId = league?.memberId ?? null;
          if (memberId == null) {
            return;
          }
          const userPicks = normalizedPicks.filter((pick) => pick.memberId === memberId);
          setDraftSelections((current) => {
            const currentById = new Map(current.map((team) => [team.teamId, team]));
            const pickedTeams = userPicks.map((pick) => {
              const known =
                teamMetaRef.current.get(pick.sportTeamId) ??
                currentById.get(pick.sportTeamId);
              if (known) {
                return known;
              }
              return {
                teamId: pick.sportTeamId,
                teamName: pick.sportTeamName ?? `Team ${pick.sportTeamId}`,
                conferenceName:
                  (pick as DraftSummaryPick & { conferenceName?: string | null })
                    .conferenceName ?? null,
              };
            });
            persistSelections(pickedTeams);
            return pickedTeams;
          });
          const pickedIds = new Set(normalizedPicks.map((pick) => pick.sportTeamId));
          setAvailableTeams((current) =>
            current.filter((team) => !pickedIds.has(team.teamId))
          );
        }

        if (Array.isArray(data.members)) {
          setDraftMembers(data.members);
        }

        if (data.state && typeof data.state === "object") {
          setDraftState(data.state as DraftState);
        }

        setOnDeckSlot(data.onDeck ?? data.state?.onDeck ?? null);
        setInTheHoleSlot(data.inTheHole ?? data.state?.inTheHole ?? null);

        if (data.serverNow) {
          const serverMs = Date.parse(data.serverNow);
          if (!Number.isNaN(serverMs)) {
            setClockOffsetMs(serverMs - Date.now());
          }
        }
      }
    } catch (err: any) {
      setError(err?.message ?? "Failed to load draft summary");
    } finally {
      setDraftSummaryLoading(false);
    }
  }, [leagueId]);

  useEffect(() => {
    if (!leagueId || initialSnapshotLoadedRef.current) {
      return;
    }
    initialSnapshotLoadedRef.current = true;
    void loadDraftSummary();
  }, [leagueId, loadDraftSummary]);

  if (!league || !leagueId) {
    return (
      <div className="draft-page">
        <button
          className="draft-page__back"
          type="button"
          onClick={() => navigate(-1)}
        >
          ← Back
        </button>
        {leagueLoading ? (
          <p className="draft-page__empty">Loading league details…</p>
        ) : (
          <p className="draft-page__empty">
            {leagueError ??
              "League context missing. Return to your leagues list and try again."}
          </p>
        )}
      </div>
    );
  }

  const toggleTeam = (team: OwnedTeam) => {
    setSelectedTeam((current) =>
      current?.teamId === team.teamId ? null : team
    );
  };

  const handleSubmit = async () => {
    if (!selectedTeam) {
      return;
    }

    try {
      const response = await createDraftPick(
        league.memberId,
        league.leagueId,
        selectedTeam.teamId
      );

      const updatedSelections = [selectedTeam, ...draftSelections];
      setDraftSelections(updatedSelections);
      persistSelections(updatedSelections);
      setSelectedTeam(null);
      setAvailableTeams((current) =>
        current.filter((team) => team.teamId !== selectedTeam.teamId)
      );
      teamMetaRef.current.set(selectedTeam.teamId, selectedTeam);

      if (response?.draftComplete) {
        setShowDraftComplete(true);
        void loadDraftSummary();
      }
    } catch (err: any) {
      setError(err?.message ?? "Failed to submit draft pick");
    }
  };

  const currentMemberId =
    typeof draftState?.currentMemberId === "number"
      ? (draftState.currentMemberId as number)
      : null;
  const userMemberId = league?.memberId ?? null;
  const isUsersTurn =
    currentMemberId !== null && currentMemberId === userMemberId;
  const currentMemberName =
    draftMembers.find((member) => member.memberId === currentMemberId)?.teamName ??
    "Unknown";
  const onDeckName =
    onDeckSlot?.memberTeamName ??
    draftMembers.find((member) => member.memberId === onDeckSlot?.memberId)?.teamName ??
    null;
  const inTheHoleName =
    inTheHoleSlot?.memberTeamName ??
    draftMembers.find((member) => member.memberId === inTheHoleSlot?.memberId)?.teamName ??
    null;
  const isUserOnDeck =
    userMemberId != null && onDeckSlot?.memberId === userMemberId;
  const isUserInTheHole =
    userMemberId != null && inTheHoleSlot?.memberId === userMemberId;
  const draftStatus =
    typeof draftState?.status === "string" ? (draftState.status as string) : null;
  const isDraftLive = draftStatus === "live";
  const isDraftComplete = draftStatus === "complete";
  const joinable = !draftStatus && !isDraftComplete;
  const joinedCountLabel = null;
  const turnEndsAtRaw =
    typeof draftState?.expiresAt === "string"
      ? (draftState.expiresAt as string)
      : null;
  const remainingSeconds = useMemo(() => {
    if (!turnEndsAtRaw) {
      return null;
    }

    const target = Date.parse(turnEndsAtRaw);
    if (Number.isNaN(target)) {
      return null;
    }

    const nowWithOffset = nowMs + clockOffsetMs;
    return Math.max(0, Math.floor((target - nowWithOffset) / 1000));
  }, [clockOffsetMs, nowMs, turnEndsAtRaw]);
  const timeLeftLabel = useMemo(() => {
    if (remainingSeconds == null) {
      return null;
    }
    const minutes = Math.floor(remainingSeconds / 60);
    const seconds = remainingSeconds % 60;
    return `${minutes}:${String(seconds).padStart(2, "0")}`;
  }, [remainingSeconds]);
  const showJoinButton = false;
  const showCommissionerActions = isCommissioner && !isDraftComplete;
  const submitDisabled =
    loading || !selectedTeam || !isUsersTurn || !isDraftLive || isDraftComplete;

  const draftStatusLabel = draftStatus
    ? draftStatus[0].toUpperCase() + draftStatus.slice(1)
    : "Not started";

  const canStartDraft = isCommissioner && joinable;
  const canPauseDraft = isCommissioner && draftStatus === "live";
  const canResumeDraft = isCommissioner && draftStatus === "paused";

  useEffect(() => {
    if (!draftStatus) {
      return;
    }

    if (draftStatus === "paused" && !pausedSnapshotLoadedRef.current) {
      pausedSnapshotLoadedRef.current = true;
      void loadDraftSummary();
    }

    if (draftStatus === "complete" && previousDraftStatusRef.current !== "complete") {
      setShowDraftComplete(true);
      void loadDraftSummary();
    }

    previousDraftStatusRef.current = draftStatus;
  }, [draftStatus, loadDraftSummary]);

  useEffect(() => {
    if (hasJoinedDraft || !league?.memberId) {
      return;
    }

    if (draftMembers.some((member) => member.memberId === league.memberId)) {
      setHasJoinedDraft(true);
    }
  }, [draftMembers, hasJoinedDraft, league?.memberId]);


  useEffect(() => {
    if (!isDraftLive) {
      return;
    }

    const interval = window.setInterval(() => {
      setNowMs(Date.now());
    }, 1000);

    return () => window.clearInterval(interval);
  }, [isDraftLive]);

  const groupedSummary = useMemo(() => {
    const map = new Map<
      number,
      { memberId: number; memberName: string; picks: DraftSummaryPick[] }
    >();

    draftSummaryPicks.forEach((pick) => {
      const fallbackName =
        draftMembers.find((member) => member.memberId === pick.memberId)?.teamName ??
        `Member ${pick.memberId}`;
      const existing = map.get(pick.memberId);
      if (existing) {
        existing.picks.push(pick);
      } else {
        map.set(pick.memberId, {
          memberId: pick.memberId,
          memberName: pick.memberTeamName ?? fallbackName,
          picks: [pick],
        });
      }
    });

    return Array.from(map.values())
      .map((entry) => ({
        ...entry,
        picks: entry.picks.sort(
          (a, b) => a.overallPickNumber - b.overallPickNumber
        ),
      }))
      .sort((a, b) => a.memberName.localeCompare(b.memberName));
  }, [draftMembers, draftSummaryPicks]);

  const latestPick = useMemo(() => {
    if (draftSummaryPicks.length === 0) {
      return null;
    }
    return draftSummaryPicks.reduce((latest, pick) =>
      pick.overallPickNumber > latest.overallPickNumber ? pick : latest
    );
  }, [draftSummaryPicks]);
  const latestPickMemberName = useMemo(() => {
    if (!latestPick) {
      return null;
    }
    return (
      latestPick.memberTeamName ??
      draftMembers.find((member) => member.memberId === latestPick.memberId)?.teamName ??
      `Member ${latestPick.memberId}`
    );
  }, [draftMembers, latestPick]);
  const latestPickTeamName = useMemo(() => {
    if (!latestPick) {
      return null;
    }
    return latestPick.sportTeamName ?? `Team ${latestPick.sportTeamId}`;
  }, [latestPick]);

  const groupedPickedTeams = useMemo(() => {
    const map = new Map<string, OwnedTeam[]>();

    draftSelections.forEach((team) => {
      const key = resolveConferenceName(team.conferenceName);
      if (key === "Unassigned") {
        return;
      }
      const current = map.get(key) ?? [];
      current.push(team);
      map.set(key, current);
    });

    return Array.from(map.entries()).sort(([a], [b]) => a.localeCompare(b));
  }, [draftSelections, resolveConferenceName]);

  const conferenceRows = useMemo(() => {
    const rows = new Map<string, OwnedTeam[]>();

    groupedPickedTeams.forEach(([conference, teams]) => {
      rows.set(conference, teams);
    });

    conferenceLimits.forEach((_limit, conference) => {
      if (!rows.has(conference)) {
        rows.set(conference, []);
      }
    });

    return Array.from(rows.entries()).sort(([a], [b]) => a.localeCompare(b));
  }, [conferenceLimits, groupedPickedTeams]);

  const teamColumns = useMemo(() => {
    let max = 1;
    conferenceLimits.forEach((limit) => {
      if (limit > max) {
        max = limit;
      }
    });
    groupedPickedTeams.forEach(([, teams]) => {
      if (teams.length > max) {
        max = teams.length;
      }
    });
    return Math.max(1, max);
  }, [conferenceLimits, groupedPickedTeams]);

  const handleCloseDraftSummary = () => {
    if (!leagueId || !league) {
      return;
    }

    const updatedLeague = {
      ...league,
      status: "Post-Draft",
    };

    navigate(`/leagues/${leagueId}`, { state: { league: updatedLeague } });
  };

  const handleDraftAction = async (action: "start" | "pause" | "resume") => {
    if (!leagueId) {
      return;
    }

    try {
      setDraftActionLoading(true);
      setError(null);

      const response =
        action === "start"
          ? await startDraft(leagueId)
          : action === "pause"
          ? await pauseDraft(leagueId)
          : await resumeDraft(leagueId);

      applyDraftSnapshot(response);
    } catch (err: any) {
      const message =
        err?.message ??
        (action === "start"
          ? "Failed to start draft"
          : action === "pause"
          ? "Failed to pause draft"
          : "Failed to resume draft");
      setError(message);
    } finally {
      setDraftActionLoading(false);
    }
  };

  const handleJoinDraft = () => {
    if (!leagueId || !socketRef.current) {
      setError("Draft connection not ready. Try again in a moment.");
      return;
    }

    console.log("Draft socket join (manual)", { leagueId });
    socketRef.current.emit("draft:join", { leagueId });
    setHasJoinedDraft(true);
  };

  return (
    <div className="draft-page">
      <button
        className="draft-page__back"
        type="button"
        onClick={() => navigate(-1)}
      >
        ← Back to League
      </button>

      <header className="draft-page__header">
        <div className="draft-page__header-content">
          <div className="draft-page__header-main">
          <p className="draft-page__eyebrow">Draft Center</p>
          <h1>{league.leagueName}</h1>
          <p className="draft-page__subhead">
            Browse all available teams for week {draftWeekNumber} and lock in your pick.
          </p>
          <p className="draft-page__status">Draft status: {draftStatusLabel}</p>
          {joinedCountLabel && (
            <p className="draft-page__status">Joined: {joinedCountLabel}</p>
          )}
          {currentMemberId && (
            <p className={`draft-page__turn ${isUsersTurn ? "draft-page__turn--user" : ""}`}>
              On the clock: {currentMemberName}
              {isUsersTurn && <span className="draft-page__turn-badge">You</span>}
              {timeLeftLabel ? ` · ${timeLeftLabel}` : ""}
            </p>
          )}
          {isUsersTurn && (
            <div className="draft-page__clock-alert" role="status">
              You are on the clock
            </div>
          )}
          {onDeckName && (
            <p className={`draft-page__turn ${isUserOnDeck ? "draft-page__turn--user" : ""}`}>
              On deck: {onDeckName}
              {isUserOnDeck && <span className="draft-page__turn-badge">You</span>}
            </p>
          )}
          {inTheHoleName && (
            <p className={`draft-page__turn ${isUserInTheHole ? "draft-page__turn--user" : ""}`}>
              In the hole: {inTheHoleName}
              {isUserInTheHole && <span className="draft-page__turn-badge">You</span>}
            </p>
          )}
          {(showJoinButton || showCommissionerActions) && (
            <div className="draft-page__actions">
              {showJoinButton && (
                <button
                  type="button"
                  className="draft-page__action-btn"
                  onClick={handleJoinDraft}
                >
                  Join Draft
                </button>
              )}
              {showCommissionerActions && canStartDraft && (
                <button
                  type="button"
                  className="draft-page__action-btn"
                  onClick={() => handleDraftAction("start")}
                  disabled={draftActionLoading}
                >
                  Start Draft
                </button>
              )}
              {showCommissionerActions && canPauseDraft && (
                <button
                  type="button"
                  className="draft-page__action-btn"
                  onClick={() => handleDraftAction("pause")}
                  disabled={draftActionLoading}
                >
                  Pause Draft
                </button>
              )}
              {showCommissionerActions && canResumeDraft && (
                <button
                  type="button"
                  className="draft-page__action-btn"
                  onClick={() => handleDraftAction("resume")}
                  disabled={draftActionLoading}
                >
                  Resume Draft
                </button>
              )}
            </div>
          )}
        </div>
          {latestPickMemberName && latestPickTeamName && (
            <aside className="draft-page__latest" aria-live="polite">
              <p className="draft-page__latest-label">Latest Pick</p>
              <p className="draft-page__latest-value draft-page__latest-member">
                {latestPickMemberName}:
              </p>
              <p className="draft-page__latest-value draft-page__latest-team">
                {latestPickTeamName}
              </p>
            </aside>
          )}
        </div>
      </header>

      <section className="draft-page__controls" aria-label="Draft filters">
        <div className="draft-page__control">
          <label htmlFor="draft-search">Search teams</label>
          <input
            id="draft-search"
            type="text"
            placeholder="Search by team name"
            value={searchTerm}
            onChange={(evt) => setSearchTerm(evt.target.value)}
          />
        </div>
        <div className="draft-page__control">
          <label htmlFor="draft-conference">Conference</label>
          <select
            id="draft-conference"
            value={conferenceFilter}
            onChange={(evt) => setConferenceFilter(evt.target.value)}
          >
            <option value="all">All conferences</option>
            {uniqueConferences.map((conf) => (
              <option key={conf} value={conf}>
                {conf}
              </option>
            ))}
          </select>
        </div>
      </section>

      {error && <p className="draft-page__error">{error}</p>}
      {loading && <p className="draft-page__loading">Loading teams…</p>}

      <section className="draft-page__list" role="region" aria-label="Available teams">
        {groupedAvailable.length === 0 && !loading ? (
          <p className="draft-page__empty">No teams available.</p>
        ) : (
          groupedAvailable.map(([conference, teams]) => (
            <div className="draft-page__group" key={conference}>
              <p className="draft-page__group-label">{conference}</p>
              <div className="draft-page__team-grid">
                {teams.map((team) => {
                  const isSelected = selectedTeam?.teamId === team.teamId;
                  return (
                    <button
                      key={team.teamId}
                      type="button"
                      className={`draft-page__team-btn ${
                        isSelected ? "is-selected" : ""
                      }`}
                      onClick={() => toggleTeam(team)}
                      aria-pressed={isSelected}
                    >
                      {team.teamName}
                    </button>
                  );
                })}
              </div>
            </div>
          ))
        )}
      </section>

      <section className="draft-page__queue">
        <p className="draft-page__queue-label">Selected Team</p>
        {!selectedTeam ? (
          <p className="draft-page__queue-empty">No team selected.</p>
        ) : (
          <div className="draft-page__queue-entry">
            <span>{selectedTeam.teamName}</span>
            <button
              type="button"
              className="draft-page__queue-remove"
              onClick={() => setSelectedTeam(null)}
              aria-label="Remove selected team"
            >
              ×
            </button>
          </div>
        )}
      </section>

      <footer className="draft-page__footer">
        <button
          type="button"
          className="draft-page__submit"
          onClick={handleSubmit}
          disabled={submitDisabled}
        >
          Draft Selected Team
        </button>
      </footer>

      <section className="draft-page__history">
        <p className="draft-page__queue-label">Picked Teams</p>
        {draftSelections.length === 0 && conferenceRows.length === 0 ? (
          <p className="draft-page__queue-empty">No teams picked yet.</p>
        ) : (
          <div
            className="draft-page__picked-table"
            style={
              {
                "--picked-columns": teamColumns,
              } as React.CSSProperties
            }
          >
            <div className="draft-page__picked-row draft-page__picked-row--header">
              <span>Conference</span>
              {Array.from({ length: teamColumns }, (_, idx) => (
                <span key={`picked-header-${idx + 1}`}>Team {idx + 1}</span>
              ))}
            </div>
            {conferenceRows.map(([conference, teams]) => {
              const limit = conferenceLimits.get(conference);
              const hasLimit = typeof limit === "number";
              const isMaxed = hasLimit && teams.length >= limit;
              return (
                <div className="draft-page__picked-row" key={conference}>
                  <span className="draft-page__picked-conf">
                    {conference}
                    {hasLimit && (
                      <span className="draft-page__picked-conf-meta">
                        {teams.length}/{limit}
                        {isMaxed && (
                          <span className="draft-page__picked-conf-maxed">Maxed</span>
                        )}
                      </span>
                    )}
                  </span>
                  {Array.from({ length: teamColumns }, (_, idx) => {
                    const team = teams[idx];
                    return (
                      <span className="draft-page__picked-teams" key={`${conference}-${idx}`}>
                        {team ? team.teamName : "—"}
                      </span>
                    );
                  })}
                </div>
              );
            })}
          </div>
        )}
      </section>

      {showDraftComplete && (
        <div className="draft-page__modal" role="presentation">
          <div
            className="draft-page__modal-card"
            role="dialog"
            aria-modal="true"
            aria-labelledby="draft-complete-title"
          >
            <button
              type="button"
              className="draft-page__modal-x"
              onClick={handleCloseDraftSummary}
              aria-label="Close draft summary"
            >
              ×
            </button>
            <p className="draft-page__modal-eyebrow">Draft Complete</p>
            <h2 id="draft-complete-title">Draft Summary</h2>
            <p className="draft-page__modal-subhead">
              All picks are locked in. Review your league results below.
            </p>
            <div className="draft-page__modal-body">
              {draftSummaryLoading ? (
                <p className="draft-page__modal-loading">Loading summary…</p>
              ) : groupedSummary.length === 0 ? (
                <p className="draft-page__modal-empty">No picks available.</p>
              ) : (
                <div className="draft-page__modal-grid">
                  {groupedSummary.map((member) => (
                    <div className="draft-page__modal-section" key={member.memberId}>
                      <h3>{member.memberName}</h3>
                      <ol>
                        {member.picks.map((pick) => (
                          <li key={pick.id}>
                            <span className="draft-page__modal-pick">
                              #{pick.overallPickNumber} · Round {pick.roundNumber}, Pick{" "}
                              {pick.pickInRound}
                            </span>
                            <span className="draft-page__modal-team">
                              {pick.sportTeamName ?? `Team ${pick.sportTeamId}`}
                            </span>
                          </li>
                        ))}
                      </ol>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default LeagueDraftPage;
