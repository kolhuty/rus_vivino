#!/usr/bin/env bash
# Прогрев ML-сервиса перед демо/проверкой жюри. Первый инференс после
# старта контейнера обычно заметно медленнее (загрузка весов, прогрев
# кэшей) — а по ТЗ SLA 3 секунды. Лучше "сжечь" эту задержку заранее,
# а не на первом реальном запросе во время созвона с кейсодержателем.
#
# Использование:
#   ./scripts/warmup.sh [N_запросов] [ML_URL] [путь_к_WebP_JPEG_или_PNG]
# По умолчанию: 3 запроса, http://127.0.0.1:8001

set -euo pipefail
cd "$(dirname "$0")/.."

N="${1:-3}"
ML_URL="${2:-http://127.0.0.1:8001}"
IMAGE="${3:-$(find data/scraped/images -maxdepth 1 -type f \( -iname '*.webp' -o -iname '*.jpg' -o -iname '*.jpeg' -o -iname '*.png' \) 2>/dev/null | sort | head -1 || true)}"

if [ -z "$IMAGE" ]; then
  echo "Не нашёл WebP/JPEG/PNG для прогрева в data/scraped/images/. Укажи путь третьим аргументом."
  exit 1
fi
if [ ! -f "$IMAGE" ]; then
  echo "Файл не найден: $IMAGE"
  exit 1
fi

echo "Жду, пока ML-сервис поднимется ($ML_URL/docs)..."
ready=0
for i in $(seq 1 60); do
  if curl -sf -o /dev/null "$ML_URL/docs"; then
    ready=1
    echo "ML-сервис отвечает"
    break
  fi
  sleep 5
done
if [ "$ready" -ne 1 ]; then
  echo "ML-сервис не поднялся за 5 минут"
  exit 1
fi

echo "Прогреваю ($N запросов, фото: $IMAGE)..."
for i in $(seq 1 "$N"); do
  t0=$(date +%s%N)
  curl -sf -X POST -F "image=@${IMAGE}" "$ML_URL/v1/predict" > /dev/null
  t1=$(date +%s%N)
  ms=$(( (t1 - t0) / 1000000 ))
  echo "  запрос $i: ${ms} мс"
done

echo "Готово, модель прогрета"
