# Installation

Kiwi runs as a Docker Compose stack: a FastAPI backend and a Vue 3 frontend served by nginx. No external services are required for the core feature set.

## Prerequisites

- Docker and Docker Compose
- 500 MB disk for images + space for your pantry database

## Quick setup

```bash
git clone https://git.opensourcesolarpunk.com/Circuit-Forge/kiwi
cd kiwi
cp .env.example .env
./manage.sh build
./manage.sh start
```

The web UI opens at `http://localhost:8511`. The FastAPI backend is at `http://localhost:8512`.

## manage.sh commands

| Command | Description |
|---------|-------------|
| `./manage.sh start` | Start all services |
| `./manage.sh stop` | Stop all services |
| `./manage.sh restart` | Restart all services |
| `./manage.sh status` | Show running containers |
| `./manage.sh logs` | Tail logs (all services) |
| `./manage.sh build` | Rebuild images |
| `./manage.sh open` | Open browser to the web UI |

## Environment variables

Copy `.env.example` to `.env` and configure:

```bash
# Required — generate a random secret
SECRET_KEY=your-random-secret-here

# Optional — LLM backend for AI features (receipt OCR, recipe suggestions)
# See LLM Setup guide for details
LLM_BACKEND=ollama          # ollama | openai-compatible | vllm
LLM_BASE_URL=http://localhost:11434
LLM_MODEL=llama3.1
```

## Data location

By default, Kiwi stores its SQLite database in `./data/kiwi.db` inside the repo directory. The `data/` folder is bind-mounted into the container so your pantry survives image rebuilds.

## Updating

```bash
git pull
./manage.sh build
./manage.sh restart
```

Database migrations run automatically on startup.

## Uninstalling

```bash
./manage.sh stop
docker compose down -v    # removes containers and volumes
rm -rf data/              # removes local database
```
