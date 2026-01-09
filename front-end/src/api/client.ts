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
  retryOnAuthError?: boolean;
};

export async function apiFetch(
  input: RequestInfo | URL,
  init: ApiFetchOptions = {}
) {
  const { skipAuth, retryOnAuthError, ...fetchInit } = init;
  const shouldRetry = retryOnAuthError !== false;
  const headers = new Headers(fetchInit.headers ?? {});

  if (!skipAuth) {
    const authHeader = await getAuthHeader();
    if (!headers.has("Authorization") && authHeader.Authorization) {
      headers.set("Authorization", authHeader.Authorization);
    }
  }

  const response = await fetch(input, { ...fetchInit, headers });

  if (shouldRetry && !skipAuth && [400, 401, 403].includes(response.status)) {
    const bodyText = await response.clone().text();
    if (bodyText.toLowerCase().includes("invalid session")) {
      const { data } = await supabase.auth.refreshSession();
      if (data?.session?.access_token) {
        const retryHeaders = new Headers(fetchInit.headers ?? {});
        retryHeaders.set("Authorization", `Bearer ${data.session.access_token}`);
        return fetch(input, { ...fetchInit, headers: retryHeaders });
      }
    }
  }

  return response;
}
