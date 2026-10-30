# Sport catalog

`SportService.list_sports()` owns the existing read transaction; `SportRepository.list_sports(conn)` owns the unchanged four-column SQL and plain-dict projection. The catalog is deliberately public (`GET /api/sports`), so this service does not require an actor or resolve an application profile. Preserve null values and unspecified ordering.

HTTP adapters call the service. `SportModel.get_sports()` remains a SQL-free compatibility facade resolving `self.db` per call, including legacy db-only construction. No configured engine, HTTP or compatibility-model imports belong in canonical service/repository files.

[Verification](../../../docs/modernization/evidence/mod-038-sport-catalog-2026-10-30.json): guarded real SQLite catalog/HTTP/failure tests; unchanged SQL AST. No new native PostgreSQL run was needed or claimed.
