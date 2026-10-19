import { getTierLabel } from "../../utils/teamTierGroups";
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { getLeagueRules } from "../../api/leagues";
import type { LeagueRules } from "../../types/leagueRules";
import "./LeagueRulesPage.css";

const labelFor = (key: string) => key.replace(/([a-z])([A-Z])/g, "$1 $2").replace(/_/g, " ").replace(/^./, c => c.toUpperCase());

function Settings({ value }: { value: unknown }) {
  if (value == null) return <span>Not configured</span>;
  if (typeof value === "boolean") return <span>{value ? "Enabled" : "Disabled"}</span>;
  if (typeof value !== "object") return <span>{String(value)}</span>;
  const entries = Object.entries(value);
  if (!entries.length) return <span>Not configured</span>;
  return <dl className="league-rules__settings">{entries.map(([key, item]) => (
    <div key={key}><dt>{labelFor(key)}</dt><dd>{(/Deadline$|Date$/.test(key) && typeof item === "string" && !Number.isNaN(Date.parse(item)))
      ? <time dateTime={item}>{new Date(item).toLocaleString()}</time>
      : <Settings value={item} />}</dd></div>
  ))}</dl>;
}

export default function LeagueRulesPage() {
  const { league_id } = useParams();
  const leagueId = Number(league_id);
  if (!Number.isInteger(leagueId) || leagueId <= 0) {
    return <main className="league-rules"><Link to="/leagues">Back to leagues</Link><p role="alert">Invalid league.</p></main>;
  }
  return <LeagueRulesContent key={leagueId} leagueId={leagueId} />;
}

function LeagueRulesContent({ leagueId }: { leagueId: number }) {
  const [rules, setRules] = useState<LeagueRules | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    let active = true;
    getLeagueRules(leagueId).then(data => { if (active) setRules(data); })
      .catch(err => { if (active) setError(err instanceof Error ? err.message : "Unable to load rules."); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [leagueId, retry]);

  return <main className="league-rules">
    <Link to={`/leagues/${leagueId}`}>← Back to league</Link>
    <header><h1>League Rules</h1>
      {rules && <><p>{rules.leagueName} · {rules.sportName} · {rules.seasonYear}</p>
        <small>Rules version {rules.version}</small></>}
    </header>
    {loading && <p role="status">Loading league rules…</p>}
    {error && <div role="alert"><p>{error}</p><button onClick={() => { setLoading(true); setError(null); setRules(null); setRetry(n => n + 1); }}>Try again</button></div>}
    {rules && <>
      {rules.sections.map(section => <section key={section.heading} className="league-rules__card">
        <h2>{section.heading}</h2>{section.paragraphs.map(text => <p key={text}>{text}</p>)}
      </section>)}
      <section className="league-rules__card"><h2>Scoring examples</h2>
        <ul>{rules.examples.map((example, index) => <li key={index}>{example.explanation}</li>)}</ul>
      </section>
      <section className="league-rules__card"><h2>This league’s settings</h2><Settings value={rules.settings} /></section>
      <section className="league-rules__card"><h2>Current team tiers</h2>
        <p>These are current assignments, not a historical record of earlier seasons.</p>
        {rules.tiers.length === 0 && <p>No team tiers are available yet.</p>}
        <div className="league-rules__tiers">{rules.tiers.map(group => <section key={group.tier}>
          <h3>{getTierLabel(group.tier, rules.sportId)}</h3><ul>{group.teams.map(team => <li key={team.teamId}>{team.teamName}</li>)}</ul>
        </section>)}</div>
      </section>
    </>}
  </main>;
}
