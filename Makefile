.PHONY: install up down test lint type-check migrate format

PYTHON ?= .venv/bin/python
RUFF ?= .venv/bin/ruff
MYPY ?= .venv/bin/mypy
ALEMBIC ?= .venv/bin/alembic

install:
	python3 -m venv .venv
	$(PYTHON) -m pip install -e 'backend[dev]'

up:
	docker compose up --build

down:
	docker compose down

test:
	$(PYTHON) -m pytest backend/tests

lint:
	$(RUFF) check backend/app backend/tests

type-check:
	$(MYPY) backend/app

migrate:
	cd backend && ../$(ALEMBIC) upgrade head

format:
	$(RUFF) format backend/app backend/tests
