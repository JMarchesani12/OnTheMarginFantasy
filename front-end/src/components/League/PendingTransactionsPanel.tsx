import { useCallback, useEffect, useMemo, useState } from "react";
import type { LeagueMember } from "../../types/leagueMember";
import type { PendingTransaction, PendingTransactionsResponse } from "../../types/roster";
import { getPendingTradesAndAddDrop } from "../../api/transaction";
import "./TradeRequestsPanel.css";

type PendingTransactionsPanelProps = {
  leagueId: number;
  members: LeagueMember[];
  teamNameLookup: Record<number, string>;
};

const formatTypeLabel = (type: string | null | undefined) => {
  if (!type) return "Transaction";
  const normalized = type.toUpperCase();
  if (normalized === "TRADE") return "Trade";
  if (normalized === "ADD_DROP" || normalized === "ADD_DROP_REQUEST") return "Add/Drop";
  return type.replace(/_/g, " ").toLowerCase().replace(/^\w/, (c) => c.toUpperCase());
};

const PendingTransactionsPanel = ({
  leagueId,
  members,
  teamNameLookup,
}: PendingTransactionsPanelProps) => {
  const [pending, setPending] = useState<PendingTransactionsResponse>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const memberNameLookup = useMemo(() => {
    const map = new Map<number, string>();
    members.forEach((member) => {
      if (member.teamName) {
        map.set(member.id, member.teamName);
      }
    });
    return map;
  }, [members]);

  const resolveMemberName = (
    memberId: number | null,
    fallbackName?: string | null
  ) => {
    if (fallbackName) return fallbackName;
    if (!memberId) return "Unassigned";
    return memberNameLookup.get(memberId) ?? `Member #${memberId}`;
  };

  const resolveTeamName = (teamId: number) =>
    teamNameLookup[teamId] ?? `Team #${teamId}`;

  const loadPending = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await getPendingTradesAndAddDrop(leagueId);
      setPending(data ?? []);
    } catch (err: any) {
      setError(err?.message ?? "Failed to load pending transactions");
    } finally {
      setLoading(false);
    }
  }, [leagueId]);

  useEffect(() => {
    loadPending();
  }, [loadPending]);

  const sortedPending = useMemo(() => {
    return [...pending].sort((a, b) => {
      const aDate = new Date(a.createdAt).getTime();
      const bDate = new Date(b.createdAt).getTime();
      return bDate - aDate;
    });
  }, [pending]);

  const renderTeamList = (
    teamIds?: number[] | null,
    teams?: PendingTransaction["fromTeams"] | PendingTransaction["toTeams"]
  ) => {
    const resolvedTeams =
      teams && teams.length > 0
        ? teams.map((team) => ({
            id: team.id,
            name: team.displayName,
          }))
        : (teamIds ?? []).map((teamId) => ({
            id: teamId,
            name: resolveTeamName(teamId),
          }));

    if (resolvedTeams.length === 0) {
      return <p className="trade-requests__teams-sub">None</p>;
    }

    return (
      <ul className="trade-requests__team-list">
        {resolvedTeams.map((team) => (
          <li key={`pending-team-${team.id}`}>{team.name}</li>
        ))}
      </ul>
    );
  };

  const renderTransaction = (txn: PendingTransaction) => (
    <article key={txn.id} className="trade-requests__item">
      <div className="trade-requests__meta">
        <span>
          Week {txn.weekNumber ?? "?"} • {new Date(txn.createdAt).toLocaleDateString()}
        </span>
        <span>{formatTypeLabel(txn.type)} • {txn.status}</span>
      </div>
      <div className="trade-requests__teams">
        <div className="trade-requests__teams-section">
          <p className="trade-requests__teams-label">From Member</p>
          <p className="trade-requests__member-name">
            {resolveMemberName(txn.memberFromId, txn.memberFromDisplayName)}
          </p>
          <p className="trade-requests__teams-label trade-requests__teams-label--secondary">
            From Teams
          </p>
          {renderTeamList(txn.fromTeamIds, txn.fromTeams)}
        </div>
        <div className="trade-requests__teams-section">
          <p className="trade-requests__teams-label">To Member</p>
          <p className="trade-requests__member-name">
            {resolveMemberName(txn.memberToId, txn.memberToDisplayName)}
          </p>
          <p className="trade-requests__teams-label trade-requests__teams-label--secondary">
            To Teams
          </p>
          {renderTeamList(txn.toTeamIds, txn.toTeams)}
        </div>
      </div>
    </article>
  );

  return (
    <section className="trade-requests">
      <header className="trade-requests__header">
        <h3>Pending Transactions</h3>
        <button
          type="button"
          className="trade-requests__refresh"
          onClick={loadPending}
          disabled={loading}
          aria-label="Refresh pending transactions"
        >
          ↻
        </button>
      </header>

      {error && <p className="trade-requests__error">{error}</p>}
      {loading && <p className="trade-requests__loading">Syncing pending items…</p>}

      {!loading && sortedPending.length === 0 && (
        <p className="trade-requests__empty">No pending transactions.</p>
      )}

      {!loading && sortedPending.length > 0 && (
        <div className="trade-requests__list">
          {sortedPending.map(renderTransaction)}
        </div>
      )}
    </section>
  );
};

export default PendingTransactionsPanel;
