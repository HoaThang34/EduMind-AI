#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

MODE="${1:-soft}"

case "$MODE" in
    soft)
        echo "[*] Dừng containers (giữ data)..."
        docker compose down
        ;;
    hard)
        echo "[!] Dừng và XOÁ volume data (Qdrant, SQLite, uploads)..."
        docker compose down -v
        rm -rf data/
        ;;
    *)
        echo "Usage: $0 [soft|hard]"
        echo "  soft  - dừng container, giữ data (mặc định)"
        echo "  hard  - dừng và xoá toàn bộ data (reset sạch)"
        exit 1
        ;;
esac

echo "[✓] Xong."
