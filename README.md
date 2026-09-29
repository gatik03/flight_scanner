# Flight Deal Aggregator & Offer-Matcher

This is a modular-monolith learning project that compares flight fares from
approved providers and explains applicable card offers. Phase 0 provides the
reproducible API foundation, dependency health checks, structured logging, and
database/cache wiring.

It does **not** process payments, store card numbers/CVV/expiry, issue tickets,
perform bookings, guarantee click-through prices, provide seats/baggage/changes,
or scrape airline and OTA websites. Live provider calls are disabled by default.

## Run locally

```sh
make install
cp .env.example .env
docker compose up --build
curl http://localhost:8000/health
curl http://localhost:8000/health/ready
```

Inside Compose, services use `postgres` and `redis` as hostnames. `localhost`
inside the API container means the API container itself.

## Checks

```sh
make test
make lint
make type-check
```

The local checks use the project virtualenv at `.venv/`. Docker is required for
the Compose stack; CI runs lint, type-check, and tests with live providers off.
