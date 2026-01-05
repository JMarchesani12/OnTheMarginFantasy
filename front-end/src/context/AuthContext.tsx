import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from 'react';
import type { Session, User } from '@supabase/supabase-js';
import { supabase } from '../lib/supabaseClient';
import { createUser } from '../api/user';

const PENDING_USER_CREATE_KEY = 'otm:pending-user-create';
const USER_CREATED_KEY_PREFIX = 'otm:user-created:';

type AuthContextValue = {
  user: User | null;
  session: Session | null;
  loading: boolean;
  signInWithEmail: (email: string) => Promise<void>;
  signOut: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const maybeCreateUser = async (currentSession: Session | null) => {
      if (!currentSession?.user) return;

      const createdKey = `${USER_CREATED_KEY_PREFIX}${currentSession.user.id}`;
      const alreadyCreated = localStorage.getItem(createdKey);
      const pendingRaw = localStorage.getItem(PENDING_USER_CREATE_KEY);

      let pending: { email?: string; displayName?: string } | null = null;
      if (pendingRaw) {
        try {
          pending = JSON.parse(pendingRaw);
        } catch (error) {
          console.warn('Failed to parse pending user payload.', error);
          localStorage.removeItem(PENDING_USER_CREATE_KEY);
        }
      }

      const displayName =
        pending?.displayName ?? currentSession.user.user_metadata?.username;
      const email = pending?.email ?? currentSession.user.email;

      if (
        pending?.email &&
        currentSession.user.email &&
        pending.email !== currentSession.user.email
      ) {
        return;
      }

      if (!email) return;
      if (!pendingRaw && alreadyCreated) return;

      try {
        const resolvedDisplayName =
          displayName?.trim() || email.split("@")[0] || email;
        await createUser(currentSession.user.id, email, resolvedDisplayName);
        localStorage.removeItem(PENDING_USER_CREATE_KEY);
        localStorage.setItem(createdKey, 'true');
      } catch (error) {
        if (String((error as Error)?.message ?? '').includes('409')) {
          localStorage.removeItem(PENDING_USER_CREATE_KEY);
          localStorage.setItem(createdKey, 'true');
          return;
        }
        console.warn('User record creation failed.', error);
      }
    };

    // Initial session load
    supabase.auth.getSession().then(({ data }) => {
      setSession(data.session ?? null);
      setUser(data.session?.user ?? null);
      setLoading(false);
      void maybeCreateUser(data.session);
    });

    // Listen for auth changes
    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, newSession) => {
      setSession(newSession);
      setUser(newSession?.user ?? null);
      setLoading(false);
      void maybeCreateUser(newSession);
    });

    return () => subscription.unsubscribe();
  }, []);

  const signInWithEmail = async (email: string) => {
    setLoading(true);
    const { error } = await supabase.auth.signInWithOtp({ email });
    setLoading(false);
    if (error) {
      console.error(error);
      alert(error.message);
    } else {
      alert('Magic link sent! Check your email.');
    }
  };

  const signOut = async () => {
    await supabase.auth.signOut();
  };

  return (
    <AuthContext.Provider
      value={{ user, session, loading, signInWithEmail, signOut }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
