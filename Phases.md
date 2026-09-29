# Phases — Build Plan

| | |
|---|---|
| **Version** | 1.0 · 2026-09-29 |
| **Rule of thumb** | One phase at a time. Each phase ends with a **working, tested, committed, documented** system. |
| **Sizing** | S ≈ 1 focused session · M ≈ 2–3 · L ≈ 4–6 (relative, not promises) |

The AI cannot build everything at once — and shouldn't. Work strictly in order. Do not start Phase N+1 until Phase N's **exit criteria** are met and the **teaching check** passes (*"Could the developer explain why this architecture exists without looking at the code?"*).

---

## Status tracker (keep in sync with `Memory.md`)

| Phase | Name | Size | Status |
|---|---|---|---|
| Pre | Pre-flight: providers, offers research, deep-link feasibility | M | ⬜ |
| 0 | Engineering foundation | M | ⬜ |
| 1 | Single-provider search | L | ⬜ |
| 2 | Provider abstraction + second provider | M | ⬜ |
| 3 | Aggregation, resilience, dedupe | L | ⬜ |
| 4 | Redis caching, rate limiting, quota guard | L | ⬜ |
| 5 | Users, payment methods, offer matching | L | ⬜ |
| 6 | Ranking | S | ⬜ |
| 7 | Redirect / handoff | M | ⬜ |
| 8 | Price watch (Celery) | L | ⬜ |
| 9 | Observability | M | ⬜ |
| 10 | Frontend | L | ⬜ |
| 11 | Hardening, README, demo | M | ⬜ |

Legend: ⬜ not started · 🔄 in progress · ✅ exit criteria met

## Cross-cutting rules for every phase
- Follow `Rules.md`: teach → design (if architectural) → implement → test → run → review → `learning.md` → `Memory.md` → commit.
- **Live provider calls are off.** Use the Fake provider and recorded fixtures unless a task says otherwise.
- **Design proposal required** where a phase lists one (per `Rules.md` §3).
- **Socratic question** (one per phase, at most) is suggested — ask it *before* explaining.
- Commits are small and Conventional. Tag `phase-N-complete` at the end.

---

## Pre-flight — Providers, offers, deep links *(mostly not code; start on day one)*

**Why first:** calendar-time delays (API access, manual research) dominate risk (PRD R1, R4). The Amadeus Self-Service shutdown proved that provider assumptions can be false. **Do these in parallel with Phase 0.**

**Tasks**
- [ ] **P1 — Provider spike (curl/Postman only, no app code).**
  - Sign up for the candidate self-serve providers from PRD §11 (start with Ignav and one Google-Flights-derived API; optionally Duffel test mode).
  - For each: make **one** real `DEL → BOM` one-way request (date ≥ 2 weeks ahead) and **save the raw response**.
  - Record in a scratch note: currency returned (INR?), Indian carriers present (IndiGo/Air India/Akasa/SpiceJet?), price semantics (per-passenger vs total; taxes included?), time fields (local/UTC/tz), self-transfer flags, booking-URL availability (in search vs separate call), documented rate limit and quota (copy exact wording + URL + date), latency, terms-of-service notes.
  - Count quota used. **Budget:** ≤ 5 calls per provider for the whole spike.
  - **Decision output (→ `Memory.md`):** chosen Provider 1 and Provider 2, or the fallback (1 real + Fake + Duffel sandbox) and the amended PRD demo bar.
- [ ] **P2 — Offer research kickoff.** Collect ≥ 20 real card offers applicable to flights (Indian banks/cards). For each capture: bank, card network/product, payment type (credit/debit), merchant/channel (airline direct or OTA), airline (if specific), domestic/international, discount type/value, cap, min spend, validity window, promo code, **source URL, date verified**, and unmodeled terms (BIN ranges, tax exclusions, per-user caps, day-of-week). Store in a scratch YAML draft. Skip offers you can't compute from an all-in fare (list them as display-only).
- [ ] **P3 — Deep-link feasibility.** For each carrier on the demo route, determine how a traveler gets to a pre-filled booking page: provider's booking-link call, or an airline/OTA URL template. Record working examples and allowed hosts (→ future `booking_channels.yaml`).
- [ ] **P4 — Dev machine.** Docker + Compose, Python 3.12+, Node LTS (later), Git; create the repo; place the five docs in `docs/`.

**Exit criteria:** Provider decision recorded with evidence (raw responses saved outside git or sanitized); ≥ 20 offers drafted with sources; deep-link approach known per demo carrier; repo initialized.

**Learning focus:** evaluating third-party dependencies; vendor lock-in and vendor disappearance; reading API docs critically; measuring instead of trusting marketing.

**Socratic question:** *"Your only source is shut down next month. What in the architecture makes that survivable, and what would make it fatal?"*

**`learning.md` entry:** "Provider reality check" (include what the spike contradicted from the docs).

---

## Phase 0 — Engineering foundation *(M)*

**Goal:** A reproducible, observable skeleton where every later phase can plug in safely.

**Depends on:** Pre-flight P4.

**Deliverables**
- Repo structure per `Architecture.md` §6 (only folders needed now).
- `pyproject.toml` with pinned deps; `ruff`, `mypy`, `pytest` configured; pre-commit.
- FastAPI app factory + lifespan; `config.py` (pydantic-settings) with **`ALLOW_LIVE_PROVIDERS=false`** default.
- structlog JSON logging; request-id middleware; redaction processor.
- Error handling skeleton (problem-details) and exception hierarchy stubs.
- Async SQLAlchemy engine/session; Alembic initialized; baseline migration (may be empty).
- Redis client wrapper.
- `GET /health` (liveness) and `GET /health/ready` (DB + Redis).
- `docker-compose.yml`: `postgres`, `redis` (AOF on), `api` (+ healthchecks, `depends_on: service_healthy`); `.env.example`; `Makefile`; Dockerfile.
- GitHub Actions: lint, type-check, tests (no network).
- README skeleton with the "what it is / is not" statement.
- **`learning.md` created** with header + Phase 0 entries. **`Memory.md` created** at the end of this phase.

**Design proposal required?** No (but explain layering and config strategy).

**Tests:** health endpoints; readiness returns 503 when a dependency is down (stop Redis in an integration test); settings validation (missing required env fails fast).

**Exit criteria**
- [ ] `docker compose up` → `/health/ready` reports db + redis OK from a clean clone.
- [ ] `make test`, `make lint` green locally and in CI.
- [ ] Killing Redis makes `/health/ready` return 503 (demonstrated).
- [ ] A **deliberate failure** was hit and documented (e.g., `localhost` vs service-name in Docker) — if none occurred naturally, reproduce this one on purpose.
- [ ] `learning.md` and `Memory.md` exist and are useful.

**Learning focus:** application layering, config management, containers/networking, DB connections & pooling, environment separation, migrations.

**Socratic question:** *"Inside the API container, what does `localhost:5432` point to?"*

**Commits:** `chore: scaffold backend`, `feat: config and logging`, `feat: health endpoints`, `feat: compose stack`, `chore: ci pipeline`, `docs: learning and memory`.

---

## Phase 1 — Single-provider search *(L)*

**Goal:** Prove one real search works end-to-end with clean domain types. **No cache, no offers, no watch, no frontend.**

**Depends on:** Phase 0; Pre-flight P1 (Provider 1 chosen, fixtures captured).

**Deliverables**
- Domain: `money.py`, `timeutil.py`, `flight.py` (`SearchQuery`, `Segment`, `FlightOffer`, `itinerary_key`), errors.
- Airport reference (IATA → IANA tz, country) via library.
- **Fake provider** (deterministic fares for any route) — built **first**, so everything is testable without quota.
- Provider 1 adapter (concrete class; **no interface yet** — D2): httpx client with timeout, auth header, response parsing → normalization per Architecture §8.4.
- `POST /search` (single provider, no cache): validation (400), response schema, error mapping (502/504 when the one provider fails).
- Recorded, sanitized fixtures of a real response.
- `scripts/smoke_live.py` — one live call, prints quota used.

**Design proposal required?** Yes — *normalization rules and the price/time invariants* (short).

**Tests**
- Unit: money parsing (string → Decimal), duration/time parsing, `itinerary_key` stability, tz attachment, IATA validation, date bounds.
- Providers: adapter vs fixture → correct `FlightOffer`s; **malformed row dropped and counted; wrong currency dropped; empty result → success with zero; 429; timeout; 5xx; invalid JSON.**
- API: validation errors, success shape, 502/504 mapping.

**Exit criteria**
- [ ] `POST /search` returns real Provider 1 results for a real route once via `smoke_live` (quota noted); all other tests offline.
- [ ] Every failure test above passes.
- [ ] Prices are `Decimal`/strings; datetimes tz-aware — verified by tests.
- [ ] `learning.md`: entries for domain modeling, normalization, timeouts, and at least one real bug/surprise from the actual response shape.

**Learning focus:** REST/async HTTP, DTO vs domain types, normalization, timeouts, money and time correctness, mocking external APIs, reading vendor docs vs reality.

**Socratic question:** *"The provider says price `7200`. Per passenger or total? Taxes included? What do you do if the docs don't say?"*

**Commits:** `feat: domain types and money helpers`, `feat: fake provider`, `feat: provider 1 adapter with normalization`, `feat: search endpoint`, `test: adapter failure paths`.

---

## Phase 2 — Provider abstraction + second provider *(M)*

**Goal:** Introduce the `FlightProvider` port **because a second concrete case now exists** (D2), and prove the abstraction by adding Provider 2 without touching upper layers.

**Depends on:** Phase 1; Pre-flight P1 (Provider 2 chosen).

**Deliverables**
- `FlightProvider` Protocol in `domain/ports.py`; `ProviderError` hierarchy; `ProviderConfig`; provider registry from `ENABLED_PROVIDERS`.
- Refactor Provider 1 to the port (behavior unchanged — tests prove it).
- Provider 2 adapter (its JSON is *different*; that's the point).
- **Shared contract test suite** parametrized over every adapter (Fake, P1, P2, optionally Duffel-sandbox): invariants on `FlightOffer` (tz-aware, Decimal, currency, `stops == len(segments)−1`, deterministic ids).
- Self-transfer flag + default exclusion.
- `/search` queries providers **sequentially** for now (concurrency is Phase 3).

**Design proposal required?** Yes — *the port: what belongs in the interface and what doesn't.*

**Tests:** contract suite; adapter-specific fixtures; regression from Phase 1.

**Exit criteria**
- [ ] Adding Provider 2 required changes only in `infra/providers/` + config (show the diff).
- [ ] Contract suite passes for all adapters.
- [ ] Upper layers contain no provider names.
- [ ] `learning.md` documents the *differences* between the two vendors' JSON and how the port absorbed them; notes anything the interface got wrong and how it was adjusted.

**Learning focus:** interfaces/Protocols, adapter pattern, dependency inversion, polymorphism, "rule of two", contract testing.

**Socratic question:** *"What would you have gotten wrong if you'd designed the interface before writing Provider 1?"*

**Commits:** `refactor: extract flight provider port`, `feat: provider 2 adapter`, `test: provider contract suite`.

---

## Phase 3 — Aggregation, resilience, dedupe *(L)*

**Goal:** Turn a loop into a fault-tolerant fan-out.

**Depends on:** Phase 2.

**Deliverables**
- `AggregationService`: concurrent fan-out (`asyncio.timeout` global budget + per-provider timeout), `_run_one` that never raises (typed exceptions → `ProviderResult`), per-provider semaphore.
- `ProviderResult`/`ProviderStatus`; response `metadata.providers`, `partial_results`.
- Merge + **dedupe** by `(itinerary_key, channel)`; `price_discrepancy` flag (> 3 %).
- Status semantics: 200 / 502 / 504.
- Fake provider **chaos modes** (`slow`, `timeout`, `500`, `429`, `malformed`, `empty`, `wrong_currency`) selectable via config/test parameter.
- Baseline sort by list price (formal ranking in Phase 6).

**Design proposal required?** Yes — *timeout/budget model, cancellation, what "partial" means.*

**Tests**
- One slow provider (10 s) + one fast (400 ms) → response at ≈ budget with fast results and `TIMEOUT` for the slow one.
- Each chaos mode; all-fail → 502; all-timeout → 504; empty ≠ failure.
- Cancellation: no orphaned tasks; `CancelledError` propagates.
- Dedupe: identical itinerary from two providers; discrepancy flagged.
- Concurrency proof: total latency ≈ max, not sum (timing test with fakes).

**Exit criteria**
- [ ] Demo: with a chaos flag one provider fails and `/search` still returns 200 with `partial_results=true`.
- [ ] Measured: 2 providers × 1 s each complete in ≈ 1 s (recorded).
- [ ] **Architecture review #1** and **Engineer's Eye #1** written in `learning.md`.
- [ ] `learning.md` covers asyncio concurrency, timeouts as control flow, fault isolation, graceful degradation.

**Learning focus:** asyncio, `gather`/TaskGroup semantics, timeouts vs cancellation, fault isolation, distributed-systems thinking.

**Socratic question:** *"Provider A takes 10 s, Provider B 400 ms. What does the user get, and when? What happens to A's request?"*

**Commits:** `feat: concurrent aggregation with budgets`, `feat: provider result statuses`, `feat: dedupe and discrepancy`, `test: chaos modes`.

---

## Phase 4 — Redis caching, rate limiting, quota guard *(L)*

**Goal:** Make search fast and make quota safe. **Measure**, don't claim.

**Depends on:** Phase 3.

**Deliverables**
- `FareCache` (per-provider slices; key `fare:v1:…`; fresh/stale/miss; hard TTL; JSON serialization with string money; **no pickle**).
- Stale-while-revalidate: serve stale, schedule background refresh (BackgroundTasks) guarded by Redis lock **and** quota guard; stale-if-error.
- Negative cache for `RATE_LIMITED`/`UPSTREAM_ERROR`/`QUOTA_EXHAUSTED`.
- In-process single-flight for identical concurrent fetches.
- Token bucket (Redis + Lua) per provider; **quota guard** with soft limit; per-provider semaphore (from Phase 3).
- User/IP limiter for `/search` (429 + `Retry-After`).
- `ref:v1:{offer_id}` storage for later handoff.
- Freshness fields in the response (`oldest_data_at`, per-provider `fetched_at`, `origin`).
- `scripts/bench_search.py` (cold vs warm; fakes with fixed latency, optionally one live cold call).
- Redis-down behavior per Architecture §10.4/§11.

**Design proposal required?** Yes — *key design, TTL/freshness policy, stampede handling, failure behavior of limiter vs cache.*

**Tests**
- Cache: hit-fresh (no provider call), stale (served + refresh scheduled once), miss, stale-if-error, corrupt value → miss, key includes cabin/currency/passengers (no cross-contamination).
- Limiter: burst then deny; refill over time (use time control); atomicity under concurrency.
- Quota: hard stop at limit; counters persist across restarts (AOF).
- Redis unavailable: cache bypassed; quota guard fails closed; documented outcome.
- Stampede: 50 concurrent identical cold requests → 1 provider call (single process).

**Exit criteria**
- [ ] **Recorded numbers in `learning.md`:** cold search time vs warm search time (p50/p95), how measured, on what machine.
- [ ] Warm p95 meets NFR-1 or the gap is explained.
- [ ] Quota can be shown decrementing; hard-stop demonstrated.
- [ ] **Architecture review #2** written.
- [ ] Explained in own words: why cache raw fares, not priced results (D4).

**Learning focus:** caching, TTL, cache invalidation, consistency vs freshness, stampedes, rate limiting algorithms, atomic operations, latency measurement.

**Socratic question:** *"Fifty users search the same cold route simultaneously. How many provider calls do you make, and why does that matter more here than on a normal website?"*

**Commits:** `feat: redis fare cache with swr`, `feat: token bucket limiter`, `feat: provider quota guard`, `feat: search freshness metadata`, `test: cache and limiter failure modes`, `docs: benchmark results`.

---

## Phase 5 — Users, payment methods, offer matching *(L)*

**Goal:** Turn list prices into effective prices with a **data-driven** offer engine.

**Depends on:** Phase 4 (offers apply *after* the cache).

**Deliverables**
- Auth: register/login, Argon2, JWT, `get_current_user` (optional + required variants).
- Tables (each with the §15 reasoning in `learning.md` first): `users`, `payment_methods`, `card_offers`. Alembic migrations (read and edit autogenerate output).
- `data/banks.yaml` (canonical slugs/aliases) validated at API and seed time.
- `payment_methods` API (metadata only; `extra=forbid`; digit-run rejection).
- `data/card_offers.seed.yaml` with **≥ 20 real offers** (from Pre-flight P2) + idempotent `seed_card_offers.py` (upsert on `external_key`) + `GET /card-offers` (with `verified_at`, `stale`).
- `domain/offer_matching.py` per Architecture §12 (pure): eligibility pipeline, `Decimal` discount, rounding down, best selection, `considered`, assumptions.
- In-memory offer snapshot (60 s) + degrade path (`offers.available=false`).
- `SearchService` integration: offers applied **after** cache, per user; response shows list/discount/effective/provenance.
- Booking-channel assumption (`airline_direct`) surfaced in `assumptions[]`.

**Design proposal required?** Yes — *schema (with indexes/constraints), eligibility model, channel assumption, what's deliberately not modeled.*

**Tests**
- Table-driven: `₹4,999` vs `₹5,000` at `min_spend 5,000`; 20 % with cap ₹1,000 at ₹4,000 / ₹8,000 / ₹20,000; expired; not yet valid; wrong bank; wrong tier; wrong network; wrong payment type; wrong channel; wrong airline; domestic vs international; currency mismatch; two eligible → larger wins; tie-break determinism; offer expiring today (IST boundary).
- Property tests: `0 ≤ discount ≤ list_price`; `effective + discount == list`; order-independence; ineligible ⇒ 0.
- Security: card-number-like input rejected; cross-user isolation; no secrets/PAN in logs.
- Integration: constraints (dup payment method → 409), seed idempotency, cache never contains personalized data.
- **Proof of the data-driven claim:** add offer #21 by editing YAML + reseed only — no code change.

**Exit criteria**
- [ ] Real offer applied end-to-end for a declared card on a real (fixture) fare; and a case where it correctly does **not** apply.
- [ ] 100 % branch coverage on `offer_matching.py`, `money.py`.
- [ ] Offers show `source_url` + `verified_at`; stale flag works.
- [ ] Explained: why `Decimal`, why round down, why offers run after the cache.

**Learning focus:** domain modeling, rule engines as data, monetary math, temporal validity, authN/authZ, password hashing, schema design (nullable uniqueness), reference-data normalization.

**Socratic question:** *"Fare ₹10,000. Offer A: 20 % off, capped ₹1,500. Offer B: flat ₹1,200. Which wins at ₹6,000? At ₹10,000? Why did we not cache the answer?"*

**Commits:** `feat: auth and users`, `feat: payment methods api`, `feat: card offers schema and seed`, `feat: offer matching engine`, `feat: effective price in search`, `test: offer eligibility and properties`.

---

## Phase 6 — Ranking *(S)*

**Goal:** Deterministic, explainable ordering.

**Depends on:** Phase 5.

**Deliverables**
- `domain/ranking.py` (pure): key `(effective_price, duration_minutes, stops, departure_utc, id)`; `sort_by` options (`effective_price`, `price`, `duration`, `stops`, `departure_time`).
- Response `metadata.ranking` echoing rule and tie-breakers.
- Remove the Phase 3 temporary sort.

**Design proposal required?** No — short explanation of why no composite "best" score.

**Tests:** stable ordering on ties (shuffle input → same output); each `sort_by`; mixed nonstop/1-stop; equal prices; property: output is a permutation of input and sorted by key.

**Exit criteria**
- [ ] Shuffling input never changes output order.
- [ ] Each result's position is explainable from the echoed rule.
- [ ] **Architecture review #3** and **Engineer's Eye #2** written.

**Learning focus:** deterministic sorting, separating business rules from routes, explainability.

**Socratic question:** *"Two flights, same effective price, same duration. What decides the order — and why must something decide?"*

**Commits:** `refactor: isolate ranking service`, `feat: sort options`, `test: ranking determinism`.

---

## Phase 7 — Redirect / handoff *(M)*

**Goal:** Send the traveler to book — safely, with no booking logic on our side.

**Depends on:** Phase 6; Pre-flight P3.

**Deliverables**
- `data/booking_channels.yaml` (id, name, `allowed_hosts`, optional `url_template`) + loader/validator.
- `provider.resolve_booking()` for real providers (lazy, cached 10–15 min, quota-guarded).
- `HandoffService` + `POST /handoff {result_id}`: lookup `ref:v1:{id}` → resolve → choose channel (prefer airline_direct) → **validate https + allowlisted host** → respond `{url, channel, price_at_search, data_age_s, price_at_link?, price_changed?, disclaimer}`.
- `410` when the reference expired; `422` when URL fails validation; `502` when resolution fails.
- (Could) re-evaluate offers for the resolved channel (FR-H4).

**Design proposal required?** Yes — *why lazy resolution, why JSON not a 302, trust boundary.*

**Tests:** allowlist accept/reject (lookalike domains, `http://`, userinfo tricks like `https://good.com@evil.com`, unicode/punycode hosts); expired ref → 410; provider link failure → 502; idempotent repeat call uses cache; no outbound fetch of returned URLs (assert).

**Exit criteria**
- [ ] Live demo (one quota-counted call): click through to a real booking/results page on an allowlisted host.
- [ ] Attempted redirect to a non-allowlisted host is refused (demonstrated).
- [ ] Quota impact of handoff documented.

**Learning focus:** responsibility boundaries, trust boundaries, URL validation, open-redirect/SSRF, lazy evaluation vs eager cost.

**Socratic question:** *"Why is `https://airline.com.evil.io` a bug you must test for, and how does a naive `startswith` check fail?"*

**Commits:** `feat: booking channel config`, `feat: provider booking link resolution`, `feat: handoff endpoint`, `test: url allowlist attacks`.

---

## Phase 8 — Price watch *(L)*

**Goal:** A background system that genuinely runs underneath the API.

**Depends on:** Phase 7 (or 6 — handoff isn't required, but caching/quota are).

**Deliverables**
- Tables (with reasoning first): `watched_routes`, `price_history`, `notification_log`.
- `WatchService` (pure-ish logic): create (cap per user, unique partial index), list, delete, history, drop decision.
- API: `POST /watch`, `GET /watch`, `DELETE /watch/{id}`, `GET /watch/{id}/history`.
- Celery app, Beat schedule; tasks `scan_watches` (group by route; deactivate past-date watches) and `check_watch` (cache-first search → history → decision → idempotent notify).
- Notifier: SMTP to Mailpit in dev (or log-only if OD-3 decides so).
- Sync engine (psycopg 3) for workers; `asyncio.run` at the task edge (D15).
- Retries with backoff, `acks_late`, `soft_time_limit`.

**Design proposal required?** Yes — *idempotency, scheduling, quota interaction, async-in-Celery approach.*

**Tests**
- Unit: drop rule (`L ≤ target`; `≥ max(₹300, 5 %)` from reference; below thresholds → no alert; reference updates after alert).
- Integration: run the task twice → one history row per bucket and **one** notification; simulated worker crash mid-task → safe re-run; duplicate delivery; quota-denied → recorded, no crash loop; past-date watch deactivated; per-user cap → 422.
- Async-in-Celery smoke test (no "different loop" errors).

**Exit criteria**
- [ ] Demo: create a watch, lower the fake provider's price, trigger the task, see exactly one email in Mailpit and one history row.
- [ ] Worker + Beat actually running in Compose.
- [ ] Explained: at-least-once delivery ⇒ idempotency; why history stores list price.

**Learning focus:** background jobs, scheduling, idempotency, retries, task failure modes, distributed workers, event loops.

**Socratic question:** *"The worker crashes after sending the email but before saving state. What happens on redelivery, and what stops a duplicate alert?"*

**Commits:** `feat: watch schema and api`, `feat: celery app and beat`, `feat: watch check task with idempotent notify`, `test: watch idempotency and retries`.

---

## Phase 9 — Observability *(M)*

**Goal:** Be able to answer "why was that search slow / wrong?" from the outside.

**Depends on:** Phases 3–8.

**Deliverables**
- Metrics per Architecture §20; `/metrics` restricted; quota-remaining gauge.
- One structured summary log line per search (request id, providers, cache states, counts, offers matched, timings).
- Correlation id propagated into worker logs where possible.
- Optional Compose profile `obs`: Prometheus + Grafana with 1 simple dashboard (provider latency, error/timeout rate, cache hit ratio, quota remaining).
- Final benchmark run recorded.

**Design proposal required?** Short — *what to measure and why (RED/USE-style thinking).*

**Tests:** metric increments on success/timeout/rate-limit; log redaction test (keys, tokens, card-like digits never appear); high-cardinality label guard (no user ids/routes as labels).

**Exit criteria**
- [ ] Given a slow request id, you can locate the responsible provider/stage from logs alone (demonstrated; written up as a debugging playbook).
- [ ] Cache hit ratio and provider timeout rate visible.
- [ ] **Architecture review #4** and **Engineer's Eye #3 (production-readiness)** written.

**Learning focus:** observability vs monitoring, metrics types, cardinality, structured logging, debugging production systems, performance analysis.

**Socratic question:** *"Users say search 'feels slow sometimes.' Which three numbers do you look at first, and why not the average?"*

**Commits:** `feat: prometheus metrics`, `feat: search summary logging`, `chore: observability compose profile`, `test: log redaction and metrics`.

---

## Phase 10 — Frontend *(L)*

**Goal:** A thin, honest UI that makes the backend legible in a demo. **Backend contract freezes** now; changes go through OpenAPI.

**Depends on:** Phases 1–9 stable; `Design.md`.

**Gate:** Confirm the stack (default React + Vite + TypeScript + Tailwind + TanStack Query + Recharts; HTMX+Jinja is the acknowledged lighter alternative). Record in `Memory.md`.

**Deliverables**
- Vite project; TS types generated from OpenAPI; design tokens from `Design.md` as CSS variables.
- Screens: Search + Results (fare ledger rows, freshness badge, provider-status strip, partial/stale/error/empty states), Payment methods, Watches + price-history chart, Auth.
- **Handoff:** open a blank tab synchronously in the click handler, then set its location after `POST /handoff` resolves (avoids popup blockers); `rel="noopener noreferrer"`.
- Accessibility pass (keyboard, focus, contrast, reduced motion) per `Design.md` §12.
- The UI never computes money.

**Design proposal required?** No — follow `Design.md`; explain state management choices briefly.

**Tests:** component tests for money/time formatting (`en-IN` grouping), state rendering (partial, stale, empty, rate-limited), handoff flow (popup-blocker-safe); one end-to-end happy path against the Fake provider.

**Exit criteria**
- [ ] The demo script (PRD §13) runs entirely from the UI.
- [ ] Every response state in `Design.md` §8 is reachable and visually verified.
- [ ] Contrast/keyboard checks pass; no layout break at 360 px width.
- [ ] Font glyph check for `₹` and tabular numerals done and recorded.

**Learning focus:** consuming a typed API contract, state vs server cache, honest UX for uncertain data, accessibility, browser popup rules.

**Commits:** `feat: frontend scaffold and tokens`, `feat: search results ui`, `feat: payment methods ui`, `feat: watches and history chart`, `test: frontend states`.

---

## Phase 11 — Hardening, README, demo *(M)*

**Goal:** Make it something you can confidently present.

**Deliverables**
- README complete per `Rules.md` §19 (incl. limitations, price accuracy, security, the Amadeus shutdown context, provider quotas).
- Security checklist run: `pip-audit`, secret scan, dependency review, CORS, rate limits, log redaction, DB roles, `.env` hygiene, confirm no card data paths.
- Offer dataset refresh: re-verify all ≥ 20 offers; update `verified_at`; remove/expire stale.
- Demo rehearsal with a **reserved quota budget** (do not burn it in development).
- Final architecture diagram; final benchmarks.
- **Interview pack in `learning.md`:** 5-minute walkthrough, top 5 design decisions with alternatives, top 3 failures and lessons, "what I'd do next", answers to likely questions (why cache raw fares? why per-provider cache? how do you keep quota safe? how do you know an offer is valid?).
- Retrospective: what surprised me, what I'd design differently, what I can now do alone.

**Exit criteria**
- [ ] A friend can clone, `docker compose up`, run the demo script, and read the README without your help.
- [ ] You can explain every phase's architecture **without opening the code**.
- [ ] All PRD §13 success criteria demonstrated.
- [ ] Tag `v1.0`.

**Socratic question (final):** *"Design a hotel-deal aggregator. Which parts of this system do you reuse unchanged, which change, and which decisions were specific to flights?"*

---

## Reviews & journals schedule

| After phase | Architecture review | Engineer's Eye |
|---|---|---|
| 3 | #1 | #1 |
| 4 | #2 | – |
| 6 | #3 | #2 |
| 9 | #4 | #3 (production-readiness) |
| 11 | Final | – |

Each review answers: *What is good? What is weak? What will break first? What should we NOT change yet? What should we change now?*

## Scope-control notes
- **Optional / drop first if time is short:** Provider 3 / Duffel adapter, Grafana dashboards, FR-H4 (channel re-evaluation), price-history chart polish, FR-F8 (stacking).
- **Never drop:** Fake provider, quota guard, failure-path tests, `learning.md`, freshness/assumption disclosure, the "not a booking platform" statement.
- **Round-trip / multi-city / flexible dates:** not in v1. Adding them requires a design proposal (they change dedupe, offers, and cache keys).
