import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import { runInNewContext } from 'node:vm';
import ts from 'typescript';

// Run real modules with SDK/transport substitutes; no env file or network.
function loadModule(path: string, dependencies: Record<string, unknown>, globals: Record<string, unknown> = {}) {
  const source = readFileSync(new URL(path, import.meta.url), 'utf8')
    .replace('import.meta.env.VITE_API_BASE_URL', 'undefined');
  const output = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX },
  }).outputText;
  const exports: Record<string, (...args: unknown[]) => Promise<unknown>> = {};
  runInNewContext(output, {
    exports, Headers, Response, ...globals,
    require: (id: string) => {
      assert.ok(id in dependencies, `Unexpected dependency: ${id}`);
      return dependencies[id];
    },
    fetch: dependencies.fetch,
  });
  return exports;
}

function profileApi(status: number) {
  const calls: { url: string; init: RequestInit & { skipAuth?: boolean } }[] = [];
  const api = loadModule('../src/api/user.ts', {
    './client': {
      API_BASE_URL: 'https://api.example.test',
      apiFetch: async (url: string, init = {}) => {
        calls.push({ url, init });
        return new Response(JSON.stringify({ id: 1 }), { status });
      },
    },
  });
  return { api, calls };
}

test('UUID lookup uses authentication and the supplied bootstrap token', async () => {
  const { api, calls } = profileApi(200);
  await api.getUserByUuid('own-uuid', 'session-token');
  assert.equal(calls[0].url, 'https://api.example.test/api/user/byUuid/own-uuid');
  assert.notEqual(calls[0].init.skipAuth, true);
  assert.equal(new Headers(calls[0].init.headers).get('Authorization'), 'Bearer session-token');
});

test('only missing profile becomes null; auth and identity failures propagate', async () => {
  assert.equal(await profileApi(404).api.getUserByUuid('own-uuid', 'token'), null);
  for (const status of [401, 403, 500]) {
    await assert.rejects(profileApi(status).api.getUserByUuid('own-uuid', 'token'));
  }
});

test('creation sends display name and session token without identity fields', async () => {
  const { api, calls } = profileApi(201);
  await api.createUser('New Name', 'session-token');
  assert.equal(calls[0].init.method, 'POST');
  assert.deepEqual(JSON.parse(String(calls[0].init.body)), { displayName: 'New Name' });
  assert.equal(new Headers(calls[0].init.headers).get('Authorization'), 'Bearer session-token');
});

test('explicit bootstrap token avoids SDK session lookup inside auth callbacks', async () => {
  const seen: Headers[] = [];
  const api = loadModule('../src/api/client.ts', {
    '../lib/supabaseClient': { supabase: { auth: {
      getSession: async () => { throw new Error('Must not reenter session lookup'); },
    } } },
    fetch: async (_url: string, init: RequestInit) => {
      seen.push(new Headers(init.headers));
      return new Response('{}', { status: 200 });
    },
  });
  await api.apiFetch('https://api.example.test/api/user', {
    headers: { Authorization: 'Bearer session-token' },
  });
  assert.equal(seen[0].get('Authorization'), 'Bearer session-token');
});

test('ordinary authenticated requests still use the SDK session token', async () => {
  const api = loadModule('../src/api/client.ts', {
    '../lib/supabaseClient': { supabase: { auth: {
      getSession: async () => ({ data: { session: { access_token: 'sdk-token' } } }),
    } } },
    fetch: async (_url: string, init: RequestInit) => {
      assert.equal(new Headers(init.headers).get('Authorization'), 'Bearer sdk-token');
      return new Response('{}', { status: 200 });
    },
  });
  await api.apiFetch('https://api.example.test/api/user/1');
});


for (const outcome of ['exists', 'missing', 'denied'] as const) {
  test(`AuthProvider bootstrap ${outcome}: create only after missing lookup`, async () => {
    const calls: { operation: string; args: unknown[] }[] = [];
    const storage = new Map<string, string>();
    const session = { access_token: 'callback-token', user: {
      id: 'own-uuid', email: 'own@example.test', user_metadata: { username: 'New Name' },
    } };
    const api = loadModule('../src/context/AuthContext.tsx', {
      react: {
        createContext: () => ({ Provider: 'provider' }),
        useContext: () => undefined,
        useState: () => [null, () => {}],
        useEffect: (effect: () => void) => effect(),
      },
      'react/jsx-runtime': { jsx: () => null },
      '../lib/supabaseClient': { supabase: { auth: {
        getSession: async () => ({ data: { session } }),
        onAuthStateChange: () => ({ data: { subscription: { unsubscribe() {} } } }),
      } } },
      '../api/user': {
        getUserByUuid: async (...args: unknown[]) => {
          calls.push({ operation: 'lookup', args });
          if (outcome === 'denied') throw new Error('Identity denied');
          return outcome === 'exists' ? { id: 1 } : null;
        },
        createUser: async (...args: unknown[]) => {
          calls.push({ operation: 'create', args });
          return { id: 1 };
        },
      },
      '../utils/safeStorage': { safeLocalStorage: {
        getItem: (key: string) => storage.get(key) ?? null,
        setItem: (key: string, value: string) => storage.set(key, value),
        removeItem: (key: string) => storage.delete(key),
      } },
    }, {
      document: { addEventListener() {}, removeEventListener() {} },
      console: { warn() {} },
    });
    await api.AuthProvider({ children: null });
    await new Promise<void>((resolve) => setImmediate(resolve));
    assert.deepEqual(calls[0], { operation: 'lookup', args: ['own-uuid', 'callback-token'] });
    if (outcome === 'missing') {
      assert.deepEqual(calls[1], { operation: 'create', args: ['New Name', 'callback-token'] });
    }
    assert.equal(calls.length, outcome === 'missing' ? 2 : 1);
    assert.equal(storage.has('otm:user-created:own-uuid'), outcome !== 'denied');
  });
}
