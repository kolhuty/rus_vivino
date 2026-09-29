#!/usr/bin/env bash
# Версия test_ml.sh для запуска ВНУТРИ backend-контейнера (docker compose exec),
# а не с хост-машины, и без изменений в docker-compose.yml/Dockerfile.
#
# Почему именно так:
#   - curl не установлен в образах backend/ml, но requests (Python-библиотека)
#     есть в backend/requirements.txt — используем её вместо curl
#   - ML напрямую эту команду не выполнить (в ml/requirements.txt нет requests,
#     только torch/fastapi) — поэтому гоняем ИЗ backend, а к ML он и так ходит
#     по сети (http://ml:8001), это его штатный путь
#   - тестовое фото встроено как base64 (а не читается из data/scraped/images/),
#     чтобы не зависеть от того, что именно смонтировано в конкретный контейнер
#
# Использование (с хост-машины, БЕЗ правок в docker-compose.yml/Dockerfile):
#   docker compose exec -T backend sh -c "$(cat scripts/test_ml_docker.sh)"
#
# Внутри backend-контейнера сам бэк отвечает на 127.0.0.1:8000 (это же процесс),
# а до ML он достаёт по имени сервиса http://ml:8001 — так же, как в его
# собственном коде (переменная ML_BASE_URL в docker-compose.yml).

set -euo pipefail

BACKEND_URL="${1:-http://127.0.0.1:8000}"
ML_URL="${2:-http://ml:8001}"

TEST_IMAGE_B64="UklGRkgAAABXRUJQVlA4IDwAAACQAwCdASpAAEAAPm02mEkkIyKhIggAgA2JaQAAEDdTUAV4hbkAAP71uH+5P0vf//ln/+y3/ZbwgAAAAAA="

python3 << PYEOF
import base64, json, sys
import requests

backend_url = "$BACKEND_URL"
ml_url = "$ML_URL"
image_bytes = base64.b64decode("$TEST_IMAGE_B64")

def section(title):
    print()
    print(f"== {title} ==")

section(f"backend health: {backend_url}/api/v1/health")
try:
    r = requests.get(f"{backend_url}/api/v1/health", timeout=10)
    r.raise_for_status()
    print(json.dumps(r.json(), indent=2, ensure_ascii=False))
except Exception as e:
    print(f"БЭК НЕ ОТВЕЧАЕТ: {e}")
    sys.exit(1)

section(f"ml docs: {ml_url}/docs")
try:
    r = requests.get(f"{ml_url}/docs", timeout=10)
    print(f"HTTP {r.status_code}")
except Exception as e:
    print(f"ML НЕ ОТВЕЧАЕТ (бэк при этом может жить в degraded режиме): {e}")

section("/api/v1/scan (плоский slug, как ждёт скрипт оценки, п.6 ТЗ)")
r = requests.post(f"{backend_url}/api/v1/scan", files={"image": ("test.webp", image_bytes, "image/webp")}, timeout=30)
r.raise_for_status()
print(json.dumps(r.json(), indent=2, ensure_ascii=False))

section("/api/v1/recognize (полная карточка для фронта)")
r = requests.post(f"{backend_url}/api/v1/recognize", files={"image": ("test.webp", image_bytes, "image/webp")}, timeout=30)
r.raise_for_status()
print(json.dumps(r.json(), indent=2, ensure_ascii=False))

print()
print("Тест пройден (встроенное тестовое фото, без зависимости от volume)")
PYEOF
