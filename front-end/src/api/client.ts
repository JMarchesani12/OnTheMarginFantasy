import { supabase } from "../lib/supabaseClient";
import { createAuthenticatedFetch } from "./authenticatedFetch";

export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:5050";

function tokenSubject(token: string): string | null {
  // Session-continuity comparison only; the server still verifies the JWT.
  try {
    const payload = token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/');
    const { sub } = JSON.parse(atob(payload));
    return typeof sub === 'string' && sub.length > 0 ? sub : null;
  } catch {
    return null;
  }
}

export const apiFetch = createAuthenticatedFetch({
  apiBaseUrl: API_BASE_URL,
  getAccessToken: async () => {
    const { data } = await supabase.auth.getSession();
    return data.session?.access_token ?? null;
  },
  refreshAccessToken: async (rejectedToken) => {
    const subject = tokenSubject(rejectedToken);
    if (!subject) return null;
    const current = await supabase.auth.getSession();
    if (current.error || current.data.session?.user.id !== subject) return null;
    const { data, error } = await supabase.auth.refreshSession();
    return error || data.session?.user.id !== subject
      ? null : data.session.access_token;
  },
  canReplay: async (rejectedToken, refreshedToken) => {
    const subject = tokenSubject(rejectedToken);
    if (!subject || tokenSubject(refreshedToken) !== subject) return false;
    const { data, error } = await supabase.auth.getSession();
    return !error && data.session?.user.id === subject
      && data.session.access_token === refreshedToken;
  },
  fetch: (input, init) => fetch(input, init),
});
