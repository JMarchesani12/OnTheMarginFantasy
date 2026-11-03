import assert from 'node:assert/strict';
import test from 'node:test';
import { createAuthenticatedFetch } from '../src/api/authenticatedFetch.ts';
const base = 'https://api.example.test';
const url = `${base}/api/change`;
const denied = () => Response.json({ error: { code: 'auth_token_invalid' } }, { status: 401 });
function setup(transport: typeof fetch, overrides = {}) {
  return createAuthenticatedFetch({ apiBaseUrl: base, getAccessToken: async () => 'old', refreshAccessToken: async () => 'new', canReplay: async () => true, fetch: transport, ...overrides });
}
function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>(r => { resolve = r; });
  return { promise, resolve };
}
test('foreign URLs, sibling paths and traversal cannot receive credentials', async () => {
  let calls = 0;
  const api = setup(async () => { calls++; return Response.json({}); });
  for (const target of ['https://evil.test/api/x', `${base}/apiary/x`, `${base}/api/../admin`, `${base}/api/%2e%2e/admin`, `${base}/api/%2f..%2fadmin`]) await assert.rejects(api(target), /outside|scope/i);
  await assert.rejects(api('https://evil.test/x', { skipAuth: true, headers: { Authorization: 'Bearer secret' } }), /outside|scope/i);
  assert.equal(calls, 0);
});
test('explicit bootstrap token skips SDK lookup and refresh and refuses redirects', async () => {
  const api = setup(async (input, init) => {
    const req = new Request(input, init);
    assert.equal(req.headers.get('Authorization'), 'Bearer supplied');
    assert.equal(req.redirect, 'error');
    return denied();
  }, { getAccessToken: async () => { throw Error('SDK reentered'); }, refreshAccessToken: async () => { throw Error('SDK refreshed'); } });
  assert.equal((await api(url, { headers: { Authorization: 'Bearer supplied' } })).status, 401);
});
test('Request inputs preserve method headers and body without replaying a body', async () => {
  let calls = 0;
  const api = setup(async (input, init) => {
    calls++;
    const req = new Request(input, init);
    assert.equal(req.method, 'POST');
    assert.equal(req.headers.get('X-Custom'), 'yes');
    assert.equal(await req.text(), '{"id":1}');
    return denied();
  });
  assert.equal((await api(new Request(url, { method: 'POST', headers: { 'X-Custom': 'yes' }, body: '{"id":1}' }))).status, 401);
  assert.equal(calls, 1);
});
test('string mutation retries once after authentication denial and response remains readable', async () => {
  const seen: string[] = [];
  const api = setup(async (input, init) => {
    const req = new Request(input, init);
    seen.push(req.headers.get('Authorization')!);
    assert.equal(await req.text(), '{"id":1}');
    return seen.length === 1 ? denied() : Response.json({ saved: true });
  });
  assert.deepEqual(await (await api(url, { method: 'POST', body: '{"id":1}' })).json(), { saved: true });
  assert.deepEqual(seen, ['Bearer old', 'Bearer new']);
});
test('concurrent and late stale responses reuse one refresh', async () => {
  let refreshes = 0;
  const late = deferred<Response>();
  const calls: string[] = [];
  const api = setup(async (input, init) => {
    const req = new Request(input, init);
    calls.push(req.headers.get('Authorization')!);
    if (req.headers.get('Authorization') === 'Bearer old') return req.url.endsWith('late') ? late.promise : denied();
    return Response.json({ ok: true });
  }, { refreshAccessToken: async () => { refreshes++; await new Promise(r => setTimeout(r, 5)); return 'new'; } });
  const slow = api(`${base}/api/late`);
  await Promise.all([api(url), api(url)]);
  late.resolve(denied());
  await slow;
  assert.equal(refreshes, 1);
  assert.equal(calls.filter(t => t === 'Bearer new').length, 3);
});
test('permission legacy text and operational failures never refresh or replay', async () => {
  for (const [status, body] of [[403, { error: { code: 'auth_token_invalid' } }], [401, { error: 'invalid session' }], [500, {}], [400, {}], [401, { error: { code: 'auth_token_missing' } }]] as const) {
    let calls = 0;
    const api = setup(async () => { calls++; return Response.json(body, { status }); }, { refreshAccessToken: async () => { throw Error('Unexpected refresh'); } });
    assert.equal((await api(url)).status, status);
    assert.equal(calls, 1);
  }
  let calls = 0;
  const api = setup(async () => { calls++; throw new TypeError('network failed'); });
  await assert.rejects(api(url, { method: 'POST', body: '{}' }), /network failed/);
  assert.equal(calls, 1);
});
test('repeated invalid token disabled retries and failed refresh stop at their budget', async () => {
  for (const [options, token, want] of [[{}, 'new', 2], [{ retryOnAuthError: false }, 'new', 1], [{}, null, 1]] as const) {
    let calls = 0;
    const api = setup(async () => { calls++; return denied(); }, { refreshAccessToken: async () => token });
    assert.equal((await api(url, options)).status, 401);
    assert.equal(calls, want);
  }
});
test('skipAuth makes no SDK calls', async () => {
  const api = setup(async (input, init) => {
    assert.equal(new Request(input, init).headers.has('Authorization'), false);
    return denied();
  }, { getAccessToken: async () => { throw Error('session'); }, refreshAccessToken: async () => { throw Error('refresh'); } });
  assert.equal((await api(url, { skipAuth: true })).status, 401);
});
test('abort during shared refresh cancels only that request and prevents its replay', async () => {
  const refresh = deferred<string>();
  const started = deferred<void>();
  let calls = 0;
  const api = setup(async () => { calls++; return calls <= 2 ? denied() : Response.json({}); }, { refreshAccessToken: async () => { started.resolve(); return refresh.promise; } });
  const controller = new AbortController();
  const first = api(url, { signal: controller.signal });
  await started.promise;
  const other = api(url);
  controller.abort();
  await assert.rejects(first, { name: 'AbortError' });
  refresh.resolve('new');
  assert.equal((await other).status, 200);
  assert.equal(calls, 3);
});
test('total timeout covers token lookup and cannot dispatch later', async () => {
  const token = deferred<string>();
  let calls = 0;
  const api = setup(async () => { calls++; return Response.json({}); }, { getAccessToken: () => token.promise });
  const keepAlive = setTimeout(() => token.resolve('eventually'), 100);
  try {
    await assert.rejects(api(url, { timeoutMs: 10 }), { name: 'TimeoutError' });
  } finally { clearTimeout(keepAlive); }
  token.resolve('late');
  await new Promise(r => setTimeout(r, 5));
  assert.equal(calls, 0);
});
test('Request cancellation is honored before SDK lookup or dispatch', async () => {
  const controller = new AbortController(); controller.abort();
  const api = setup(async () => { throw Error('dispatched'); }, { getAccessToken: async () => { throw Error('looked up'); } });
  await assert.rejects(api(new Request(url, { signal: controller.signal })), { name: 'AbortError' });
});

test('different rejected tokens cannot share refreshed credentials across sessions', async () => {
  const a = deferred<string>();
  const started = deferred<void>();
  let sessionToken = 'account-a-old';
  let refreshes = 0;
  const api = setup(async (input, init) => {
    const req = new Request(input, init);
    const token = req.headers.get('Authorization');
    if (token?.endsWith('-old')) return denied();
    return Response.json({ token });
  }, {
    getAccessToken: async () => sessionToken,
    refreshAccessToken: async () => {
      refreshes++;
      if (refreshes === 1) { started.resolve(); return a.promise; }
      return 'account-b-new';
    },
  });
  const first = api(url);
  await started.promise;
  sessionToken = 'account-b-old';
  const second = api(url);
  await new Promise(r => setTimeout(r, 5));
  a.resolve('account-a-new');
  const responses = await Promise.all([first, second]);
  assert.equal((await responses[1].json()).token, 'Bearer account-b-new');
});

test('caller cancellation still aborts body consumption after response headers', async () => {
  const controller = new AbortController();
  const api = setup(async (input, init) => {
    const req = new Request(input, init);
    return new Response(new ReadableStream({ start(stream) {
      req.signal.addEventListener('abort', () => stream.error(req.signal.reason), { once: true });
    } }));
  });
  const response = await api(url, { signal: controller.signal });
  const body = response.text();
  controller.abort();
  await Promise.race([assert.rejects(body, { name: 'AbortError' }), new Promise((_, reject) => setTimeout(() => reject(Error('Body ignored cancellation')), 30))]);
});
