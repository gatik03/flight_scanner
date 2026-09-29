# PRD — Flight Deal Aggregator & Offer-Matcher

| | |
|---|---|
| **Version** | 1.0 |
| **Date** | 2026-09-29 |
| **Status** | Approved baseline for Phase 0 |
| **Companion docs** | `Architecture.md` · `Rules.md` · `Phases.md` · `Design.md` (all in `docs/`) |
| **Working title** | Flight Deal Aggregator (repo: `flight-deal-aggregator`) |

> **Read this first — the brief changed underneath us.**
> The original brief named *Amadeus Self-Service* as the primary data source. Amadeus decommissioned that portal on **2026-07-17**; only Enterprise (sales-contract) access remains. Every other "obvious" alternative is either invite-only, partner-gated, or sandbox-only (see §11). This PRD is therefore written **provider-agnostic**: the product requirements do not depend on any single vendor, and *choosing* the two real providers is the first task of the project (Phase Pre-flight, task P1), not an assumption.

---

## 1. Summary

A **backend-first flight metasearch platform**. For a route and date it:

1. fetches fares from multiple independent providers in parallel,
2. normalizes them into one schema,
3. works out the **effective price** each traveler would pay after applying bank/card offers for the payment methods *they declare they hold*,
4. ranks by that effective price, and
5. hands the traveler off to the airline/OTA's own booking page.

It never touches money, never stores card numbers, and is honest about how fresh its prices are.

**Elevator pitch (interview version):**
> "A fault-tolerant flight metasearch backend that normalizes multiple provider APIs into one canonical schema, caches with Redis, applies data-driven card offers, ranks fares by real out-of-pocket cost, and asynchronously watches saved routes for price drops."

## 2. Problem

- Comparing fares means opening several airline sites and OTAs in separate tabs, each with a different UI, and repeating for every date.
- The price shown is rarely what a *specific* traveler pays: bank- and card-linked discounts exist but are scattered across dozens of bank pages and are never factored into any comparison tool. Travelers miss them or discover them at checkout.
- No system aggregates fares, computes the **true out-of-pocket cost per payment method held**, and sends the traveler to book — without taking on liability for their money or the booking.

## 3. Objectives

### 3.1 Product objective
For a given route and date, show a ranked list of fares from ≥ 2 independent sources with **list price**, **applied card offer**, and **"you pay"** price, then redirect to the provider's booking flow.

### 3.2 Engineering-learning objective (equal weight)
The project is also a **structured apprenticeship in software architecture**. Success is *not* "the app works"; success is that the developer can independently design the next system. Concretely: every meaningful change is documented in `learning.md` (see `Rules.md`), including failures and dead ends.

> If the two objectives conflict, **learning wins over speed** — but never over correctness or safety.

## 4. Target users

| Persona | Description | Needs from the product |
|---|---|---|
| **P1 — Budget-conscious Indian traveler** (primary) | Compares routes/dates; holds 2+ cards (e.g., a premium credit card and a debit card). | Know *which card* saves the most on *which fare*; trust the number; click through and book. |
| **P2 — The developer (audience of one)** | Builds, demos, and explains the system. | "Correct and demoable for any real route." Clear architecture, real failures handled, interview-ready story. |
| **P3 — Interviewer / reviewer** (implicit) | Reads the README, runs the demo, probes decisions. | Evidence of engineering judgment: bounded scope, honest limitations, tests, measured performance. |

Design decisions favor P2/P3 credibility over P1 scale. There is **no** multi-tenant, high-traffic, or monetization target.

## 5. Scope

### 5.1 In scope (v1)
- One-way fare search, 1–9 adults, selectable cabin, currency **INR**.
- **2–3 providers**: ≥ 2 real independent sources + 1 deterministic fake (for dev/tests/chaos).
- Parallel fan-out with per-provider timeouts and partial results.
- Normalization to a canonical `FlightOffer`.
- Redis caching (stale-while-revalidate), per-provider rate limiting, **quota guard**.
- Users, declared payment methods (metadata only), a **curated dataset of ≥ 20 real card offers** stored as data.
- Offer matching → effective price; explainable ranking.
- Deep-link handoff to the provider/airline/OTA.
- Price-drop watch with a scheduled Celery worker, price history, alerts.
- Observability (structured logs + metrics), tests, Docker Compose.
- A thin frontend, built **after** the backend is stable.

### 5.2 Explicitly out of scope (state this in the README)
| Not doing | Why (this is a strength, not a limitation) |
|---|---|
| Payment processing / checkout | We never touch money → no PCI-DSS scope, no fraud liability. |
| Storing card numbers, CVV, expiry | Only `network + issuing bank + product tier + credit/debit` metadata. |
| Issuing tickets / creating bookings | Provider's job. Keeps responsibility boundary crisp. |
| Seat selection, baggage add-ons, itinerary changes | Provider's job after redirect. |
| Guaranteeing the price at click-through | Cached comparison ≠ live checkout. Said out loud in the UI and README. |
| Scraping airline/OTA sites ourselves | Legal/ToS/fragility risk. If a provider is scraping-derived, that risk is the provider's and is disclosed (see R6). |
| Currency conversion | v1 is INR-only; non-INR results are dropped and counted. |

### 5.3 Later / optional ("Could")
Round-trip and multi-city; flexible-date grids; offer stacking; base-fare-only offer rules; historical price chart beyond watched routes; SSE progressive results; multi-currency; admin UI for offers; user-facing account deletion.

## 6. Core user journeys

**J1 — Search and compare.** Enter DEL → BOM, 15 Oct 2026, 1 adult, economy → see ranked fares, each with list price, card offer, **You pay**, source, and "checked 42 seconds ago". If a provider timed out: "2 of 3 sources responded — results may be incomplete."

**J2 — Declare cards.** Add "HDFC · Regalia · Visa · Credit" (never a card number). Search results now show effective prices for the best-matching card.

**J3 — Hand off to book.** Click **Book on IndiGo** → system resolves the provider's booking URL, validates it, opens it in a new tab with a note: "Price may differ on IndiGo's site."

**J4 — Watch a route.** Save DEL → BOM on 15 Oct with target ₹6,000. A background job re-checks on a schedule, records history, and emails when the price drops meaningfully (once per drop).

## 7. Key user stories & acceptance criteria

**US-1 Compare fares across sources**
- *Given* a valid route/date, *when* I search, *then* results come from every enabled provider that responds within the time budget, each labeled with its provider.
- *Given* one provider times out, *when* I search, *then* I still get 200 with the other providers' results and `partial_results=true`, naming the failed provider and reason.
- *Given* all providers fail, *then* I get a 502/504 with a clear, non-technical explanation and per-provider reasons.

**US-2 See the real price for my cards**
- *Given* I hold HDFC Regalia and an offer "₹750 off on fares ≥ ₹5,000 at airline X, valid until 30 Sep", *when* a ₹7,200 fare on airline X is returned on 20 Sep, *then* the result shows list ₹7,200, discount ₹750, **You pay ₹6,450** and names the card and offer.
- *Given* the fare is ₹4,999 (below minimum spend) or the offer expired or I hold a different card tier, *then* **no** discount is applied.
- *Given* two eligible offers, *then* the larger discount is applied and the other is listed as considered.

**US-3 Trust the freshness**
- Every response shows when prices were fetched; stale data is labeled as stale; nothing is described as "live" unless it was fetched during this request.

**US-4 Book without friction or risk**
- *When* I click "Book on X", *then* the destination host is on the allowlist, uses HTTPS, and the system never asks me for payment details.

**US-5 Get told about drops**
- *Given* a watch, *when* the price falls by ≥ max(₹300, 5%) versus the last reference price (or hits my target), *then* I get exactly one notification for that drop, even if the job retries.

## 8. Functional requirements

Priority: **M**ust / **S**hould / **C**ould. Phase = where it lands (see `Phases.md`).

### A. Search & aggregation
| ID | Requirement | Pri | Phase |
|---|---|---|---|
| FR-A1 | Accept origin (IATA), destination (IATA), departure date, passengers (1–9), cabin (default ECONOMY). | M | 1 |
| FR-A2 | Fan out to all enabled providers **concurrently**, each with its own timeout, under a global time budget (default 5 s). | M | 3 |
| FR-A3 | Return whatever responded in time; include per-provider status, latency, count; set `partial_results`. | M | 3 |
| FR-A4 | Error out only when **no** provider yields usable data (fresh, live, or stale-if-error). | M | 3 |
| FR-A5 | Validate input: 3-letter IATA, origin ≠ destination, date not in the past (origin-airport local date) and within booking horizon (default 330 days), passengers range. | M | 1 |
| FR-A6 | Exclude self-transfer / separate-ticket itineraries by default; report how many were excluded. | S | 2 |

### B. Normalization
| ID | Requirement | Pri | Phase |
|---|---|---|---|
| FR-B1 | All provider output is mapped to canonical `FlightOffer` inside the provider adapter; nothing downstream sees provider JSON. | M | 1–2 |
| FR-B2 | **Price rule (documented, single):** `list_price` = all-in payable total for *all* passengers, taxes and mandatory fees included, in the requested currency. Results that cannot satisfy this are dropped and counted. | M | 1 |
| FR-B3 | All datetimes timezone-aware; local departure/arrival keep their IANA zone; UTC used for comparison, sorting, and storage. | M | 1 |
| FR-B4 | Deterministic `itinerary_key` (ordered segment carrier+number+departure UTC). | M | 2 |
| FR-B5 | Dedupe: same `itinerary_key` + same booking channel → keep lowest price. Same itinerary via different providers → keep both, flag `price_discrepancy` if they differ by > 3 %. | M | 3 |

### C. Caching
| ID | Requirement | Pri | Phase |
|---|---|---|---|
| FR-C1 | Cache normalized fares **per provider** keyed by (provider, origin, destination, date, adults, cabin, currency). | M | 4 |
| FR-C2 | Fresh → serve, no provider call. Stale → serve immediately + refresh in background. Miss → fetch. | M | 4 |
| FR-C3 | Stale-if-error: if a refresh fails, keep serving stale data until the hard TTL. | S | 4 |
| FR-C4 | Every response exposes `fetched_at` and age per provider and an overall "oldest data" timestamp. | M | 4 |
| FR-C5 | Cache holds provider-level fares only — **never** user-personalized results. | M | 4 |

### D. Rate limiting & quota
| ID | Requirement | Pri | Phase |
|---|---|---|---|
| FR-D1 | Every outbound provider call passes through a limiter configured from **that provider's documented limits**. | M | 4 |
| FR-D2 | **Quota guard:** hard-stop provider calls at a configured budget (free tiers are tiny and may be one-time). | M | 4 |
| FR-D3 | Per-user/IP rate limit on `/search`, `/handoff`, `/auth/login` (a cold search *costs quota*, so abuse is expensive). | S | 4–5 |
| FR-D4 | Live provider calls are **off by default** in dev/test/CI; enabled only via explicit flag. | M | 0–1 |

### E. Users & payment methods
| ID | Requirement | Pri | Phase |
|---|---|---|---|
| FR-E1 | Register/login with email + password; short-lived JWT access token. | M | 5 |
| FR-E2 | CRUD declared payment methods: card network, issuing bank (canonical slug), product tier, credit/debit. | M | 5 |
| FR-E3 | Payment data is **metadata only.** API rejects unknown fields and any value resembling a card number (12–19 digits) in any free-text field. | M | 5 |

### F. Offer matching
| ID | Requirement | Pri | Phase |
|---|---|---|---|
| FR-F1 | Offers are **rows of data** (`card_offers`); adding an offer is never a code change. | M | 5 |
| FR-F2 | Seed ≥ 20 **real** offers, each with `source_url` and `verified_at`. | M | 5 |
| FR-F3 | Eligibility checks: active, validity window, bank, network, product tier, payment type, booking channel, airline, route scope (domestic/international), minimum spend. | M | 5 |
| FR-F4 | Discount types FLAT and PERCENT with optional cap; `Decimal` math; conservative rounding (round **down**). | M | 5 |
| FR-F5 | Apply the single best eligible offer per fare; expose the alternatives considered. | M | 5 |
| FR-F6 | Response shows list price, discount, effective price, offer provenance (source URL, verified date) and any modeling assumptions. | M | 5 |
| FR-F7 | Flag offers not re-verified within N days (default 30). | S | 5 |
| FR-F8 | Stacking: schema-ready (`stackable`), engine inactive until a real offer needs it. | C | — |

### G. Ranking
| ID | Requirement | Pri | Phase |
|---|---|---|---|
| FR-G1 | Default order: effective price ↑, duration ↑, stops ↑, departure (UTC) ↑, id ↑ (deterministic). | M | 3/6 |
| FR-G2 | Selectable `sort_by`: `effective_price`, `price`, `duration`, `stops`, `departure_time`. | S | 6 |
| FR-G3 | Response states the sort rule. No opaque "best flight" score. | S | 6 |

### H. Handoff
| ID | Requirement | Pri | Phase |
|---|---|---|---|
| FR-H1 | "Book on X" resolves the provider's booking URL at click time; no booking or payment logic on our side. | M | 7 |
| FR-H2 | URL must be `https` and its host on the booking-channel allowlist; else refuse. | M | 7 |
| FR-H3 | Handoff response includes URL, channel, price seen at search time, data age, and `price_changed` if the provider reports a different price at link time. | S | 7 |
| FR-H4 | Re-evaluate offers for the *actual* resolved channel. | C | 7 |

### I. Price-drop watch
| ID | Requirement | Pri | Phase |
|---|---|---|---|
| FR-I1 | Save a watch: route, date, passengers, cabin, optional target price. | M | 8 |
| FR-I2 | Scheduled job re-checks watches, stores history. | M | 8 |
| FR-I3 | "Meaningful drop" = new lowest list price ≤ target, **or** drop ≥ max(₹300, 5 %) vs the reference price. Notify **once** per drop (idempotent). | M | 8 |
| FR-I4 | `GET /watch/{id}/history`. | M | 8 |
| FR-I5 | Cap active watches per user (default 5) — quota protection. | M | 8 |

### J. Observability
| ID | Requirement | Pri | Phase |
|---|---|---|---|
| FR-J1 | Structured JSON logs with request id; secrets and PII redacted. | M | 0 |
| FR-J2 | Liveness + readiness endpoints. | M | 0 |
| FR-J3 | Metrics: request latency, per-provider latency/error/timeout, cache hit ratio, results count, offers matched, quota remaining, worker outcomes. | S | 9 |

### K. Frontend (after backend stabilizes)
| ID | Requirement | Pri | Phase |
|---|---|---|---|
| FR-K1 | Search form, ranked results with fare "ledger", freshness + partial-results banners, handoff button. | S | 10 |
| FR-K2 | Payment-method manager (with visible "we never ask for card numbers"). | S | 10 |
| FR-K3 | Watch list + price-history chart. | S | 10 |

## 9. Non-functional requirements

| ID | Category | Requirement / target | How we prove it |
|---|---|---|---|
| NFR-1 | Performance | Warm (fully cached) search: server-side **p95 ≤ 250 ms** on the dev machine. Cold: completes at the global budget (default 5 s) + ≤ 500 ms overhead. | `scripts/bench_search.py`; numbers recorded in `learning.md`. *Measured, not claimed.* |
| NFR-2 | Resilience | One provider failing never fails the search. Redis cache outage → bypass cache, keep working. DB outage → search still works with list prices and `offers_unavailable=true`. | Chaos tests using the fake provider; integration tests with services stopped. |
| NFR-3 | Freshness honesty | Never present cached data as live. Age always visible. | API contract tests; UI review. |
| NFR-4 | Privacy/security | No PAN/CVV/expiry anywhere (DB, logs, requests). Secrets only in env. Passwords hashed (Argon2-class). Outbound calls only to allowlisted hosts. | Schema tests, log-redaction tests, dependency audit, checklist in Phase 11. |
| NFR-5 | Quota safety | Never exceed configured provider budgets; no live calls in tests/CI by default. | Quota guard tests; `ALLOW_LIVE_PROVIDERS=false` default. |
| NFR-6 | Correctness | Money exact (`Decimal`); effective ≤ list; effective ≥ 0; boundary conditions covered. | Table-driven + property-based tests; 100 % branch coverage on money/offer/ranking modules. |
| NFR-7 | Testability | Domain logic is pure (no I/O). CI needs no external network. | Layering rule enforced in review; CI config. |
| NFR-8 | Maintainability | New provider = one adapter + config. New offer = one data row. New booking channel = one config entry. | Demonstrated in Phases 2, 5, 7. |
| NFR-9 | Reproducibility | `docker compose up` starts everything; one command runs tests. | README setup verified from a clean clone. |
| NFR-10 | Accessibility (UI) | WCAG 2.2 AA target; keyboard operable; reduced-motion respected. | Checklist in `Design.md`. |

## 10. Assumptions & constraints

1. **Single developer**, part-time; each phase must leave a working, committed system.
2. **Free/low-cost tiers only.** Provider quotas may be as small as a few hundred *lifetime* calls. Architecture must make quota the scarcest resource, not CPU.
3. **India-centric demo**: INR, Indian carriers (e.g., IndiGo, Air India, Akasa, SpiceJet — *to be confirmed available in the chosen providers*), Indian bank/card offers.
4. **Effective price assumes a booking channel.** Search results from some providers don't say *where* you'll buy (airline direct vs OTA). Unless the provider says otherwise, the effective price **assumes booking on the operating airline's own site**, and the response says so. (See Architecture D3.)
5. Offers are **manually curated**; their accuracy is bounded by verification date, which is displayed.
6. No production hosting is required; a local Docker demo is the deliverable.
7. Timezone reference for offer validity is **Asia/Kolkata (IST)** unless an offer states otherwise.

## 11. External dependencies — provider reality check (researched 2026-09-29)

> These are **vendor and third-party claims read from public pages, not verified by us.** Treat every number as unconfirmed until the Phase Pre-flight spike (P1) records real responses. Free-tier figures conflict between sources.

| Option | Access model (as reported) | Fit | Notes |
|---|---|---|---|
| **Amadeus Self-Service** | **Shut down 17 Jul 2026**; enterprise contract only | ❌ Removed | The original primary source. Do not build on it. |
| **Ignav** | Self-serve API key; reported 1,000 free requests (one-time) then ~$2 per 1,000 successful requests | ✅ Candidate P1 | Search results reportedly **don't include booking URLs**; a *separate* booking-links request returns airline/OTA URLs (and counts as a request). Response reportedly includes local time, timezone, and UTC per segment, plus a `requires_self_transfer` flag. Verify INR + Indian carriers. |
| **Google-Flights-derived APIs** (e.g., SerpApi, HasData, others) | Self-serve; small free tiers (reported ~66–250 searches/month; sources disagree) | ✅ Candidate P2 | Reseller/scraper of Google Flights data → ToS/legal/fragility risk sits with the vendor, but must be disclosed (R6). Booking options are reportedly fetched via a token in a second call. |
| **Duffel** | Test mode free; live access needs approval | ⚠️ Adapter practice only | Test mode uses **sandbox/mock airline data** → cannot satisfy "real route" demo, but excellent for contract-testing a third adapter. |
| **Kiwi.com Tequila** | Invite-only partner access | ❌ | No self-serve signup reported. |
| **Skyscanner (official)** | Commercial partner approval | ❌ | Gated by business criteria. |
| **Travelpayouts Data API** | Reported traffic thresholds (secondary source) | ❓ Evaluate in spike | Confirm current requirements. |

**Sources consulted:** phocuswire.com (Amadeus shutdown report); ignav.com docs (quickstart, booking-links, pricing, Amadeus migration guide); thunderbit.com and phptravels.com API roundups; serpapi.com and hasdata.com pricing/docs pages.

**Implication:** the demo bar "≥ 2 independent real sources" is achievable only if the spike confirms two viable providers. If it does not, the fallback (decided in Phase P1, recorded in `Memory.md`) is: 1 real provider + Fake provider + Duffel sandbox adapter, with the PRD demo bar amended honestly.

## 12. Risks & mitigations

| ID | Risk | L | I | Mitigation |
|---|---|---|---|---|
| R1 | **Provider availability** — Amadeus gone; others gated or tiny. | H | H | Spike first (P1). Provider-agnostic adapter interface. Fake provider guarantees the rest of the system is buildable and demoable regardless. |
| R2 | **Tiny quotas exhausted** by dev/tests/watches. | H | H | Live calls off by default; recorded fixtures; quota guard; cache-first everywhere; watch cap; demo budget reserved. |
| R3 | **Booking channel unknown at search time** → offer matching (which is per merchant) can't be exact. | H | M | Separate *data source* from *booking channel*; explicit assumption (`airline_direct`); channel re-evaluated at handoff. |
| R4 | **Offer data goes stale.** | H | M | `source_url` + `verified_at` per row; stale flag; monthly refresh checklist; validity windows enforced. |
| R5 | Two providers disagree on the same flight's price. | M | M | One documented price rule; `price_discrepancy` flag; never silently average. |
| R6 | Scraping-derived provider: legal/ToS/reliability. | M | M | Prefer documented APIs; treat as replaceable; disclose in README; never scrape sites directly. |
| R7 | Users expect booking-grade real-time accuracy. | H | M | Age shown everywhere; "may differ at checkout" copy; `price_changed` at handoff. |
| R8 | Bank offers have hidden terms (BIN ranges, tax exclusions, per-user caps, day-of-week, payment mode). | H | M | Seed only offers we can compute; store unmodeled terms as `terms_note` and display it; never claim eligibility beyond what's modeled. |
| R9 | Timezone/date bugs (airport-local times, IST offer windows, date rollovers). | M | H | Timezone-aware types only; airport→IANA tz lookup; explicit tests around midnight and DST-less IST vs foreign zones. |
| R10 | Over-engineering / scope creep. | M | M | `Rules.md` guardrails; phase gates; "no abstraction before the second concrete case". |
| R11 | Celery + asyncio friction (event loops, DB pools). | M | M | Design decision recorded (Architecture D15); worker tests; learning entry. |
| R12 | Learning overhead slows delivery. | M | L | Accepted by design (§3.2). Lite/Full entry rules in `Rules.md` keep it proportionate. |

## 13. Success criteria — "interview-ready" definition

The project is done when, **live**, the developer can:

1. Search a **real** route (e.g., DEL → BOM) and show a ranked list from **≥ 2 independent real sources** (or the amended bar from §11).
2. Show `providers` status with one source deliberately failing (toggle a chaos flag) and the search still succeeding.
3. Show **cold vs warm** timings with measured numbers, and the "checked N seconds ago" freshness label.
4. Apply a **real offer end-to-end** for a declared card, with source URL and verified date visible, and show a case where an offer correctly does *not* apply.
5. Click through to an **actual booking page** on an allowlisted host.
6. Show the **Celery worker** running: a watch, its history, and one alert.
7. Open `learning.md` and walk the audience through at least three real decisions, one real failure, and what they'd do differently.
8. Answer "why is X designed this way?" for every phase without reading the code.

**Demo script (5 minutes):** search → partial-results toggle → cache timing → add card → offer applied vs not applied → handoff → watch + history → metrics/log tour → `learning.md` highlight.

## 14. Open questions (tracked; resolved in `Memory.md` "Decisions")

| ID | Question | Resolve in |
|---|---|---|
| OD-1 | Which two real providers? Do they return INR and Indian carriers? | P1 |
| OD-2 | What URL/deep-link mechanism works for each carrier on the demo route? | P3 |
| OD-3 | Notification channel: email via SMTP (Mailpit in dev) vs log-only? | Phase 8 |
| OD-4 | Offer refresh cadence and owner (default: monthly manual). | Phase 5 |
| OD-5 | Frontend stack confirmation (default React + Vite + TS). | Phase 10 gate |
| OD-6 | Auth scope: multi-user (default) vs single-user mode. | Phase 5 |
| OD-7 | Do any curated offers require stacking? (default: no) | Phase 5 |

## 15. Glossary

| Term | Meaning |
|---|---|
| **FlightOffer** | One purchasable fare for an itinerary, as returned by a provider and normalized. (The original brief's `FlightOffer`.) |
| **CardOffer** | A bank/card promotion (row in `card_offers`). *Renamed from the brief's "Offer" to avoid clashing with FlightOffer.* |
| **Provider (data source)** | The API we query for fares (e.g., Ignav). Not necessarily where the traveler buys. |
| **Booking channel / merchant** | Where the traveler actually pays (airline's own site or an OTA). Card offers attach to this. |
| **list_price** | All-in total payable for all passengers before any card offer. (The brief's `base_price`; renamed because "base" also means "excluding taxes" in provider vocabulary.) |
| **effective_price** ("You pay") | `list_price − best eligible card discount`. |
| **Fresh / stale / hard TTL** | Fresh: serve as-is. Stale: serve + refresh in background. Hard TTL: delete; stale-if-error ends. |
| **Quota guard** | Counter that hard-stops provider calls at a configured budget. |
| **Itinerary key** | Deterministic identifier of the flights (segment carriers, numbers, departure UTC), used for dedupe. |

## 16. Honest-limitations statement (paste into README)

> Prices come from third-party providers and are cached for a short time. They may differ from what the airline or OTA shows at the moment you click through. Card-offer savings are computed from a manually curated dataset with a visible verification date, using only the conditions we model; the airline/OTA decides final eligibility at checkout. This tool does not process payments, store card numbers, issue tickets, manage seats or baggage, or modify bookings.
