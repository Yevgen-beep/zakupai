.PHONY: up down restart logs ps build test lint fmt dbsh smoke

up:            ## build+up
	docker compose up -d --build

down:          ## stop+rm
	docker compose down

restart:       ## restart all
	docker compose restart

ps:            ## containers status
	docker compose ps

logs:          ## tail logs
	docker compose logs -f --tail=100

build:         ## build images
	docker compose build

dbsh:          ## psql shell
	docker exec -it zakupai-db psql -U zakupai -d zakupai

test:          ## run unit tests inside services (если появятся)
	@echo "TODO: pytest in each service container"

lint:          ## ruff/flake8/mypy при необходимости
	@echo "TODO: linters (optional)"

fmt:           ## форматирование
	@echo "TODO: black/ruff format (optional)"

smoke:         ## run smoke tests
	./scripts/smoke.sh
