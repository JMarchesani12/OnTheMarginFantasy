import { useCallback, useEffect, useMemo, useState, useRef } from "react";
import { useRequestScope } from "../../hooks/useRequestScope";
import type {
  OpenTradesResponse,
  TradeStatus,
  TradeResponseAction,
} from "../../types/roster";
import {
  cancelTradeRequest,
  getOpenTradeRequests,
  responseToTradeRequest,
  vetoTrade,
} from "../../api/transaction";
import "./TradeRequestsPanel.css";

type TradeRequestsPanelProps = {
  leagueId: number;
  refreshRevision?: number;
  onMutationSuccess?: () => void;
  isCurrent: () => boolean;
  memberId: number;
  tradeDeadlinePassed: boolean;
};

type TradeTab = "incoming" | "outgoing" | "league";

const actionLabels: Record<TradeTab, string> = {
  incoming: "Incoming",
  outgoing: "Outgoing",
  league: "League",
};

const TradeRequestsPanel = ({
  leagueId,
  refreshRevision = 0,
  onMutationSuccess,
  isCurrent,
  memberId,
  tradeDeadlinePassed,
}: TradeRequestsPanelProps) => {
  const scope = useRequestScope(isCurrent);
  const [activeTab, setActiveTab] = useState<TradeTab>("incoming");
  const [trades, setTrades] = useState<OpenTradesResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [actionLoadingId, setActionLoadingId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [readyRevision, setReadyRevision] = useState<number | null>(null);
  const readiness = useRef({ revision: refreshRevision, context: isCurrent, ready: false });
  if (readiness.current.revision !== refreshRevision || readiness.current.context !== isCurrent) readiness.current = { revision: refreshRevision, context: isCurrent, ready: false };
  const actionInFlight = useRef(false);

  const loadTrades = useCallback(async () => {
    if (!scope.isCurrent()) return;
    const request = scope.capture("trades");
    const current = () => request() && isCurrent() && readiness.current.revision === refreshRevision;
    try {
      readiness.current.ready = false;
      setReadyRevision(null);
      setLoading(true);
      setError(null);
      const data = await getOpenTradeRequests(leagueId, memberId, request.signal);
      if (current()) {
        setTrades(data);
        readiness.current.ready = true;
        setReadyRevision(refreshRevision);
      }
    } catch (err: any) {
      if (current()) setError(err?.message ?? "Failed to load trade requests");
    } finally {
      if (current()) setLoading(false);
    }
  }, [leagueId, memberId, scope, isCurrent, refreshRevision]);

  useEffect(() => {
    loadTrades();
    return () => scope.cancel("trades");
  }, [loadTrades, refreshRevision, scope]);

  const tabTrades: TradeStatus[] = useMemo(() => {
    if (!trades || readyRevision !== refreshRevision || !readiness.current.ready) {
      return [];
    }

    if (activeTab === "incoming") {
      return (trades.mine?.incoming ?? []).filter(
        (trade) => trade.status !== "PENDING_APPLY"
      );
    }
    if (activeTab === "outgoing") {
      return (trades.mine?.outgoing ?? []).filter(
        (trade) => trade.status !== "PENDING_APPLY"
      );
    }

    // league tab: show other members' activity, including their pending trades
    return trades.others;
  }, [trades, activeTab, readyRevision, refreshRevision, isCurrent]);

  const handleRespond = async (
    transactionId: number,
    action: TradeResponseAction
  ) => {
    if (!scope.isCurrent() || !isCurrent() || !readiness.current.ready || actionInFlight.current) return;
    const request = scope.capture();
    const current = () => request() && isCurrent();
    actionInFlight.current = true;
    try {
      setActionLoadingId(transactionId);
      setError(null);
      await responseToTradeRequest(leagueId, transactionId, action, memberId);
      if (current()) {
        if (onMutationSuccess) onMutationSuccess();
        else await loadTrades();
      }
    } catch (err: any) {
      if (current()) setError(err?.message ?? "Failed to update trade request");
    } finally {
      actionInFlight.current = false;
      if (request()) setActionLoadingId(null);
    }
  };

  const handleCancel = async (transactionId: number) => {
    if (!scope.isCurrent() || !isCurrent() || !readiness.current.ready || actionInFlight.current) return;
    const request = scope.capture();
    const current = () => request() && isCurrent();
    actionInFlight.current = true;
    try {
      setActionLoadingId(transactionId);
      setError(null);
      await cancelTradeRequest(leagueId, transactionId, memberId);
      if (current()) {
        if (onMutationSuccess) onMutationSuccess();
        else await loadTrades();
      }
    } catch (err: any) {
      if (current()) setError(err?.message ?? "Failed to cancel trade request");
    } finally {
      actionInFlight.current = false;
      if (request()) setActionLoadingId(null);
    }
  };

  const handleVeto = async (transactionId: number) => {
    if (!scope.isCurrent() || !isCurrent() || !readiness.current.ready || actionInFlight.current) return;
    const request = scope.capture();
    const current = () => request() && isCurrent();
    actionInFlight.current = true;
    try {
      setActionLoadingId(transactionId);
      setError(null);
      await vetoTrade(leagueId, transactionId, memberId);
      if (current()) {
        if (onMutationSuccess) onMutationSuccess();
        else await loadTrades();
      }
    } catch (err: any) {
      if (current()) setError(err?.message ?? "Failed to update veto");
    } finally {
      actionInFlight.current = false;
      if (request()) setActionLoadingId(null);
    }
  };

  const renderActions = (trade: TradeStatus) => {
    const disabled =
      actionLoadingId !== null || loading || readyRevision !== refreshRevision || tradeDeadlinePassed;

    if (activeTab === "incoming") {
      return (
        <>
          <button
            type="button"
            className="trade-requests__btn trade-requests__btn--primary"
            onClick={() => handleRespond(trade.transactionId, "ACCEPT")}
            disabled={disabled}
          >
            Accept
          </button>
          <button
            type="button"
            className="trade-requests__btn"
            onClick={() => handleRespond(trade.transactionId, "REJECT")}
            disabled={disabled}
          >
            Reject
          </button>
        </>
      );
    }

    if (activeTab === "outgoing") {
      return (
        <button
          type="button"
          className="trade-requests__btn"
          onClick={() => handleCancel(trade.transactionId)}
          disabled={disabled}
        >
          Cancel
        </button>
      );
    }

    const hasVetoed = Boolean(trade.memberHasVetoed);
    return (
      <button
        type="button"
        className="trade-requests__btn"
        onClick={() => handleVeto(trade.transactionId)}
        disabled={disabled}
      >
        {hasVetoed ? "Unveto" : "Veto"}
      </button>
    );
  };

  return (
    <section className="trade-requests">
      <header className="trade-requests__header">
        <h3>Trade Requests</h3>
        {tradeDeadlinePassed && (
          <span className="trade-requests__lock-badge">Trades Locked</span>
        )}
        <div className="trade-requests__tabs">
          {(["incoming", "outgoing", "league"] as TradeTab[]).map((tab) => (
            <button
              key={tab}
              type="button"
              className={`trade-requests__tab ${
                activeTab === tab ? "is-active" : ""
              }`}
              onClick={() => setActiveTab(tab)}
            >
              {actionLabels[tab]}
            </button>
          ))}
        </div>
        <button
          type="button"
          className="trade-requests__refresh"
          onClick={loadTrades}
          disabled={loading}
          aria-label="Refresh trade requests"
        >
          ↻
        </button>
      </header>

      {tradeDeadlinePassed && (
        <p className="trade-requests__error">
          Trade deadline passed — trade actions are disabled.
        </p>
      )}
      {error && <p role="alert" className="trade-requests__error">{error}</p>}
      {(loading || actionLoadingId !== null) && (
        <p className="trade-requests__loading">Syncing trades…</p>
      )}

      {!loading && !error && readyRevision === refreshRevision && tabTrades.length === 0 && (
        <p className="trade-requests__empty">
          No {actionLabels[activeTab].toLowerCase()} trades.
        </p>
      )}

      {!loading && tabTrades.length > 0 && (
        <div className="trade-requests__list">
          {tabTrades.map((trade) => (
            <article
              key={trade.transactionId}
              className="trade-requests__item"
            >
              <div className="trade-requests__meta">
                <span>
                  Week {trade.weekNumber} • {new Date(trade.createdAt).toLocaleDateString()}
                </span>
              </div>
              <div className="trade-requests__teams">
                <div className="trade-requests__teams-section">
                  <p className="trade-requests__teams-label">From Member</p>
                  <p className="trade-requests__member-name">
                    {trade.memberFromDisplayName}
                  </p>
                  <p className="trade-requests__member-team">
                    {trade.memberFromTeamName}
                  </p>
                  <p className="trade-requests__teams-label trade-requests__teams-label--secondary">
                    Teams Offered
                  </p>
                  <ul className="trade-requests__team-list">
                    {(trade.fromTeams ?? []).map((team) => (
                      <li key={`trade-from-${trade.transactionId}-${team.id}`}>
                        {team.displayName}
                      </li>
                    ))}
                  </ul>
                </div>
                <div className="trade-requests__teams-section">
                  <p className="trade-requests__teams-label">To Member</p>
                  <p className="trade-requests__member-name">
                    {trade.memberToDisplayName}
                  </p>
                  <p className="trade-requests__member-team">
                    {trade.memberToTeamName}
                  </p>
                  <p className="trade-requests__teams-label trade-requests__teams-label--secondary">
                    Teams Requested
                  </p>
                  <ul className="trade-requests__team-list">
                    {(trade.toTeams ?? []).map((team) => (
                      <li key={`trade-to-${trade.transactionId}-${team.id}`}>
                        {team.displayName}
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
              <div className="trade-requests__actions">{renderActions(trade)}</div>
            </article>
          ))}
        </div>
      )}
    </section>
  );
};

export default TradeRequestsPanel;
