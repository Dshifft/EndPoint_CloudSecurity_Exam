.PHONY: up down reset run restart logs backup

up:
	docker compose up -d --build

down:
	docker compose down

reset:
	docker compose down --volumes
	docker compose up -d --build

run:
	docker compose up --build

restart:
	$(MAKE) reset
	$(MAKE) run

logs:
	docker compose logs -f

backup:
	docker compose exec backups /usr/local/bin/backup.sh
