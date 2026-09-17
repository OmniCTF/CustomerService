COMPOSE := $(shell docker compose version >/dev/null 2>&1 && echo "docker compose" || echo "docker-compose")

.PHONY: up logs verify solve reset down clean

up:
	$(COMPOSE) up -d

logs:
	$(COMPOSE) logs -f wordpress cli

verify:
	./scripts/verify.sh

solve:
	python3 poc/exploit.py

reset:
	./scripts/reset.sh

down:
	$(COMPOSE) down

clean:
	$(COMPOSE) down -v --remove-orphans
