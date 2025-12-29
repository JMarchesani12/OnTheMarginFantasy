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

  const openDraftPage = () => {
    if (!league) return;
    navigate(`/leagues/${league.leagueId}/draft`, { state: { league } });
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

  const canStartDraft =
    league.status === "Pre-Draft" && league.commissionerId === currentUserId;
  const canManageLeague = league.commissionerId === currentUserId;
  const canEditTeamName = league.memberId != null;
  const canLeaveLeague =
    league.status === "Pre-Draft" && league.commissionerId !== currentUserId;

  const scoreboardRows = useMemo<{
    weekNumbers: number[];
    rows: LeagueScoreboardRow[];
  }>(() => {
    const weekNumbers = Object.keys(scoreboard)
      .map((key) => Number(key))
      .sort((a, b) => a - b);

    const membersById = new Map<number, LeagueMember>();
    members.forEach((member) => {
      membersById.set(member.id, member);
    });

    const rows = new Map<number, LeagueScoreboardRow>();

    weekNumbers.forEach((week) => {
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

    return {
      weekNumbers,
      rows: Array.from(rows.values()).sort((a, b) => b.totalPoints - a.totalPoints),
    };
  }, [scoreboard, members]);

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

      <section className="league-detail__content">
        <div className="league-detail__card">
          <h2>Your Team</h2>
          <p>
            <span className="label">Team Name: </span>
            <span className="value">{teamNameValue || "TBD"}</span>
          </p>
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
          ) : canEditTeamName ? (
            <button
              className="league-detail__team-edit"
              type="button"
              onClick={() => {
                setTeamNameInput(teamNameValue);
                setEditingTeamName(true);
              }}
            >
              Edit Team Name
            </button>
          ) : null}
          <p>
            <span className="label">Season Points: </span>
            <span className="value">{league.seasonPoints ?? 0}</span>
          </p>
          {league.draftOrder != null && (
            <p>
              <span className="label">Draft Order: </span>
              <span className="value">#{league.draftOrder}</span>
            </p>
          )}
          <div className="league-detail__add-drop">
            <button
              className="league-detail__add-drop-btn"
              type="button"
              onClick={openRosterManagement}
              disabled={tradeDeadlinePassed}
            >
              Manage Roster
            </button>
            {tradeDeadlinePassed && (
              <p className="league-detail__add-drop-note">
                Trade deadline passed on {formatLeagueDate(league.tradeDeadline)}
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
      </section>

      <section className="league-detail__actions">
        <div className="league-detail__card">
          <h2>League Actions</h2>
          <div className="league-detail__action-buttons">
            {canStartDraft && (
              <button
                className="league-detail__start-draft-btn"
                type="button"
                onClick={openDraftPage}
              >
                Start Draft
              </button>
            )}
            {canManageLeague && (
              <button
                className="league-detail__manage-btn"
                type="button"
                onClick={openManageLeague}
              >
                Manage League
              </button>
            )}
            <button
              className="league-detail__conference-btn"
              type="button"
              onClick={openConferencePage}
            >
              View Conference Scores
            </button>
          </div>
        </div>
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
