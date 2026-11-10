import {
  createContext,
  useContext,
  useCallback,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import type { Session, User } from '@supabase/supabase-js';
import { supabase } from '../lib/supabaseClient';
type AuthContextValue = {
  user: User | null;
  session: Session | null;
  loading: boolean;
  sessionIdentityKey: string;
  isSessionIdentityCurrent: () => boolean;
  isSessionCredentialCurrent: () => boolean;
  signInWithEmail: (email: string) => Promise<void>;
  signOut: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const source = useRef<{ session: Session | null; subject: string | null; accessToken: string | undefined; identity: number; credential: number }>({ session: null, subject: null, accessToken: undefined, identity: 0, credential: 0 });
  const [accepted, setAccepted] = useState(source.current);
  const session = accepted.session;
  const user = session?.user ?? null;
  const lifecycle = useRef({ active: false, generation: 0 });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    let eventGeneration = 0;
    let lookup = 0;
    lifecycle.current.active = true;
    const publish = (next: Session | null) => {
      const previous = source.current;
      const subject = next?.user.id ?? null;
      const accessToken = next?.access_token;
      const identityChanged = previous.subject !== subject;
      const credentialChanged = identityChanged || previous.accessToken !== accessToken;
      const snapshot = {
        session: next,
        subject, accessToken,
        identity: previous.identity + Number(identityChanged),
        credential: previous.credential + Number(credentialChanged),
      };
      // Invalidate captured work now; React may batch several accepted transitions.
      source.current = snapshot;
      setAccepted(snapshot);
      setLoading(false);
    };
    const loadSession = async () => {
      const request = ++lookup;
      const events = eventGeneration;
      const current = () => active && request === lookup && events === eventGeneration;
      try {
        const { data, error } = await supabase.auth.getSession();
        if (!current()) return;
        if (error) throw error;
        publish(data.session ?? null);
      } catch {
        if (current()) {
          console.error("Failed to load session.");
          setLoading(false);
        }
      }
    };
    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, newSession) => {
      if (!active) return;
      eventGeneration++;
      lifecycle.current.generation++;
      publish(newSession);
    });
    void loadSession();
    const handleVisibility = () => {
      if (document.visibilityState === 'visible') void loadSession();
    };
    document.addEventListener('visibilitychange', handleVisibility);
    return () => {
      active = false;
      lifecycle.current.active = false;
      lifecycle.current.generation++;
      subscription.unsubscribe();
      document.removeEventListener('visibilitychange', handleVisibility);
    };
  }, []);

  const isSessionIdentityCurrent = useCallback(() => lifecycle.current.active &&
    source.current.identity === accepted.identity, [accepted.identity]);
  const isSessionCredentialCurrent = useCallback(() => lifecycle.current.active &&
    source.current.credential === accepted.credential, [accepted.credential]);

  const signInWithEmail = async (email: string) => {
    const generation = lifecycle.current.generation;
    setLoading(true);
    const { error } = await supabase.auth.signInWithOtp({ email });
    if (!lifecycle.current.active || lifecycle.current.generation !== generation) return;
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
      value={{ user, session, loading, signInWithEmail, signOut,
        sessionIdentityKey: String(accepted.identity), isSessionIdentityCurrent, isSessionCredentialCurrent }}
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
