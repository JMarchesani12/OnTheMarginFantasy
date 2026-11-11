import { safeErrorMessage, TRANSACTION_UNCERTAIN, READ_ERROR } from "../../api/safeError";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import type { League } from "../../types/league";
import type { OwnedTeam } from "../../types/schedule";
import type { LeagueMember } from "../../types/leagueMember";
import { getMembersOfLeague } from "../../api/leagues";
import { getAvailableTeams, getMemberTeams } from "../../api/roster";
import { submitFreeAgencyRequest, tradeRequestProposal } from "../../api/transaction";
import PendingTransactionsPanel from "../../components/League/PendingTransactionsPanel";
import TradeRequestsPanel from "../../components/League/TradeRequestsPanel";
import { formatLeagueDate } from "../../utils/date";
import { normalizeOwnedTeams, type RawOwnedTeam } from "../../utils/teams";
import { getEffectiveWeekNumber } from "../../utils/weekCutoff";
import { safeLocalStorage } from "../../utils/safeStorage";
import { useLeagueContext } from "../../hooks/useLeagueContext";
import { useRequestScope } from "../../hooks/useRequestScope";
import "./LeagueRosterPage.css";

const EMPTY_TEAMS: OwnedTeam[] = [];

type GroupedTeams = [string, OwnedTeam[]][];
type RosterContextProps = { league: League; isCurrent: () => boolean };

const LeagueRosterPage = () => {
  const { league_id } = useParams();
  const context = useLeagueContext(league_id);
  const navigate = useNavigate();
  if (!context.league || !context.isMember) return (
    <div className="roster-page">
      <button className="roster-page__back" type="button" onClick={() => navigate(-1)}>← Back</button>
      <button className="roster-page__back" type="button" onClick={() => navigate("/leagues")}>Go to My Leagues</button>
      <p className="roster-page__empty">{context.loading ? "Loading league details…" : context.error ?? (context.league ? "League membership is required to manage a roster." : "League context missing. Please open this page from your league detail view.")}</p>
      {context.canRetry && <button type="button" onClick={context.retry}>Retry</button>}
    </div>
  );
  return <LeagueRosterView key={context.scopeKey} league={context.league} isCurrent={context.isCurrent} />;
};

const LeagueRosterView = ({ league, isCurrent }: RosterContextProps) => {
  const navigate = useNavigate();
  const scope = useRequestScope(isCurrent);
  const leagueId = league.leagueId;
  const memberId = league.memberId;

  const isBrowser = typeof window !== "undefined";

  const [ownedTeamsValue, setOwnedTeams] = useState<OwnedTeam[]>([]);
  const [availableTeamsValue, setAvailableTeams] = useState<OwnedTeam[]>([]);
  const [selectedAddValue, setSelectedAdd] = useState<OwnedTeam | null>(null);
  const [selectedDropValue, setSelectedDrop] = useState<OwnedTeam | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [submissionStatus, setSubmissionStatus] = useState<string | null>(null);
  const [refreshRevision, setRefreshRevision] = useState(0);
  const revisionRef = useRef(0);
  // Only user edits advance these versions; read reconciliation can replace team objects.
  const selectionEdits = useRef({ add: 0, drop: 0, give: 0, receive: 0 });
  const [searchTerm, setSearchTerm] = useState("");
  const [conferenceFilter, setConferenceFilter] = useState("all");
  const tabStorageKey =
    isBrowser && league?.leagueId ? `rosterTab:${league.leagueId}` : null;
  const [activeTab, setActiveTab] = useState<"addDrop" | "trade">(() => {
    if (!tabStorageKey || !isBrowser) {
      return "addDrop";
    }
    const stored = safeLocalStorage.getItem(tabStorageKey);
    return stored === "trade" ? "trade" : "addDrop";
  });
  const [members, setMembers] = useState<LeagueMember[]>([]);
  const [membersLoading, setMembersLoading] = useState(false);
  const [membersError, setMembersError] = useState<string | null>(null);
  const [tradeMemberId, setTradeMemberId] = useState<number | null>(null);
  const [tradeMemberTeamsValue, setTradeMemberTeams] = useState<OwnedTeam[]>([]);
  const [tradeTeamsLoading, setTradeTeamsLoading] = useState(false);
  const [tradeTeamsError, setTradeTeamsError] = useState<string | null>(null);
  const [selectedTradeGiveValue, setSelectedTradeGive] = useState<OwnedTeam | null>(null);
  const [selectedTradeReceiveValue, setSelectedTradeReceive] = useState<OwnedTeam | null>(null);
  const getRosterWeek = useCallback(() =>
    getEffectiveWeekNumber({
      currentWeekNumber: league.currentWeekNumber,
      currentWeekStartDate: league.currentWeekStartDate,
      timeZone: league.settings?.timezone ?? null,
    }) ?? 1, [league]);
  const rosterWeekNumber = getRosterWeek();
  const [, checkWeek] = useState(0);
  const rosterScope = useRef({ week: rosterWeekNumber, generation: 0 });
  if (rosterScope.current.week !== rosterWeekNumber) {
    rosterScope.current = { week: rosterWeekNumber, generation: rosterScope.current.generation + 1 };
  }
  const rosterGeneration = rosterScope.current.generation;
  const [loadedRosterGeneration, setLoadedRosterGeneration] = useState<number | null>(null);
  const [loadedRosterRevision, setLoadedRosterRevision] = useState<number | null>(null);
  const rosterReady = loadedRosterGeneration === rosterGeneration && loadedRosterRevision === refreshRevision;
  const ownedTeams = rosterReady ? ownedTeamsValue : EMPTY_TEAMS;
  const availableTeams = rosterReady ? availableTeamsValue : EMPTY_TEAMS;
  const selectedAdd = rosterReady ? selectedAddValue : null;
  const selectedDrop = rosterReady ? selectedDropValue : null;
  const selectedTradeGive = rosterReady ? selectedTradeGiveValue : null;
  const isRosterCurrent = useCallback(() => scope.isCurrent() &&
    rosterScope.current.generation === rosterGeneration && getRosterWeek() === rosterWeekNumber,
    [scope, rosterGeneration, getRosterWeek, rosterWeekNumber]);
  const rosterWeekId = league?.currentWeekId ?? rosterWeekNumber;
  const partnerScope = useRef({ memberId: tradeMemberId, week: rosterWeekNumber, generation: 0 });
  if (partnerScope.current.memberId !== tradeMemberId || partnerScope.current.week !== rosterWeekNumber) {
    partnerScope.current = { memberId: tradeMemberId, week: rosterWeekNumber, generation: partnerScope.current.generation + 1 };
  }
  const partnerGeneration = partnerScope.current.generation;
  const [loadedPartnerGeneration, setLoadedPartnerGeneration] = useState<number | null>(null);
  const [loadedPartnerRevision, setLoadedPartnerRevision] = useState<number | null>(null);
  const partnerReady = loadedPartnerGeneration === partnerGeneration && loadedPartnerRevision === refreshRevision;
  const tradeMemberTeams = partnerReady ? tradeMemberTeamsValue : EMPTY_TEAMS;
  const selectedTradeReceive = partnerReady ? selectedTradeReceiveValue : null;


  const refreshRelatedData = useCallback(() => {
    if (!isRosterCurrent()) return;
    revisionRef.current += 1;
    setRefreshRevision(revisionRef.current);
  }, [isRosterCurrent]);
  const onTradeMutationSuccess = useCallback(() => {
    if (!isRosterCurrent()) return;
    setSubmissionStatus("Trade updated.");
    refreshRelatedData();
  }, [isRosterCurrent, refreshRelatedData]);

  useEffect(() => {
    if (!tabStorageKey || !isBrowser) {
      return;
    }
    safeLocalStorage.setItem(tabStorageKey, activeTab);
  }, [tabStorageKey, activeTab, isBrowser]);

  const loadRosterData = useCallback(async () => {
    if (!isRosterCurrent() || !leagueId || !memberId) {
      return;
    }

    const request = scope.capture("roster");
    const current = () => request() && isRosterCurrent() && revisionRef.current === refreshRevision;
    try {
      setLoading(true);
      setError(null);
      setLoadedRosterRevision(null);

      const [memberTeams, available] = await Promise.all([
        getMemberTeams(memberId, rosterWeekNumber, leagueId, request.signal),
        getAvailableTeams(rosterWeekNumber, leagueId, request.signal),
      ]);

      if (!current()) return;
      const normalizedOwned = normalizeOwnedTeams(memberTeams as RawOwnedTeam[]);
      const normalizedAvailable = normalizeOwnedTeams(available as RawOwnedTeam[]);
      setOwnedTeams(normalizedOwned);
      setAvailableTeams(normalizedAvailable);
      setLoadedRosterGeneration(rosterGeneration);
      setLoadedRosterRevision(refreshRevision);
      setSelectedDrop((current) => {
        if (!current) return null;
        return normalizedOwned.find((team) => team.teamId === current.teamId) ?? null;
      });
      setSelectedAdd((current) => {
        if (!current) return null;
        return (
          normalizedAvailable.find((team) => team.teamId === current.teamId) ?? null
        );
      });
    } catch (err: any) {
      if (current()) setError(safeErrorMessage(err, READ_ERROR));
    } finally {
      if (current()) setLoading(false);
      else if (scope.isCurrent() && getRosterWeek() !== rosterWeekNumber) checkWeek(value => value + 1);
    }
  }, [leagueId, memberId, rosterWeekNumber, rosterGeneration, scope, isRosterCurrent, refreshRevision]);

  useEffect(() => {
    setSelectedAdd(null);
    setSelectedDrop(null);
    setSelectedTradeGive(null);
    setSubmitting(false);
    setSubmissionStatus(null);
  }, [rosterGeneration]);

  useEffect(() => {
    loadRosterData();
    return () => scope.cancel("roster");
  }, [loadRosterData, scope]);

  useEffect(() => {
    if (!leagueId) {
      return;
    }

    let isCancelled = false;
    const current = scope.capture("members");

    const loadMembers = async () => {
      try {
        setMembersLoading(true);
        setMembersError(null);

        const data = await getMembersOfLeague(leagueId, current.signal);

        if (!isCancelled && current()) {
          setMembers(data);
          const defaultPartner = data.find((m) => m.id !== memberId) ?? null;
          setTradeMemberId(defaultPartner?.id ?? null);
        }
      } catch (err: any) {
        if (!isCancelled && current()) {
          setMembersError(safeErrorMessage(err, READ_ERROR));
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
  }, [leagueId, memberId, scope]);

  useEffect(() => {
    if (!tradeMemberId || !leagueId) {
      setTradeMemberTeams([]);
      setSelectedTradeReceive(null);
      return;
    }

    if (loadedPartnerGeneration !== partnerGeneration) {
      setSelectedTradeReceive(null);
      setTradeMemberTeams([]);
    }
    setLoadedPartnerRevision(null);

    let isCancelled = false;
    const request = scope.capture("partner");
    const current = () => request() && isRosterCurrent() && partnerScope.current.generation === partnerGeneration && revisionRef.current === refreshRevision;

    const loadTradeTeams = async () => {
      try {
        setTradeTeamsLoading(true);
        setTradeTeamsError(null);

        const teams = await getMemberTeams(tradeMemberId, rosterWeekNumber, leagueId, request.signal);

        if (!isCancelled && current()) {
          const normalized = normalizeOwnedTeams(teams as RawOwnedTeam[]);
          setTradeMemberTeams(normalized);
          setLoadedPartnerGeneration(partnerGeneration);
          setLoadedPartnerRevision(refreshRevision);
          setSelectedTradeReceive((current) => {
            if (!current) return null;
            return normalized.find((team) => team.teamId === current.teamId) ?? null;
          });
        }
      } catch (err: any) {
        if (!isCancelled && current()) {
          setTradeTeamsError(safeErrorMessage(err, READ_ERROR));
        }
      } finally {
        if (!isCancelled && current()) {
          setTradeTeamsLoading(false);
        }
      }
    };

    loadTradeTeams();

    return () => {
      isCancelled = true;
      request.cancel();
    };
  }, [tradeMemberId, leagueId, rosterWeekNumber, partnerGeneration, scope, refreshRevision, isRosterCurrent]);

  useEffect(() => {
    if (!rosterReady) return;
    setSelectedTradeGive((current) => {
      if (!current) return null;
      return ownedTeams.find((team) => team.teamId === current.teamId) ?? null;
    });
  }, [ownedTeams, rosterReady]);

  const groupTeams = (teams: OwnedTeam[]): GroupedTeams => {
    const map = new Map<string, OwnedTeam[]>();

    teams.forEach((team) => {
      const key = team.conferenceName ?? "Conference unavailable";
      const current = map.get(key) ?? [];
      current.push(team);
      map.set(key, current);
    });

    return Array.from(map.entries()).sort(([a], [b]) => a.localeCompare(b));
  };

  const uniqueConferences = useMemo(() => {
    const all = [...ownedTeams, ...availableTeams, ...tradeMemberTeams]
      .map((team) => team.conferenceName ?? "Conference unavailable")
      .filter(Boolean);
    return Array.from(new Set(all)).sort((a, b) => a.localeCompare(b));
  }, [ownedTeams, availableTeams, tradeMemberTeams]);

  const applyFilters = (teams: OwnedTeam[]) =>
    teams.filter((team) => {
      const name = team.teamName ?? "";
      const matchesSearch = name
        .toLowerCase()
        .includes(searchTerm.toLowerCase());
      const matchesConference =
        conferenceFilter === "all" ||
        (team.conferenceName ?? "Conference unavailable") === conferenceFilter;
      return matchesSearch && matchesConference;
    });

  const groupedOwned = useMemo(
    () => groupTeams(applyFilters(ownedTeams)),
    [ownedTeams, searchTerm, conferenceFilter]
  );
  const groupedAvailable = useMemo(
    () => groupTeams(applyFilters(availableTeams)),
    [availableTeams, searchTerm, conferenceFilter]
  );
  const groupedTradeTarget = useMemo(
    () => groupTeams(applyFilters(tradeMemberTeams)),
    [tradeMemberTeams, searchTerm, conferenceFilter]
  );

  const teamNameLookup = useMemo(() => {
    const lookup: Record<number, string> = {};
    [...ownedTeams, ...availableTeams, ...tradeMemberTeams].forEach((team) => {
      if (!Number.isFinite(team.teamId)) return;
      if (!lookup[team.teamId]) {
        lookup[team.teamId] = team.teamName;
      }
    });
    return lookup;
  }, [ownedTeams, availableTeams, tradeMemberTeams]);

  const toggleAddTeam = (team: OwnedTeam) => {
    selectionEdits.current.add += 1;
    setSelectedAdd((current) =>
      current?.teamId === team.teamId ? null : team
    );
  };

  const toggleDropTeam = (team: OwnedTeam) => {
    selectionEdits.current.drop += 1;
    setSelectedDrop((current) =>
      current?.teamId === team.teamId ? null : team
    );
  };

  const toggleTradeGiveTeam = (team: OwnedTeam) => {
    selectionEdits.current.give += 1;
    setSelectedTradeGive((current) =>
      current?.teamId === team.teamId ? null : team
    );
  };

  const toggleTradeReceiveTeam = (team: OwnedTeam) => {
    selectionEdits.current.receive += 1;
    setSelectedTradeReceive((current) =>
      current?.teamId === team.teamId ? null : team
    );
  };

  const handleSubmitAddDrop = async () => {
    if (!scope.isCurrent() || !league || !memberId || !leagueId) {
      return;
    }

    if (!selectedAdd && !selectedDrop) {
      return;
    }

    if (submitting || !rosterReady || loadedRosterRevision !== revisionRef.current || !isRosterCurrent()) {
      if (scope.isCurrent()) checkWeek(value => value + 1);
      return;
    }
    const submittedEdits = { ...selectionEdits.current };
    const operation = scope.capture();
    const current = () => operation() && isRosterCurrent();
    try {
      setSubmitting(true);
      setError(null);

      await submitFreeAgencyRequest(
        league.leagueId,
        rosterWeekNumber,
        rosterWeekId,
        league.memberId,
        selectedAdd ? selectedAdd.teamId : null,
        selectedDrop ? selectedDrop.teamId : null
      );

      if (!current()) return;
      setSelectedAdd(value => selectionEdits.current.add === submittedEdits.add && value?.teamId === selectedAddValue?.teamId ? null : value);
      setSelectedDrop(value => selectionEdits.current.drop === submittedEdits.drop && value?.teamId === selectedDropValue?.teamId ? null : value);
      setSubmissionStatus("Request submitted.");
      refreshRelatedData();
    } catch (err: any) {
      if (!current()) return;
      setError(safeErrorMessage(err, TRANSACTION_UNCERTAIN));
    } finally {
      if (!current()) {
        if (scope.isCurrent() && getRosterWeek() !== rosterWeekNumber) checkWeek(value => value + 1);
        return;
      }
      setSubmitting(false);
    }
  };

  const handleSubmitTrade = async () => {
    if (!scope.isCurrent() || !tradeMemberId || !selectedTradeGive || !selectedTradeReceive || !league) {
      return;
    }

    if (submitting || !rosterReady || loadedRosterRevision !== revisionRef.current || !isRosterCurrent()) {
      if (scope.isCurrent()) checkWeek(value => value + 1);
      return;
    }
    const submittedEdits = { ...selectionEdits.current };
    const operation = scope.capture();
    const current = () => operation() && isRosterCurrent();
    try {
      setSubmitting(true);
      setError(null);

      await tradeRequestProposal(
        league.leagueId,
        rosterWeekNumber,
        rosterWeekId,
        tradeMemberId,
        league.memberId,
        [selectedTradeReceive.teamId],
        [selectedTradeGive.teamId]
      );

      if (!current()) return;
      setSelectedTradeGive(value => selectionEdits.current.give === submittedEdits.give && value?.teamId === selectedTradeGiveValue?.teamId ? null : value);
      if (partnerScope.current.generation === partnerGeneration) {
        setSelectedTradeReceive(value => selectionEdits.current.receive === submittedEdits.receive && value?.teamId === selectedTradeReceiveValue?.teamId ? null : value);
      }
      setSubmissionStatus("Request submitted.");
      refreshRelatedData();
    } catch (err: any) {
      if (!current()) return;
      setError(safeErrorMessage(err, TRANSACTION_UNCERTAIN));
    } finally {
      if (!current()) {
        if (scope.isCurrent() && getRosterWeek() !== rosterWeekNumber) checkWeek(value => value + 1);
        return;
      }
      setSubmitting(false);
    }
  };

  const tradeDeadlinePassed = useMemo(() => {
    if (!league?.tradeDeadline) {
      return false;
    }

    const deadline = new Date(league.tradeDeadline);
    if (Number.isNaN(deadline.getTime())) {
      return false;
    }

    return deadline.getTime() < Date.now();
  }, [league?.tradeDeadline]);

  const freeAgentDeadlinePassed = useMemo(() => {
    if (!league?.freeAgentDeadline) {
      return false;
    }

    const deadline = new Date(league.freeAgentDeadline);
    if (Number.isNaN(deadline.getTime())) {
      return false;
    }

    return deadline.getTime() < Date.now();
  }, [league?.freeAgentDeadline]);

  const renderTeamGroups = (
    groups: GroupedTeams,
    {
      emptyText,
      selectedTeam,
      onToggle,
      disabled,
    }: {
      emptyText: string;
      selectedTeam: OwnedTeam | null;
      onToggle: (team: OwnedTeam) => void;
      disabled?: boolean;
    }
  ) => {
    if (groups.length === 0) {
      return <p className="roster-page__empty">{emptyText}</p>;
    }

    return groups.map(([conference, teams]) => (
      <div className="roster-page__group" key={`${conference}-${emptyText}`}>
        <p className="roster-page__group-label">{conference}</p>
        <div className="roster-page__team-grid">
          {teams.map((team) => {
            const isSelected = selectedTeam?.teamId === team.teamId;
            return (
              <button
                key={`${conference}-${team.teamId}`}
                type="button"
                className={`roster-page__team-btn ${
                  isSelected ? "is-selected" : ""
                }`}
                onClick={() => onToggle(team)}
                aria-pressed={isSelected}
                disabled={disabled}
              >
                {team.teamName}
              </button>
            );
          })}
        </div>
      </div>
    ));
  };

  const addDropSubmitDisabled =
    !rosterReady ||
    freeAgentDeadlinePassed ||
    loading ||
    submitting ||
    (!selectedAdd && !selectedDrop);

  const tradeSubmitDisabled =
    !rosterReady ||
    tradeDeadlinePassed ||
    loading ||
    submitting ||
    tradeTeamsLoading ||
    !selectedTradeGive ||
    !selectedTradeReceive ||
    !partnerReady ||
    !tradeMemberId;

  const tradePartners = members.filter((member) => member.id !== memberId);
  const activeTradeMember = tradePartners.find(
    (member) => member.id === tradeMemberId
  );

  return (
    <div className="roster-page">
      <button
        className="roster-page__back"
        type="button"
        onClick={() => navigate(-1)}
      >
        ← Back to League
      </button>

      <header className="roster-page__header">
        <div>
          <p className="roster-page__eyebrow">Roster Management</p>
          <h1>{league.leagueName}</h1>
          <p className="roster-page__subhead">
            Add or drop teams for week {rosterWeekNumber}. Grouped by conference for
            quick scanning.
          </p>
        </div>
        <div className="roster-page__meta">
          <div className="roster-page__meta-line">
            <span className="roster-page__meta-label">Trade deadline</span>
            <span className="roster-page__meta-value">
              {formatLeagueDate(league.tradeDeadline)}
            </span>
            <span className="roster-page__deadline-badge roster-page__deadline-badge--trade">
              Trades
            </span>
          </div>
          <div className="roster-page__meta-line">
            <span className="roster-page__meta-label">Free agent deadline</span>
            <span className="roster-page__meta-value">
              {formatLeagueDate(league.freeAgentDeadline)}
            </span>
            <span className="roster-page__deadline-badge roster-page__deadline-badge--fa">
              Add/Drop
            </span>
          </div>
          {tradeDeadlinePassed && (
            <span className="roster-page__deadline">
              Trade deadline passed — trades locked.
            </span>
          )}
          {freeAgentDeadlinePassed && (
            <span className="roster-page__deadline">
              Free agent deadline passed — add/drop locked.
            </span>
          )}
        </div>
      </header>

      <nav className="roster-page__tabs" aria-label="Roster modes">
        <button
          type="button"
          className={`roster-page__tab ${
            activeTab === "addDrop" ? "is-active" : ""
          }`}
          onClick={() => setActiveTab("addDrop")}
        >
          Add / Drop
        </button>
        <button
          type="button"
          className={`roster-page__tab ${
            activeTab === "trade" ? "is-active" : ""
          }`}
          onClick={() => setActiveTab("trade")}
        >
          Trade
        </button>
      </nav>

      {error && <p className="roster-page__error">{error}</p>}
      {submissionStatus && <p role="status">{submissionStatus}</p>}
      {(loading || submitting) && <p className="roster-page__loading">Loading teams…</p>}
      {error && <button type="button" onClick={refreshRelatedData}>Retry roster data</button>}
      {tradeTeamsError && <button type="button" onClick={refreshRelatedData}>Retry partner roster</button>}

      <section className="roster-page__controls" aria-label="Roster filters">
        <div className="roster-page__control">
          <label htmlFor="roster-search">Search teams</label>
          <input
            id="roster-search"
            type="text"
            placeholder="Search by team name"
            value={searchTerm}
            onChange={(evt) => setSearchTerm(evt.target.value)}
          />
        </div>
        <div className="roster-page__control">
          <label htmlFor="roster-conference">Conference</label>
          <select
            id="roster-conference"
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

      {activeTab === "addDrop" && (
        <>
          <section className="roster-page__sections">
            <div>
              <h2>Add Teams</h2>
              <p className="roster-page__helper">
                Tap a team to queue it for addition. Your selections appear below.
              </p>
              <div className="roster-page__list" role="region" aria-label="Add teams list">
                {renderTeamGroups(groupedAvailable, {
                  emptyText: "No available teams.",
                  selectedTeam: selectedAdd,
                  onToggle: toggleAddTeam,
                  disabled: freeAgentDeadlinePassed,
                })}
              </div>
            </div>

            <div>
              <h2>Drop Teams</h2>
              <p className="roster-page__helper">
                Choose teams from your roster to release.
              </p>
              <div className="roster-page__list" role="region" aria-label="Drop teams list">
                {renderTeamGroups(groupedOwned, {
                  emptyText: "No teams on roster.",
                  selectedTeam: selectedDrop,
                  onToggle: toggleDropTeam,
                  disabled: freeAgentDeadlinePassed,
                })}
              </div>
            </div>
          </section>

          <section className="roster-page__queue">
            <div>
              <p className="roster-page__queue-label">Teams to Add</p>
              {!selectedAdd ? (
                <p className="roster-page__queue-empty">No adds selected.</p>
              ) : (
                <div className="roster-page__queue-entry">
                  <span>{selectedAdd.teamName}</span>
                  <button
                    type="button"
                    className="roster-page__queue-remove"
                    onClick={() => { selectionEdits.current.add += 1; setSelectedAdd(null); }}
                    aria-label="Remove add selection"
                  >
                    ×
                  </button>
                </div>
              )}
            </div>
            <div>
              <p className="roster-page__queue-label">Teams to Drop</p>
              {!selectedDrop ? (
                <p className="roster-page__queue-empty">No drops selected.</p>
              ) : (
                <div className="roster-page__queue-entry">
                  <span>{selectedDrop.teamName}</span>
                  <button
                    type="button"
                    className="roster-page__queue-remove"
                    onClick={() => { selectionEdits.current.drop += 1; setSelectedDrop(null); }}
                    aria-label="Remove drop selection"
                  >
                    ×
                  </button>
                </div>
              )}
            </div>
          </section>

          <footer className="roster-page__footer">
            <button
              type="button"
              className="roster-page__submit"
              onClick={handleSubmitAddDrop}
              disabled={addDropSubmitDisabled}
            >
              Submit Add / Drop Request
            </button>
            {freeAgentDeadlinePassed && (
              <p className="roster-page__deadline">
                Free agent deadline passed on{" "}
                {formatLeagueDate(league.freeAgentDeadline)}.
              </p>
            )}
          </footer>
        </>
      )}

      {activeTab === "trade" && (
        <>
          <section className="roster-page__trade-panel">
            <div className="roster-page__trade-header">
              <p>Select a member to trade with</p>
              {membersLoading && (
                <span className="roster-page__loading">Loading members…</span>
              )}
            </div>
            <div className="roster-page__trade-members">
              {tradePartners.map((member) => (
                <button
                  key={member.id}
                  type="button"
                  className={`roster-page__trade-member-btn ${
                    member.id === tradeMemberId ? "is-active" : ""
                  }`}
                  onClick={() => setTradeMemberId(member.id)}
                >
                  {member.teamName ?? `Member #${member.id}`}
                </button>
              ))}
            </div>
            {tradePartners.length === 0 && !membersLoading && (
              <p className="roster-page__empty">
                Need at least one other member in the league to propose trades.
              </p>
            )}
            {membersError && <p className="roster-page__error">{membersError}</p>}
          </section>

          {tradePartners.length > 0 && (
            <>
              {!tradeMemberId && (
                <p className="roster-page__empty">
                  Select a member above to view their roster.
                </p>
              )}
              {tradeTeamsError && (
                <p className="roster-page__error">{tradeTeamsError}</p>
              )}
              {tradeTeamsLoading && tradeMemberId && (
                <p className="roster-page__loading">Loading member teams…</p>
              )}

              {tradeMemberId && (
                <section className="roster-page__sections">
                  <div>
                    <h2>Your Offer</h2>
                    <p className="roster-page__helper">
                      Choose one of your teams to include in the trade.
                    </p>
                    <div className="roster-page__list" role="region" aria-label="Teams you can trade away">
                      {renderTeamGroups(groupedOwned, {
                        emptyText: "No teams on roster.",
                        selectedTeam: selectedTradeGive,
                        onToggle: toggleTradeGiveTeam,
                        disabled: tradeDeadlinePassed,
                      })}
                    </div>
                  </div>

                  <div>
                    <h2>Request from {activeTradeMember?.teamName ?? "Member"}</h2>
                    <p className="roster-page__helper">
                      Select a team from your trade partner.
                    </p>
                    <div className="roster-page__list" role="region" aria-label="Teams you can request">
                      {renderTeamGroups(groupedTradeTarget, {
                        emptyText: "No teams available for this member.",
                        selectedTeam: selectedTradeReceive,
                        onToggle: toggleTradeReceiveTeam,
                        disabled: tradeDeadlinePassed || tradeTeamsLoading,
                      })}
                    </div>
                  </div>
                </section>
              )}

              {tradeMemberId && (
                <section className="roster-page__queue">
                  <div>
                    <p className="roster-page__queue-label">Teams You Offer</p>
                    {!selectedTradeGive ? (
                      <p className="roster-page__queue-empty">No team selected.</p>
                    ) : (
                      <div className="roster-page__queue-entry">
                        <span>{selectedTradeGive.teamName}</span>
                        <button
                          type="button"
                          className="roster-page__queue-remove"
                          onClick={() => { selectionEdits.current.give += 1; setSelectedTradeGive(null); }}
                          aria-label="Remove offered team"
                        >
                          ×
                        </button>
                      </div>
                    )}
                  </div>
                  <div>
                    <p className="roster-page__queue-label">Teams You Request</p>
                    {!selectedTradeReceive ? (
                      <p className="roster-page__queue-empty">No team selected.</p>
                    ) : (
                      <div className="roster-page__queue-entry">
                        <span>{selectedTradeReceive.teamName}</span>
                        <button
                          type="button"
                          className="roster-page__queue-remove"
                          onClick={() => { selectionEdits.current.receive += 1; setSelectedTradeReceive(null); }}
                          aria-label="Remove requested team"
                        >
                          ×
                        </button>
                      </div>
                    )}
                  </div>
                </section>
              )}

              {tradeMemberId && (
                <footer className="roster-page__footer">
                  <button
                    type="button"
                    className="roster-page__submit"
                    onClick={handleSubmitTrade}
                    disabled={tradeSubmitDisabled}
                  >
                    Submit Trade Proposal
                  </button>
                  {tradeDeadlinePassed && (
                    <p className="roster-page__deadline">
                      Trade deadline passed on {formatLeagueDate(league.tradeDeadline)}.
                    </p>
                  )}
                </footer>
              )}
            </>
          )}
          <TradeRequestsPanel
            leagueId={league.leagueId}
            memberId={league.memberId}
            isCurrent={isRosterCurrent}
            refreshRevision={refreshRevision}
            onMutationSuccess={onTradeMutationSuccess}
            tradeDeadlinePassed={tradeDeadlinePassed}
          />
        </>
      )}
      <PendingTransactionsPanel
        leagueId={league.leagueId}
        members={members}
        teamNameLookup={teamNameLookup}
        isCurrent={isRosterCurrent}
        refreshRevision={refreshRevision}
      />
    </div>
  );
};

export default LeagueRosterPage;
