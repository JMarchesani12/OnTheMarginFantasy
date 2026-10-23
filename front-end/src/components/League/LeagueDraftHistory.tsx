import { useEffect, useState } from "react";
import { getDraftState } from "../../api/draft";
import type { DraftSnapshot } from "../../types/draft";
import "./LeagueDraftHistory.css";

export default function LeagueDraftHistory({ leagueId }: { leagueId: number }) {
  const [snapshot, setSnapshot] = useState<DraftSnapshot | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const [expandedMembers, setExpandedMembers] = useState<Set<number>>(new Set());

  useEffect(() => {
    let cancelled = false;
    getDraftState(leagueId).then((data) => {
      if (!cancelled) setSnapshot(data);
    }).catch(() => {
      if (!cancelled) setError("Unable to load the draft. Please try again.");
    });
    return () => { cancelled = true; };
  }, [leagueId, attempt]);

  const picks = [...(snapshot?.picks ?? [])].sort(
    (a, b) => a.overallPickNumber - b.overallPickNumber,
  );
  const members = [...(snapshot?.members ?? [])].sort(
    (a, b) => (a.draftOrder ?? Infinity) - (b.draftOrder ?? Infinity) || a.memberId - b.memberId,
  );
  const panelId = `league-draft-history-${leagueId}`;

  return (
    <div className="league-draft-history">
        <section id={panelId} className="league-draft-history__panel" aria-label="Draft history">
          {error ? (
            <div role="alert">
              <p>{error}</p>
              <button type="button" onClick={() => {
                setError(null);
                setAttempt((value) => value + 1);
              }}>Try again</button>
            </div>
          ) : !snapshot ? (
            <p role="status">Loading draft…</p>
          ) : picks.length === 0 ? (
            <p>No draft picks have been made yet.</p>
          ) : (
            <div className="league-draft-history__grid">
              {members.map((member) => {
                const memberPicks = picks.filter((pick) => pick.memberId === member.memberId);
                const expanded = expandedMembers.has(member.memberId);
                const listId = `${panelId}-member-${member.memberId}`;
                return (
                  <article className="league-draft-history__member" key={member.memberId}>
                    <h4>{member.teamName || `Team ${member.memberId}`}</h4>
                    <p className="league-draft-history__order">Draft position: {member.draftOrder ?? "Unassigned"}</p>
                    {memberPicks.length === 0 ? <p>No picks yet.</p> : (
                      <ol id={listId} className="league-draft-history__picks">
                        {(expanded ? memberPicks : memberPicks.slice(0, 5)).map((pick, index) => (
                          <li key={pick.id}>
                            <span className="league-draft-history__number">{index + 1}</span>
                            <span>{pick.sportTeamName || `Team ${pick.sportTeamId}`} ({pick.conferenceName || "Independent"})</span>
                            <span className="league-draft-history__overall" aria-label={`Overall pick ${pick.overallPickNumber}`} title="Overall pick">#{pick.overallPickNumber}</span>
                          </li>
                        ))}
                      </ol>
                    )}
                    {memberPicks.length > 5 && (
                      <button type="button" aria-expanded={expanded} aria-controls={listId}
                        aria-label={`${expanded ? "Show less" : "Show more"} for ${member.teamName || `Team ${member.memberId}`}`}
                        onClick={() => setExpandedMembers((previous) => {
                          const next = new Set(previous);
                          if (next.has(member.memberId)) next.delete(member.memberId);
                          else next.add(member.memberId);
                          return next;
                        })}>
                        {expanded ? "Show less" : `Show more (${memberPicks.length - 5})`}
                      </button>
                    )}
                  </article>
                );
              })}
            </div>
          )}
        </section>
    </div>
  );
}
