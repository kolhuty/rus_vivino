#!/usr/bin/env bash
# Быстрая проверка живого стека: бэк, ML и один реальный прогон карточки.
# Работает и при локальном запуске (python app.py / uvicorn ...), и при
# docker-compose, если порты backend/ml прокинуты на хост (либо запускай
# изнутри контейнера: docker compose exec backend ./scripts/test_ml.sh).
#
# Использование:
#   ./scripts/test_ml.sh [путь_к_фото] [BACKEND_URL] [ML_URL]
# По умолчанию: первое фото из data/scraped/images/, localhost:8000/:8001

set -euo pipefail
cd "$(dirname "$0")/.."

BACKEND_URL="${2:-http://127.0.0.1:8000}"
ML_URL="${3:-http://127.0.0.1:8001}"
IMAGE="${1:-$(ls data/scraped/images/*.webp 2>/dev/null | head -1 || true)}"

if [ -z "$IMAGE" ]; then
  echo "Не нашёл тестовое фото. Укажи путь: ./scripts/test_ml.sh path/to/photo.jpg"
  exit 1
fi
if [ ! -f "$IMAGE" ]; then
  echo "Файл не найден: $IMAGE"
  exit 1
fi

echo "== backend health: $BACKEND_URL/api/v1/health =="
if ! HEALTH=$(curl -sf "$BACKEND_URL/api/v1/health"); then
  echo "БЭК НЕ ОТВЕЧАЕТ"
  exit 1
fi
echo "$HEALTH" | python3 -m json.tool

echo
echo "== ml docs: $ML_URL/docs =="
curl -sf -o /dev/null -w "HTTP %{http_code}\n" "$ML_URL/docs" || { echo "ML НЕ ОТВЕЧАЕТ (бэк при этом может жить в mock/degraded режиме)"; }

echo
echo "== /api/v1/scan (плоский slug, как ждёт скрипт оценки, п.6 ТЗ) =="
curl -sf -X POST -F "image=@${IMAGE}" "$BACKEND_URL/api/v1/scan" | python3 -m json.tool

echo
echo "== /api/v1/recognize (полная карточка для фронта) =="
curl -sf -X POST -F "image=@${IMAGE}" "$BACKEND_URL/api/v1/recognize" | python3 -m json.tool

echo
echo "Тестовое фото: $IMAGE"
