import { createContext, useCallback, useContext, useEffect, useState } from "react";
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
  const [userId, setUserId] = useState<number | null>(null);
  const [email, setEmail] = useState<string | null>(null);
  const [displayName, setDisplayName] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const authUserId = user?.id ?? null;

  const refreshUser = useCallback(async () => {
    if (authLoading) return;

    if (!authUserId) {
      setUserId(null);
      setEmail(null);
      setDisplayName(null);
      setError(null);
      setLoading(false);
      return;
    }

    setLoading(true);

    try {
      const { data, error } = await supabase
        .from("User")
        .select('id, email, "displayName"')
        .eq("uuid", authUserId)
        .maybeSingle();

      if (error) {
        throw error;
      }

      if (data) {
        setUserId(data.id);
        setEmail(data.email);
        setDisplayName(data.displayName);
        setError(null);
      } else {
        setUserId(null);
        setEmail(null);
        setDisplayName(null);
        setError("No user record found for this session.");
      }
    } catch (err) {
      console.error("Failed to load internal user", err);
      setError("Failed to load user profile.");
    } finally {
      setLoading(false);
    }
  }, [authLoading, authUserId]);

  useEffect(() => {
    refreshUser();
  }, [refreshUser]);

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
