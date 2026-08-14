.PHONY: up down api web test lint migrate fmt

up:            ## Start local infra (postgres, redis, qdrant)
	docker compose up -d postgres redis qdrant

down:          ## Stop everything
	docker compose down

api:           ## Run API with hot reload
	cd apps/api && uvicorn aegis_api.main:app --reload --port 8000

web:           ## Run web app with hot reload
	cd apps/web && npm run dev

migrate:       ## Apply database migrations
	cd apps/api && alembic upgrade head

test:          ## Run all tests (hermetic, no network)
	cd apps/api && python -m pytest -q

test-live:     ## Test the real Anthropic API (needs ANTHROPIC_API_KEY, costs a few tokens)
	cd apps/api && AEGIS_RUN_LIVE_TESTS=1 python -m pytest tests/test_live_sentinel.py -v -s

lint:          ## Lint backend and frontend
	cd apps/api && ruff check src tests
	cd apps/web && npm run lint

fmt:           ## Format code
	cd apps/api && ruff format src tests
