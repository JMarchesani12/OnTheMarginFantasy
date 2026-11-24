# On The Margin Fantasy

College-sports fantasy leagues with a React/TypeScript frontend, Flask API, Supabase Auth and PostgreSQL.

| Directory | Purpose |
| --- | --- |
| [front-end](front-end/README.md) | Web application and frontend tests |
| [api](api/README.md) | API, scoring, drafts, scheduled jobs and backend tests |
| [db](db/README.md) | Schema reference, migrations, snapshots and applied-change records |
| [scripts/database](scripts/database/README.md) | Read-only database snapshot tooling |
| [scripts/team-search](scripts/team-search/README.md) | Alias seed maintenance and canonical school-name migration tools |
| [scripts/basketball-tiers](scripts/basketball-tiers) | Basketball tier analysis CLI |

## Development

Start the API using the [backend setup](api/README.md), then run `npm ci` and `npm run dev` from `front-end`. Keep credentials in local environment files or hosting settings; never commit them.

## Checks

From the repository root:

```sh
python3 api/tests/run_isolated.py
python3 -m unittest discover -s scripts/database/tests
```

From `front-end`:

```sh
node --test --experimental-strip-types tests/*.test.ts
npm run build
```

CI uses Python 3.14 and Node 22.22.2. The backend runner prevents configured database/network access. Optional native integration tests are documented in [api/tests/integration](api/tests/integration/README.md).

See [operations](docs/operations.md) for deployment, jobs and recovery, and [follow-ups](docs/follow-ups.md) for outstanding operating decisions.

Public Privacy Policy and Terms of Service drafts are implemented in [the frontend](front-end/src/screens/Legal/LegalPage.tsx). Earlier drafting references and the publication checklist are in [legal](legal/README.md). They require completion and review before final publication.

Keep maintained behavior and operating instructions in the documentation linked above. Completed agent plans/specs and one-off audit output belong in Git history rather than the working tree; preserve database migration files and execution receipts for traceability.
