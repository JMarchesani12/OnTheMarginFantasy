import type { FreeAgencyResponse, OpenTradesResponse, TradeResponse, TradeResponseAction, VetoResponse } from "../types/roster";

const API_BASE_URL = import.meta.env.API_BASE_URL ?? "http://127.0.0.1:5050";

type FreeAgencyPayload = {
  weekId: number;
  weekNumber: number;
  memberId: number;
  addTeamId: number | null;
  dropTeamId: number | null;
};

type TradePayload = {
    weekId: number;
    weekNumber: number;
    fromMemberId: number;
    toMemberId: number;
    fromTeamIds: number[];
    toTeamIds: number[];
}

export async function submitFreeAgencyRequest(
  leagueId: number,
  weekNumber: number,
  weekId: number,
  memberId: number,
  addTeamId: number | null,
  dropTeamId: number | null
): Promise<FreeAgencyResponse> {
  const payload: FreeAgencyPayload = {
    weekId,
    weekNumber,
    memberId,
    addTeamId,
    dropTeamId,
  };

  const res = await fetch(`${API_BASE_URL}/api/league/${leagueId}/freeAgency/addDrop`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    throw new Error(`Failed to submit add/drop request: ${res.status}`);
  }

  const data = (await res.json()) as FreeAgencyResponse;
  return data;
}

export async function tradeRequestProposal(
  leagueId: number,
  weekNumber: number,
  weekId: number,
  toMemberId: number,
  fromMemberId: number,
  toTeamIds: number[],
  fromTeamIds: number[]
): Promise<TradeResponse> {
  const payload: TradePayload = {
    weekId,
    weekNumber,
    toMemberId,
    fromMemberId,
    toTeamIds,
    fromTeamIds
  };

  const res = await fetch(`${API_BASE_URL}/api/league/${leagueId}/week/${weekId}/trade/propose`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    throw new Error(`Failed to submit add/drop request: ${res.status}`);
  }

  const data = (await res.json()) as TradeResponse;
  return data;
}

export async function cancelTradeRequest(
    leagueId: number,
    transactionId: number,
    requesterMemberId: number,
): Promise<TradeResponse> {
  const payload = {
    "requesterMemberId": requesterMemberId
  };

  const res = await fetch(`${API_BASE_URL}/api/league/${leagueId}/transaction/${transactionId}/trade/cancel`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    throw new Error(`Failed to submit add/drop request: ${res.status}`);
  }

  const data = (await res.json()) as TradeResponse;
  return data;
}

export async function responseToTradeRequest(
    leagueId: number,
    transactionId: number,
    response: TradeResponseAction,
    responderMemberId: number
): Promise<TradeResponse> {
  const payload = {
    "action": response,
    "responderMemberId": responderMemberId
  };

  const res = await fetch(`${API_BASE_URL}/api/league/${leagueId}/transaction/${transactionId}/trade/respond`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    throw new Error(`Failed to submit add/drop request: ${res.status}`);
  }

  const data = (await res.json()) as TradeResponse;
  return data;
}

export async function getOpenTradeRequests(
    leagueId: number,
    memberId: number
): Promise<OpenTradesResponse> {
  const payload = {
    "memberId": memberId,
  };

  const res = await fetch(`${API_BASE_URL}/api/league/${leagueId}/transactions/trades/open`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    throw new Error(`Failed to submit add/drop request: ${res.status}`);
  }

  const data = (await res.json()) as OpenTradesResponse;
  return data;
}

export async function vetoTrade(
    leagueId: number,
    transactionId: number,
    memberId: number
): Promise<VetoResponse> {
  const payload = {
    "memberId": memberId,
  };

  const res = await fetch(`${API_BASE_URL}/api/league/${leagueId}/transaction/${transactionId}/trade/veto`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    throw new Error(`Failed to submit add/drop request: ${res.status}`);
  }

  const data = (await res.json()) as VetoResponse;
  return data;
}