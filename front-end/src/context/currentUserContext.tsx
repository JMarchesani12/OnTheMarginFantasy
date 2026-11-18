import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import type { User } from "../types/user";
import { loadApplicationProfile, ProfileSetupError } from "../lib/profileBootstrap";
import { useAuth } from "./AuthContext";

type CurrentUserContextValue = {
  userId: number | null;
  email: string | null;
  displayName: string | null;
  loading: boolean;
  error: string | null;
  authUserId: string | null;
  authLoading: boolean;
  identityKey: string;
  isCurrentIdentity: () => boolean;
  refreshUser: () => Promise<void>;
};
type ProfileState = { generation: number; value: User | null; loading: boolean; error: string | null };
type Work = { generation: number; token: string; controller: AbortController; running: boolean; isCredentialCurrent: () => boolean; promise: Promise<void> };
const CurrentUserContext = createContext<CurrentUserContextValue | undefined>(undefined);

export function CurrentUserProvider({ children }: { children: React.ReactNode }) {
  const { user, session, loading: authLoading, sessionIdentityKey, isSessionIdentityCurrent, isSessionCredentialCurrent } = useAuth();
  const authUserId = user?.id ?? null;
  const identity = useRef({ authUserId, authLoading, sessionIdentityKey, generation: 0 });
  if (identity.current.authUserId !== authUserId || identity.current.authLoading !== authLoading || identity.current.sessionIdentityKey !== sessionIdentityKey) {
    identity.current = { authUserId, authLoading, sessionIdentityKey, generation: identity.current.generation + 1 };
  }
  const generation = identity.current.generation;
  const token = session?.user.id === authUserId ? session?.access_token : undefined;
  const latest = useRef({ user, authUserId, authLoading, token, isSessionCredentialCurrent });
  latest.current = { user, authUserId, authLoading, token, isSessionCredentialCurrent };
  const mounted = useRef(true);
  const work = useRef<Work | null>(null);
  const state = useRef<ProfileState | null>(null);
  const [profile, setProfile] = useState<ProfileState | null>(null);
  const isCurrentIdentity = useCallback(() => mounted.current && identity.current.generation === generation && isSessionIdentityCurrent(), [generation, isSessionIdentityCurrent]);

  const start = useCallback((force: boolean): Promise<void> => {
    if (!isCurrentIdentity()) return Promise.reject(new Error("Profile request superseded."));
    const auth = latest.current;
    const publish = (value: User | null, loading: boolean, error: string | null) => {
      const next = { generation, value, loading, error };
      state.current = next;
      setProfile(next);
    };
    if (auth.authLoading || !auth.authUserId) {
      work.current?.controller.abort();
      publish(null, auth.authLoading, null);
      return Promise.resolve();
    }
    if (!auth.token) {
      work.current?.controller.abort();
      publish(null, false, "Session credentials are unavailable. Sign in again.");
      return Promise.reject(new Error("Session credentials are unavailable. Sign in again."));
    }
    if (!auth.isSessionCredentialCurrent()) return Promise.reject(new Error("Session credentials changed. Please retry."));
    if (!force && state.current?.generation === generation && state.current.value) return Promise.resolve();
    if (!force && work.current?.running && !work.current.controller.signal.aborted && work.current.isCredentialCurrent() && work.current.generation === generation && work.current.token === auth.token) {
      return work.current.promise;
    }
    work.current?.controller.abort();
    const operation: Work = { generation, token: auth.token, controller: new AbortController(), running: true, isCredentialCurrent: auth.isSessionCredentialCurrent, promise: Promise.resolve() };
    work.current = operation;
    const current = () => isCurrentIdentity() && work.current === operation &&
      !operation.controller.signal.aborted && operation.isCredentialCurrent() && latest.current.token === operation.token;
    publish(null, true, null);
    operation.promise = loadApplicationProfile({
      subject: auth.authUserId, accessToken: auth.token, email: auth.user?.email,
      username: auth.user?.user_metadata?.username,
      signal: operation.controller.signal, isCurrent: current,
    }).then(value => {
      if (!current()) throw new Error("Profile request superseded.");
      publish(value, false, null);
    }).catch((error: unknown) => {
      const message = error instanceof ProfileSetupError ? error.message : "Could not load your profile. Please retry.";
      if (current()) publish(null, false, message);
      throw new Error(message);
    }).finally(() => { operation.running = false; });
    return operation.promise;
  }, [generation, isCurrentIdentity]);
  const refreshUser = useCallback(() => start(true), [start]);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      work.current?.controller.abort();
    };
  }, []);
  useEffect(() => { void start(false).catch(() => {}); }, [start, token, isSessionCredentialCurrent]);

  const matching = !authLoading && !!authUserId && profile?.generation === generation;
  const value = matching && !profile.loading ? profile.value : null;
  return <CurrentUserContext.Provider value={{
    userId: value?.id ?? null,
    email: typeof value?.email === "string" ? value.email : null,
    displayName: typeof value?.displayName === "string" ? value.displayName : null,
    loading: authLoading || (!!authUserId && (!matching || profile.loading)),
    error: matching ? profile.error : null,
    authUserId, authLoading, identityKey: String(generation), isCurrentIdentity, refreshUser,
  }}>{children}</CurrentUserContext.Provider>;
}

export function useCurrentUser() {
  const ctx = useContext(CurrentUserContext);
  if (!ctx) throw new Error("useCurrentUser must be used within CurrentUserProvider");
  return ctx;
}
