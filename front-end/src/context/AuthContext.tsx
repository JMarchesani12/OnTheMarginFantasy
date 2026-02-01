import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from 'react';
import type { Session, User } from '@supabase/supabase-js';
import { supabase } from '../lib/supabaseClient';
import { createUser, getUserByUuid } from '../api/user';
import { safeLocalStorage } from '../utils/safeStorage';

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

      const userId = currentSession.user.id;
      const createdKey = `${USER_CREATED_KEY_PREFIX}${userId}`;
      const alreadyCreated = safeLocalStorage.getItem(createdKey);
      const pendingRaw = safeLocalStorage.getItem(PENDING_USER_CREATE_KEY);

      let pending: { email?: string; displayName?: string } | null = null;
      if (pendingRaw) {
        try {
          pending = JSON.parse(pendingRaw);
        } catch (error) {
          console.warn('Failed to parse pending user payload.', error);
          safeLocalStorage.removeItem(PENDING_USER_CREATE_KEY);
        }
      }

      const email = currentSession.user.email ?? pending?.email;
      if (!email) return;

      if (pending?.email && pending.email !== email) {
        safeLocalStorage.removeItem(PENDING_USER_CREATE_KEY);
      }

      if (alreadyCreated && !pendingRaw) {
        return;
      }

      try {
        const existingUser = await getUserByUuid(userId);
        if (existingUser) {
          safeLocalStorage.setItem(createdKey, 'true');
          if (pendingRaw) {
            safeLocalStorage.removeItem(PENDING_USER_CREATE_KEY);
          }
          return;
        }
      } catch (error) {
        console.warn('Failed to look up user record.', error);
      }

      const displayName =
        pending?.displayName ?? currentSession.user.user_metadata?.username;

      try {
        const resolvedDisplayName =
          displayName?.trim() || email.split("@")[0] || email;
        await createUser(userId, email, resolvedDisplayName);
        safeLocalStorage.removeItem(PENDING_USER_CREATE_KEY);
        safeLocalStorage.setItem(createdKey, 'true');
      } catch (error) {
        console.warn('User record creation failed.', error);
      }
    };

    const loadSession = async () => {
      const { data } = await supabase.auth.getSession();
      setSession(data.session ?? null);
      setUser(data.session?.user ?? null);
      setLoading(false);
      void maybeCreateUser(data.session);
    };

    // Initial session load
    void loadSession();

    // Listen for auth changes
    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, newSession) => {
      setSession(newSession);
      setUser(newSession?.user ?? null);
      setLoading(false);
      void maybeCreateUser(newSession);
    });

    const handleVisibility = () => {
      if (document.visibilityState === 'visible') {
        void loadSession();
      }
    };

    document.addEventListener('visibilitychange', handleVisibility);

    return () => {
      subscription.unsubscribe();
      document.removeEventListener('visibilitychange', handleVisibility);
    };
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
