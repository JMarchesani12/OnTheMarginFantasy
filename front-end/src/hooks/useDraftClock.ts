import { useCallback, useEffect, useMemo, useState } from "react";

/** Existing draft clock policy, independent of snapshot/network ownership. */
export function useDraftClock(isLive: boolean, expiresAt: string | null) {
  const [nowMs, setNowMs] = useState(() => Date.now());
  const [clockOffsetMs, setClockOffsetMs] = useState(0);
  const updateServerNow = useCallback((serverNow?: string) => {
    if (serverNow) {
      const serverMs = Date.parse(serverNow);
      if (!Number.isNaN(serverMs)) {
        setClockOffsetMs(serverMs - Date.now());
      }
    }
  }, []);

  const remainingSeconds = useMemo(() => {
    if (!expiresAt) {
      return null;
    }

    const target = Date.parse(expiresAt);
    if (Number.isNaN(target)) {
      return null;
    }

    const nowWithOffset = nowMs + clockOffsetMs;
    return Math.max(0, Math.floor((target - nowWithOffset) / 1000));
  }, [clockOffsetMs, nowMs, expiresAt]);
  const timeLeftLabel = useMemo(() => {
    if (remainingSeconds == null) {
      return null;
    }
    const minutes = Math.floor(remainingSeconds / 60);
    const seconds = remainingSeconds % 60;
    return `${minutes}:${String(seconds).padStart(2, "0")}`;
  }, [remainingSeconds]);

  useEffect(() => {
    if (!isLive) {
      return;
    }

    const interval = window.setInterval(() => {
      setNowMs(Date.now());
    }, 1000);

    return () => window.clearInterval(interval);
  }, [isLive]);

  return { remainingSeconds, timeLeftLabel, updateServerNow };
}
