// src/components/leagues/LeagueCard.tsx
import type { League } from "../../types/league";
import "./LeagueCard.css";
import { useNavigate } from "react-router-dom";

type LeagueCardProps = {
  league: League;
};

const statusClassMap: Record<League["status"], string> = {
  "Pre-Draft": "league-card__status--pre-draft",
  "Post-Draft": "league-card__status--post-draft",
  Drafting: "league-card__status--drafting",
  Completed: "league-card__status--completed",
  "In-Season": "league-card__status--in-season",
};

const LeagueCard = ({ league }: LeagueCardProps) => {
  const navigate = useNavigate();

  const teamName = league.teamName ?? "TBD";
  const seasonPoints = league.seasonPoints ?? 0;

  const handleViewLeague = () => {
    navigate(`/leagues/${league.leagueId}`, {
      state: { league },
    });
  };

  return (
    <article className="league-card">
      <div className="league-card__header">
        <div>
          <h2>{league.leagueName}</h2>
          <p className="league-card__commissioner">
            Commissioner: {league.commissionerDisplayName}
          </p>
        </div>
        <span
          className={`league-card__status ${statusClassMap[league.status]}`}
        >
          {league.status}
        </span>
      </div>

      <div className="league-card__meta">
        <div>
          <span className="meta-label">Your Team</span>
          <span className="meta-value">{teamName}</span>
        </div>
        <div>
          <span className="meta-label">Season Points</span>
          <span className="meta-value">{seasonPoints}</span>
        </div>
      </div>

      <div className="league-card__actions">
        <span className="meta-value">{league.sport}</span>
        <button
          className="league-card__action-btn"
          type="button"
          onClick={handleViewLeague}
        >
          View League
        </button>
      </div>
    </article>
  );
};

export default LeagueCard;
