# MOD-027C: ineligible team-search loading reset

User authorized design and implementation together, opting out of a separate design approval. In TeamLookupPage, reset loading alongside results/error when leagueId is absent or trimmed query has fewer than two characters. Preserve debounce, cancelled-response/finally guards, ranking, APIs and league-context resolution. Alternatives (new search hook, request framework or context rewrite) exceed this one-line correction.

Verify actual component using controlled timers/transport: held eligible search then empty/one-character/whitespace query, late success or rejection cannot restore loading/results/errors; subsequent eligible request renders loading and its own result. Verify cancelled debounce and unmount suppress callbacks. Run full frontend tests/build/import/diff. Existing broader context/navigation behavior remains separate; no live service or browser-runtime proof, no commit/deploy.
