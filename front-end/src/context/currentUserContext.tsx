import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { supabase } from "../lib/supabaseClient";
import { useAuth } from "./AuthContext";

type CurrentUserContextValue = {
  userId: number | null;
  email: string | null;
  displayName: string | null;
  loading: boolean;
  error: string | null;
  authUserId: string | null;
  authLoading: boolean;
  refreshUser: () => Promise<void>;
};

const CurrentUserContext =
  createContext<CurrentUserContextValue | undefined>(undefined);

export function CurrentUserProvider({ children }: { children: React.ReactNode }) {
  const { user, loading: authLoading } = useAuth();
  const authUserId = user?.id ?? null;
  const identity = useRef({ authUserId, authLoading, generation: 0 });
  if (identity.current.authUserId !== authUserId || identity.current.authLoading !== authLoading) {
    identity.current = { authUserId, authLoading, generation: identity.current.generation + 1 };
  }
  const generation = identity.current.generation;
  const request = useRef(0);
  const [profile, setProfile] = useState<{
    generation: number;
    userId: number | null;
    email: string | null;
    displayName: string | null;
    loading: boolean;
    error: string | null;
  } | null>(null);

  const refreshUser = useCallback(async () => {
    if (identity.current.generation !== generation) return;
    const requestId = ++request.current;
    const isCurrent = () => identity.current.generation === generation && request.current === requestId;
    const empty = { generation, userId: null, email: null, displayName: null, error: null };
    if (authLoading || !authUserId) {
      setProfile({ ...empty, loading: authLoading });
      return;
    }
    setProfile({ ...empty, loading: true });
    try {
      const { data, error } = await supabase
        .from("User")
        .select('id, email, "displayName"')
        .eq("uuid", authUserId)
        .maybeSingle();
      if (!isCurrent()) return;
      if (error) throw error;
      setProfile(data ? {
        generation, userId: data.id, email: data.email, displayName: data.displayName,
        loading: false, error: null,
      } : { ...empty, loading: false, error: "No user record found for this session." });
    } catch (err) {
      if (!isCurrent()) return;
      console.error("Failed to load internal user", err);
      setProfile({ ...empty, loading: false, error: "Failed to load user profile." });
    }
  }, [authLoading, authUserId, generation]);

  useEffect(() => {
    void refreshUser();
    return () => { request.current++; };
  }, [refreshUser]);

  const matching = !authLoading && !!authUserId && profile?.generation === generation;
  const userId = matching && !profile.loading ? profile.userId : null;
  const email = matching && !profile.loading ? profile.email : null;
  const displayName = matching && !profile.loading ? profile.displayName : null;
  const loading = authLoading || (!!authUserId && (!matching || profile.loading));
  const error = matching ? profile.error : null;

  return (
    <CurrentUserContext.Provider
      value={{
        userId,
        email,
        displayName,
        loading,
        error,
        authUserId,
        authLoading,
        refreshUser,
      }}
    >
      {children}
    </CurrentUserContext.Provider>
  );
}

export function useCurrentUser() {
  const ctx = useContext(CurrentUserContext);
  if (!ctx) {
    throw new Error("useCurrentUser must be used within CurrentUserProvider");
  }
  return ctx;
}
