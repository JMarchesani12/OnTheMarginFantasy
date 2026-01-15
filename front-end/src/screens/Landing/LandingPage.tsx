import { Link } from "react-router-dom";
import "./LandingPage.css";

const LandingPage = () => {
  return (
    <main className="landing">
      <header className="landing__nav">
        <div className="landing__logo">Sicko Fantasy</div>
        <div className="landing__nav-actions">
          <Link className="landing__link" to="/signin">
            Sign in
          </Link>
          <Link className="landing__cta landing__cta--small" to="/signin">
            Start a league
          </Link>
        </div>
      </header>

      <section className="landing__hero">
        <div className="landing__hero-content">
          <p className="landing__eyebrow">College fantasy · Team based · Point differential</p>
          <h1>Every possession matters. Every conference counts.</h1>
          <p className="landing__lead">
            Sicko Fantasy is a college fantasy league where you draft teams, not
            players. Wins add points, losses subtract, and the weekly point
            differential decides who climbs the standings.
          </p>
          <div className="landing__hero-actions">
            <Link className="landing__cta" to="/signin">
              Create your league
            </Link>
            <Link className="landing__ghost" to="/signin">
              Join your friends
            </Link>
          </div>
          <div className="landing__tags">
            <span>Draft a set number of teams per conference</span>
            <span>Weekly scoring</span>
            <span>Live draft room</span>
          </div>
        </div>

        <div className="landing__hero-card" aria-hidden="true">
          <div className="landing__hero-card-header">
            <div>
              <p className="landing__card-eyebrow">Week 10 snapshot</p>
              <h2>Point Differential Board</h2>
            </div>
            <span className="landing__card-pill">Live</span>
          </div>
          <div className="landing__hero-card-body">
            <div className="landing__card-row">
              <div>
                <p className="landing__card-team">Big 12 Stack</p>
                <p className="landing__card-meta">SEC · B1G · Big 12</p>
              </div>
              <span className="landing__card-score">+28</span>
            </div>
            <div className="landing__card-row">
              <div>
                <p className="landing__card-team">Mountain Madness</p>
                <p className="landing__card-meta">MWC · AAC · Sun Belt</p>
              </div>
              <span className="landing__card-score">+16</span>
            </div>
            <div className="landing__card-row landing__card-row--dim">
              <div>
                <p className="landing__card-team">Independent Chaos</p>
                <p className="landing__card-meta">ACC · Pac-12 · Independent</p>
              </div>
              <span className="landing__card-score">-4</span>
            </div>
          </div>
        </div>
      </section>

      <section className="landing__grid">
        <article>
          <h3>How it works</h3>
          <ol>
            <li>Build a league with your rules and draft order.</li>
            <li>Draft a set number of teams from every conference.</li>
            <li>Every week, point differential decides the winner.</li>
          </ol>
        </article>
        <article>
          <h3>Scoring that feels alive</h3>
          <p>
            Wins add points, losses subtract. The bigger the margin, the louder
            the swing. Watch your weekly total update as games go final.
          </p>
        </article>
        <article>
          <h3>League tools built for commissioners</h3>
          <p>
            Draft lobbies, roster management, trade deadlines, and conference
            filters keep every manager locked in all season.
          </p>
        </article>
      </section>

      <section className="landing__split">
        <div>
          <h2>Team-based college fantasy, finally.</h2>
          <p>
            Sicko Fantasy rewards conference knowledge, weekly strategy, and a
            little bit of chaos. Perfect for rival groups, alumni chats, and
            anyone who wants more than just a box score.
          </p>
          <ul>
            <li>Season-long standings with weekly performance tracking.</li>
            <li>Conference views and schedules per team.</li>
            <li>Custom league settings for points and draft format.</li>
          </ul>
        </div>
        <div className="landing__stat-card">
          <h3>Built for the grind</h3>
          <p>Trade windows lock rosters for the week.</p>
          <div className="landing__stat-row">
            <span>Live scoring</span>
            <strong>Every game</strong>
          </div>
          <div className="landing__stat-row">
            <span>Draft format</span>
            <strong>Snake or straight</strong>
          </div>
          <div className="landing__stat-row">
            <span>Roster style</span>
            <strong>Set teams per conference</strong>
          </div>
        </div>
      </section>

      <section className="landing__cta-block">
        <h2>Ready to build your league?</h2>
        <p>Launch a Sicko Fantasy league and start drafting in minutes.</p>
        <Link className="landing__cta" to="/signin">
          Get started
        </Link>
      </section>
    </main>
  );
};

export default LandingPage;
