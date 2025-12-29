import { useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import type {
  DraftType,
  GetRequestResponse,
  League,
  LeagueBonuses,
  SingleLeague,
  UpdateLeague,
} from "../../types/league";
import type { LeagueMember } from "../../types/leagueMember";
import {
  approveRequestToJoinLeague,
  denyRequestToJoinLeague,
  getLeague,
  getMembersOfLeague,
  getRequestsToJoinLeague,
  removeLeagueMember,
  deleteLeague,
  updateLeague,
} from "../../api/leagues";
import {
  BonusesEditor,
  BONUS_TEMPLATES,
  type BonusWithLocalId,
} from "../CreateLeague/BonusesEditor";
import { useCurrentUser } from "../../context/currentUserContext";
import "../CreateLeague/CreateLeague.css";
import "./ManageLeaguePage.css";

type LocationState = {
  league?: League;
};

type ManageLeagueFormState = {
  draftDate: string;
  freeAgentDeadline: string;
  tradeDeadline: string;
  tradeVetoEnabled: boolean;
  tradeVetoRequiredCount: string;
  bonuses: BonusWithLocalId[];
  draftType: DraftType;
  selectionTime: string;
  numberOfRounds: number;
};

const makeId = () => Math.random().toString(36).slice(2);

const formatDateInput = (iso: string | null | undefined): string => {
  if (!iso) return "";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  return date.toISOString().slice(0, 10);
};

const toIsoOrNull = (dateStr: string): string | null => {
  if (!dateStr) return null;
  const date = new Date(`${dateStr}T00:00:00`);
  if (Number.isNaN(date.getTime())) return null;
  return date.toISOString();
};

const humanizeKey = (value: string) => {
  const spaced = value.replace(/_/g, " ").replace(/([a-z])([A-Z])/g, "$1 $2");
  return spaced.replace(/\b\w/g, (match) => match.toUpperCase());
};

const buildBonusState = (bonuses: LeagueBonuses): BonusWithLocalId[] => {
  return Object.entries(bonuses).map(([bonusKey, placements]) => {
    const template = BONUS_TEMPLATES.find((item) => item.bonusKey === bonusKey);
    const placementKeys = template
      ? template.placements
          .map((placement) => placement.key)
          .filter((key) => Object.prototype.hasOwnProperty.call(placements, key))
      : Object.keys(placements);

    const placementRows = placementKeys.map((key) => {
      const templatePlacement = template?.placements.find((p) => p.key === key);
      return {
        id: makeId(),
        key,
        label: templatePlacement?.label ?? humanizeKey(key),
        points: String(placements[key] ?? 0),
      };
    });

    return {
      id: makeId(),
      bonusKey,
      label: template?.label ?? humanizeKey(bonusKey),
      hint: template?.hint ?? "",
      placements: placementRows,
    };
  });
};

const buildBonusesPayload = (bonuses: BonusWithLocalId[]): LeagueBonuses => {
  const payload: LeagueBonuses = {};
  bonuses.forEach((bonus) => {
    const placementValues: Record<string, number> = {};
    bonus.placements.forEach((placement) => {
      if (placement.points === "") return;
      placementValues[placement.key] = Number(placement.points);
    });
    if (Object.keys(placementValues).length > 0) {
      payload[bonus.bonusKey] = placementValues;
    }
  });
  return payload;
};

const shuffleMembers = (members: LeagueMember[]) => {
  const copy = [...members];
  for (let i = copy.length - 1; i > 0; i -= 1) {
    const j = Math.floor(Math.random() * (i + 1));
    [copy[i], copy[j]] = [copy[j], copy[i]];
  }
  return copy;
};

const makeInitialForm = (league: League | null): ManageLeagueFormState => ({
  draftDate: formatDateInput(league?.draftDate ?? null),
  freeAgentDeadline: formatDateInput(league?.freeAgentDeadline ?? null),
  tradeDeadline: formatDateInput(league?.tradeDeadline ?? null),
  tradeVetoEnabled:
    league?.settings?.transactions?.tradeVeto?.enabled ?? true,
  tradeVetoRequiredCount: String(
    league?.settings?.transactions?.tradeVeto?.requiredVetoCount ?? 0
  ),
  bonuses: league?.settings?.bonuses
    ? buildBonusState(league.settings.bonuses)
    : [],
  draftType: league?.settings?.draft?.draftType ?? "SNAKE",
  selectionTime: String(league?.settings?.draft?.selectionTime ?? 60),
  numberOfRounds: league?.settings?.draft?.numberOfRounds ?? 0,
});

const ManageLeaguePage = () => {
  const navigate = useNavigate();
  const { league_id } = useParams();
  const location = useLocation();
  const state = location.state as LocationState | null;
  const initialLeague = state?.league ?? null;
  const [leagueState, setLeagueState] = useState<League | null>(initialLeague);
  const leagueId =
    leagueState?.leagueId ?? (league_id ? Number(league_id) : null);

  const { userId: currentUserId, loading: authLoading, error: authError } = useCurrentUser();

  const [form, setForm] = useState<ManageLeagueFormState>(
    makeInitialForm(leagueState)
  );
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);

  const [members, setMembers] = useState<LeagueMember[]>([]);
  const [membersLoading, setMembersLoading] = useState(false);
  const [membersError, setMembersError] = useState<string | null>(null);
  const [draftOrder, setDraftOrder] = useState<Record<number, string>>({});
  const [orderedMemberIds, setOrderedMemberIds] = useState<number[]>([]);
  const [draggingMemberId, setDraggingMemberId] = useState<number | null>(null);
  const [memberActionError, setMemberActionError] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const [requests, setRequests] = useState<GetRequestResponse[]>([]);
  const [requestsLoading, setRequestsLoading] = useState(false);
  const [requestsError, setRequestsError] = useState<string | null>(null);
  const [leagueLoading, setLeagueLoading] = useState(false);
  const [leagueError, setLeagueError] = useState<string | null>(null);

  useEffect(() => {
    setLeagueState(initialLeague);
    setForm(makeInitialForm(initialLeague));
  }, [initialLeague]);

  const normalizeLeagueSettings = (value: unknown) => {
    if (!value) return undefined;
    if (typeof value === "string") {
      try {
        return JSON.parse(value) as League["settings"];
      } catch {
        return undefined;
      }
    }
    return value as League["settings"];
  };

  const mapLeagueFromResponse = (
    payload: SingleLeague | League | { league?: SingleLeague | League }
  ): League => {
    const data =
      (payload as { league?: SingleLeague | League }).league ?? payload;

    if ((data as League).leagueId) {
      const leagueData = data as League;
      return {
        ...leagueData,
        settings: normalizeLeagueSettings(leagueData.settings) ?? leagueData.settings,
      };
    }

    const single = data as SingleLeague;
    const status = single.status ?? "Pre-Draft";
    const commissionerId =
      (single as { commissionerId?: number }).commissionerId ??
      (single as { commissioner?: number }).commissioner ??
      0;

    return {
      leagueId: single.id,
      leagueCreatedAt: single.createdAt,
      leagueName: single.name,
      sport: String(single.sport),
      maxPlayersToHaveMaxRounds: 0,
      numPlayers: single.numPlayers,
      status,
      settings: normalizeLeagueSettings(single.settings) ?? {
        bonuses: {},
        transactions: { tradeVeto: { enabled: false, requiredVetoCount: 0 } },
        draft: { draftType: "SNAKE", selectionTime: 60, numberOfRounds: 0 },
      },
      updatedAt: single.updatedAt ?? single.createdAt,
      draftDate: single.draftDate,
      tradeDeadline: single.tradeDeadline,
      freeAgentDeadline: single.freeAgentDeadline,
      seasonYear: single.seasonYear,
      commissionerId,
      commissionerDisplayName:
        (single as { commissionerDisplayName?: string })
          .commissionerDisplayName ?? "",
      memberId: 0,
      teamName: null,
      draftOrder: null,
      seasonPoints: null,
      currentWeekEndDate: null,
      currentWeekId: null,
      currentWeekNumber: null,
      currentWeekStartDate: null,
    };
  };

  useEffect(() => {
    if (!league_id) return;

    let isMounted = true;

    const loadLeague = async () => {
      try {
        setLeagueLoading(true);
        setLeagueError(null);
        const data = await getLeague(Number(league_id));
        if (!isMounted) return;
        const nextLeague = mapLeagueFromResponse(data);
        setLeagueState(nextLeague);
        setForm(makeInitialForm(nextLeague));
      } catch (err: any) {
        if (isMounted) {
          setLeagueError(err?.message ?? "Failed to load league.");
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
  }, [league_id]);

  const loadMembers = async (options?: { isCancelled?: () => boolean }) => {
    if (!leagueId) return;
    setMembersLoading(true);
    setMembersError(null);

    try {
      const data = await getMembersOfLeague(leagueId);
      if (options?.isCancelled?.()) {
        return;
      }
      setMembers(data);
    } catch (err: any) {
      if (options?.isCancelled?.()) {
        return;
      }
      setMembersError(err?.message ?? "Failed to load league members");
    } finally {
      if (options?.isCancelled?.()) {
        return;
      }
      setMembersLoading(false);
    }
  };

  useEffect(() => {
    if (!leagueId) return;

    let isCancelled = false;

    loadMembers({ isCancelled: () => isCancelled });

    return () => {
      isCancelled = true;
    };
  }, [leagueId]);

  useEffect(() => {
    if (members.length === 0) {
      setOrderedMemberIds([]);
      return;
    }
    setDraftOrder((current) => {
      const hasOrder = Object.keys(current).length > 0;
      const next: Record<number, string> = { ...current };
      members.forEach((member, index) => {
        if (next[member.id]) {
          return;
        }
        next[member.id] = String(member.draftOrder ?? index + 1);
      });
      return next;
    });
    setOrderedMemberIds((current) => {
      if (current.length > 0) {
        const existing = new Set(current);
        const appended = members
          .filter((member) => !existing.has(member.id))
          .map((member) => member.id);
        return [...current, ...appended];
      }
      return [...members]
        .sort(
          (a, b) =>
            (a.draftOrder ?? Number.POSITIVE_INFINITY) -
            (b.draftOrder ?? Number.POSITIVE_INFINITY)
        )
        .map((member) => member.id);
    });
  }, [members]);

  const isCommissioner =
    !!leagueState &&
    !!currentUserId &&
    leagueState.commissionerId === currentUserId;
  const isEditableStatus =
    leagueState?.status !== "In-Season" &&
    leagueState?.status !== "Completed";
  const isPreDraft = leagueState?.status === "Pre-Draft";

  const orderedMembers = useMemo(() => {
    const memberMap = new Map(members.map((member) => [member.id, member]));
    return orderedMemberIds
      .map((id) => memberMap.get(id))
      .filter((member): member is LeagueMember => Boolean(member));
  }, [members, orderedMemberIds]);

  const updateForm = (patch: Partial<ManageLeagueFormState>) =>
    setForm((prev) => ({ ...prev, ...patch }));

  const handleSave = async () => {
    if (!leagueId) return;
    setSaveError(null);
    setSaveMessage(null);

    try {
      setSaving(true);
      const bonuses = buildBonusesPayload(form.bonuses);
      const payload: UpdateLeague = {
        settings: {
          bonuses,
          transactions: {
            tradeVeto: {
              enabled: form.tradeVetoEnabled,
              requiredVetoCount: Number(form.tradeVetoRequiredCount || 0),
            },
          },
          draft: {
            draftType: form.draftType,
            selectionTime: Number(form.selectionTime || 0),
            numberOfRounds: form.numberOfRounds,
          },
        },
        draftDate: toIsoOrNull(form.draftDate),
        freeAgentDeadline: toIsoOrNull(form.freeAgentDeadline),
        tradeDeadline: toIsoOrNull(form.tradeDeadline),
      };

      await updateLeague(payload, leagueId);
      const refreshed = await getLeague(leagueId);
      const nextLeague = mapLeagueFromResponse(refreshed);
      setLeagueState(nextLeague);
      setForm(makeInitialForm(nextLeague));
      setSaveMessage("League settings saved.");
    } catch (err: any) {
      setSaveError(err?.message ?? "Failed to save league settings.");
    } finally {
      setSaving(false);
    }
  };

  const handleRandomizeDraftOrder = () => {
    const shuffled = shuffleMembers(members);
    const nextIds = shuffled.map((member) => member.id);
    setOrderedMemberIds(nextIds);
    const next: Record<number, string> = {};
    nextIds.forEach((memberId, index) => {
      next[memberId] = String(index + 1);
    });
    setDraftOrder(next);
  };

  const loadRequests = async () => {
    if (!leagueId || !currentUserId) return;
    setRequestsError(null);
    setRequestsLoading(true);

    try {
      const data = await getRequestsToJoinLeague(
        leagueId,
        currentUserId,
        "PENDING"
      );
      setRequests(data);
    } catch (err: any) {
      setRequestsError(err?.message ?? "Failed to load join requests.");
    } finally {
      setRequestsLoading(false);
    }
  };

  useEffect(() => {
    if (!leagueId || !currentUserId || !isPreDraft || !isCommissioner) {
      return;
    }
    loadRequests();
  }, [leagueId, currentUserId, isPreDraft, isCommissioner]);

  const handleApproveRequest = async (requestId: number) => {
    if (!leagueId || !currentUserId) return;
    try {
      await approveRequestToJoinLeague(leagueId, requestId, currentUserId);
      await Promise.all([loadRequests(), loadMembers()]);
    } catch (err: any) {
      setRequestsError(err?.message ?? "Failed to approve request.");
    }
  };

  const handleDenyRequest = async (requestId: number) => {
    if (!leagueId || !currentUserId) return;
    try {
      await denyRequestToJoinLeague(leagueId, requestId, currentUserId);
      await loadRequests();
    } catch (err: any) {
      setRequestsError(err?.message ?? "Failed to decline request.");
    }
  };

  const handleRemoveMember = async (member: LeagueMember) => {
    if (!leagueId || !currentUserId || !isPreDraft) return;
    if (member.userId === currentUserId) {
      setMemberActionError("Commissioner cannot remove themselves.");
      return;
    }
    const name = member.teamName ?? member.displayName ?? `Member ${member.id}`;
    const confirmed = window.confirm(`Remove ${name} from this league?`);
    if (!confirmed) return;

    setMemberActionError(null);

    try {
      await removeLeagueMember(leagueId, member.id, currentUserId);
      setDraftOrder((current) => {
        const next = { ...current };
        delete next[member.id];
        return next;
      });
      setOrderedMemberIds((current) =>
        current.filter((memberId) => memberId !== member.id)
      );
      await loadMembers();
    } catch (err: any) {
      setMemberActionError(err?.message ?? "Failed to remove member.");
    }
  };

  const handleLeaveLeague = async () => {
    if (!leagueId || !currentUserId) return;
    const selfMember = members.find((member) => member.userId === currentUserId);
    if (!selfMember) {
      setMemberActionError("Could not find your membership for this league.");
      return;
    }
    const confirmed = window.confirm("Leave this league?");
    if (!confirmed) return;

    setMemberActionError(null);

    try {
      await removeLeagueMember(leagueId, selfMember.id, currentUserId);
      navigate("/leagues");
    } catch (err: any) {
      setMemberActionError(err?.message ?? "Failed to leave league.");
    }
  };

  const handleDragStart = (memberId: number) => {
    setDraggingMemberId(memberId);
  };

  const handleDragOver = (memberId: number) => {
    if (draggingMemberId === null || draggingMemberId === memberId) {
      return;
    }
    setOrderedMemberIds((current) => {
      const next = [...current];
      const fromIndex = next.indexOf(draggingMemberId);
      const toIndex = next.indexOf(memberId);
      if (fromIndex === -1 || toIndex === -1) {
        return current;
      }
      next.splice(fromIndex, 1);
      next.splice(toIndex, 0, draggingMemberId);
      const nextOrder: Record<number, string> = {};
      next.forEach((id, index) => {
        nextOrder[id] = String(index + 1);
      });
      setDraftOrder(nextOrder);
      return next;
    });
  };

  const handleDragEnd = () => {
    setDraggingMemberId(null);
  };

  const handleDeleteLeague = async () => {
    if (!leagueId || !currentUserId) return;
    const confirmed = window.confirm(
      "Delete this league? This cannot be undone."
    );
    if (!confirmed) return;

    setDeleteError(null);

    try {
      await deleteLeague(leagueId, currentUserId);
      navigate("/leagues");
    } catch (err: any) {
      setDeleteError(err?.message ?? "Failed to delete league.");
    }
  };

  if (!leagueState) {
    return (
      <div className="ml-page cl-page">
        <div className="cl-page-inner">
          <button
            className="ml-back"
            type="button"
            onClick={() => navigate(-1)}
          >
            ← Back
          </button>
          {leagueLoading ? (
            <p>Loading league details…</p>
          ) : (
            <p>
              {leagueError ??
                "League data is not available. Open this page from the league detail screen."}
            </p>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="ml-page cl-page">
      <div className="cl-page-inner">
        <header className="ml-header">
          <div>
            <h1>Manage League</h1>
          <p className="ml-subtitle">{leagueState.leagueName}</p>
          </div>
          <button className="ml-back" type="button" onClick={() => navigate(-1)}>
            ← Back
          </button>
        </header>

        {authError && <p className="ml-error">{authError}</p>}

        {isCommissioner ? (
          isEditableStatus ? (
            <section className="ml-section cl-form">
              <div className="ml-section-header">
                <h2>League Settings</h2>
                <p>Bonuses, deadlines, and transaction rules.</p>
              </div>

              <BonusesEditor
                value={form.bonuses}
                onChange={(bonuses) => updateForm({ bonuses })}
              />

              <div className="cl-form-grid">
                <div className="cl-field-group">
                  <label className="cl-field-label">Free Agent Deadline</label>
                  <input
                    type="date"
                    value={form.freeAgentDeadline}
                    onChange={(event) =>
                      updateForm({ freeAgentDeadline: event.target.value })
                    }
                  />
                </div>
                <div className="cl-field-group">
                  <label className="cl-field-label">Trade Deadline</label>
                  <input
                    type="date"
                    value={form.tradeDeadline}
                    onChange={(event) =>
                      updateForm({ tradeDeadline: event.target.value })
                    }
                  />
                </div>
              </div>

              <div className="ml-inline-actions">
                <button
                  className="cl-btn-secondary"
                  type="button"
                  onClick={() =>
                    updateForm({ freeAgentDeadline: "", tradeDeadline: "" })
                  }
                >
                  Clear deadlines
                </button>
              </div>

              <div className="cl-field-group cl-field-inline">
                <label className="cl-field-label">Trade Veto</label>
                <label className="cl-inline-checkbox">
                  <input
                    type="checkbox"
                    checked={form.tradeVetoEnabled}
                    onChange={(event) =>
                      updateForm({ tradeVetoEnabled: event.target.checked })
                    }
                  />
                  Enabled
                </label>
                {form.tradeVetoEnabled && (
                  <div className="cl-inline-number">
                    <span>
                      Required veto count: <span className="cl-required">*</span>
                    </span>
                    <input
                      type="number"
                      min={1}
                      value={form.tradeVetoRequiredCount}
                      onChange={(event) =>
                        updateForm({ tradeVetoRequiredCount: event.target.value })
                      }
                    />
                  </div>
                )}
              </div>

              {saveError && <p className="ml-error">{saveError}</p>}
              {saveMessage && <p className="ml-success">{saveMessage}</p>}

              <div className="ml-section-actions">
                <button
                  className="cl-btn-primary"
                  type="button"
                  onClick={handleSave}
                  disabled={saving}
                >
                  {saving ? "Saving…" : "Save League Settings"}
                </button>
              </div>
            </section>
          ) : (
            <section className="ml-section cl-form">
              <div className="ml-section-header">
                <h2>League Settings</h2>
                <p>Settings are locked while the league is in-season or completed.</p>
              </div>
            </section>
          )
        ) : (
          <section className="ml-section cl-form">
            <div className="ml-section-header">
              <h2>League Settings</h2>
              <p>Only the commissioner can edit league settings.</p>
            </div>
          </section>
        )}

        {isPreDraft && isCommissioner && (
          <section className="ml-section cl-form">
            <div className="ml-section-header">
              <h2>Draft Setup</h2>
              <p>Configure the draft schedule and order.</p>
            </div>

            <div className="cl-form-grid">
              <div className="cl-field-group">
                <label className="cl-field-label">Draft Date</label>
                <input
                  type="date"
                  value={form.draftDate}
                  onChange={(event) =>
                    updateForm({ draftDate: event.target.value })
                  }
                />
              </div>
              <div className="cl-field-group">
                <label className="cl-field-label">Draft Type</label>
                <select
                  value={form.draftType}
                  onChange={(event) =>
                    updateForm({ draftType: event.target.value as DraftType })
                  }
                >
                  <option value="SNAKE">Snake</option>
                  <option value="STRAIGHT">Straight</option>
                </select>
              </div>
              <div className="cl-field-group">
                <label className="cl-field-label">Selection Time (seconds)</label>
                <input
                  type="number"
                  min={10}
                  value={form.selectionTime}
                  onChange={(event) =>
                    updateForm({ selectionTime: event.target.value })
                  }
                />
              </div>
              <div className="cl-field-group">
                <label className="cl-field-label">Number of Rounds</label>
                <input type="number" value={form.numberOfRounds} readOnly />
              </div>
            </div>

            {isCommissioner && (
              <div className="ml-draft-order">
                <div className="ml-draft-order-header">
                  <h3>Draft Order</h3>
                  <button
                    className="cl-btn-secondary"
                    type="button"
                    onClick={handleRandomizeDraftOrder}
                    disabled={members.length === 0}
                  >
                    Randomize Draft Order
                  </button>
                </div>

                {membersLoading && (
                  <p className="ml-muted">Loading league members…</p>
                )}
                {membersError && <p className="ml-error">{membersError}</p>}
                {memberActionError && (
                  <p className="ml-error">{memberActionError}</p>
                )}

                {members.length > 0 && (
                  <div className="ml-draft-order-list">
                    {orderedMembers.map((member, index) => (
                      <div
                        key={member.id}
                        className={`ml-draft-order-row ${draggingMemberId === member.id ? "is-dragging" : ""}`}
                        draggable
                        onDragStart={() => handleDragStart(member.id)}
                        onDragOver={(event) => {
                          event.preventDefault();
                          handleDragOver(member.id);
                        }}
                        onDragEnd={handleDragEnd}
                      >
                        <div className="ml-draft-order-main">
                          <span className="ml-draft-rank">
                            {index + 1}
                          </span>
                          <div>
                            <p className="ml-draft-member">
                              {member.teamName ?? `Member ${member.id}`}
                            </p>
                            <span className="ml-draft-sub">
                              {member.displayName}
                            </span>
                          </div>
                        </div>
                        <div className="ml-draft-actions">
                          <button
                            className="ml-remove-btn"
                            type="button"
                            onClick={() => handleRemoveMember(member)}
                            disabled={member.userId === currentUserId}
                            title={
                              member.userId === currentUserId
                                ? "You cannot remove yourself."
                                : "Remove member"
                            }
                          >
                            Remove
                          </button>
                          <span className="ml-drag-hint" aria-hidden="true">
                            ⇅
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {saveError && <p className="ml-error">{saveError}</p>}
            {saveMessage && <p className="ml-success">{saveMessage}</p>}

            <div className="ml-section-actions">
              <button
                className="cl-btn-primary"
                type="button"
                onClick={handleSave}
                disabled={saving}
              >
                {saving ? "Saving…" : "Save"}
              </button>
              <button
                className="cl-btn-secondary"
                type="button"
                onClick={handleSave}
                disabled={saving}
              >
                Save and Start Draft
              </button>
            </div>
          </section>
        )}

        {isPreDraft && isCommissioner && (
          <section className="ml-section cl-form">
            <div className="ml-section-header">
              <h2>Join Requests</h2>
              <p>Approve or decline new members.</p>
            </div>

            {requestsLoading && (
              <p className="ml-muted">Loading requests…</p>
            )}
            {requestsError && <p className="ml-error">{requestsError}</p>}

            {requests.length === 0 && !requestsLoading ? (
              <p className="ml-muted">No pending requests.</p>
            ) : (
              <div className="ml-requests-list">
                {requests.map((request) => (
                  <div key={request.id} className="ml-request-card">
                    <div>
                      <p className="ml-request-name">
                        {request.userDisplayName || request.userEmail}
                      </p>
                      <p className="ml-request-sub">{request.userEmail}</p>
                      {request.message && (
                        <p className="ml-request-message">{request.message}</p>
                      )}
                    </div>
                    <div className="ml-request-actions">
                      <button
                        className="cl-btn-primary"
                        type="button"
                        onClick={() => handleApproveRequest(request.id)}
                      >
                        Accept
                      </button>
                      <button
                        className="cl-btn-secondary"
                        type="button"
                        onClick={() => handleDenyRequest(request.id)}
                      >
                        Decline
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>
        )}

        {isCommissioner && (
          <section className="ml-section cl-form">
            <div className="ml-section-header">
              <h2>Danger Zone</h2>
              <p>Irreversible actions for this league.</p>
            </div>

            {deleteError && <p className="ml-error">{deleteError}</p>}

            <div className="ml-section-actions">
              <button
                className="ml-delete-btn"
                type="button"
                onClick={handleDeleteLeague}
              >
                Delete League
              </button>
            </div>
          </section>
        )}

        {!isCommissioner && (
          <section className="ml-section cl-form">
            <div className="ml-section-header">
              <h2>Membership</h2>
              <p>Leave the league if you no longer want to participate.</p>
            </div>

            {memberActionError && (
              <p className="ml-error">{memberActionError}</p>
            )}

            <div className="ml-section-actions">
              <button
                className="ml-remove-btn"
                type="button"
                onClick={handleLeaveLeague}
              >
                Leave League
              </button>
            </div>
          </section>
        )}
      </div>
    </div>
  );
};

export default ManageLeaguePage;
