import { supabase } from "../lib/supabaseClient";

export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:5050";

async function getAuthHeader() {
  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;

  return token ? { Authorization: `Bearer ${token}` } : {};
}

type ApiFetchOptions = RequestInit & {
  skipAuth?: boolean;
};

export async function apiFetch(
  input: RequestInfo | URL,
  init: ApiFetchOptions = {}
) {
  const headers = new Headers(init.headers ?? {});

  if (!init.skipAuth) {
    const authHeader = await getAuthHeader();
    if (!headers.has("Authorization") && authHeader.Authorization) {
      headers.set("Authorization", authHeader.Authorization);
    }
  }

  return fetch(input, { ...init, headers });
}
