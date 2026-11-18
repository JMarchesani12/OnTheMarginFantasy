import { safeErrorMessage, READ_ERROR } from "../api/safeError";
import { useCallback, useEffect, useRef, useState } from "react";
import { useCurrentUser } from "../context/currentUserContext";
import { resolveLeagueContext } from "../utils/leagueContext";

type Resolved = Awaited<ReturnType<typeof resolveLeagueContext>>;

/** A ready context belongs to one route/account generation, including A→B→A. */
export function useLeagueContext(routeId: string | undefined) {
  const { userId, authUserId, authLoading, loading: profileLoading, error: profileError } = useCurrentUser();
  const [attempt, setAttempt] = useState(0);
  const retry = useCallback(() => setAttempt(value => value + 1), []);
  const parsed = routeId && /^\d+$/.test(routeId) ? Number(routeId) : NaN;
  const leagueId = Number.isSafeInteger(parsed) && parsed > 0 ? parsed : null;
  const canResolve = !!leagueId && !!userId && !!authUserId && !authLoading && !profileLoading && !profileError;
  const key = JSON.stringify([routeId, authUserId, userId, authLoading, profileLoading, profileError, attempt]);
  const scope = useRef({ key, generation: 0, mounted: true });
  if (scope.current.key !== key) {
    scope.current = { key, generation: scope.current.generation + 1, mounted: true };
  }
  const generation = scope.current.generation;
  const [result, setResult] = useState<{ generation: number; value?: Resolved; error?: string } | null>(null);
  const isCurrent = useCallback(() => scope.current.mounted && scope.current.generation === generation, [generation]);

  useEffect(() => {
    scope.current.mounted = true;
    const controller = new AbortController();
    if (canResolve) {
      void resolveLeagueContext(leagueId!, userId!, controller.signal).then(value => {
        if (!controller.signal.aborted && isCurrent()) setResult({ generation, value });
      }).catch((err: unknown) => {
        if (!controller.signal.aborted && isCurrent()) setResult({ generation, error: safeErrorMessage(err, READ_ERROR) });
      });
    }
    return () => {
      controller.abort();
      if (scope.current.generation === generation) scope.current.mounted = false;
    };
  }, [generation, canResolve, leagueId, userId, isCurrent]);

  const matching = canResolve && result?.generation === generation ? result : null;
  const error = !leagueId ? "Invalid league ID." : profileError ?? matching?.error ?? null;
  return {
    league: matching?.value?.league ?? null,
    isMember: matching?.value?.isMember ?? false,
    loading: !error && (authLoading || profileLoading || (canResolve && !matching)),
    error,
    userId,
    scopeKey: String(generation),
    isCurrent,
    retry,
    canRetry: canResolve && !!matching?.error,
  };
}
