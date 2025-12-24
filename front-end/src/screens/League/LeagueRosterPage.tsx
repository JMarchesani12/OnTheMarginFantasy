import { useCallback, useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import type { League } from "../../types/league";
import type { OwnedTeam } from "../../types/schedule";
import type { LeagueMember } from "../../types/leagueMember";
import { getMembersOfLeague } from "../../api/leagues";
import { getAvailableTeams, getMemberTeams } from "../../api/roster";
import { submitFreeAgencyRequest, tradeRequestProposal } from "../../api/transaction";
import TradeRequestsPanel from "../../components/League/TradeRequestsPanel";
import { formatLeagueDate } from "../../utils/date";
import { normalizeOwnedTeams, type RawOwnedTeam } from "../../utils/teams";
import "./LeagueRosterPage.css";

type LocationState = {
  league?: League;
};

type GroupedTeams = [string, OwnedTeam[]][];

const LeagueRosterPage = () => {
  const navigate = useNavigate();
  const { league_id } = useParams();
  const location = useLocation();
  const state = location.state as LocationState | null;
  const league = state?.league;

  const leagueId = league?.leagueId ?? (league_id ? Number(league_id) : null);
  const memberId = league?.memberId ?? null;

  const isBrowser = typeof window !== "undefined";

  const [ownedTeams, setOwnedTeams] = useState<OwnedTeam[]>([]);
  const [availableTeams, setAvailableTeams] = useState<OwnedTeam[]>([]);
  const [selectedAdd, setSelectedAdd] = useState<OwnedTeam | null>(null);
  const [selectedDrop, setSelectedDrop] = useState<OwnedTeam | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState("");
  const [conferenceFilter, setConferenceFilter] = useState("all");
  const tabStorageKey =
    isBrowser && league?.leagueId ? `rosterTab:${league.leagueId}` : null;
  const [activeTab, setActiveTab] = useState<"addDrop" | "trade">(() => {
    if (!tabStorageKey || !isBrowser) {
      return "addDrop";
    }
    const stored = window.localStorage.getItem(tabStorageKey);
    return stored === "trade" ? "trade" : "addDrop";
  });
  const [members, setMembers] = useState<LeagueMember[]>([]);
  const [membersLoading, setMembersLoading] = useState(false);
  const [membersError, setMembersError] = useState<string | null>(null);
  const [tradeMemberId, setTradeMemberId] = useState<number | null>(null);
  const [tradeMemberTeams, setTradeMemberTeams] = useState<OwnedTeam[]>([]);
  const [tradeTeamsLoading, setTradeTeamsLoading] = useState(false);
  const [tradeTeamsError, setTradeTeamsError] = useState<string | null>(null);
  const [selectedTradeGive, setSelectedTradeGive] = useState<OwnedTeam | null>(null);
  const [selectedTradeReceive, setSelectedTradeReceive] = useState<OwnedTeam | null>(null);
  const rosterWeekNumber = league?.currentWeekNumber ?? 1;
  const rosterWeekId = league?.currentWeekId ?? rosterWeekNumber;

  useEffect(() => {
    if (!tabStorageKey || !isBrowser) {
      return;
    }
    window.localStorage.setItem(tabStorageKey, activeTab);
  }, [tabStorageKey, activeTab, isBrowser]);

  const loadRosterData = useCallback(async () => {
    if (!leagueId || !memberId) {
      return;
    }

    try {
      setLoading(true);
      setError(null);

      const [memberTeams, available] = await Promise.all([
        getMemberTeams(memberId, rosterWeekNumber, leagueId),
        getAvailableTeams(rosterWeekNumber, leagueId),
      ]);

      const normalizedOwned = normalizeOwnedTeams(memberTeams as RawOwnedTeam[]);
      const normalizedAvailable = normalizeOwnedTeams(available as RawOwnedTeam[]);
      setOwnedTeams(normalizedOwned);
      setAvailableTeams(normalizedAvailable);
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
      setError(err?.message ?? "Failed to load roster data");
    } finally {
      setLoading(false);
    }
  }, [leagueId, memberId, rosterWeekNumber]);

  useEffect(() => {
    loadRosterData();
  }, [loadRosterData]);

  useEffect(() => {
    if (!leagueId) {
      return;
    }

    let isCancelled = false;

    const loadMembers = async () => {
      try {
        setMembersLoading(true);
        setMembersError(null);

        const data = await getMembersOfLeague(leagueId);

        if (!isCancelled) {
          setMembers(data);
          const defaultPartner = data.find((m) => m.id !== memberId) ?? null;
          setTradeMemberId(defaultPartner?.id ?? null);
        }
      } catch (err: any) {
        if (!isCancelled) {
          setMembersError(err?.message ?? "Failed to load league members");
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
  }, [leagueId, memberId]);

  useEffect(() => {
    if (!tradeMemberId || !leagueId) {
      setTradeMemberTeams([]);
      setSelectedTradeReceive(null);
      return;
    }

    setSelectedTradeReceive(null);

    let isCancelled = false;

    const loadTradeTeams = async () => {
      try {
        setTradeTeamsLoading(true);
        setTradeTeamsError(null);

        const teams = await getMemberTeams(tradeMemberId, rosterWeekNumber, leagueId);

        if (!isCancelled) {
          const normalized = normalizeOwnedTeams(teams as RawOwnedTeam[]);
          setTradeMemberTeams(normalized);
          setSelectedTradeReceive((current) => {
            if (!current) return null;
            return normalized.find((team) => team.teamId === current.teamId) ?? null;
          });
        }
      } catch (err: any) {
        if (!isCancelled) {
          setTradeTeamsError(err?.message ?? "Failed to load member roster");
        }
      } finally {
        if (!isCancelled) {
          setTradeTeamsLoading(false);
        }
      }
    };

    loadTradeTeams();

    return () => {
      isCancelled = true;
    };
  }, [tradeMemberId, leagueId, rosterWeekNumber]);

  useEffect(() => {
    setSelectedTradeGive((current) => {
      if (!current) return null;
      return ownedTeams.find((team) => team.teamId === current.teamId) ?? null;
    });
  }, [ownedTeams]);

  const groupTeams = (teams: OwnedTeam[]): GroupedTeams => {
    const map = new Map<string, OwnedTeam[]>();

    teams.forEach((team) => {
      const key = team.conferenceName ?? "Independent";
      const current = map.get(key) ?? [];
      current.push(team);
      map.set(key, current);
    });

    return Array.from(map.entries()).sort(([a], [b]) => a.localeCompare(b));
  };

  const uniqueConferences = useMemo(() => {
    const all = [...ownedTeams, ...availableTeams, ...tradeMemberTeams]
      .map((team) => team.conferenceName ?? "Independent")
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
        (team.conferenceName ?? "Independent") === conferenceFilter;
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

  const toggleAddTeam = (team: OwnedTeam) => {
    setSelectedAdd((current) =>
      current?.teamId === team.teamId ? null : team
    );
  };

  const toggleDropTeam = (team: OwnedTeam) => {
    setSelectedDrop((current) =>
      current?.teamId === team.teamId ? null : team
    );
  };

  const toggleTradeGiveTeam = (team: OwnedTeam) => {
    setSelectedTradeGive((current) =>
      current?.teamId === team.teamId ? null : team
    );
  };

  const toggleTradeReceiveTeam = (team: OwnedTeam) => {
    setSelectedTradeReceive((current) =>
      current?.teamId === team.teamId ? null : team
    );
  };

  const handleSubmitAddDrop = async () => {
    if (!league || !memberId || !leagueId) {
      return;
    }

    if (!selectedAdd && !selectedDrop) {
      return;
    }

    try {
      setLoading(true);
      setError(null);

      await submitFreeAgencyRequest(
        league.leagueId,
        rosterWeekNumber,
        rosterWeekId,
        league.memberId,
        selectedAdd ? selectedAdd.teamId : null,
        selectedDrop ? selectedDrop.teamId : null
      );

      if (selectedAdd) {
        setSelectedAdd(null);
      }
      if (selectedDrop) {
        setSelectedDrop(null);
      }

      await loadRosterData();
    } catch (err: any) {
      setError(err?.message ?? "Failed to submit add/drop request");
    } finally {
      setLoading(false);
    }
  };

  const handleSubmitTrade = async () => {
    if (!tradeMemberId || !selectedTradeGive || !selectedTradeReceive || !league) {
      return;
    }

    try {
      setLoading(true);
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

      setSelectedTradeGive(null);
      setSelectedTradeReceive(null);
      await loadRosterData();
    } catch (err: any) {
      setError(err?.message ?? "Failed to submit trade request");
    } finally {
      setLoading(false);
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

  if (!league || !memberId || !leagueId) {
    return (
      <div className="roster-page">
        <button
          className="roster-page__back"
          type="button"
          onClick={() => navigate(-1)}
        >
          ← Back
        </button>
        <p className="roster-page__empty">
          League context missing. Please open this page from your league detail view.
        </p>
      </div>
    );
  }

  const addDropSubmitDisabled =
    tradeDeadlinePassed ||
    loading ||
    (!selectedAdd && !selectedDrop);

  const tradeSubmitDisabled =
    tradeDeadlinePassed ||
    loading ||
    tradeTeamsLoading ||
    !selectedTradeGive ||
    !selectedTradeReceive ||
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
          <span>
            Trade deadline: {formatLeagueDate(league.tradeDeadline)}
          </span>
          {tradeDeadlinePassed && (
            <span className="roster-page__deadline">
              Deadline passed — roster moves locked.
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
      {loading && <p className="roster-page__loading">Loading teams…</p>}

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
                  disabled: tradeDeadlinePassed,
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
                  disabled: tradeDeadlinePassed,
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
                    onClick={() => setSelectedAdd(null)}
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
                    onClick={() => setSelectedDrop(null)}
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
            {tradeDeadlinePassed && (
              <p className="roster-page__deadline">
                Trade deadline passed on {formatLeagueDate(league.tradeDeadline)}.
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
                          onClick={() => setSelectedTradeGive(null)}
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
                          onClick={() => setSelectedTradeReceive(null)}
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
          <TradeRequestsPanel leagueId={league.leagueId} memberId={league.memberId} />
        </>
      )}
    </div>
  );
};

export default LeagueRosterPage;
