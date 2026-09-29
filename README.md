# Сканер российских вин «Своё Вино»

Веб-сервис распознаёт российское вино по фотографии бутылки или этикетки и открывает соответствующую карточку каталога «Своё Вино». Пользователь может сделать снимок камерой телефона или выбрать изображение из галереи.

Текущая поисковая модель — `google/siglip2-base-patch16-224`. Сервис извлекает визуальные признаки фотографии, сравнивает их с заранее построенным индексом эталонов и возвращает один лучший `slug`, а для интерфейса — также ближайшие позиции и диагностические значения.

> Сервис предназначен для пользователей старше 18 лет. Чрезмерное употребление алкоголя вредит здоровью.

## Возможности

- загрузка JPEG/PNG из галереи и съёмка камерой телефона;
- нормализация EXIF-ориентации и перевод изображения в RGB;
- локализация центральной бутылки и области этикетки;
- визуальный поиск SigLIP 2 по каталогу;
- строгий оценочный ответ `{"slug":"wine-slug"}`;
- диагностический top-5, similarity, margin и время ML-инференса;
- мобильная карточка найденного вина и похожие позиции;
- локальный запуск через Docker Compose или без Docker.

Подробное описание слоёв и pipeline находится в [ARCHITECTURE.md](ARCHITECTURE.md).

## Архитектура

```text
Браузер
   |
   v
React + Nginx :80
   |
   v
Flask + Gunicorn :8000
   |
   v
FastAPI + SigLIP 2 :8001
   |
   v
artifacts/index.npz
```

- `frontend` — React-интерфейс камеры и карточки вина;
- `backend` — публичное API, каталог и обогащение ML-ответа;
- `ml` — нормализация изображения, локализация, SigLIP и поиск по индексу.

## Требования

Для Docker-запуска нужны Docker Engine, Docker Compose plugin, не менее 8 ГБ RAM и доступ к Hugging Face при первом запуске.

Для локального запуска нужны Python 3.11, Node.js 22, npm и не менее 8 ГБ RAM. NVIDIA GPU опционален.

## Необходимые данные

Перед запуском должны существовать:

```text
data/catalog.jsonl
data/scraped/images/
artifacts/index.npz
```

`catalog.jsonl` содержит точные `slug` и пути к эталонным изображениям. Индекс должен быть построен той же моделью и для той же версии каталога. При несовпадении каталога и индекса результат поиска нельзя считать корректным.

Каталог и исходные изображения не публикуются вместе с исходным кодом, если это ограничено условиями передачи данных.

## Быстрый запуск через Docker

Скопируйте пример конфигурации:

```bash
cp .env.example .env
```

В PowerShell:

```powershell
Copy-Item .env.example .env
```

Запустите сервисы:

```bash
docker compose up -d --build
docker compose ps
```

Приложение будет доступно по адресу `http://localhost`. Для другого порта измените `APP_PORT` в `.env`, например `APP_PORT=8080`.

Проверка backend:

```bash
curl http://localhost/api/v1/health
```

Логи и остановка:

```bash
docker compose logs -f
docker compose down
```

При первом запуске ML-контейнер скачивает веса SigLIP 2 и YOLOS Small с Hugging Face. Они сохраняются в volume `huggingface-cache`; последующие старты используют кеш. Готовность ML-сервиса может занять несколько минут.

Backend и ML-сервис доступны только во внутренней сети Compose. Наружу публикуется Nginx, который раздаёт frontend и проксирует `/api/*`.

## Переменные окружения

Основные параметры находятся в `.env.example`.

| Переменная | Назначение | По умолчанию |
|---|---|---|
| `APP_PORT` | Публичный порт приложения | `80` |
| `ML_TIMEOUT` | Таймаут обращения backend к ML | `120` секунд |
| `WINE_DEVICE` | Устройство инференса: `cpu`, `cuda` или `auto` | `cpu` в Compose |
| `WINE_LOCALIZER` | Включение локализации бутылки | `1` |

Внутренние переменные сервисов:

| Переменная | Назначение | По умолчанию |
|---|---|---|
| `WINE_INDEX` | Путь к `index.npz` в ML-сервисе | `artifacts/index.npz` |
| `ML_BASE_URL` | Адрес ML-сервиса для backend | `http://127.0.0.1:8001` |
| `DATA_DIR` | Каталог данных backend | `data/` проекта |
| `ALLOW_ON_DEMAND_FETCH` | Разрешить загрузку отсутствующих изображений | `false` |
| `SITE_BASE_URL` | Адрес портала для загрузки изображений | `https://vino-svoe.ru` |

Для воспроизводимой демонстрации `ALLOW_ON_DEMAND_FETCH` следует оставлять выключенным: runtime не должен зависеть от внешнего сайта.

## Локальный запуск без Docker

### 1. Python-окружение

PowerShell:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r ml\requirements.txt
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
```

Linux/macOS:

```bash
python3.11 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r ml/requirements.txt
.venv/bin/python -m pip install -r backend/requirements.txt
```

Для CUDA установите подходящую сборку PyTorch согласно документации PyTorch до запуска ML-сервиса.

### 2. ML-сервис

PowerShell из корня проекта:

```powershell
$env:PYTHONPATH = "ml"
$env:WINE_INDEX = "artifacts/index.npz"
$env:WINE_DEVICE = "cpu"
$env:WINE_LOCALIZER = "1"
.\.venv\Scripts\python.exe -m uvicorn wine_recognition.api:app --host 127.0.0.1 --port 8001
```

Linux/macOS:

```bash
PYTHONPATH=ml \
WINE_INDEX=artifacts/index.npz \
WINE_DEVICE=cpu \
WINE_LOCALIZER=1 \
.venv/bin/python -m uvicorn wine_recognition.api:app --host 127.0.0.1 --port 8001
```

Используйте один worker: каждый дополнительный worker создаёт отдельную копию модели в памяти.

### 3. Backend

В новом терминале из корня проекта:

```powershell
$env:ML_BASE_URL = "http://127.0.0.1:8001"
$env:DATA_DIR = (Resolve-Path "data").Path
.\.venv\Scripts\python.exe backend\app.py
```

Backend будет доступен на `http://127.0.0.1:8000`.

### 4. Frontend

В третьем терминале:

```bash
cd frontend
npm ci
npm run dev
```

Откройте `http://localhost:5173`. Vite проксирует `/api` на backend с портом 8000. Доступ к камере браузера обычно разрешён для `localhost`; при открытии с другого устройства потребуется HTTPS.

## Подготовка каталога

PowerShell:

```powershell
.\.venv\Scripts\python.exe ml\scripts\prepare_catalog.py `
  --csv catalog_scraped.csv `
  --images data\scraped\images `
  --output data\catalog.jsonl
```

Скрипт проверяет `slug` и локальные изображения, формирует каталог, записывает проблемы и дубли в `data/catalog_report.jsonl`, а происхождение файлов — в `data/sources.jsonl`.

После выполнения необходимо вручную проверить отчёт. Автоматическое сопоставление имени файла с карточкой не гарантирует правильность пары «этикетка — slug».

## Построение индекса

PowerShell:

```powershell
$env:PYTHONPATH = "ml"
.\.venv\Scripts\python.exe -m wine_recognition build-index `
  --catalog data\catalog.jsonl `
  --output artifacts\index.npz `
  --device cpu
```

Linux/macOS:

```bash
PYTHONPATH=ml .venv/bin/python -m wine_recognition build-index \
  --catalog data/catalog.jsonl \
  --output artifacts/index.npz \
  --device cpu
```

Индекс нужно перестраивать после изменения каталога, эталонов, модели или алгоритма извлечения признаков. Идентификатор и ревизия модели сохраняются в метаданных индекса и используются при инференсе.

## Проверка одного изображения

```powershell
$env:PYTHONPATH = "ml"
.\.venv\Scripts\python.exe -m wine_recognition predict `
  --image C:\photos\wine.jpg `
  --index artifacts\index.npz `
  --output prediction.json `
  --diagnostic `
  --device cpu
```

Добавьте `--no-localizer`, чтобы проверить поиск без локализации. Краткий режим без `--diagnostic` записывает только `slug`.

## API

### Оценочный endpoint

```bash
curl -F "image=@wine.jpg" http://localhost/api/v1/scan
```

Успешный ответ строго соответствует контракту организатора:

```json
{"slug":"wine-slug"}
```

### Продуктовый endpoint

```bash
curl -F "image=@wine.jpg" http://localhost/api/v1/recognize
```

Пример сокращённого ответа:

```json
{
  "status": "matched",
  "main": {
    "slug": "wine-slug",
    "name": "Название вина",
    "producer": "Винодельня",
    "score": 0.89,
    "margin": 0.14
  },
  "others": [],
  "confidence": null,
  "model_version": "siglip2-baseline-v1",
  "catalog_version": "catalog-v1",
  "latency_ms": 1035
}
```

`score` — cosine similarity, а `margin` — разность score первого и второго кандидатов. Они не являются вероятностью правильного ответа. `confidence` остаётся `null` до калибровки на отдельной размеченной выборке.

### Остальные endpoints

| Метод и путь | Назначение |
|---|---|
| `GET /api/v1/health` | Состояние backend, ML и размер каталога |
| `GET /api/v1/wines/{slug}` | Карточка вина по `slug` |
| `GET /api/v1/images/by-slug/{slug}` | Изображение вина |
| `POST /v1/eval/predict` | Внутренний минимальный endpoint ML |
| `POST /v1/predict` | Внутренний диагностический endpoint ML |

Ограничения входного изображения:

- только JPEG или PNG;
- не более 15 МиБ;
- не более 25 миллионов пикселей;
- multipart-поле должно называться `image`.

## Оценка качества

`scripts/evaluate.py` прогоняет размеченные изображения через работающий сервис и сохраняет Top-1 accuracy, macro-F1, Recall@5, median/p95 времени ответа, качество по условиям съёмки и наиболее частые пары ошибок.

Пример с JSONL-манифестом:

```bash
python scripts/evaluate.py \
  --manifest data/public_test/manifest.jsonl \
  --base-url http://127.0.0.1:8000 \
  --mode recognize
```

Формат строки манифеста:

```json
{"query_id":"q-000001","image_path":"public_test/q-000001.jpg","slug":"wine-slug","split":"test_real","conditions":["glare"]}
```

Адаптер к `queries.tsv` организатора:

```bash
python scripts/evaluate.py \
  --queries-tsv path/to/queries.tsv \
  --base-url http://127.0.0.1:8000 \
  --mode scan
```

Результаты записываются в:

```text
reports/eval_results.json
reports/eval_predictions.jsonl
```

Не публикуйте метрики, полученные только на эталонных изображениях, как качество на полевых фотографиях. Для сравнения вариантов модели необходимо использовать один и тот же неизменный test split.

## Тесты и проверки

ML unit-тесты:

```powershell
$env:PYTHONPATH = "ml"
.\.venv\Scripts\python.exe -m unittest discover -s ml\tests -v
```

Frontend:

```bash
cd frontend
npm run lint
npm run build
```

Docker-конфигурация:

```bash
docker compose config --quiet
```

## Smoke-тест и прогрев API

`backend` и `ml` публикуют порты на `127.0.0.1` (`8000` и `8001` соответственно) — доступны с хост-машины напрямую, даже когда подняты через `docker compose up`.

```bash
./scripts/test_ml.sh
./scripts/warmup.sh
```

Первым аргументом можно передать путь к своему фото, вторым/третьим — другие адреса backend/ML.

`warmup.sh` стоит прогнать перед демонстрацией/проверкой жюри — у ML-сервиса `start_period: 240s` в `docker-compose.yml`, и первый инференс после холодного старта может не уложиться в целевой SLA (3 секунды).

**Если понадобится гонять проверку изнутри самого контейнера** (например, порты по какой-то причине недоступны с хоста) — есть альтернативные версии `test_ml_docker.sh`/`warmup_docker.sh`, без зависимости от `curl` и смонтированных файлов:

```bash
docker compose exec -T backend sh -c "$(cat scripts/test_ml_docker.sh)"
docker compose exec -T backend sh -c "$(cat scripts/warmup_docker.sh)"
```

## Структура репозитория

```text
backend/                  Flask API, каталог и изображения
frontend/                 React mobile-first интерфейс
ml/
  scripts/                подготовка каталога
  tests/                  unit-тесты ML-pipeline
  wine_recognition/       SigLIP, локализатор, индекс, API и CLI
scripts/
  evaluate.py             оценка качества и скорости
  test_ml.sh              smoke-тест ML API (с хоста, без Docker)
  warmup.sh               прогрев сервиса (с хоста, без Docker)
  test_ml_docker.sh        smoke-тест через docker compose exec
  warmup_docker.sh         прогрев через docker compose exec
artifacts/
  index.npz               поисковый индекс
data/                     каталог, эталоны и тестовые данные
ARCHITECTURE.md            подробная архитектура
docker-compose.yml         production-like локальный запуск
```

## Известные ограничения

1. Текущая версия всегда выбирает ближайший `slug`; откалиброванного ответа `not_found` пока нет.
2. OCR не используется, поэтому похожие этикетки, отличающиеся мелким текстом, годом или категорией, остаются главным источником ошибок.
3. `confidence` не рассчитан до появления отдельной размеченной калибровочной выборки.
4. Полнота карточки ограничена полями подготовленного `catalog.jsonl`.
5. «Цифровой сомелье» пока является точкой расширения интерфейса.
6. Подтверждённые метрики на публичном и приватном наборах должны быть получены отдельным оценочным прогоном.
7. Первый старт зависит от доступности Hugging Face; для офлайн-демонстрации веса необходимо заранее прогреть и сохранить в кеше.

## Устранение неполадок

### `No module named wine_recognition.__main__`

Запускайте ML-команды из корня с `PYTHONPATH=ml`:

```powershell
$env:PYTHONPATH = "ml"
```

### ML долго находится в состоянии starting

Первый запуск скачивает две модели. Проверьте интернет, свободное место и логи:

```bash
docker compose logs -f ml
```

### Backend возвращает HTTP 503

Убедитесь, что ML-сервис прошёл healthcheck, индекс смонтирован и модель загрузилась:

```bash
docker compose ps
docker compose logs ml
```

### Камера не открывается на телефоне

Браузеры требуют защищённый контекст для камеры. Используйте HTTPS либо выберите фотографию из галереи.

### Недостаточно памяти

- используйте один ML worker;
- установите `WINE_DEVICE=cpu`, если конфигурация CUDA некорректна;
- при построении индекса уменьшите `--batch-size` до `1`.

## Статус проекта

Работает end-to-end pipeline: фотография → нормализация → локализация → SigLIP → поиск → `slug` → карточка вина. Перед конкурсной сдачей необходимо провести и зафиксировать оценку на публичном датасете, откалибровать обработку неизвестных вин и завершить дополнительную функцию после поиска.
