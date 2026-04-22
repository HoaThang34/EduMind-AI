#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if [ ! -f .env ]; then
    echo "[!] Chưa có .env, đang tạo từ .env.example..."
    cp .env.example .env
    echo "[!] Hãy mở .env điền GEMINI_API_KEY và OPENAI_API_KEY rồi chạy lại."
    exit 1
fi

echo "[*] Build & start containers (app + qdrant)..."
docker compose up -d --build

echo ""
echo "[*] Trạng thái:"
docker compose ps

echo ""
echo "[✓] Mở http://localhost:8985"
echo "[i] Xem log: scripts/logs.sh  |  Dừng: scripts/stop.sh"
