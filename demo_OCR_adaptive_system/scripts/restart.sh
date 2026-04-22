#!/usr/bin/env bash
# Restart nhanh khi sửa code.
#   scripts/restart.sh           # mặc định: chỉ rebuild + restart service `app` (nhanh)
#   scripts/restart.sh --all     # rebuild + restart toàn bộ (app + qdrant)
#   scripts/restart.sh --no-build  # không rebuild, chỉ restart container (code mount sẵn / chỉ đổi env)
set -euo pipefail

cd "$(dirname "$0")/.."

MODE="app"
DO_BUILD=1
for arg in "$@"; do
    case "$arg" in
        --all) MODE="all" ;;
        --no-build) DO_BUILD=0 ;;
        -h|--help)
            echo "Usage: $0 [--all] [--no-build]"
            echo "  --all        restart cả qdrant (mất hot-state Qdrant nếu chưa persist đúng)"
            echo "  --no-build   không rebuild image, chỉ restart container"
            exit 0
            ;;
    esac
done

if [ ! -f .env ]; then
    echo "[!] Thiếu .env, copy từ .env.example trước."
    exit 1
fi

if [ "$MODE" = "all" ]; then
    if [ "$DO_BUILD" = "1" ]; then
        echo "[*] Rebuild & recreate tất cả (app + qdrant)..."
        docker compose up -d --build
    else
        echo "[*] Restart tất cả (không build)..."
        docker compose restart
    fi
else
    if [ "$DO_BUILD" = "1" ]; then
        echo "[*] Rebuild image app + recreate container app..."
        docker compose up -d --build --no-deps app
    else
        echo "[*] Restart container app (không build)..."
        docker compose restart app
    fi
fi

echo ""
docker compose ps

echo ""
echo "[✓] App: http://localhost:8985"
echo "[i] Log real-time: scripts/logs.sh"
