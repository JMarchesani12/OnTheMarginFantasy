import { useNavigate, useParams, type To, type NavigateOptions } from "react-router-dom";
import { useEffect, useMemo, useState } from "react";
import type { League } from "../../types/league";
import type { LeagueMember } from "../../types/leagueMember";
import {
  getMembersOfLeague,
  removeLeagueMember,
  updateLeagueMember,
} from "../../api/leagues";
import { formatLeagueDate } from "../../utils/date";
import { LeagueScheduleTabs } from "../../components/League/LeagueScheduleTabs";
import LeagueScoreboard, {
  type ScoreboardRow as LeagueScoreboardRow,
} from "../../components/League/LeagueScoreboard";
import { getScoresForWeek } from "../../api/scoring";
import type { ScoreWeek } from "../../types/scoring";
import { useLeagueContext } from "../../hooks/useLeagueContext";
import { useRequestScope } from "../../hooks/useRequestScope";
import { getEffectiveWeekNumber, MIN_SCHEDULE_WEEK_NUMBER } from "../../utils/weekCutoff";
import { getDisplayedSeasonPoints, getLeagueRank } from "../../utils/leagueDetailCalculations";
import "./LeagueDetailPage.css";

type DetailContextProps = { initialLeague: League; currentUserId: number; isMember: boolean; isCurrent: () => boolean };

const LeagueDetailPage = () => {
  const { league_id } = useParams();
  const context = useLeagueContext(league_id);
  const navigate = useNavigate();
  if (!context.league) return (
    <div className="league-detail">
      <button className="league-detail__back" type="button" onClick={() => navigate("/leagues")}>← Back</button>
      <p>{context.loading ? "Loading league details…" : context.error ?? "League data is not available. Try opening this page from your leagues list."}</p>
      {context.canRetry && <button type="button" onClick={context.retry}>Retry</button>}
    </div>
  );
  return <LeagueDetailView key={context.scopeKey} initialLeague={context.league} currentUserId={context.userId!} isMember={context.isMember} isCurrent={context.isCurrent} />;
};

const LeagueDetailView = ({ initialLeague, currentUserId, isMember, isCurrent }: DetailContextProps) => {
  const rawNavigate = useNavigate();
  const scope = useRequestScope(isCurrent);
  const navigate = (to: To, options?: NavigateOptions) => {
    if (scope.isCurrent()) return rawNavigate(to, options);
  };
  const [league] = useState(initialLeague);
  const [members, setMembers] = useState<LeagueMember[]>([]);
  const [loadingMembers, setLoadingMembers] = useState(false);
  const [membersError, setMembersError] = useState<string | null>(null);
  const [scoreboard, setScoreboard] = useState<Record<number, ScoreWeek[]>>({});
  const [scoreboardLoading, setScoreboardLoading] = useState(false);
  const [scoreboardError, setScoreboardError] = useState<string | null>(null);
  const [teamNameValue, setTeamNameValue] = useState<string>(
    league?.teamName ?? ""
  );
  const [teamNameInput, setTeamNameInput] = useState<string>(
    league?.teamName ?? ""
  );
  const [editingTeamName, setEditingTeamName] = useState(false);
  const [teamNameSaving, setTeamNameSaving] = useState(false);
  const [teamNameError, setTeamNameError] = useState<string | null>(null);
  const [teamNameSuccess, setTeamNameSuccess] = useState<string | null>(null);
  const startDraftLoading = false;
  const [startDraftError, setStartDraftError] = useState<string | null>(null);
  const leagueTimeZone = league?.settings?.timezone ?? null;
  const effectiveWeekNumber = useMemo(
    () =>
      getEffectiveWeekNumber({
        currentWeekNumber: league?.currentWeekNumber ?? null,
        currentWeekStartDate: league?.currentWeekStartDate ?? null,
        timeZone: leagueTimeZone,
      }),
    [league?.currentWeekNumber, league?.currentWeekStartDate, leagueTimeZone]
  );

  useEffect(() => {
    setTeamNameValue(league?.teamName ?? "");
    setTeamNameInput(league?.teamName ?? "");
  }, [league?.teamName]);
  const [leaveError, setLeaveError] = useState<string | null>(null);
  const [leaveLoading, setLeaveLoading] = useState(false);

  // Fetch members on init
  useEffect(() => {
    if (!scope.isCurrent()) return;
    const current = scope.capture("members");

    const loadMembers = async () => {
      setLoadingMembers(true);
      setMembersError(null);

      try {
        const memberData = await getMembersOfLeague(league.leagueId, current.signal);
        if (current()) setMembers(memberData);
      } catch (error: any) {
        if (current()) setMembersError(error?.message ?? "Failed to load league members");
      } finally {
        if (current()) setLoadingMembers(false);
      }
    };

    loadMembers();
    return () => current.cancel();
  }, [league, scope]);

  useEffect(() => {
    if (!league?.leagueId) {
      return;
    }

    const currentWeek = effectiveWeekNumber ?? null;
    if (currentWeek === null || currentWeek < 0) {
      return;
    }

    let isCancelled = false;
    const current = scope.capture("scores");

    const loadScores = async () => {
      setScoreboardLoading(true);
      setScoreboardError(null);

      try {
        const scoresByWeek: Record<number, ScoreWeek[]> = {};

        if (currentWeek <= 10) {
          const { results } = await getScoresForWeek(
            Array.from({ length: currentWeek + 1 }, (_, idx) => idx),
            league.leagueId, current.signal
          );

          results.forEach((score) => {
            const list = scoresByWeek[score.weekNumber] ?? [];
            list.push(score);
            scoresByWeek[score.weekNumber] = list;
          });
        } else {
          for (let week = 0; week <= currentWeek; week += 10) {
            if (isCancelled || !current()) return;
            const chunk = Array.from(
              { length: Math.min(10, currentWeek - week + 1) },
              (_, idx) => week + idx
            );
            const { results } = await getScoresForWeek(chunk, league.leagueId, current.signal);

            results.forEach((score) => {
              const list = scoresByWeek[score.weekNumber] ?? [];
              list.push(score);
              scoresByWeek[score.weekNumber] = list;
            });
          }
        }

        if (!isCancelled && current()) {
          setScoreboard(scoresByWeek);
        }
      } catch (error: any) {
        if (!isCancelled && current()) {
          setScoreboardError(error?.message ?? "Failed to load scoreboard");
        }
      } finally {
        if (!isCancelled && current()) {
          setScoreboardLoading(false);
        }
      }
    };

    loadScores();

    return () => {
      isCancelled = true;
      current.cancel();
    };
  }, [league?.leagueId, effectiveWeekNumber, scope]);

  const openRosterManagement = () => {
    if (!isMember) return;
    if (!league) return;
    navigate(`/leagues/${league.leagueId}/roster`, { state: { league } });
  };

  const openDraftPage = (autoJoin = false) => {
    if (!isMember) return;
    if (!league) return;
    navigate(`/leagues/${league.leagueId}/draft`, {
      state: { league, autoJoin },
    });
  };

  const openConferencePage = () => {
    if (!league) return;
    navigate(`/leagues/${league.leagueId}/conference`, { state: { league } });
  };

  const openTeamLookupPage = () => {
    if (!league) return;
    navigate(`/leagues/${league.leagueId}/team-search`, { state: { league } });
  };

  const openManageLeague = () => {
    if (!isMember) return;
    if (!league) return;
    navigate(`/leagues/${league.leagueId}/manage`, { state: { league } });
  };

  const handleTeamNameSave = async () => {
    if (!scope.isCurrent() || !isMember || !league.memberId) return;
    const current = scope.capture();
    setTeamNameError(null);
    setTeamNameSuccess(null);

    const nextName = teamNameInput.trim();
    if (!nextName) {
      setTeamNameError("Team name is required.");
      return;
    }

    try {
      setTeamNameSaving(true);
      await updateLeagueMember(league.memberId, nextName);
      if (!current()) return;

      setTeamNameValue(nextName);
      setMembers((current) =>
        current.map((member) =>
          member.id === league.memberId ? { ...member, teamName: nextName } : member
        )
      );
      setEditingTeamName(false);
      setTeamNameSuccess("Team name updated.");
    } catch (err: any) {
      if (!current()) return;
      setTeamNameError(err?.message ?? "Failed to update team name.");
    } finally {
      if (!current()) return;
      setTeamNameSaving(false);
    }
  };

  const handleLeaveLeague = async () => {
    if (!scope.isCurrent() || !isMember || !league.memberId || !currentUserId) return;
    const current = scope.capture();
    const confirmed = window.confirm("Leave this league?");
    if (!confirmed) return;

    setLeaveError(null);
    setLeaveLoading(true);

    try {
      await removeLeagueMember(league.leagueId, league.memberId, currentUserId);
      if (!current()) return;
      navigate("/leagues");
    } catch (err: any) {
      if (!current()) return;
      setLeaveError(err?.message ?? "Failed to leave league.");
    } finally {
      if (!current()) return;
      setLeaveLoading(false);
    }
  };

  const tradeDeadlinePassed = useMemo(() => {
    if (!league?.tradeDeadline) {
      return false;
    }

    const now = new Date();
    const deadline = new Date(league.tradeDeadline);
    if (Number.isNaN(deadline.getTime())) {
      return false;
    }

    return deadline.getTime() < now.getTime();
  }, [league?.tradeDeadline]);
  const freeAgentDeadlinePassed = useMemo(() => {
    if (!league?.freeAgentDeadline) {
      return false;
    }

    const now = new Date();
    const deadline = new Date(league.freeAgentDeadline);
    if (Number.isNaN(deadline.getTime())) {
      return false;
    }

    return deadline.getTime() < now.getTime();
  }, [league?.freeAgentDeadline]);

  const scoreboardRows = useMemo<{
    weekNumbers: number[];
    rows: LeagueScoreboardRow[];
  }>(() => {
    const weekNumbersFromScores = Object.keys(scoreboard)
      .map((key) => Number(key))
      .sort((a, b) => a - b);
    const fallbackWeekNumber = effectiveWeekNumber ?? 1;
    const weekNumbers =
      weekNumbersFromScores.length > 0
        ? weekNumbersFromScores
        : [fallbackWeekNumber];

    const membersById = new Map<number, LeagueMember>();
    members.forEach((member) => {
      membersById.set(member.id, member);
    });

    const rows = new Map<number, LeagueScoreboardRow>();

    weekNumbersFromScores.forEach((week) => {
      const scores = scoreboard[week] ?? [];
      scores.forEach((score) => {
        const row = rows.get(score.memberId) ?? {
          memberId: score.memberId,
          teamName:
            score.teamName ??
            membersById.get(score.memberId)?.teamName ??
            `Member ${score.memberId}`,
          weeklyPoints: {} as Record<number, number | null | undefined>,
          weeklyDifferentials: {} as Record<number, number | null | undefined>,
          totalPoints: 0,
        };
        row.weeklyPoints[week] = score.pointsAwarded;
        row.weeklyDifferentials[week] = score.pointDifferential;
        row.totalPoints += score.pointsAwarded ?? 0;
        rows.set(score.memberId, row);
      });
    });

    members.forEach((member) => {
      if (!rows.has(member.id)) {
        rows.set(member.id, {
          memberId: member.id,
          teamName: member.teamName ?? `Member ${member.id}`,
          weeklyPoints: {} as Record<number, number | null | undefined>,
          weeklyDifferentials: {} as Record<number, number | null | undefined>,
          totalPoints: 0,
        });
      }
    });

    rows.forEach((row) => {
      let totalPoints = 0;
      weekNumbers.forEach((week) => {
        const points =
          typeof row.weeklyPoints[week] === "number"
            ? (row.weeklyPoints[week] as number)
            : 0;
        row.weeklyPoints[week] = points;
        totalPoints += points;
      });
      row.totalPoints = totalPoints;
    });

    return {
      weekNumbers,
      rows: Array.from(rows.values()).sort((a, b) => b.totalPoints - a.totalPoints),
    };
  }, [scoreboard, members, effectiveWeekNumber]);

  const currentWeekTotals = useMemo(() => {
    const currentWeek = effectiveWeekNumber ?? null;
    const scores = currentWeek !== null ? scoreboard[currentWeek] ?? [] : [];
    const scoreMap = new Map<number, ScoreWeek>();
    scores.forEach((score) => {
      scoreMap.set(score.memberId, score);
    });

    const totals = new Map<
      number,
      { memberId: number; teamName: string; differential: number }
    >();

    members.forEach((member) => {
      const score = scoreMap.get(member.id);
      const memberDifferential =
        typeof member.currentWeekPointDifferential === "number"
          ? member.currentWeekPointDifferential
          : undefined;
      const scoreboardDifferential =
        typeof score?.pointDifferential === "number"
          ? score.pointDifferential
          : undefined;
      const differential = memberDifferential ?? scoreboardDifferential ?? 0;

      totals.set(member.id, {
        memberId: member.id,
        teamName:
          member.teamName ??
          score?.teamName ??
          `Member ${member.id}`,
        differential,
      });
    });

    scores.forEach((score) => {
      if (!totals.has(score.memberId)) {
        totals.set(score.memberId, {
          memberId: score.memberId,
          teamName: score.teamName ?? `Member ${score.memberId}`,
          differential:
            typeof score.pointDifferential === "number"
              ? score.pointDifferential
              : 0,
        });
      }
    });

    return {
      weekNumber: currentWeek,
      rows: Array.from(totals.values()).sort(
        (a, b) => b.differential - a.differential
      ),
    };
  }, [scoreboard, members, effectiveWeekNumber]);


  const currentMemberId = league?.memberId ?? null;
  const currentMember = useMemo(
    () =>
      currentMemberId
        ? members.find((member) => member.id === currentMemberId) ?? null
        : null,
    [members, currentMemberId]
  );

  const currentMemberRow = useMemo(
    () =>
      currentMemberId
        ? scoreboardRows.rows.find((row) => row.memberId === currentMemberId) ??
          null
        : null,
    [scoreboardRows.rows, currentMemberId]
  );
  const currentMemberHasScoreboardScores = useMemo(() => {
    if (!currentMemberId) {
      return false;
    }

    return Object.values(scoreboard).some((scores) =>
      scores.some((score) => score.memberId === currentMemberId)
    );
  }, [scoreboard, currentMemberId]);

  const currentLeagueRank = useMemo(() => {
    const rowsByMember = new Map(scoreboardRows.rows.map((row) => [row.memberId, row]));
    const scoredMembers = new Set(Object.values(scoreboard).flatMap((scores) => scores.map((score) => score.memberId)));
    return getLeagueRank(members.map((member) => ({
      memberId: member.id,
      points: getDisplayedSeasonPoints({
        scoreboardTotalPoints: rowsByMember.get(member.id)?.totalPoints,
        hasScoreboardScores: scoredMembers.has(member.id),
        memberSeasonPoints: member.seasonPoints,
        leagueSeasonPoints: member.id === currentMemberId ? league?.seasonPoints : null,
      }),
    })), currentMemberId);
  }, [members, scoreboardRows.rows, scoreboard, currentMemberId, league?.seasonPoints]);

  const currentWeekDifferential = useMemo(() => {
    const currentWeek = effectiveWeekNumber ?? null;
    if (currentWeek === null || !currentMemberId) {
      return { weekNumber: currentWeek, differential: 0 };
    }

    if (typeof currentMember?.currentWeekPointDifferential === "number") {
      return {
        weekNumber: currentWeek,
        differential: currentMember.currentWeekPointDifferential,
      };
    }

    const weekScores = scoreboard[currentWeek] ?? [];
    const entry = weekScores.find((score) => score.memberId === currentMemberId);
    const fallbackDifferential =
      typeof entry?.pointDifferential === "number" ? entry.pointDifferential : 0;

    return { weekNumber: currentWeek, differential: fallbackDifferential };
  }, [
    scoreboard,
    effectiveWeekNumber,
    currentMemberId,
    currentMember?.currentWeekPointDifferential,
  ]);

  const statusClass = `league-detail__status league-detail__status--${league.status
    .toLowerCase()
    .replace(/\s+/g, "-")}`;
  const canStartDraft =
    (league.status === "Pre-Draft" || league.status === "Drafting") &&
    isMember && league.commissionerId === currentUserId;
  const canManageLeague = isMember && league.commissionerId === currentUserId;
  const canEditTeamName = isMember && league.memberId > 0;
  const canLeaveLeague =
    isMember && league.status === "Pre-Draft" && league.commissionerId !== currentUserId;
  const showAdminActions = canManageLeague;
  const canJoinDraft =
    (league.status === "Pre-Draft" || league.status === "Drafting") &&
    isMember && league.commissionerId !== currentUserId;
  const isDraftCompleted =
    league.status === "Post-Draft" || league.status === "In-Season" || league.status === "Completed";
  const rosterActionsLocked = tradeDeadlinePassed && freeAgentDeadlinePassed;

  const handleStartDraft = () => {
    setStartDraftError(null);
    openDraftPage(true);
  };

  const handleJoinDraft = () => {
    setStartDraftError(null);
    openDraftPage(true);
  };

  return (
    <div className="league-detail">
      <button
        className="league-detail__back"
        type="button"
        onClick={() => navigate("/leagues")}
      >
        ← Back to Leagues
      </button>

      <header className="league-detail__header">
        <div>
          <h1 className="league-detail__title">{league.leagueName}</h1>
          <p className="league-detail__commissioner">
            Commissioner: <span>{league.commissionerDisplayName}</span>
          </p>
        </div>
        <div className={statusClass}>{league.status}</div>
      </header>

      <section className="league-detail__overview">
        <div className="league-detail__overview-row">
          <div className="league-detail__overview-item">
            <span className="label">Sport</span>
            <span className="value">{league.sport}</span>
          </div>
          <div className="league-detail__overview-item">
            <span className="label">Season</span>
            <span className="value">{league.seasonYear}</span>
          </div>
          <div className="league-detail__overview-item">
            <span className="label">Number of Teams</span>
            <span className="value">{league.numPlayers}</span>
          </div>
          <div className="league-detail__overview-item">
            <span className="label">Status: </span>
            <span className="value">{league.status}</span>
          </div>
        </div>

        <div className="league-detail__overview-row">
          <div className="league-detail__overview-item">
            <span className="label">Draft Date</span>
            <span className="value">{formatLeagueDate(league.draftDate)}</span>
          </div>
          <div className="league-detail__overview-item">
            <span className="label">Trade Deadline</span>
            <span className="value">
              {formatLeagueDate(league.tradeDeadline)}
            </span>
          </div>
          <div className="league-detail__overview-item">
            <span className="label">Free Agent Deadline</span>
            <span className="value">
              {formatLeagueDate(league.freeAgentDeadline)}
            </span>
          </div>
        </div>
      </section>

      <section className="league-detail__card league-detail__tools-card">
        <h2>League Tools</h2>
        <div className="league-detail__primary-actions">
          <button
            className="league-detail__conference-btn"
            type="button"
            onClick={openConferencePage}
          >
            View Conference Scores
          </button>
          <button
            className="league-detail__conference-btn"
            type="button"
            onClick={openTeamLookupPage}
          >
            Find Team
          </button>
          {isDraftCompleted && (
            <button
              className="league-detail__conference-btn"
              type="button"
              onClick={() => navigate(`/leagues/${league.leagueId}/draft-results`)}
            >
              View Draft
            </button>
          )}
        </div>
      </section>

      <section
        className={`league-detail__content ${
          showAdminActions ? "league-detail__content--admin" : ""
        }`}
      >
        <div className="league-detail__card">
          <h2>Your Team</h2>
          <div className="league-detail__team-row">
            <div className="league-detail__team-name">
              <span className="label">Team Name</span>
              <div className="league-detail__team-name-value">
                <span className="value">{teamNameValue || "TBD"}</span>
                {canEditTeamName && !editingTeamName && (
                  <button
                    className="league-detail__team-edit-icon"
                    type="button"
                    aria-label="Edit team name"
                    onClick={() => {
                      setTeamNameInput(teamNameValue);
                      setEditingTeamName(true);
                    }}
                  >
                    <svg
                      viewBox="0 0 24 24"
                      aria-hidden="true"
                      focusable="false"
                    >
                      <path
                        d="M4 20.25L5.5 16l9.75-9.75a1.5 1.5 0 012.12 0l1.38 1.38a1.5 1.5 0 010 2.12L9 19.5 4 20.25z"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="1.6"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                      <path
                        d="M13.5 6.5l4 4"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="1.6"
                        strokeLinecap="round"
                      />
                    </svg>
                  </button>
                )}
              </div>
            </div>
            <div className="league-detail__team-stats">
              <div className="league-detail__team-stat">
                <span className="label">Season Points</span>
                <span className="value">
                  {getDisplayedSeasonPoints({
                    scoreboardTotalPoints: currentMemberRow?.totalPoints,
                    hasScoreboardScores: currentMemberHasScoreboardScores,
                    memberSeasonPoints: currentMember?.seasonPoints,
                    leagueSeasonPoints: league.seasonPoints,
                  })}
                </span>
              </div>
              <div className="league-detail__team-stat">
                <span className="label">League Rank</span>
                <span className="value">
                  {!loadingMembers && !scoreboardLoading && currentLeagueRank
                    ? `${currentLeagueRank.tied ? "Tied " : ""}#${currentLeagueRank.rank}`
                    : "—"}
                </span>
              </div>
              <div className="league-detail__team-stat">
                <span className="label">
                  Week {currentWeekDifferential.weekNumber ?? "-"} Diff
                </span>
                <span className="value">
                  {`${currentWeekDifferential.differential > 0 ? "+" : ""}${currentWeekDifferential.differential} pts`}
                </span>
              </div>
              {league.draftOrder != null && (
                <div className="league-detail__team-stat">
                  <span className="label">Draft Order</span>
                  <span className="value">#{league.draftOrder}</span>
                </div>
              )}
            </div>
          </div>
          {canEditTeamName && editingTeamName ? (
            <div className="league-detail__team-name-editor">
              <input
                type="text"
                value={teamNameInput}
                onChange={(event) => setTeamNameInput(event.target.value)}
                disabled={teamNameSaving}
              />
              <div className="league-detail__team-name-actions">
                <button
                  className="league-detail__team-save"
                  type="button"
                  onClick={handleTeamNameSave}
                  disabled={teamNameSaving}
                >
                  {teamNameSaving ? "Saving…" : "Save"}
                </button>
                <button
                  className="league-detail__team-cancel"
                  type="button"
                  onClick={() => {
                    setTeamNameInput(teamNameValue);
                    setEditingTeamName(false);
                  }}
                >
                  Cancel
                </button>
              </div>
              {teamNameError && (
                <p className="league-detail__error-text">{teamNameError}</p>
              )}
              {teamNameSuccess && (
                <p className="league-detail__success-text">
                  {teamNameSuccess}
                </p>
              )}
            </div>
          ) : null}
          <div className="league-detail__add-drop">
            <div className="league-detail__primary-actions">
              {isDraftCompleted && (
                <button
                  className="league-detail__add-drop-btn"
                  type="button"
                  onClick={openRosterManagement}
                  disabled={rosterActionsLocked || !isMember}
                >
                  Manage Roster
                </button>
              )}
              <button
                className="league-detail__conference-btn"
                type="button"
                onClick={() => navigate(`/leagues/${league.leagueId}/rules`)}
              >
                View league rules
              </button>
              {canJoinDraft && (
                <button
                  className="league-detail__conference-btn"
                  type="button"
                  onClick={handleJoinDraft}
                >
                  Join Draft Lobby
                </button>
              )}
            </div>
            {tradeDeadlinePassed && (
              <p className="league-detail__add-drop-note">
                <span className="league-detail__deadline-pill league-detail__deadline-pill--trade">
                  Trades
                </span>
                Trade deadline passed on {formatLeagueDate(league.tradeDeadline)}
              </p>
            )}
            {freeAgentDeadlinePassed && (
              <p className="league-detail__add-drop-note">
                <span className="league-detail__deadline-pill league-detail__deadline-pill--fa">
                  Add/Drop
                </span>
                Free agent deadline passed on{" "}
                {formatLeagueDate(league.freeAgentDeadline)}
              </p>
            )}
            {canLeaveLeague && (
              <button
                className="league-detail__leave-btn"
                type="button"
                onClick={handleLeaveLeague}
                disabled={leaveLoading}
              >
                {leaveLoading ? "Leaving…" : "Leave League"}
              </button>
            )}
            {leaveError && (
              <p className="league-detail__error-text">{leaveError}</p>
            )}
          </div>
        </div>
        {showAdminActions && (
          <div className="league-detail__card league-detail__card--compact">
            <h2 className="league-detail__card-title--compact">
              League Functions
            </h2>
            <div className="league-detail__action-buttons league-detail__action-buttons--compact">
              {canStartDraft && (
                <button
                  className="league-detail__start-draft-btn"
                  type="button"
                  onClick={handleStartDraft}
                  disabled={startDraftLoading}
                >
                  Start Draft
                </button>
              )}
              {startDraftError && (
                <p className="league-detail__error-text">{startDraftError}</p>
              )}
              <button
                className="league-detail__manage-btn"
                type="button"
                onClick={openManageLeague}
              >
                Manage League
              </button>
            </div>
          </div>
        )}
      </section>

      {loadingMembers && (
        <p className="league-detail__loading">Loading league members…</p>
      )}
      {membersError && (
        <p className="league-detail__error-text">{membersError}</p>
      )}
      {members.length > 0 && (
        <LeagueScheduleTabs
          sport={league.sport}
          leagueId={league.leagueId}
          members={members}
          currentMemberId={league.memberId}
          initialWeekNumber={effectiveWeekNumber ?? MIN_SCHEDULE_WEEK_NUMBER}
          timeZone={leagueTimeZone}
        />
      )}

      <div className="league-detail__scoreboard-grid">
        <LeagueScoreboard
          weekNumbers={scoreboardRows.weekNumbers}
          rows={scoreboardRows.rows}
          currentWeekNumber={effectiveWeekNumber ?? null}
          loading={scoreboardLoading}
          error={scoreboardError}
        />
        <section className="league-detail__week-totals">
          <header className="league-detail__week-totals-header">
            <p className="league-detail__week-totals-eyebrow">Current Week</p>
            <h2>Point Differential</h2>
            <p className="league-detail__week-totals-subhead">
              Week {currentWeekTotals.weekNumber ?? "-"}
            </p>
          </header>

          {scoreboardLoading && (
            <p className="league-detail__week-totals-loading">
              Loading week totals…
            </p>
          )}
          {scoreboardError && (
            <p className="league-detail__week-totals-error">
              {scoreboardError}
            </p>
          )}

          {!scoreboardLoading &&
            !scoreboardError &&
            currentWeekTotals.rows.length > 0 && (
              <div className="league-detail__week-totals-list">
                {currentWeekTotals.rows.map((row) => (
                  <div
                    className="league-detail__week-totals-row"
                    key={`week-total-${row.memberId}`}
                  >
                    <span className="league-detail__week-totals-team">
                      {row.teamName}
                    </span>
                    <span
                      className={`league-detail__week-totals-value ${
                        row.differential > 0
                          ? "is-positive"
                          : row.differential < 0
                          ? "is-negative"
                          : "is-neutral"
                      }`}
                    >
                      {`${row.differential > 0 ? "+" : ""}${row.differential} pts`}
                    </span>
                  </div>
                ))}
              </div>
            )}
        </section>
      </div>

    </div>
  );
};

export default LeagueDetailPage;
