import { supabase } from "../lib/supabaseClient";

export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:5050";

async function getAuthHeader() {
  const { data } = await supabase.auth.getSession();
  console.log("token exists?", !!data.session?.access_token);
  const token = data.session?.access_token;

  return token ? { Authorization: `Bearer ${token}` } : {};
}

export async function apiFetch(
  input: RequestInfo | URL,
  init: RequestInit = {}
) {
  const authHeader = await getAuthHeader();
  const headers = new Headers(init.headers ?? {});

  if (!headers.has("Authorization") && authHeader.Authorization) {
    headers.set("Authorization", authHeader.Authorization);
  }

  return fetch(input, { ...init, headers });
}
