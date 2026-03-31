#!/usr/bin/env bash
set -euo pipefail

SERVICE=kiwi
WEB_PORT=8511        # Vue SPA (nginx) — dev
API_PORT=8512        # FastAPI — dev
CLOUD_WEB_PORT=8515  # Vue SPA (nginx) — cloud
COMPOSE_FILE="compose.yml"
CLOUD_COMPOSE_FILE="compose.cloud.yml"
CLOUD_PROJECT="kiwi-cloud"

usage() {
    echo "Usage: $0 {start|stop|restart|status|logs|open|build|test"
    echo "           |cloud-start|cloud-stop|cloud-restart|cloud-status|cloud-logs|cloud-build}"
    echo ""
    echo "Dev:"
    echo "  start         Build (if needed) and start all services"
    echo "  stop          Stop and remove containers"
    echo "  restart       Stop then start"
    echo "  status        Show running containers"
    echo "  logs [svc]    Follow logs (api | web — defaults to all)"
    echo "  open          Open web UI in browser"
    echo "  build         Rebuild Docker images without cache"
    echo "  test          Run pytest test suite"
    echo ""
    echo "Cloud (menagerie.circuitforge.tech/kiwi):"
    echo "  cloud-start   Build cloud images and start kiwi-cloud project"
    echo "  cloud-stop    Stop cloud instance"
    echo "  cloud-restart Stop then start cloud instance"
    echo "  cloud-status  Show cloud containers"
    echo "  cloud-logs    Follow cloud logs [api|web — defaults to all]"
    echo "  cloud-build   Rebuild cloud images without cache"
    exit 1
}

cmd="${1:-help}"
shift || true

case "$cmd" in
  start)
    docker compose -f "$COMPOSE_FILE" up -d --build
    echo "Kiwi running → http://localhost:${WEB_PORT}"
    ;;
  stop)
    docker compose -f "$COMPOSE_FILE" down
    ;;
  restart)
    docker compose -f "$COMPOSE_FILE" down
    docker compose -f "$COMPOSE_FILE" up -d --build
    echo "Kiwi running → http://localhost:${WEB_PORT}"
    ;;
  status)
    docker compose -f "$COMPOSE_FILE" ps
    ;;
  logs)
    svc="${1:-}"
    docker compose -f "$COMPOSE_FILE" logs -f ${svc}
    ;;
  open)
    xdg-open "http://localhost:${WEB_PORT}" 2>/dev/null \
      || open "http://localhost:${WEB_PORT}" 2>/dev/null \
      || echo "Open http://localhost:${WEB_PORT} in your browser"
    ;;
  build)
    docker compose -f "$COMPOSE_FILE" build --no-cache
    ;;
  test)
    docker compose -f "$COMPOSE_FILE" run --rm api \
      conda run -n job-seeker pytest tests/ -v
    ;;

  cloud-start)
    docker compose -f "$CLOUD_COMPOSE_FILE" -p "$CLOUD_PROJECT" up -d --build
    echo "Kiwi cloud running → https://menagerie.circuitforge.tech/kiwi"
    ;;
  cloud-stop)
    docker compose -f "$CLOUD_COMPOSE_FILE" -p "$CLOUD_PROJECT" down
    ;;
  cloud-restart)
    docker compose -f "$CLOUD_COMPOSE_FILE" -p "$CLOUD_PROJECT" down
    docker compose -f "$CLOUD_COMPOSE_FILE" -p "$CLOUD_PROJECT" up -d --build
    echo "Kiwi cloud running → https://menagerie.circuitforge.tech/kiwi"
    ;;
  cloud-status)
    docker compose -f "$CLOUD_COMPOSE_FILE" -p "$CLOUD_PROJECT" ps
    ;;
  cloud-logs)
    svc="${1:-}"
    docker compose -f "$CLOUD_COMPOSE_FILE" -p "$CLOUD_PROJECT" logs -f ${svc}
    ;;
  cloud-build)
    docker compose -f "$CLOUD_COMPOSE_FILE" -p "$CLOUD_PROJECT" build --no-cache
    ;;

  *)
    usage
    ;;
esac
