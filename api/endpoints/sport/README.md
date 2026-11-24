# Sport catalog

`SportService.list_sports()` owns the existing read transaction; `SportRepository.list_sports(conn)` owns the unchanged four-column SQL and plain-dict projection. The catalog is deliberately public (`GET /api/sports`), so this service does not require an actor or resolve an application profile. Preserve null values and unspecified ordering.

HTTP adapters call the service. The former SportModel facade is retired; tests and tools use `SportService.list_sports()` directly. No configured engine, HTTP or compatibility-model imports belong in canonical service/repository files.
