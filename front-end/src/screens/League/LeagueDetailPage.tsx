import { useLocation, useNavigate } from "react-router-dom";
import { useEffect, useMemo, useState } from "react";
import type { League } from "../../types/league";
import type { LeagueMember } from "../../types/leagueMember";
import { getMembersOfLeague, removeLeagueMember, updateLeagueMember } from "../../api/leagues";
import { formatLeagueDate } from "../../utils/date";
import { LeagueScheduleTabs } from "../../components/League/LeagueScheduleTabs";
import LeagueScoreboard, {
  type ScoreboardRow as LeagueScoreboardRow,
} from "../../components/League/LeagueScoreboard";
import { getScoresForWeek } from "../../api/scoring";
import type { ScoreWeek } from "../../types/scoring";
import { useCurrentUser } from "../../context/currentUserContext";
import "./LeagueDetailPage.css";

type LocationState = {
  league?: League;
};

const LeagueDetailPage = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const state = location.state as LocationState | null;
  const league = state?.league;
  const { userId: currentUserId, error: userError } = useCurrentUser();

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

  useEffect(() => {
    setTeamNameValue(league?.teamName ?? "");
    setTeamNameInput(league?.teamName ?? "");
  }, [league?.teamName]);
  const [leaveError, setLeaveError] = useState<string | null>(null);
  const [leaveLoading, setLeaveLoading] = useState(false);

  // Fetch members on init
  useEffect(() => {
    if (!league) return;

    const loadMembers = async () => {
      setLoadingMembers(true);
      setMembersError(null);

      try {
        const memberData = await getMembersOfLeague(league.leagueId);
        setMembers(memberData);
      } catch (error: any) {
        setMembersError(error?.message ?? "Failed to load league members");
      } finally {
        setLoadingMembers(false);
      }
    };

    loadMembers();
  }, [league]);

  useEffect(() => {
    if (!league?.leagueId) {
      return;
    }

    const currentWeek = league.currentWeekNumber ?? null;
    if (!currentWeek || currentWeek < 1) {
      return;
    }

    let isCancelled = false;

    const loadScores = async () => {
      setScoreboardLoading(true);
      setScoreboardError(null);

      try {
        const scoresByWeek: Record<number, ScoreWeek[]> = {};

        if (currentWeek <= 10) {
          const { results } = await getScoresForWeek(
            Array.from({ length: currentWeek }, (_, idx) => idx + 1),
            league.leagueId
          );

          results.forEach((score) => {
            const list = scoresByWeek[score.weekNumber] ?? [];
            list.push(score);
            scoresByWeek[score.weekNumber] = list;
          });
        } else {
          for (let week = 1; week <= currentWeek; week += 10) {
            const chunk = Array.from(
              { length: Math.min(10, currentWeek - week + 1) },
              (_, idx) => week + idx
            );
            const { results } = await getScoresForWeek(chunk, league.leagueId);

            results.forEach((score) => {
              const list = scoresByWeek[score.weekNumber] ?? [];
              list.push(score);
              scoresByWeek[score.weekNumber] = list;
            });
          }
        }

        if (!isCancelled) {
          setScoreboard(scoresByWeek);
        }
      } catch (error: any) {
        if (!isCancelled) {
          setScoreboardError(error?.message ?? "Failed to load scoreboard");
        }
      } finally {
        if (!isCancelled) {
          setScoreboardLoading(false);
        }
      }
    };

    loadScores();

    return () => {
      isCancelled = true;
    };
  }, [league?.leagueId, league?.currentWeekNumber]);

  const openRosterManagement = () => {
    if (!league) return;
    navigate(`/leagues/${league.leagueId}/roster`, { state: { league } });
  };

  const openDraftPage = (autoJoin = false) => {
    if (!league) return;
    navigate(`/leagues/${league.leagueId}/draft`, {
      state: { league, autoJoin },
    });
  };

  const openConferencePage = () => {
    if (!league) return;
    navigate(`/leagues/${league.leagueId}/conference`, { state: { league } });
  };

  const openManageLeague = () => {
    if (!league) return;
    navigate(`/leagues/${league.leagueId}/manage`, { state: { league } });
  };

  const handleTeamNameSave = async () => {
    if (!league?.memberId) return;
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

      setTeamNameValue(nextName);
      setEditingTeamName(false);
      setTeamNameSuccess("Team name updated.");
    } catch (err: any) {
      setTeamNameError(err?.message ?? "Failed to update team name.");
    } finally {
      setTeamNameSaving(false);
    }
  };

  const handleLeaveLeague = async () => {
    if (!league || !currentUserId) return;
    const confirmed = window.confirm("Leave this league?");
    if (!confirmed) return;

    setLeaveError(null);
    setLeaveLoading(true);

    try {
      await removeLeagueMember(league.leagueId, league.memberId, currentUserId);
      navigate("/leagues");
    } catch (err: any) {
      setLeaveError(err?.message ?? "Failed to leave league.");
    } finally {
      setLeaveLoading(false);
    }
  };

  // If you want, you can later add a fetch here if `league` is missing.
  if (!league) {
    return (
      <div className="league-detail">
        <button
          className="league-detail__back"
          type="button"
          onClick={() => navigate(-1)}
        >
          ← Back
        </button>
        <p>League data is not available. Try opening this page from your leagues list.</p>
      </div>
    );
  }

  const statusClass = `league-detail__status league-detail__status--${league.status
    .toLowerCase()
    .replace(/\s+/g, "-")}`;
  const tradeDeadlinePassed = useMemo(() => {
    if (!league.tradeDeadline) {
      return false;
    }

    const now = new Date();
    const deadline = new Date(league.tradeDeadline);
    if (Number.isNaN(deadline.getTime())) {
      return false;
    }

    return deadline.getTime() < now.getTime();
  }, [league.tradeDeadline]);
  const freeAgentDeadlinePassed = useMemo(() => {
    if (!league.freeAgentDeadline) {
      return false;
    }

    const now = new Date();
    const deadline = new Date(league.freeAgentDeadline);
    if (Number.isNaN(deadline.getTime())) {
      return false;
    }

    return deadline.getTime() < now.getTime();
  }, [league.freeAgentDeadline]);

  const canStartDraft =
    (league.status === "Pre-Draft" || league.status === "Drafting") &&
    league.commissionerId === currentUserId;
  const canManageLeague = league.commissionerId === currentUserId;
  const canEditTeamName = league.memberId != null;
  const canLeaveLeague =
    league.status === "Pre-Draft" && league.commissionerId !== currentUserId;
  const showAdminActions = canManageLeague;
  const canJoinDraft =
    (league.status === "Pre-Draft" || league.status === "Drafting") &&
    league.commissionerId !== currentUserId;
  const rosterActionsLocked = tradeDeadlinePassed && freeAgentDeadlinePassed;

  const handleStartDraft = () => {
    if (!league) {
      return;
    }

    setStartDraftError(null);
    openDraftPage(true);
  };

  const handleJoinDraft = () => {
    if (!league) {
      return;
    }

    setStartDraftError(null);
    openDraftPage(true);
  };

  const scoreboardRows = useMemo<{
    weekNumbers: number[];
    rows: LeagueScoreboardRow[];
  }>(() => {
    const weekNumbersFromScores = Object.keys(scoreboard)
      .map((key) => Number(key))
      .sort((a, b) => a - b);
    const fallbackWeekNumber = league.currentWeekNumber ?? 1;
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
          totalPoints: 0,
        };
        row.weeklyPoints[week] = score.pointsAwarded;
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
  }, [scoreboard, members, league.currentWeekNumber]);

  return (
    <div className="league-detail">
      <button
        className="league-detail__back"
        type="button"
        onClick={() => navigate(-1)}
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
                <span className="value">{league.seasonPoints ?? 0}</span>
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
              <button
                className="league-detail__add-drop-btn"
                type="button"
                onClick={openRosterManagement}
                disabled={rosterActionsLocked}
              >
                Manage Roster
              </button>
              <button
                className="league-detail__conference-btn"
                type="button"
                onClick={openConferencePage}
              >
                View Conference Scores
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
                  Join Draft Lobby
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
      {userError && (
        <p className="league-detail__error-text">{userError}</p>
      )}
      {members.length > 0 && (
        <LeagueScheduleTabs
          leagueId={league.leagueId}
          members={members}
          currentMemberId={league.memberId}
          initialWeekNumber={league.currentWeekNumber ?? 1}
        />
      )}

      <LeagueScoreboard
        weekNumbers={scoreboardRows.weekNumbers}
        rows={scoreboardRows.rows}
        currentWeekNumber={league.currentWeekNumber ?? null}
        loading={scoreboardLoading}
        error={scoreboardError}
      />

    </div>
  );
};

export default LeagueDetailPage;
