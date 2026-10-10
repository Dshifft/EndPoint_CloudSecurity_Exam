.PHONY: up down reset run restart

up:
	docker compose up -d --build

down:
	docker compose down

reset:
	docker compose down --volumes
	docker compose up -d --build
