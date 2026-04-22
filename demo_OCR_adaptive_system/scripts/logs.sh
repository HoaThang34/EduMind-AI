#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

SERVICE="${1:-app}"
TAIL="${2:-200}"

case "$SERVICE" in
    app|qdrant)
        echo "[*] Log realtime cho '$SERVICE' (Ctrl+C để thoát)..."
        docker compose logs -f --tail="$TAIL" "$SERVICE"
        ;;
    all)
        echo "[*] Log realtime toàn bộ services..."
        docker compose logs -f --tail="$TAIL"
        ;;
    *)
        echo "Usage: $0 [app|qdrant|all] [tail_lines]"
        echo "  app     - log Flask app (mặc định)"
        echo "  qdrant  - log vector DB"
        echo "  all     - log tất cả"
        exit 1
        ;;
esac
