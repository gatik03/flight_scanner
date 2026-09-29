# Memory — Current Project State
Last updated: 2026-09-29 · by: Codex · after: Phase 0 foundation review correction

## Where we are
- Phase: 0 — Engineering foundation · Status: in progress pending Compose demonstration and teaching check
- Current task: Foundation code, tests, containers, CI, and journals are implemented; review corrections are applied.
- Next 3 steps: 1) verify Docker Compose on a machine with Docker 2) demonstrate Redis stop → readiness 503 3) run teaching check, then begin Pre-flight/Phase 1 only after approval.

## How to run
- Install: `make install`
- Start: `make up` · Tests: `make test` · Lint: `make lint` · Type-check: `make type-check` · Migrate: `make migrate`
- URLs/ports: API :8000 · Postgres :5432 · Redis :6379
- Health: `GET /health` and `GET /health/ready`

## Environment facts (verified)
- Python 3.14.4 · FastAPI 0.115.6 · Pydantic 2.13.5 · pydantic-settings 2.15.0
- SQLAlchemy 2.0.37 · Alembic 1.14.1 · psycopg 3.2.10 · Redis 5.2.1 · structlog 24.4.0
- pytest 8.3.4 · pytest-asyncio 0.25.2 · ruff 0.9.2 · mypy 1.20.2
- Providers enabled: `fake` default; live providers disabled by default.
- No provider quota used; no API keys configured; no live calls made.
- Docker was not installed/available in this execution environment, so Compose startup was not verified here.

## Decisions
- App factory + lifespan-managed async DB/Redis clients; no hidden global I/O.
- Health route maps a `ReadinessService`; DB/Redis implement health ports and translate infrastructure failures.
- Request IDs are bound to structlog context and emitted in `request_completed` logs.
- `ALLOW_LIVE_PROVIDERS=false` is the master safety default.
- Pydantic settings parse documented CSV list variables explicitly.
- Empty Alembic baseline: no application tables are justified in Phase 0.
- Root-level planning documents were not relocated into `docs/` because that mismatch predates implementation and relocation was out of scope.

## File map
- `backend/app/main.py` — FastAPI factory, lifespan, router/handler wiring
- `backend/app/config.py` — validated Settings boundary
- `backend/app/api/middleware.py` — request IDs, JSON logging, redaction
- `backend/app/api/routes/health.py` — liveness/readiness
- `backend/app/services/health_service.py` — readiness orchestration
- `backend/app/domain/ports.py` — pure health capability protocol
- `backend/app/api/errors.py` — problem-details skeleton
- `backend/app/domain/errors.py` — exception stubs
- `backend/app/infra/db/` — async engine/session and metadata root
- `backend/app/infra/cache/redis_client.py` — Redis wrapper
- `backend/migrations/` — Alembic environment and empty baseline
- `backend/tests/` — 8 no-provider tests, including Redis-down integration-style test
- `docker-compose.yml`, `backend/Dockerfile`, `Makefile`, `.github/workflows/ci.yml` — reproducibility

## Done / not done
- ✅ settings validation and live-provider safety default
- ✅ request-id middleware, JSON logs, redaction
- ✅ health endpoints and failure tests
- ✅ async DB/Redis wiring, Alembic baseline, Compose/CI artifacts
- ✅ `make test`, `make lint`, `make type-check`
- ✅ Sol review findings fixed: service-layer health checks and request-log correlation
- 🔄 Docker Compose runtime demonstration
- ⬜ Phase 0 tag and teaching check

## Known issues / gotchas
- FastAPI/Starlette emit Python 3.14 deprecation warnings for `asyncio.iscoroutinefunction`; this is upstream and does not fail checks.
- Docker and live Compose services could not be exercised in this environment.
- Inside Compose use `postgres` and `redis`, never `localhost`, for service hosts.

## Do not touch / careful
- Do not enable live providers or add API keys during foundation work.
- Do not create application tables without the required entity/index design entry in `learning.md`.

## Open questions for the developer
- P1: which real providers survive the pre-flight spike?
- P2: which 20+ offers are computable and verified?
- P3: which deep-link hosts are allowlisted?

## Recent learning.md entries
- 2026-09-29 — Phase 0 engineering foundation
