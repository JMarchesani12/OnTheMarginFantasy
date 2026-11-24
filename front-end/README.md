# Frontend

React 19, TypeScript and Vite. CI uses Node 22.22.2.

```sh
npm ci
npm run dev
```

Configure VITE_API_BASE_URL (defaults to http://127.0.0.1:5050), VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY in a local environment file or hosting settings. Only public browser configuration belongs here; never put a database URL or service-role key in Vite variables.

Supabase manages authentication sessions. CurrentUserProvider owns application profile loading/provisioning through the backend API. API clients handle authenticated requests, safe errors and cancellation. League screens require fresh matching account/route context before mutations; draft UI consumes authenticated Socket.IO snapshots/updates.

## Checks

```sh
node --test --experimental-strip-types tests/*.test.ts
npm run build
npm run lint
```

Tests exercise API contracts, session ordering, stale-response isolation, draft lifecycle/accessibility and display helpers. Some component tests transpile real modules into a controlled hook harness; their fixtures are synthetic and use no configured service.

Basketball tier tooling is available through npm run basketball:tiers, basketball:tiers:test and basketball:tiers:typecheck. See [the tool](../scripts/basketball-tiers) and its CLI help for options.

Production is hosted on Vercel. See [operations](../docs/operations.md) for backend jobs/deployment and [follow-ups](../docs/follow-ups.md) for remaining acceptance.
Run with: `python3 dev.py` in api folder


Object.keys(localStorage)
JSON.parse(localStorage.getItem("sb-{thing}-auth-token") || "{}")

## Public legal pages and feedback

`/privacy`, `/terms`, and `/feedback` are public React Router routes. The shared footer links to them on every page; signup also links to both policies. Public email and copyright ownership are centralized in `src/lib/siteInfo.ts`.

The legal pages are visibly labeled drafts. Before final publication, confirm the service operator, complete hosting/provider details, actual retention/deletion practices, intended audience, and any payments/prize arrangements; obtain legal review appropriate to the service. Update the date when revising the policies.

Feedback prepares a `mailto:` draft addressed to the configured support email. Users must send it from their email app; the site does not claim delivery or persist reports. Copy message provides a clipboard/manual-copy fallback. Page context is optional and omits URL queries and fragments; account details, tokens, and logs are not automatically attached.
