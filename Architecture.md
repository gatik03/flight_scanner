# Architecture — Flight Deal Aggregator & Offer-Matcher

| | |
|---|---|
| **Version** | 1.0 · 2026-09-29 |
| **Style** | Modular monolith (FastAPI + workers), ports-and-adapters-lite |
| **Read with** | `PRD.md` (what), `Rules.md` (how the AI must behave), `Phases.md` (when) |

This document is the **source of truth for structure and design decisions**. If code and this file disagree, either the code is wrong or this file must be updated in the same change (and a `learning.md` entry written explaining why).

---

## 1. Deliberate deviations from the original brief

These are conscious corrections, not accidents. Each one is a good interview story.

| # | Original brief / first draft said | This architecture says | Why |
|---|---|---|---|
| 1 | Amadeus Self-Service is the primary source. | **Provider-agnostic.** Real providers chosen in Pre-flight spike; a Fake provider always exists. | Amadeus Self-Service was decommissioned 2026-07-17. |
| 2 | Data flow: fetch → offer engine → ranking → **write to cache**. | Cache **only provider fares**. Apply offers and rank **at read time**, after the cache. | Offers depend on *who is asking* (their cards) and on *today's date*. Caching personalized output serves user A's discount to user B and freezes expired offers. |
| 3 | One cache key per search. | Cache **per provider**: `fare:v1:{provider}:…`. | Partial failure becomes natural (each slice has its own TTL/status), quota is per provider, and adding/removing a provider invalidates nothing. |
| 4 | `search_cache` table in Postgres. | Redis only; no such table. | Avoids dual-write and consistency problems; price *history* (durable, queryable) stays in Postgres. |
| 5 | `merchant` on offers implicitly = the data provider. | **Data source ≠ booking channel.** Offers match on the *booking channel*; default assumption `airline_direct`. | A fare found via provider X may be bought on the airline's site or an OTA. Card offers apply to where you pay. |
| 6 | "Many flight APIs return a deep link directly." | Deep links are resolved **lazily at handoff**, validated against an allowlist. | At least one candidate provider needs a *second (billable)* call to get booking URLs. Resolving for every result would burn quota. |
| 7 | `base_price`. | `list_price` (all-in total, all passengers). | Providers use "base" to mean *excluding taxes*. Ambiguous names cause money bugs. |
| 8 | `Offer` (bank promo) and `FlightOffer` (fare). | `CardOffer` and `FlightOffer`. | Two things called "offer" in one codebase guarantees confusion. |
| 9 | Rate limiting = requests/second. | Rate limiting **and a quota guard** (total budget). | Free tiers can be a few hundred *lifetime* calls. Quota, not RPS, is the binding constraint. |
| 10 | Cache key: origin+dest+date(+pax). | Also cabin and currency, with a `v1` prefix. | Every parameter that changes the result must be in the key; the prefix allows safe schema changes. |

---

## 2. Principles

1. **Modular monolith first.** One deployable API, one worker image. No microservices, Kubernetes, Kafka, event sourcing, or CQRS unless a concrete requirement forces it.
2. **External services are unreliable dependencies, not trusted components.** Timeouts, partial failure, and malformed data are normal control flow.
3. **Domain logic is pure.** Money, offers, ranking, normalization helpers have no I/O and are trivially testable.
4. **Data, not branches.** Offers are rows; booking channels are config; providers are adapters.
5. **Quota is the scarcest resource.** Cache-first, live-off-by-default, fixtures for tests.
6. **Never lie about external data.** Age is always visible; assumptions are always stated.
7. **Earn every abstraction.** Extract an interface only after two concrete implementations exist.

---

## 3. Technology stack

*(Exact versions are pinned in Phase 0 and recorded in `Memory.md`. Choose current stable releases at that time.)*

| Concern | Choice | Why | Rejected alternative (and why) |
|---|---|---|---|
| Language | **Python 3.12+** | Strong async + typing story; matches learning goals. | Node/Express — fine, but Python chosen for FastAPI/Pydantic learning. |
| API | **FastAPI** + Uvicorn | Async, OpenAPI for free, Pydantic validation, dependency injection. | Flask (sync-first), Django (heavier than needed). |
| Validation/DTOs | **Pydantic v2** (+ `pydantic-settings`) | Boundary validation, config, serialization. | dataclasses only (no validation). |
| ORM | **SQLAlchemy 2.x** (async) + **Alembic** | Mature; explicit; migrations. | SQLModel (thin wrapper hides concepts we want to learn). |
| DB driver | **psycopg 3** (sync *and* async) | One driver for API (async) and Celery workers (sync). | asyncpg + psycopg2 (two drivers, two behaviors). |
| Database | **PostgreSQL 16+** | Constraints, `NUMERIC`, `timestamptz`, partial indexes. | SQLite (weak concurrency/constraints for the worker). |
| Cache / limiter / broker | **Redis 7+** (`redis-py` asyncio) | TTLs, atomic ops, Lua, locks; Celery broker. | Memcached (no atomic scripts/structures). |
| Background jobs | **Celery** + Celery Beat | Required by brief; teaches retries/idempotency. | ARQ/RQ (simpler, but Celery is the interview-standard). |
| HTTP client | **httpx** (`AsyncClient`) | Async, timeouts, transport mocking. | `requests` (blocking — forbidden in async paths). |
| Logging | **structlog** (JSON) | Structured, context-bound logs. | print/`logging` strings. |
| Metrics | **prometheus-client** | Standard exposition format. | Vendor APM (out of scope). |
| Auth | **PyJWT** + **Argon2** hashing (`argon2-cffi`/`pwdlib`) | Simple stateless tokens; modern password hashing. | Sessions (extra state), bcrypt (acceptable, Argon2 preferred). |
| Reference data | `airportsdata` (or equivalent) | IATA → IANA timezone, country. | Hand-rolled table (error-prone). |
| Seed/config data | PyYAML | Human-diffable offers & channels. | Admin UI (out of scope). |
| Tests | **pytest**, `pytest-asyncio`, **respx**, **fakeredis** (or testcontainers), `freezegun`/`time-machine`, **hypothesis**, `pytest-cov` | See §22. | Live-API tests in CI (quota + flakiness). |
| Quality | **ruff**, **mypy --strict** (domain/services), pre-commit, `pip-audit` | Catch bugs before runtime. | — |
| Containers | **Docker + Docker Compose** | Reproducible local env. | Kubernetes (no requirement). |
| Frontend (Phase 10) | **React + Vite + TypeScript**, Tailwind CSS (tokens via CSS variables), TanStack Query, Recharts; TS types generated from OpenAPI | Standard, interview-relevant, keeps effort small. | HTMX + Jinja (viable; revisit at Phase 10 gate if frontend time is a concern). |

---

## 4. System context

```
                     ┌──────────────────────────┐
                     │  Traveler (browser, P1)  │
                     └────────────┬─────────────┘
                                  │ HTTPS/JSON
                     ┌────────────▼─────────────┐
                     │     FastAPI  (api)       │
                     │  auth · search · cards   │
                     │  handoff · watch · admin │
                     └───┬──────────┬───────┬───┘
            ┌────────────┘          │       └───────────────┐
            ▼                       ▼                       ▼
     ┌─────────────┐        ┌───────────────┐       ┌───────────────┐
     │   Redis     │        │  PostgreSQL   │       │ Flight data   │
     │ fare cache  │        │ users, cards, │       │ providers     │
     │ rate limits │        │ offers, watch,│       │  P1 (real)    │
     │ quota, locks│        │ history       │       │  P2 (real)    │
     │ celery queue│        └───────▲───────┘       │  Fake (dev)   │
     └──────▲──────┘                │               │  (Duffel sbx) │
            │                       │               └───────▲───────┘
     ┌──────┴───────────────────────┴───────────────────────┘
     │            Celery worker + Celery Beat
     │     scan watches → check route → history → notify
     └────────────────────────────────────────────────────────
                                  │
                        SMTP (Mailpit in dev)
```

The traveler is **redirected out** to airline/OTA sites; nothing flows back. We are never in the payment path.

---

## 5. Layers and the dependency rule

```
   api            HTTP concerns only: routes, request/response schemas, auth deps,
    │             error → status mapping, middleware. No business logic.
    ▼
   services       Use-cases: SearchService, AggregationService, HandoffService,
    │             WatchService, AuthService. Orchestrate; own transactions.
    ▼
   domain         PURE. Money, FlightOffer, CardOffer, offer matching, ranking,
    ▲             normalization helpers, domain errors, ports (Protocols).
    │
   infra          Everything with I/O: DB repositories, Redis cache/limiter/quota,
                  provider adapters, HTTP client, security, logging, metrics.
```

**Rules**
- `domain` imports **nothing** from `api`, `services`, `infra`, FastAPI, SQLAlchemy, Redis, or httpx. Only stdlib + typing (+ `pydantic` only if unavoidable; prefer `dataclasses`).
- `services` depend on **ports** (Protocols in `domain/ports.py`); `infra` implements them; wiring happens in `api/deps.py` (composition root).
- `api` never talks to `infra` directly, except via dependencies that return services.
- Celery tasks are *thin*: they call services like an API route does.
- Any dependency arrow pointing upward is a bug. Reviewers check this every phase.

---

## 6. Repository structure

```
flight-deal-aggregator/
├── README.md                     # public face: what/why/not, setup, API, limits
├── learning.md                   # chronological engineering journal (append-only)
├── Memory.md                     # AI hand-off state (created in Phase 0 coding session)
├── docs/
│   ├── PRD.md  Architecture.md  Rules.md  Phases.md  Design.md
├── data/
│   ├── card_offers.seed.yaml     # curated real offers (source_url + verified_at each)
│   ├── booking_channels.yaml     # channel id → display name, allowed hosts, url template
│   └── banks.yaml                # canonical bank slugs, aliases, card products
├── docker-compose.yml
├── .env.example                  # placeholders only
├── Makefile                      # up, down, test, lint, migrate, seed, bench
├── .github/workflows/ci.yml
├── backend/
│   ├── pyproject.toml            # deps, ruff, mypy, pytest config
│   ├── Dockerfile
│   ├── alembic.ini
│   ├── migrations/versions/
│   ├── scripts/
│   │   ├── seed_card_offers.py   # idempotent upsert by external_key
│   │   ├── smoke_live.py         # ONE explicit, quota-counted live call per provider
│   │   └── bench_search.py       # cold vs warm timings
│   ├── app/
│   │   ├── main.py               # app factory, lifespan, router mounting
│   │   ├── config.py             # pydantic-settings; single Settings object
│   │   ├── api/
│   │   │   ├── deps.py           # composition root (DI wiring)
│   │   │   ├── errors.py         # exception → problem-details mapping
│   │   │   ├── middleware.py     # request id, timing, logging context
│   │   │   ├── schemas/          # request/response models (wire format)
│   │   │   └── routes/           # health, auth, search, payment_methods,
│   │   │                         #   card_offers, handoff, watch
│   │   ├── services/
│   │   │   ├── search_service.py     # orchestrates cache → aggregate → offers → rank
│   │   │   ├── aggregation.py        # concurrent fan-out, timeouts, merge, dedupe
│   │   │   ├── handoff_service.py
│   │   │   ├── watch_service.py
│   │   │   └── auth_service.py
│   │   ├── domain/
│   │   │   ├── money.py              # Decimal helpers, rounding, Money type
│   │   │   ├── timeutil.py           # tz-aware helpers, IST constants
│   │   │   ├── flight.py             # FlightOffer, Segment, SearchQuery, itinerary_key
│   │   │   ├── card_offer.py         # CardOffer, PaymentMethod (value objects)
│   │   │   ├── offer_matching.py     # eligibility + discount + selection (PURE)
│   │   │   ├── ranking.py            # sort keys (PURE)
│   │   │   ├── provider_result.py    # ProviderStatus, ProviderResult
│   │   │   ├── errors.py             # domain + provider exception hierarchy
│   │   │   └── ports.py              # Protocols: FlightProvider, FareCache, RateLimiter, …
│   │   ├── infra/
│   │   │   ├── http.py               # httpx client factory, host allowlist
│   │   │   ├── security.py           # password hash, JWT
│   │   │   ├── db/
│   │   │   │   ├── base.py  session.py
│   │   │   │   ├── models/           # SQLAlchemy tables
│   │   │   │   └── repositories/     # user, payment_method, card_offer, watch, history
│   │   │   ├── cache/
│   │   │   │   ├── redis_client.py
│   │   │   │   ├── fare_cache.py     # slices, fresh/stale/miss, negative cache
│   │   │   │   └── locks.py          # refresh lock, in-process single-flight
│   │   │   ├── ratelimit/
│   │   │   │   ├── token_bucket.py   # Redis + Lua
│   │   │   │   └── quota_guard.py
│   │   │   ├── providers/
│   │   │   │   ├── registry.py       # enabled providers from config
│   │   │   │   ├── fake.py           # deterministic + chaos modes
│   │   │   │   ├── <provider_1>.py   # chosen in Pre-flight (e.g., ignav.py)
│   │   │   │   └── <provider_2>.py
│   │   │   ├── notifications.py      # SMTP/log notifier
│   │   │   └── observability/        # logging.py, metrics.py
│   │   └── workers/
│   │       ├── celery_app.py         # app, beat schedule
│   │       └── tasks/watch.py        # scan_watches, check_watch
│   └── tests/
│       ├── unit/                     # pure domain (no I/O)
│       ├── providers/                # adapter + normalization vs recorded fixtures
│       ├── integration/              # real Postgres/Redis (compose or testcontainers)
│       ├── api/                      # route-level via ASGI test client
│       ├── live/                     # opt-in only: pytest -m live
│       └── fixtures/providers/<name>/*.json   # sanitized real responses
└── frontend/                         # Phase 10 (React + Vite + TS)
```

---

## 7. Domain model

```python
# domain/flight.py  (shapes, not final code)
@dataclass(frozen=True)
class SearchQuery:
    origin: str            # IATA, uppercase
    destination: str
    departure_date: date   # local date at origin airport
    adults: int            # 1..9
    cabin: Cabin           # ECONOMY | PREMIUM_ECONOMY | BUSINESS | FIRST
    currency: str = "INR"

@dataclass(frozen=True)
class Segment:
    carrier: str           # IATA airline code (marketing carrier)
    flight_number: str     # "887"
    origin: str; destination: str
    departs_at: datetime   # tz-aware, airport-local zone
    arrives_at: datetime   # tz-aware, airport-local zone
    # UTC derived: departs_at.astimezone(UTC)

@dataclass(frozen=True)
class FlightOffer:                     # a purchasable fare, provider-normalized
    id: str                            # deterministic: hash(provider, itinerary_key, cabin, adults, currency)
    provider: str                      # DATA SOURCE (not necessarily where you buy)
    provider_ref: str | None           # opaque handle for later booking-link resolution
    itinerary_key: str                 # hash of ordered (carrier+number+departs_utc)
    segments: tuple[Segment, ...]
    airline: str                       # primary/marketing carrier code
    duration_minutes: int
    stops: int                         # len(segments) - 1
    list_price: Decimal                # ALL-IN total, ALL passengers, in `currency`
    currency: str
    cabin: Cabin
    channel: str | None                # booking channel if provider says; else None
    self_transfer: bool
    fetched_at: datetime               # tz-aware UTC

# What the API returns is FlightOffer + personalization:
@dataclass(frozen=True)
class PricedOffer:
    flight: FlightOffer
    discount: Decimal                  # >= 0, <= list_price
    effective_price: Decimal           # list_price - discount
    applied: AppliedOffer | None
    considered: tuple[AppliedOffer, ...]   # other eligible offers, for explainability
    assumptions: tuple[str, ...]       # e.g., "assumes booking on airline site"
```

**Why two types?** `FlightOffer` is cacheable and user-independent. `PricedOffer` is per-request and per-user. Mixing them is exactly what deviation #2 prevents.

---

## 8. Provider layer

### 8.1 Port

```python
# domain/ports.py
class FlightProvider(Protocol):
    name: str
    async def search(self, q: SearchQuery) -> list[FlightOffer]: ...
    async def resolve_booking(self, ref: str, q: SearchQuery) -> list[BookingOption]: ...
```

*Adapters raise typed exceptions; they never return status codes.* The **aggregator** owns timeouts, limiting, quota, and mapping exceptions to `ProviderResult`.

### 8.2 Exceptions and status

```
ProviderError (base)
├── ProviderTimeout          → ProviderStatus.TIMEOUT
├── ProviderRateLimited      → RATE_LIMITED   (HTTP 429 from vendor, or our limiter denied)
├── ProviderQuotaExhausted   → QUOTA_EXHAUSTED (our quota guard denied, or vendor says so)
├── ProviderAuthError        → AUTH_ERROR     (401/403 — misconfiguration; alert, don't retry)
├── ProviderBadResponse      → BAD_RESPONSE   (schema/parse failure; log sample, never crash)
└── ProviderUpstreamError    → UPSTREAM_ERROR (5xx / connection reset)
(anything else)              → INTERNAL_ERROR (logged with traceback — this is OUR bug)
```

```python
@dataclass(frozen=True)
class ProviderResult:
    provider: str
    status: ProviderStatus           # OK | TIMEOUT | RATE_LIMITED | ...
    offers: tuple[FlightOffer, ...]
    latency_ms: int | None
    origin: Literal["live", "cache_fresh", "cache_stale"]
    fetched_at: datetime | None
    dropped: int                     # rows failing normalization (currency, self-transfer, malformed)
    error_code: str | None           # safe, machine-readable
```

An `OK` result with zero offers is **success** (no flights), not failure.

### 8.3 Adapters

| Adapter | Purpose |
|---|---|
| `fake` | Deterministic fares for any route; **chaos modes**: `slow`, `timeout`, `500`, `429`, `malformed`, `empty`, `wrong_currency`. Default in dev/tests/CI. Also lets you demo partial failure on demand. |
| `<provider_1>`, `<provider_2>` | Real sources chosen in Pre-flight P1. One file each; only place vendor JSON is known. |
| `duffel` (optional) | Sandbox-only third adapter to prove the interface holds a *third* shape. |

### 8.4 Normalization rules (single source of truth)

1. **Price:** `list_price` = all-in payable total for the whole party, including taxes and mandatory fees. If a provider gives only per-passenger or base-only prices, the adapter computes/derives the all-in total or **drops the row** (`dropped += 1`). Never guess.
2. **Currency:** must equal the requested currency. Otherwise drop and count. **No FX conversion in v1.**
3. **Time:** parse to tz-aware. If a provider gives naive local times, attach the airport's IANA zone from the airport reference data; if it also gives UTC, cross-check and prefer UTC as truth. Duration must be consistent with `arrival_utc − departure_utc`; mismatch → log + trust UTC-derived.
4. **Decimal from the wire:** parse JSON numbers as `Decimal(str(value))`, never via float.
5. **Stops:** `len(segments) − 1`. Do not trust a provider's "stops" field without checking.
6. **Self-transfer / separate tickets:** flag `self_transfer=True`; excluded from results by default.
7. **`itinerary_key`:** stable hash of ordered `(carrier, flight_number, departs_utc_iso)` for each segment.
8. **Unknown fields ignored; missing required fields → drop row**, not crash. A structurally unexpected *whole response* → `ProviderBadResponse`.

---

## 9. Search flow

### 9.1 Sequence

```
Client ──POST /search──► API
                          │ validate (400 on error) · rate-limit user (429)
                          ▼
                     SearchService
                          │ 1. build SearchQuery
                          │ 2. for each enabled provider: FareCache.get(slice)
                          │        → FRESH | STALE | MISS  (Redis down → treat as MISS)
                          │ 3. providers needing data = MISS slices   (STALE served now, refreshed later)
                          ▼
                     AggregationService  (only for MISS slices)
                          │   async with asyncio.timeout(GLOBAL_BUDGET):
                          │     gather( _run_one(p) for p in miss )      ◄── never raises
                          │   _run_one: negative-cache check → quota guard → token bucket →
                          │             asyncio.timeout(PROVIDER_TIMEOUT) → provider.search →
                          │             map exceptions → ProviderResult
                          │   successful slices → FareCache.set (soft+hard TTL)
                          ▼
                     SearchService (continued)
                          │ 4. merge slices → dedupe (itinerary_key, channel)
                          │ 5. load CardOffers (in-memory snapshot, 60 s) + user's PaymentMethods
                          │ 6. OfferMatching.price(each FlightOffer)      ← per user, AFTER cache
                          │ 7. Ranking.sort(...)
                          │ 8. build response: results + providers{} + freshness + ranking rule
                          ▼
                     API returns 200 / 502 / 504 ; schedules BackgroundTasks for STALE refreshes
```

### 9.2 Pseudocode (service level)

```python
async def search(q: SearchQuery, user: User | None, sort_by: SortBy) -> SearchOutcome:
    slices = await cache.get_many([(p.name, q) for p in providers])      # never raises
    fresh   = {p: s for p, s in slices.items() if s.state is FRESH}
    stale   = {p: s for p, s in slices.items() if s.state is STALE}
    missing = [p for p in providers if p not in fresh and p not in stale]

    fetched = await aggregation.fetch(missing, q) if missing else []      # bounded by budget
    results = to_provider_results(fresh, stale, fetched)                  # includes statuses

    usable = [r for r in results if r.status is OK or r.origin == "cache_stale"]
    if not usable:
        raise AllProvidersFailed(results)                                 # → 502/504

    offers  = dedupe(merge(r.offers for r in usable))
    methods = await payment_methods.for_user(user) if user else []
    card_offers = card_offer_snapshot.get()                               # may be None → flag
    priced  = [pricing.price(o, methods, card_offers, now=utcnow()) for o in offers]
    ranked  = ranking.sort(priced, sort_by)

    return SearchOutcome(ranked, results, refresh_needed=list(stale))
```

### 9.3 Timing budget

- `GLOBAL_BUDGET` (default **5 s**) bounds the whole fan-out.
- `PROVIDER_TIMEOUT` (per provider, default 4.5 s) ≤ `GLOBAL_BUDGET`.
- A provider slower than its timeout is **cancelled** (not left running). *Known trade-off:* we could let it finish in the background to warm the cache; deferred until measured need.
- `asyncio.CancelledError` is never swallowed.

### 9.4 Response shape (abridged)

```jsonc
{
  "search": { "origin":"DEL","destination":"BOM","departure_date":"2026-10-15",
              "adults":1,"cabin":"ECONOMY","currency":"INR" },
  "metadata": {
    "search_id": "01J…",
    "partial_results": true,
    "oldest_data_at": "2026-09-29T10:12:31Z",
    "generated_at":   "2026-09-29T10:13:13Z",
    "providers": {
      "provider_1": { "status":"OK",      "origin":"live",        "latency_ms":1180,
                      "fetched_at":"2026-09-29T10:13:12Z", "count":37, "dropped":2 },
      "provider_2": { "status":"TIMEOUT", "origin":"cache_stale", "latency_ms":null,
                      "fetched_at":"2026-09-29T10:12:31Z", "count":21, "dropped":0 }
    },
    "ranking": { "sort_by":"effective_price",
                 "tie_breakers":["duration_minutes","stops","departure_utc","id"] },
    "offers": { "available": true, "assumption": "booking on airline's own site",
                "dataset_verified_range": ["2026-09-12","2026-09-27"] }
  },
  "results": [{
    "id":"k3f9…", "provider":"provider_1", "itinerary_key":"a1b2…",
    "airline":"AI", "flight_numbers":["AI887"],
    "departure": { "local":"2026-10-15T06:05:00+05:30","tz":"Asia/Kolkata","utc":"2026-10-15T00:35:00Z","airport":"DEL" },
    "arrival":   { "local":"2026-10-15T08:20:00+05:30","tz":"Asia/Kolkata","utc":"2026-10-15T02:50:00Z","airport":"BOM" },
    "duration_minutes":135, "stops":0,
    "list_price":      { "amount":"7200.00","currency":"INR" },
    "discount":        { "amount":"750.00", "currency":"INR" },
    "effective_price": { "amount":"6450.00","currency":"INR" },
    "applied_offer": { "offer_id":"…","bank":"hdfc","card_product":"regalia",
                       "discount_amount":"750.00","promo_code":null,
                       "source_url":"https://…","verified_at":"2026-09-20","terms_note":"…" },
    "considered_offers": [],
    "assumptions": ["Assumes booking on the airline's own site"],
    "price_discrepancy": false
  }]
}
```
**Money is always a string** on the wire. The frontend formats but never computes.

---

## 10. Cache design

### 10.1 Keys and values
```
fare:v1:{provider}:{ORIG}:{DEST}:{YYYY-MM-DD}:{adults}:{cabin}:{currency}
  → JSON { fetched_at, provider, status:"OK", offers:[…normalized…], dropped:int }
  → Redis TTL = HARD_TTL (default 3600 s); freshness computed in app from fetched_at

neg:v1:{provider}:{same route fields}     → short (30–60 s) negative cache for
                                           RATE_LIMITED / UPSTREAM_ERROR / QUOTA_EXHAUSTED
ref:v1:{offer_id}                         → { provider, provider_ref, list_price, fetched_at, query }
                                           (handoff lookup; TTL = HARD_TTL)
lock:refresh:{slice key}                  → SET NX PX 30000  (one background refresher)
```
Redis logical DBs: `0` cache/limits, `1` Celery broker, `2` Celery results (if used).

### 10.2 States (per provider slice)
| State | Condition | Behavior |
|---|---|---|
| FRESH | age < `FRESH_TTL` (default **300 s**) | Serve. No provider call. |
| STALE | `FRESH_TTL` ≤ age < `HARD_TTL` | Serve now; enqueue background refresh (guarded by lock **and** quota). |
| MISS | absent | Fetch (blocking, budget-bounded). |
| Stale-if-error | refresh fails while STALE | Keep serving stale until `HARD_TTL`; report `origin: cache_stale`. |

### 10.3 Stampede control
- **In-process single-flight:** concurrent identical fetches within one API process share one in-flight task (`dict[key, asyncio.Future]`).
- **Cross-process:** Redis lock only for *background refresh*. A cold-start stampede across many workers is accepted at this scale and documented.
- Background tasks are held in a set (strong references) — un-referenced `asyncio` tasks can be garbage-collected mid-flight. Prefer FastAPI `BackgroundTasks` scheduled by the route from `refresh_needed`.

### 10.4 Failure behavior
- Redis down → `FareCache` returns MISS and logs/metrics; search continues (but the **quota guard fails closed** — see §11).
- Corrupt/undeserializable value → treat as MISS, delete key, log.
- Serialization: JSON with money as strings and ISO-8601 datetimes. **Never `pickle`.**

---

## 11. Rate limiting & quota

Three separate mechanisms — do not conflate them:

| Mechanism | Protects | Implementation | On deny |
|---|---|---|---|
| **Token bucket per provider** | Provider's documented RPS/burst | Redis Lua script (atomic), key `rl:{provider}` | Fast-fail → `RATE_LIMITED`. Do **not** queue/sleep. |
| **Quota guard per provider** | Total call budget (per month or lifetime) | Redis `INCR quota:{provider}:{period}` before call; compare to `PROVIDER_x_QUOTA_LIMIT`; AOF-persisted | `QUOTA_EXHAUSTED`; metric + log; UI says "source unavailable". |
| **User/IP limiter** | Abuse; each cold search burns provider quota | Same token-bucket module, key by user id or IP | HTTP 429 + `Retry-After`. |

- Count **attempts**, not just successes (conservative, since some vendors bill only successes).
- The vendor dashboard is authoritative; our counter is a safety margin with a **soft limit below the real limit**.
- **If Redis is down the quota guard fails closed** for quota-limited providers (protects the budget). Consequence: search returns 502 with a clear reason. This is a documented weakness (§24).
- Per-provider `asyncio.Semaphore` caps concurrent in-flight calls.
- **Retries:** none by default (each retry spends quota). At most one immediate retry on connection-establishment errors, never on timeouts/5xx/429.

---

## 12. Offer engine (`domain/offer_matching.py` — pure)

### 12.1 Inputs
`FlightOffer` · `list[PaymentMethod]` · `list[CardOffer]` · `now` · `channel_assumption` · airport reference (for domestic/international).

### 12.2 Eligibility pipeline (all must pass)
1. `active` and `valid_from ≤ now ≤ valid_to` (IST semantics; `valid_to` inclusive end-of-day).
2. Optional travel-date window (`travel_valid_from/to`) contains the departure date.
3. User holds a payment method matching: `bank` (canonical slug), and — **if the offer specifies them** — `card_network`, `card_product`/tier, `payment_type`.
4. `merchant` is null (any channel) or equals the fare's channel (`fare.channel` or the assumed `airline_direct`).
5. `airline` is null or equals `fare.airline`.
6. `route_scope` in (`ANY`, `DOMESTIC`, `INTERNATIONAL`) matches airports' countries.
7. `list_price ≥ min_spend`.
8. Currency matches.

### 12.3 Discount (all `Decimal`)
```
FLAT:     raw = discount_value
PERCENT:  raw = list_price × discount_value / 100
cap:      raw = min(raw, max_discount)          if max_discount is not None
bound:    raw = min(raw, list_price)
round:    discount = raw.quantize(Decimal("0.01"), rounding=ROUND_DOWN)   # never overstate savings
effective = list_price − discount               # always 0 ≤ effective ≤ list_price
```

### 12.4 Selection
Best = highest `discount`; ties → lowest `offer.id`. Also return up to 3 runners-up in `considered`. **One offer per fare.** `stackable` exists in the schema but the engine ignores it until a real offer needs it (OD-7).

### 12.5 Data flow for offers
```
data/card_offers.seed.yaml ──seed_card_offers.py (idempotent upsert on external_key)──► card_offers
card_offers ──(loaded every 60 s into an in-memory snapshot)──► OfferSnapshot
per request:  PaymentMethods(user) + OfferSnapshot + FlightOffers ──► PricedOffers
```
If the DB is unavailable and there is no snapshot: return list prices, `offers.available=false`.

### 12.6 Honesty rules
- Show `source_url`, `verified_at`, and `terms_note` (unmodeled conditions like BIN range, per-user caps, day-of-week, payment-mode exclusions).
- Offers whose basis we can't compute (e.g., "10 % off *base fare* only" when we only know the all-in total) are **not seeded** as computable; they may be listed with `computable=false` for display only.
- Assumptions travel with the result (`assumptions[]`).

---

## 13. Ranking (`domain/ranking.py` — pure)

Sort key (all ascending, deterministic):
```
effective_price, duration_minutes, stops, departure_utc, id
```
`sort_by` changes the *first* key (`price`, `duration`, `stops`, `departure_time`); the rest remain as tie-breakers. No composite "score". The response echoes the rule so a result's position is always explainable.

---

## 14. Handoff (`services/handoff_service.py`)

```
POST /handoff {result_id}
   │ ref:v1:{result_id} in Redis?  ── no ─► 410 Gone ("results expired — search again")
   ▼
provider.resolve_booking(provider_ref)      ← may be a second billable call; cached 10–15 min
   ▼
BookingOption[]  →  pick channel (prefer airline_direct, else first allowlisted)
   ▼
validate: scheme == https AND host ∈ booking_channels.yaml allowed_hosts
   ▼                                  └─ fail ─► 422 (never redirect to unknown hosts)
respond { url, channel, price_at_search, data_age_s, price_at_link?, price_changed?, disclaimer }
```
- Client opens the URL in a new tab with `rel="noopener noreferrer"`. **We do not 302-redirect from the API** (keeps disclaimer + `price_changed` visible; avoids an open-redirect endpoint).
- `booking_channels.yaml` is **data**: `{id, name, allowed_hosts[], url_template?}`. If a provider can't give URLs, a channel's `url_template` may build an airline search URL — feasibility is proven per carrier in Pre-flight P3.
- Handoff is idempotent (cached), rate-limited, and works for anonymous users.

---

## 15. Price watch & workers

```
Celery Beat (every WATCH_SCAN_INTERVAL_MIN) ─► scan_watches
     │ SELECT active watches WHERE departure_date ≥ today AND due (last_checked_at old enough)
     │ GROUP BY route key → one search per distinct route (cache-first!)
     ▼
check_watch(route) ─► SearchService (list price only; no user personalization)
     │ lowest list price L
     │ INSERT price_history (idempotent per watch+hour bucket)
     │ decide drop:  L ≤ target  OR  (ref − L) ≥ max(300, 5 % of ref)
     │ INSERT notification_log ON CONFLICT DO NOTHING (dedupe_key = watch_id:price:date)
     └─ if inserted → notifier.send(); update ref := L
```
- **Idempotent** (safe under retries/duplicate delivery). `acks_late`, bounded retries with exponential backoff, `soft_time_limit`.
- Tasks are thin; logic lives in `WatchService` (unit-testable without Celery).
- **Async in Celery:** tasks are sync functions; they call `asyncio.run(...)` around the async provider fan-out, and use a **sync** SQLAlchemy engine (psycopg 3). Never share an async engine/connection pool across event loops (classic failure: "attached to a different loop"). Recorded as decision D15.
- Watch price history uses **list price**, not effective price, so history is comparable across users and time.
- Quota protection: cap active watches/user; scan interval configurable (default 12 h); cache-first; skipped when quota guard denies (recorded, not retried aggressively).

---

## 16. Data model (PostgreSQL)

Conventions: UUID PKs (`gen_random_uuid()`), `timestamptz` everywhere, `NUMERIC(12,2)` for money, `text + CHECK` instead of native enums (simpler migrations), explicit constraint names via SQLAlchemy `MetaData(naming_convention=…)`. Every table below must have its reasoning (entity, keys, indexes, constraints, query patterns) written in `learning.md` when created (see `Rules.md` §16).

```sql
users
  id            uuid PK
  email         text NOT NULL
  password_hash text NOT NULL
  is_admin      boolean NOT NULL DEFAULT false
  created_at    timestamptz NOT NULL DEFAULT now()
  UNIQUE INDEX ux_users_email_lower ON (lower(email))
  -- Query: lookup by lower(email) at login.

payment_methods                      -- METADATA ONLY. No PAN/CVV/expiry columns. Ever.
  id            uuid PK
  user_id       uuid NOT NULL FK users(id) ON DELETE CASCADE
  card_network  text NOT NULL CHECK (card_network IN ('VISA','MASTERCARD','RUPAY','AMEX','DINERS','OTHER'))
  issuing_bank  text NOT NULL             -- canonical slug from banks.yaml, e.g. 'hdfc'
  product_tier  text NOT NULL DEFAULT ''  -- '' not NULL, so UNIQUE works (NULLs are distinct in UNIQUE)
  payment_type  text NOT NULL DEFAULT 'CREDIT' CHECK (payment_type IN ('CREDIT','DEBIT'))
  nickname      text NULL CHECK (nickname !~ '\d{12,}')   -- defense in depth vs pasted card numbers
  created_at    timestamptz NOT NULL DEFAULT now()
  UNIQUE (user_id, card_network, issuing_bank, product_tier, payment_type)
  INDEX ix_pm_user ON (user_id)
  -- Query: all methods for a user, every authenticated search.

card_offers
  id               uuid PK
  external_key     text NOT NULL UNIQUE        -- stable key from seed file; upsert target
  bank             text NOT NULL               -- canonical slug
  card_network     text NULL                   -- NULL = any
  card_product     text NULL                   -- NULL = any tier of that bank
  payment_type     text NULL CHECK (payment_type IN ('CREDIT','DEBIT'))
  merchant         text NULL                   -- booking channel id; NULL = any channel
  airline_code     text NULL                   -- IATA; NULL = any airline
  route_scope      text NOT NULL DEFAULT 'ANY' CHECK (route_scope IN ('ANY','DOMESTIC','INTERNATIONAL'))
  discount_type    text NOT NULL CHECK (discount_type IN ('FLAT','PERCENT'))
  discount_value   numeric(12,2) NOT NULL CHECK (discount_value > 0)
  max_discount     numeric(12,2) NULL CHECK (max_discount > 0)
  min_spend        numeric(12,2) NOT NULL DEFAULT 0 CHECK (min_spend >= 0)
  currency         char(3) NOT NULL DEFAULT 'INR'
  promo_code       text NULL
  valid_from       timestamptz NOT NULL
  valid_to         timestamptz NOT NULL
  travel_valid_from date NULL
  travel_valid_to   date NULL
  stackable        boolean NOT NULL DEFAULT false      -- reserved; engine ignores in v1
  computable       boolean NOT NULL DEFAULT true       -- false = display-only
  terms_note       text NULL                            -- unmodeled conditions
  source_url       text NOT NULL
  verified_at      date NOT NULL
  active           boolean NOT NULL DEFAULT true
  created_at, updated_at timestamptz
  CHECK (valid_to > valid_from)
  CHECK (discount_type <> 'PERCENT' OR discount_value <= 100)
  INDEX ix_offers_active_window ON (active, valid_from, valid_to)
  -- Query: "active offers valid now" → loaded whole (tens of rows) into memory every 60 s.

watched_routes
  id, user_id FK CASCADE
  origin char(3), destination char(3), departure_date date, adults smallint, cabin text
  target_price numeric(12,2) NULL
  reference_price numeric(12,2) NULL          -- baseline for drop detection
  last_checked_price numeric(12,2) NULL, last_checked_at timestamptz NULL
  active boolean NOT NULL DEFAULT true, created_at
  UNIQUE (user_id, origin, destination, departure_date, adults, cabin) WHERE active   -- partial unique
  INDEX ix_watch_due ON (active, departure_date, last_checked_at)
  -- Query: scanner selects due, active, future watches; user lists own watches.

price_history
  id bigserial PK
  watched_route_id FK CASCADE
  lowest_price numeric(12,2) NOT NULL, currency char(3), provider text
  recorded_at timestamptz NOT NULL DEFAULT now()
  INDEX ix_hist_watch_time ON (watched_route_id, recorded_at DESC)
  -- Query: history for a watch, newest first / time range.

notification_log
  id, user_id FK, watched_route_id FK CASCADE
  dedupe_key text NOT NULL, kind text, payload jsonb, status text, created_at
  UNIQUE (watched_route_id, dedupe_key)       -- makes notify idempotent
```

Not tables (deliberately): `search_cache` (Redis), `provider_usage` (Redis counters + metrics), `banks` (YAML), `booking_channels` (YAML).

---

## 17. HTTP API (`/api/v1`)

Errors use a problem-details style body: `{type, title, status, detail, request_id, errors?[]}`. Auth = `Authorization: Bearer <jwt>`.

| Endpoint | Purpose | Auth | Request → Response | Status codes | Idempotency | Rate limit |
|---|---|---|---|---|---|---|
| `GET /health` | Liveness | – | → `{status}` | 200 | yes | – |
| `GET /health/ready` | Readiness (DB, Redis) | – | → `{db, redis}` | 200 / 503 | yes | – |
| `POST /auth/register` | Create account | – | `{email,password}` → `{id,email}` | 201 · 400 · 409 | no (409 on dup) | IP |
| `POST /auth/login` | Get token | – | form → `{access_token,expires_in}` | 200 · 400 · 401 · 429 | yes | strict IP |
| `POST /search` | Ranked fares with effective price | Optional | `SearchRequest` → `SearchResponse` | 200 · 400 · 429 · 502 · 504 | yes (safe, cache-backed) | per user/IP |
| `GET /payment-methods` | List my methods | Required | → `[PaymentMethod]` | 200 · 401 | yes | user |
| `POST /payment-methods` | Declare a method | Required | metadata only → `PaymentMethod` | 201 · 400 · 401 · 409 | no (409) | user |
| `DELETE /payment-methods/{id}` | Remove | Required | – | 204 · 401 · 404 | yes | user |
| `GET /card-offers` | Inspect dataset (debug) | Required (admin later) | filters → `[CardOffer]` incl. `verified_at`, `stale` | 200 · 401 | yes | user |
| `POST /handoff` | Resolve booking URL | Optional | `{result_id}` → `{url,channel,…}` | 200 · 404 · 410 · 422 · 429 · 502 | yes (cached) | per user/IP |
| `POST /watch` | Save route | Required | route + `target_price?` → `Watch` | 201 · 400 · 401 · 409 · 422 (cap) | no (409) | user |
| `GET /watch` | List mine | Required | → `[Watch]` | 200 · 401 | yes | user |
| `DELETE /watch/{id}` | Stop watching | Required | – | 204 · 401 · 404 | yes | user |
| `GET /watch/{id}/history` | Price history | Required (owner) | `?from&to` → `[{recorded_at,price}]` | 200 · 401 · 404 | yes | user |
| `GET /metrics` | Prometheus | Internal only | – | 200 | yes | network-restricted |

**Search status semantics**
- `200` — at least one provider produced a usable slice (live or cached), even with zero flights.
- `400` — invalid input (bad IATA, past date, > horizon, origin = destination, pax range).
- `429` — our limiter (with `Retry-After`).
- `504` — every provider failed and all failures were timeouts. `502` — every provider failed otherwise. Body lists per-provider reasons.
- Never `500` for provider problems; `500` means *our* bug.

**Validation:** `extra="forbid"` on all request models; IATA `^[A-Z]{3}$` (normalize case first); dates parsed as `date`; enums for cabin/sort.

---

## 18. Error handling

| Class | Examples | Handling | HTTP |
|---|---|---|---|
| Validation | bad IATA, past date | Pydantic/domain validation at the boundary | 400 |
| Authentication/authorization | bad token, not owner | Dependency raises | 401 / 403 / 404 (don't leak existence) |
| Conflict | duplicate card/watch | Catch `IntegrityError` **narrowly** | 409 |
| Provider | timeout, 429, 5xx, malformed | Typed exceptions → `ProviderResult`; isolated | per-provider status; overall 200/502/504 |
| Infrastructure | Redis/DB unavailable | Degrade per §10.4 / NFR-2; readiness reflects | 200 (degraded) / 503 (ready) |
| Internal bug | anything else | Log with traceback + request id; generic body | 500 |

Rules: no `except: pass`; no blanket `except Exception` except at the **provider boundary** (`_run_one`) and worker task edges, where it is converted to a typed result/log and never swallows `CancelledError`.

---

## 19. Security

- **Payment data:** metadata only; schema has no PAN/CVV/expiry; request models forbid extras; free-text fields reject 12–19 digit runs; logs never contain request bodies for these endpoints.
- **Secrets:** env only; `.env` gitignored; `.env.example` placeholders; never log API keys or tokens; redaction processor in structlog.
- **AuthN/Z:** Argon2 password hashes; JWT with short expiry, explicit `alg`, required `exp`/`sub`; ownership checks on watches/payment methods; generic login errors (no user enumeration).
- **SSRF / outbound control:** all outbound HTTP goes through one factory with a host allowlist derived from provider config. Provider-returned URLs are **never fetched**; they are only validated and returned (handoff).
- **Open redirect:** the API never issues redirects to provider-supplied URLs; handoff returns validated JSON.
- **Untrusted provider data:** validated with strict models, size-capped, HTML/URL fields sanitized; malformed rows dropped.
- **Abuse:** rate limits on search/login/handoff; quota guard bounds the blast radius.
- **Transport/CORS:** HTTPS at the edge (out of scope locally), CORS origin allowlist, no wildcard with credentials.
- **Supply chain:** `pip-audit` and lockfile; minimal dependencies (see `Rules.md`).
- **Least privilege:** app DB user cannot alter schema at runtime (migrations use a separate role in non-dev).

---

## 20. Observability

**Logs (structlog JSON):** `request_id`, `search_id`, `user_id` (hashed or id only), route, per-provider `{status, latency_ms, origin, count, dropped}`, `cache_state`, `offers_matched`, `total_ms`. One summary line per search.

**Metrics (Phase 9):**
```
http_request_duration_seconds{route,method,status}
provider_request_duration_seconds{provider,outcome}
provider_requests_total{provider,outcome}       # ok|timeout|rate_limited|quota|auth|bad_response|upstream
fare_cache_lookups_total{provider,state}        # fresh|stale|miss|error
search_results_count (histogram)
offers_matched_total
provider_quota_remaining{provider}
worker_tasks_total{task,outcome}
```
Debugging playbook (goes into `learning.md`): given a slow search, find the request id → read the summary log → identify which provider/stage consumed the budget.

---

## 21. Configuration (env → `Settings`)

| Variable | Default | Notes |
|---|---|---|
| `APP_ENV` | `dev` | `dev`/`test`/`prod` |
| `LOG_LEVEL` | `INFO` | |
| `DATABASE_URL` | – | Host must be `postgres` **inside** Compose (not `localhost`) |
| `REDIS_URL` | – | Host `redis` inside Compose; DB 0 |
| `CELERY_BROKER_URL` | – | Redis DB 1 |
| `JWT_SECRET` · `JWT_ALG` · `ACCESS_TOKEN_TTL_MIN` | – / `HS256` / `30` | Secret ≥ 32 random bytes |
| `CORS_ORIGINS` | `http://localhost:5173` | Comma-separated |
| `ENABLED_PROVIDERS` | `fake` | e.g. `fake,provider_1,provider_2` |
| `ALLOW_LIVE_PROVIDERS` | `false` | **Master safety switch** for real calls |
| `SEARCH_BUDGET_S` · `PROVIDER_TIMEOUT_S` | `5` · `4.5` | |
| `CACHE_FRESH_TTL_S` · `CACHE_HARD_TTL_S` · `NEG_CACHE_TTL_S` | `300` · `3600` · `45` | |
| `PROVIDER_<X>_API_KEY` / `_BASE_URL` | – | Never logged |
| `PROVIDER_<X>_RPS` · `_BURST` · `_QUOTA_LIMIT` · `_QUOTA_PERIOD` | from vendor docs | Don't invent; copy from docs and note the date |
| `BOOKING_HORIZON_DAYS` | `330` | |
| `OFFER_STALE_AFTER_DAYS` | `30` | |
| `WATCH_SCAN_INTERVAL_MIN` · `WATCH_MAX_PER_USER` | `720` · `5` | |
| `SMTP_HOST` · `SMTP_PORT` · `MAIL_FROM` | `mailpit` · `1025` | Dev SMTP sink |

---

## 22. Docker Compose topology

```
services:
  postgres   (healthcheck: pg_isready)      volume: pgdata
  redis      (healthcheck: redis-cli ping;  command: redis-server --appendonly yes)   volume: redisdata
  api        depends_on: postgres/redis (condition: service_healthy)   ports: 8000
  worker     same image, command: celery -A app.workers.celery_app worker
  beat       same image, command: celery -A app.workers.celery_app beat
  mailpit    SMTP sink + UI (dev)
  # Phase 9 (compose profile "obs"): prometheus, grafana
  # Phase 10: frontend dev server runs on the host (Vite) or as a service
```
Inside a container, `localhost` is **that container**. Services reach each other by Compose service name (`postgres`, `redis`).

---

## 23. Testing architecture

| Layer | Tooling | What it proves | Runs in CI |
|---|---|---|---|
| `tests/unit/` | pytest, hypothesis, freezegun | Money, offer matching, ranking, normalization helpers — pure, no I/O | ✅ |
| `tests/providers/` | pytest, respx, JSON fixtures | Each adapter maps *recorded real responses* correctly; malformed/empty/429/timeout paths; a **shared contract suite** parametrized over every adapter | ✅ |
| `tests/integration/` | Postgres + Redis (Compose/testcontainers) | Repositories, constraints, Lua limiter, cache states, quota guard, Celery task logic, Redis-down degradation | ✅ |
| `tests/api/` | ASGI test client + fake provider | Status codes, schemas, auth, partial results, chaos modes | ✅ |
| `tests/live/` | `pytest -m live` | One smoke test per real provider; **never in CI**; counts against quota | ❌ opt-in |

Required failure cases (minimum): provider OK / timeout / malformed / empty / 429 / wrong currency / self-transfer; Redis unavailable; DB unavailable; offer expired / below min spend / wrong bank / wrong tier / wrong channel / multiple offers / cap applied / rounding boundary.

Fixtures are captured **once** (costs quota), sanitized (no keys), committed, and replayed forever.

Property tests (offer engine): `0 ≤ discount ≤ list_price`; `effective + discount == list_price`; result invariant to offer list order; ineligible ⇒ discount 0.

---

## 24. Failure-mode matrix

| Failure | Detection | System behavior | User sees |
|---|---|---|---|
| One provider times out | `asyncio.timeout` | `TIMEOUT` status; others used; stale slice used if present | "2 of 3 sources responded" |
| All providers time out | all `TIMEOUT` | No usable data → 504 | Clear error, retry hint |
| Provider returns malformed JSON | Pydantic/parse error | `BAD_RESPONSE`, sample logged (redacted), row/response dropped | Source marked unavailable |
| Vendor 429 / our bucket empty | 429 / limiter deny | `RATE_LIMITED`, negative-cached briefly | Source marked unavailable |
| Quota exhausted | quota guard | `QUOTA_EXHAUSTED`; metric + log | Source marked unavailable |
| Vendor auth fails (401/403) | status | `AUTH_ERROR`; alert; no retry | Source unavailable (config issue) |
| Provider schema changes | parse failures spike | `BAD_RESPONSE` metric spike; fixtures diverge | Source unavailable |
| Redis down | client exceptions | Cache bypass; quota guard **fails closed** → likely 502 | "Temporarily unavailable" |
| Postgres down | connection errors | Search uses offer snapshot or list prices; auth/watch endpoints 503 | Offers hidden, flagged |
| Stale offer data | `verified_at` age | `stale` flag on offer | "Offer last verified N days ago" |
| Expired offer | validity window | Not applied | No discount |
| Duplicate itineraries | `itinerary_key` | Dedupe / discrepancy flag | One row, or flagged price gap |
| Worker crash mid-task | Celery acks_late redelivery | Task re-runs; idempotent inserts | Nothing duplicated |
| Duplicate alerts | `notification_log` UNIQUE | Second insert no-ops | One email |
| Clock/timezone slip | tests around midnight/IST | tz-aware only | Correct dates |
| Handoff URL off-allowlist | validator | 422; no redirect | "Couldn't open a safe booking link" |

---

## 25. What will break first (honest weaknesses)

1. **Quota**, long before CPU. Every design choice above trades freshness for quota.
2. **Redis is a single point of failure** for limiting/caching (accepted; single-node dev scale).
3. **Cross-process cold stampede** — in-process single-flight only.
4. **Offer accuracy** — manual curation; hidden terms; verification lag.
5. **Booking-channel assumption** — effective price may not match the channel the traveler finally uses.
6. **Provider terms/coverage drift** — vendors can change or vanish (Amadeus did).
7. **Cancelling slow providers** wastes a call we may have paid for.

## 26. Scale-up path (do NOT build now)

Only when measured need appears: extract workers to separate deployments; Redis Cluster/Sentinel; provider circuit breaker with half-open probes; request coalescing across processes via Redis pub/sub; let slow providers finish in background to warm cache; read replicas; CDN for frontend. Each requires a design proposal and a `learning.md` entry justifying *why now*.

## 27. Key decisions index (referenced from other docs)

| ID | Decision |
|---|---|
| D1 | Modular monolith |
| D2 | Provider port extracted **after** two concrete adapters exist |
| D3 | Data source ≠ booking channel; assumption `airline_direct` stated in responses |
| D4 | Cache provider fares only; personalize after cache |
| D5 | Per-provider cache slices; versioned keys incl. cabin + currency |
| D6 | Fresh/stale/hard TTL; stale-if-error; negative caching |
| D7 | `Decimal`/`NUMERIC(12,2)`; money as strings on the wire; `list_price` all-in |
| D8 | Timezone-aware everywhere; airport IANA tz; UTC for comparison |
| D9 | Offers = DB rows seeded from YAML; one best offer; stacking deferred |
| D10 | Booking channels = config; lazy link resolution; host allowlist; no server redirects |
| D11 | Token bucket + quota guard + concurrency cap per provider; quota guard fails closed |
| D12 | Dedupe on `(itinerary_key, channel)`; discrepancy flag > 3 % |
| D13 | INR only; no FX |
| D14 | Redis-only fare cache; Postgres for durable history |
| D15 | Async API, sync Celery worker (`asyncio.run` around provider fan-out); psycopg 3 for both |
| D16 | JWT + Argon2; search/handoff open to anonymous users |
| D17 | Live provider calls disabled by default; fixtures + Fake provider for dev/test |
