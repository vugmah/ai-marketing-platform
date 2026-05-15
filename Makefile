.PHONY: up down logs migrate migrate-create shell-backend shell-db ps test

up:
	docker-compose up -d

down:
	docker-compose down

logs:
	docker-compose logs -f

migrate:
	docker-compose exec backend alembic upgrade head

migrate-create:
	docker-compose exec backend alembic revision --autogenerate -m "$(name)"

shell-backend:
	docker-compose exec backend bash

shell-db:
	docker-compose exec mysql mysql -u aimp -p aimp

ps:
	docker-compose ps

test:
	docker-compose exec backend pytest
