# Распознавание вина: SigLIP 2 Base без обучения

Python 3.10+. Модель сравнивает полный кадр с эталонами по cosine similarity.
OCR, локализация этикетки, обучение и калиброванные отказы в этот baseline не входят.

## Установка

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Для CUDA установите подходящую сборку PyTorch по https://pytorch.org/get-started/locally/.
Первое построение индекса скачивает веса Google с Hugging Face и требует интернета.
Дальнейший запуск использует локальный кеш, если нужная ревизия уже скачана.

## Подготовка имеющихся данных

```powershell
.\.venv\Scripts\python.exe scripts/prepare_catalog.py
```

Скрипт читает `data/dataset_vino.csv`, ищет изображения в `data/vino`, учитывает
префиксы размера Strapi и суффиксы хеша, конвертирует изображения в RGB PNG.
Неоднозначные изображения и повторяющиеся slug пропускаются и попадают в
`data/catalog_report.jsonl`; одинаковые картинки разных slug сохраняются и отмечаются.
Проверьте отчёт: полученный каталог может содержать только часть исходного CSV.
Автоматическое сопоставление имён не заменяет проверку соответствия фото карточке.
Происхождение файлов записывается в `data/sources.jsonl`; URL отсутствуют в исходном CSV.

Можно самостоятельно подготовить `data/catalog.jsonl`:

```json
{"slug":"real-catalog-slug","reference_images":["references/bottle.png"]}
```

Пути изображений относительны папке, содержащей каталог; slug должны быть уникальны.

## Индекс и JSON-файл

```powershell
.\.venv\Scripts\python.exe -m wine_recognition build-index --device cpu
.\.venv\Scripts\python.exe -m wine_recognition predict --image C:\photos\wine.jpg --output prediction.json
```

Файл результата соответствует оценочному формату ТЗ:

```json
{"slug":"real-catalog-slug"}
```

Для расширенного формата с top5, score, margin и временем:

```powershell
.\.venv\Scripts\python.exe -m wine_recognition predict --image C:\photos\wine.jpg --output diagnostics.json --diagnostic
```

Индекс содержит ревизию скачанных весов; распознавание загружает эту же ревизию.
Можно явно передать commit модели: `build-index --revision COMMIT_SHA`.
После изменения каталога индекс нужно перестроить. `--batch-size 1` снижает пиковую память.
`--device auto` выбирает CUDA, если она доступна, иначе CPU.

## Загрузка фото через HTTP

```powershell
.\.venv\Scripts\python.exe -m uvicorn wine_recognition.api:app --host 127.0.0.1 --port 8000
curl.exe -F "image=@C:\photos\wine.jpg" http://127.0.0.1:8000/v1/eval/predict -o prediction.json
curl.exe -F "image=@C:\photos\wine.jpg" http://127.0.0.1:8000/v1/predict -o diagnostics.json
```

Multipart-поле: `image`; JPEG/PNG, до 15 МиБ и 25 млн пикселей. EXIF-ориентация учитывается.
Повреждённые изображения возвращают HTTP 400, превышение размера — 413.
Пустой/повреждённый индекс вызывает ошибку запуска. Модель загружается один раз на процесс.
Переменные окружения: `WINE_INDEX` (по умолчанию `artifacts/index.npz`) и `WINE_DEVICE`.
Для начала используйте один worker, чтобы не копировать модель в память.

`score` — cosine similarity, для нескольких эталонов берётся максимум по slug.
`confidence` всегда null. `matched` означает только выбор лучшего кандидата:
baseline всегда выбирает вино, даже для фото вне каталога. Это не подтверждение наличия вина.
Если кандидат один, margin равен null. Качество и p95 требуют измерения на реальных фото.

## Структура

- `catalog.py`: чтение и проверка каталога.
- `images.py`: ограничения, декодирование и ориентация изображений.
- `encoder.py`: предобученная модель, получение нормализованных векторов.
- `index.py`: построение, сохранение и поиск по индексу.
- `service.py`: сценарий распознавания и форматы ответа.
- `api.py`: HTTP-адаптер.
- `__main__.py`: CLI-адаптер.
- `scripts/prepare_catalog.py`: преобразование локального CSV.

Проверки: `python -m unittest discover -s tests`.
Веса используются по официальному примеру: https://huggingface.co/google/siglip2-base-patch16-224.
