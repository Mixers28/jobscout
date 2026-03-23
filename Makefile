VENV?=.venv
PYTHON?=$(VENV)/bin/python
PIP?=$(VENV)/bin/pip
PYTHONPATH_BASE=packages/shared:apps/api:apps/worker

NODE?=$(shell ls $$HOME/.nvm/versions/node/v20.*/bin/node 2>/dev/null | tail -1)

.PHONY: bootstrap check-venv lint typecheck test run-api run-web run-worker run-scheduler-once run-scheduler-loop migrate-up migrate-revision docker-up docker-down docker-logs docker-migrate

bootstrap:
	python3 -m venv $(VENV)
	$(PYTHON) -m pip install --upgrade pip
	$(PIP) install -r requirements-dev.txt

check-venv:
	@test -x "$(PYTHON)" || (echo "Virtual environment not found. Run: make bootstrap"; exit 1)

lint: check-venv
	PYTHONPATH=$(PYTHONPATH_BASE) $(PYTHON) -m ruff check .

typecheck: check-venv
	PYTHONPATH=$(PYTHONPATH_BASE) $(PYTHON) -m mypy packages/shared/jobscout_shared apps/api/app apps/worker/worker

test: check-venv
	PYTHONPATH=$(PYTHONPATH_BASE) $(PYTHON) -m pytest

run-web:
	cd apps/web && $(NODE) node_modules/.bin/next dev

run-api: check-venv
	PYTHONPATH=$(PYTHONPATH_BASE) $(PYTHON) -m uvicorn app.main:app --app-dir apps/api --reload

run-worker: check-venv
	PYTHONPATH=$(PYTHONPATH_BASE) $(PYTHON) -m worker.main

run-scheduler-once: check-venv
	PYTHONPATH=$(PYTHONPATH_BASE) $(PYTHON) -m worker.main --schedule-once

run-scheduler-loop: check-venv
	PYTHONPATH=$(PYTHONPATH_BASE) $(PYTHON) -m worker.main --schedule-loop

migrate-up: check-venv
	PYTHONPATH=$(PYTHONPATH_BASE) $(PYTHON) -m alembic -c alembic.ini upgrade head

migrate-revision: check-venv
	PYTHONPATH=$(PYTHONPATH_BASE) $(PYTHON) -m alembic -c alembic.ini revision --autogenerate -m "$(m)"

# Docker targets
docker-up:
	docker compose up --build -d

docker-down:
	docker compose down

docker-logs:
	docker compose logs -f

docker-migrate:
	docker compose exec api python -m alembic -c alembic.ini upgrade head
