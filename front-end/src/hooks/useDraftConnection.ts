import { useEffect, useRef } from "react";
import { io } from "socket.io-client";
import { createDraftRealtime, type DraftRealtime } from "../lib/draftRealtime";

type DraftConnectionOptions<T> = {
  leagueId: number | null;
  token?: string;
  socketUrl: string;
  scopeKey: string;
  memberId?: number;
  readSnapshot: (leagueId: number, signal: AbortSignal) => Promise<T>;
  applySnapshot: (snapshot: T) => void;
  clearDraftView: () => void;
  onReady: (ready: boolean) => void;
  onError: (message: string | null) => void;
  onLoading: (loading: boolean) => void;
};

/** Own the subscription; retain the actual controller identity for command guards. */
export function useDraftConnection<T>(options: DraftConnectionOptions<T>) {
  const { leagueId, token, socketUrl, scopeKey, memberId, clearDraftView } = options;
  const callbacks = useRef(options);
  callbacks.current = options;
  const controllerRef = useRef<DraftRealtime | null>(null);

  useEffect(() => {
    clearDraftView();
    if (!leagueId || !token) return;
    const socket = io(socketUrl, { auth: { token }, autoConnect: false });
    const controller = createDraftRealtime({
      socket, leagueId,
      read: signal => callbacks.current.readSnapshot(leagueId, signal),
      apply: snapshot => callbacks.current.applySnapshot(snapshot),
      clear: clearDraftView,
      ready: value => callbacks.current.onReady(value),
      error: message => callbacks.current.onError(message),
      loading: value => callbacks.current.onLoading(value),
    });
    controllerRef.current = controller;
    return () => {
      controller.dispose();
      if (controllerRef.current === controller) controllerRef.current = null;
    };
  }, [leagueId, token, socketUrl, clearDraftView, scopeKey]);

  // Metadata may arrive after the first read; refresh without replacing the socket.
  useEffect(() => { controllerRef.current?.refresh(); }, [memberId]);
  return controllerRef;
}
