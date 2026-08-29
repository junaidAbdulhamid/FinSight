.PHONY: dev down test lint build migrate
dev:
	docker compose up --build
down:
	docker compose down
migrate:
	docker compose run --rm migrate
test:
	cd backend && pytest
lint:
	cd backend && ruff check .
build:
	cd frontend && npm run build
	docker compose build
