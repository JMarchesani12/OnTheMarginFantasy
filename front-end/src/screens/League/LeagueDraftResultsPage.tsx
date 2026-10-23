import { Link, useParams } from "react-router-dom";
import LeagueDraftHistory from "../../components/League/LeagueDraftHistory";
import "./LeagueDetailPage.css";

export default function LeagueDraftResultsPage() {
  const { league_id } = useParams();
  const leagueId = Number(league_id);

  if (!Number.isSafeInteger(leagueId) || leagueId <= 0) {
    return <main className="league-detail"><p>Invalid league.</p><Link to="/leagues">Back to Leagues</Link></main>;
  }

  return (
    <main className="league-detail">
      <Link className="league-detail__back" to={`/leagues/${leagueId}`}>← Back to League</Link>
      <header className="league-detail__header">
        <h1 className="league-detail__title">Draft Results</h1>
      </header>
      <section className="league-detail__card" aria-label="League draft results">
        <LeagueDraftHistory key={leagueId} leagueId={leagueId} />
      </section>
    </main>
  );
}
