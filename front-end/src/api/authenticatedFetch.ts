/** Browser transport policy, composed with the SDK in client.ts. */
export type ApiFetchOptions = RequestInit & {
  skipAuth?: boolean;
  retryOnAuthError?: boolean;
  timeoutMs?: number;
};
type Dependencies = {
  apiBaseUrl: string;
  getAccessToken: () => Promise<string | null>;
  refreshAccessToken: (rejectedToken: string) => Promise<string | null>;
  canReplay: (rejectedToken: string, refreshedToken: string) => Promise<boolean>;
  fetch: typeof fetch;
  timeoutMs?: number;
};

function abortable<T>(work: Promise<T>, signal: AbortSignal): Promise<T> {
  signal.throwIfAborted();
  return new Promise((resolve, reject) => {
    const abort = () => reject(signal.reason);
    signal.addEventListener('abort', abort, { once: true });
    work.then(resolve, reject).finally(() => signal.removeEventListener('abort', abort));
  });
}

export function createAuthenticatedFetch(deps: Dependencies) {
  const base = new URL(deps.apiBaseUrl);
  const scope = `${base.pathname.replace(/\/$/, '')}/api/`;
  // Retain refresh results only while requests with that token are in flight.
  const batches = new Map<string, { users: number; refresh?: Promise<string | null> }>();

  return async function apiFetch(input: RequestInfo | URL, init: ApiFetchOptions = {}): Promise<Response> {
    const { skipAuth = false, retryOnAuthError = true, timeoutMs = deps.timeoutMs ?? 30_000, ...options } = init;
    if (!Number.isFinite(timeoutMs) || timeoutMs <= 0) throw new RangeError('timeoutMs must be finite and positive');
    const original = input instanceof Request ? input : undefined;
    const target = new URL(original?.url ?? String(input), base);
    const headers = new Headers(options.headers ?? original?.headers);
    const explicitAuth = headers.has('Authorization');
    const encodedPath = /%(?:2f|5c|2e)/i.test(target.pathname);
    const inScope = target.origin === base.origin && target.pathname.startsWith(scope) && !encodedPath && !target.username && !target.password;
    if ((!skipAuth || explicitAuth) && !inScope) throw new TypeError('Authenticated request outside configured API scope');

    const callerSignal = options.signal !== undefined ? options.signal : original?.signal;
    // Native composition preserves cancellation while callers consume the body,
    // after this function has returned response headers.
    const deadline = AbortSignal.timeout(timeoutMs);
    const signal = callerSignal ? AbortSignal.any([callerSignal, deadline]) : deadline;
    let token: string | null = null;
    let batch: { users: number; refresh?: Promise<string | null> } | undefined;
    try {
      signal.throwIfAborted();
      if (!skipAuth && !explicitAuth) {
        token = await abortable(deps.getAccessToken(), signal);
        if (token) {
          headers.set('Authorization', `Bearer ${token}`);
          batch = batches.get(token) ?? { users: 0 };
          batch.users++;
          batches.set(token, batch);
        }
      }
      const request = new Request(original ?? target, {
        ...options, headers, signal: signal,
        ...(!skipAuth || explicitAuth ? { redirect: 'error' as const } : {}),
      });
      const send = (credential?: string) => {
        signal.throwIfAborted();
        if (!credential) return abortable(deps.fetch(request), signal);
        const retryHeaders = new Headers(request.headers);
        retryHeaders.set('Authorization', `Bearer ${credential}`);
        // Bodyless Request inputs still retain method and other Request options.
        return abortable(deps.fetch(new Request(target, {
          method: request.method, credentials: request.credentials, cache: request.cache,
          mode: request.mode, referrer: request.referrer, referrerPolicy: request.referrerPolicy,
          integrity: request.integrity, keepalive: request.keepalive,
          ...options, headers: retryHeaders, signal: signal, redirect: 'error',
        })), signal);
      };
      const response = await send();
      const replayable = original ? original.body === null && options.body == null : options.body == null || typeof options.body === 'string';
      if (!token || !batch || !retryOnAuthError || !replayable || response.status !== 401) return response;
      const body = await abortable(response.clone().json().catch(() => null), signal);
      if (body?.error?.code !== 'auth_token_invalid') return response;
      if (!batch.refresh) {
        batch.refresh = Promise.resolve().then(() => deps.refreshAccessToken(token!)).catch(() => null);
      }
      const fresh = await abortable(batch.refresh, signal);
      // A late denial may reuse a completed refresh after a session switch.
      // Check continuity for every replay, not just while refreshing.
      if (!fresh || !await abortable(deps.canReplay(token, fresh), signal)) return response;
      return await send(fresh);
    } finally {
      if (token && batch && --batch.users === 0) batches.delete(token);
    }
  };
}
