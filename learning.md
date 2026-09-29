# Learning Log
> Chronological engineering journal. Append-only. Failures included.
> Format and rules: docs/Rules.md §5 and Appendix A.

<!-- entries below -->

## 2026-09-29 — Phase 0 engineering foundation        (Phase 0 · Full · commit <working-tree>)

### 1. What were we trying to accomplish?
Create a small, reproducible backend foundation that can be extended without
mixing HTTP, use-case, domain, and infrastructure concerns.

### 2. Requirement behind this change
Phase 0 deliverables in `Phases.md`; FR-J1/FR-J2/FR-D4; NFR-4/NFR-5/NFR-7/NFR-9;
Architecture §2, §5, §6, §21, and §22.

### 3. Before this change
The checkout contained the planning documents but no application code, test
harness, container configuration, or migration history. The documents are at
the repository root in this checkout, although the brief names `docs/` paths;
they were not moved because relocation was not part of Phase 0.

### 4. Problem we encountered
Several failures were deliberate or natural:

- The first test collection failed with `KeyError: 'INFO'` because structlog's
  filtering logger expects a numeric level, not the string used by Settings.
- `psycopg[binary]==3.2.3` had no package for verified Python 3.14.4.
- Pydantic 2.10.5's core could not build on Python 3.14 because its PyO3
  version supported only Python 3.13.
- A readiness test initially used `ConnectionError` while production catches
  Redis's typed `RedisError`; the test double did not model the real boundary.
- `Settings` list fields failed from environment CSV with `SettingsError`:
  pydantic-settings tried JSON decoding before the validator.
- The integration test initially tried to bind a local socket, which the
  sandbox rejected with `PermissionError`; it now uses a nonexistent Unix
  socket path to represent stopped Redis without opening a socket.
- Full mypy initially stalled under 1.14.1; upgrading the approved tool to
  1.20.2 made the complete check finish and exposed two handler type errors.

### 5. Root cause
Configuration and integration boundaries have contracts that are stricter than
their surface syntax: logging levels are typed values, environment complex
fields have source-specific decoding, and framework callback signatures must
match the framework's base exception type. Python version support also includes
native-extension availability, not only language syntax compatibility.

### 6. Architecture decision
Decision: use an app factory, lifespan-owned async SQLAlchemy/Redis clients, a
single validated `Settings` object, and a thin health route.

Why: dependencies become explicit and replaceable in tests; liveness remains
cheap; readiness reports each required dependency separately; no route reads
environment variables or constructs hidden global clients.

Alternatives: module-level singletons (simpler but hidden and order-dependent),
or dependency creation inside each route (duplicated and difficult to clean up).

Tradeoffs: the app factory has a little more wiring, and readiness intentionally
depends on both services being reachable. Phase 0 has no application tables, so
the baseline migration is empty apart from Alembic's version table.

### 7. System / data flow
```text
HTTP request
  -> request-id middleware
  -> FastAPI route
  -> readiness probes async SQLAlchemy + Redis adapters
  -> JSON response with per-dependency status and request id header

Environment -> Settings -> app factory -> lifespan cleanup
```

### 8. Code-level explanation
- `backend/app/config.py`: pydantic-settings boundary; live providers default
  to false; CSV parsing is explicit for documented list variables.
- `backend/app/main.py`: composition root, app factory, exception handlers,
  middleware, and lifespan cleanup.
- `backend/app/api/routes/health.py`: liveness and readiness only; no business
  logic.
- `backend/app/api/middleware.py`: request id and structlog JSON/redaction.
- `backend/app/infra/db/session.py` and `infra/cache/redis_client.py`: I/O
  adapters kept below the API/service boundary.
- `backend/migrations/`: Alembic environment plus reviewed empty baseline.
- `backend/tests/`: API, unit, and integration-style failure tests with no
  provider calls or external network.

### 9. Concepts to learn
- Layering keeps HTTP concerns from leaking into pure domain logic and makes
  later provider replacement local to infrastructure.
- Liveness answers “is the process alive?”; readiness answers “can it serve
  traffic now?” and therefore checks dependencies.
- Container service names are DNS names. Inside the API container, `localhost`
  means the API container, not the `postgres` or `redis` container.
- A lifespan is the lifecycle boundary for acquiring and closing async clients.

### 10. What can go wrong?
Redis or DB outage returns 503 readiness; malformed settings fail at startup;
request IDs can be missing or client-supplied; redaction patterns are not a
complete secret detector; Docker image tags and upstream deprecations can drift.

### 11. Security considerations
Secrets are environment-only, placeholders are used in Compose/example files,
and common secret keys/query values are redacted before JSON logging. Error
responses contain stable codes and request IDs, not stack traces or connection
details. No provider keys, payment data, or live calls exist in this phase.

### 12. Performance considerations
No performance claim is made. Liveness performs no I/O; readiness performs one
small DB query and one Redis ping sequentially. Search/cache performance belongs
to later phases and must be measured then.

### 13. Testing strategy
Tests cover liveness 200, readiness 200, readiness 503 with both dependencies
down, readiness 503 with the real Redis client against a stopped socket, default
live-provider safety, missing required settings, CSV settings, and log
redaction. CI has no provider calls and no external service dependency.

### 14. What I should have noticed myself
The first implementation should have checked the actual Python version before
pinning native dependencies, and should have tested environment parsing rather
than only direct `Settings(...)` construction. An experienced engineer also
expects framework callback typing and lifecycle behavior to differ between a
production server and an ASGI test transport.

### 15. Engineering lessons
1. Pin versions against the environment you actually run, including wheels.
2. Treat configuration parsing as an external interface and test its source format.
3. Keep health endpoints operationally boring and explicit.
4. Typed test doubles expose whether a failure contract is modeled correctly.
5. “No network in CI” does not mean “no failure-path integration test”; a real
   client pointed at a stopped local endpoint is still valuable.

### 16. Interview explanation
“I built a modular-monolith foundation with an app factory and lifecycle-managed
async DB/Redis clients. Liveness is independent of dependencies, readiness
probes both dependencies and reports a 503 with per-check status, and live
provider calls are disabled by configuration so tests cannot spend quota.”

## 2026-09-29 — Layering and request-correlation review correction        (Phase 0 · Full · commit <working-tree>)

### 1. What were we trying to accomplish?
Close two architecture gaps found by the final reviewer: keep health orchestration
out of the HTTP route and make request IDs useful in structured logs.

### 2. Requirement behind this change
Architecture §5 and Rules §8 layering; FR-J1; the Phase 0 logging and health
deliverables.

### 3. Before this change
The health route directly opened the SQLAlchemy engine and called Redis. The
request-id middleware added a response header but did not bind the ID to
structlog context or emit a completion event.

### 4. Problem we encountered
Review found both gaps before completion. They were not caught by the first
tests because the endpoint behavior was correct even though the dependency
direction and observability contract were wrong.

### 5. Root cause
Behavioral tests alone do not prove dependency direction. The route had become
the convenient place to perform probes, and request ID generation had been
treated as a transport concern rather than an observability context.

### 6. Architecture decision
Introduce `ReadinessService` depending on the domain `HealthCheck` protocol;
DB and Redis adapters translate their own connection exceptions to booleans.
Bind request IDs with structlog contextvars, emit `request_completed`, and
reset the context in `finally`.

Alternatives were to suppress the review finding or add an infrastructure
dependency directly to the service. Both would preserve the wrong boundary.
The tradeoff is a few small adapter/service classes in exchange for testable,
replaceable infrastructure and correlated logs.

### 7. System / data flow
```text
API route -> ReadinessService -> HealthCheck ports
                         ^            ^
                  DB/Redis adapters  infra
```

### 8. Code-level explanation
`domain/ports.py` defines the capability; `services/health_service.py` combines
the checks; `infra/db/health.py` and `RedisClient.check()` own I/O failures;
`health.py` only maps the result to HTTP; middleware binds and resets the
request context.

### 9. Concepts to learn
Ports are capability contracts, not implementations. A reviewer should be able
to replace a DB or cache adapter without changing the route or service.

### 10. What can go wrong?
A new route can bypass the service boundary; a missing `finally` can leak
context between requests; adapter error translation can become too broad.

### 11. Security considerations
The request ID is operational metadata, not authentication. It is returned and
logged, but request bodies, secrets, and provider keys remain excluded.

### 12. Performance considerations
The added service and protocol calls are in-process and negligible relative to
the DB and Redis probes. No measurement claim is made.

### 13. Testing strategy
Existing health tests now inject `HealthCheck` ports; the stopped-Redis test
uses the real Redis client; lint and mypy verify the dependency signatures.

### 14. What I should have noticed myself
Passing endpoint tests is not enough for a layered architecture. The import
graph and composition root need an explicit review, especially for “simple”
health endpoints.

### 15. Engineering lessons
1. Test architecture, not only output.
2. Translate infrastructure failures at the adapter boundary.
3. Correlation requires both propagation and emission.

### 16. Interview explanation
“The reviewer caught that health was bypassing the service layer. I moved probes
behind a domain capability port and made adapters translate failures, then bound
the request ID into structured logging context so response and completion logs
can be joined reliably.”
