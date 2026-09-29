#!/usr/bin/env bash
# Версия warmup.sh для запуска ВНУТРИ backend-контейнера (docker compose exec),
# без правок в docker-compose.yml/Dockerfile. Логика та же, что у обычного
# warmup.sh (см. его комментарии) — отличия по тем же причинам, что и у
# test_ml_docker.sh: requests вместо curl, встроенное фото вместо volume.
#
# Использование (с хост-машины):
#   docker compose exec -T backend sh -c "$(cat scripts/warmup_docker.sh)"
# Аргументы (опционально): N_запросов, ML_URL
#   docker compose exec -T backend sh -c "$(cat scripts/warmup_docker.sh)" -- 5 http://ml:8001

set -euo pipefail

N="${1:-3}"
ML_URL="${2:-http://ml:8001}"
TEST_IMAGE_B64="UklGRkgAAABXRUJQVlA4IDwAAACQAwCdASpAAEAAPm02mEkkIyKhIggAgA2JaQAAEDdTUAV4hbkAAP71uH+5P0vf//ln/+y3/ZbwgAAAAAA="

python3 << PYEOF
import base64, sys, time
import requests

n = $N
ml_url = "$ML_URL"
image_bytes = base64.b64decode("$TEST_IMAGE_B64")

print(f"Жду, пока ML-сервис поднимется ({ml_url}/docs)...")
ready = False
for i in range(60):
    try:
        r = requests.get(f"{ml_url}/docs", timeout=5)
        ready = True
        print("ML-сервис отвечает")
        break
    except Exception:
        time.sleep(5)
if not ready:
    print("ML-сервис не поднялся за 5 минут")
    sys.exit(1)

print(f"Прогреваю ({n} запросов)...")
for i in range(1, n + 1):
    t0 = time.monotonic()
    r = requests.post(f"{ml_url}/v1/predict", files={"image": ("test.webp", image_bytes, "image/webp")}, timeout=30)
    r.raise_for_status()
    ms = round((time.monotonic() - t0) * 1000)
    print(f"  запрос {i}: {ms} мс")

print("Готово, модель прогрета")
PYEOF
