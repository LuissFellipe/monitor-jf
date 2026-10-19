.PHONY: up down logs testes coletar

up:
	test -f config.toml || cp config.exemplo.toml config.toml
	test -f .env || cp .env.exemplo .env
	docker compose up -d --build --wait

down:
	docker compose down

logs:
	docker compose logs -f coletor

testes:
	docker compose exec coletor python -m pytest -q

coletar:
	docker compose restart coletor
