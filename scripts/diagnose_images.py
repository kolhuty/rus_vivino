#!/usr/bin/env python3
"""Послойная диагностика загрузки фото: диск -> backend -> vite -> сайт.

Запуск из корня репозитория:
    .\.venv\Scripts\python.exe scripts/diagnose_images.py [slug]
    (без аргумента берётся контрольный slug из кэша)

Печатает [OK]/[WARN]/[FAIL] по каждому слою и итоговый вердикт.
"""
import json
import re
import socket
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
FRONT = ROOT / "frontend"
BACKEND = "http://127.0.0.1:8000"
VITE = "http://127.0.0.1:5173"
SITE = "https://vino-svoe.ru"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
BROWSER = {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "ru,en;q=0.8",
    "Referer": "https://vino-svoe.ru/",
}

slug = sys.argv[1] if len(sys.argv) > 1 else "fanagoriya-100-ottenkov-shardone-beloe-suhoe-14"
problems = []


def ok(msg):   print(f"  [OK]   {msg}")
def warn(msg): print(f"  [WARN] {msg}"); problems.append(msg)
def fail(msg): print(f"  [FAIL] {msg}"); problems.append(msg)
def info(msg): print(f"  [INFO] {msg}")


def tcp(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=2):
            return True
    except OSError:
        return False


# ---------------------------------------------------------------- СЛОЙ 1: диск
print(f"=== СЛОЙ 1: ДИСК (slug={slug}) ===")
cat_path = DATA / "catalog.jsonl"
rec = None
if cat_path.exists():
    lines = [l for l in cat_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    ok(f"catalog.jsonl существует, записей: {len(lines)}")
    for line in lines:
        r = json.loads(line)
        if r.get("slug") == slug:
            rec = r
            break
else:
    fail("data/catalog.jsonl отсутствует")

if rec:
    refs = rec.get("reference_images") or []
    ok(f"slug найден в каталоге; reference_images={refs}")
    if refs and (DATA / refs[0]).exists():
        ok(f"файл эталона на диске: {refs[0]} ({(DATA / refs[0]).stat().st_size} байт)")
    else:
        fail(f"файл эталона НЕ найден на диске: {refs[0] if refs else '(список пуст)'}")
else:
    warn("slug НЕТ в catalog.jsonl: карточка и индекс этого вина не знают")

vino = DATA / "vino"
hits = list(vino.glob(f"{slug}.*")) if vino.is_dir() else []
if hits:
    ok(f"сырой файл в vino/: {hits[0].name}")
else:
    warn("сырого файла в data/vino/ нет (он никогда не скачивался)")

# ------------------------------------------------------------ СЛОЙ 2: backend
print("=== СЛОЙ 2: BACKEND (порт 8000) ===")
if not tcp(8000):
    fail("backend НЕ слушает порт 8000 — Vite на любой /api-запрос вернёт 502")
else:
    ok("порт 8000 открыт")
    try:
        r = requests.get(f"{BACKEND}/api/v1/health", timeout=5)
        ok(f"health: HTTP {r.status_code} {r.text[:100]}")
    except Exception as e:
        fail(f"health не ответил: {type(e).__name__}: {e}")

    if rec and rec.get("reference_images"):
        rel = rec["reference_images"][0]
        r = requests.get(f"{BACKEND}/api/v1/images/{rel}", timeout=10)
        if r.status_code == 200 and len(r.content) > 1000:
            ok(f"статическая отдача /api/v1/images/{rel}: HTTP 200, {len(r.content)} байт")
        else:
            fail(f"статическая отдача сломана: HTTP {r.status_code}, {len(r.content)} байт")

    r = requests.get(f"{BACKEND}/api/v1/images/by-slug/{slug}", timeout=90)
    info(f"напрямую в backend /images/by-slug/{slug} -> HTTP {r.status_code} {r.text[:120]!r}")
    if r.status_code == 502:
        fail("backend сам вернул 502 (значит, он проксирует сайт и сайт лёг)")
    elif r.status_code == 404:
        warn("by-slug вернул 404: роут удалён (это норма после отката) ИЛИ on-demand не удался")
    elif r.status_code == 500:
        fail("backend упал с исключением на этом запросе — смотри traceback в его консоли")

# --------------------------------------------------------------- СЛОЙ 3: vite
print("=== СЛОЙ 3: VITE (порт 5173) ===")
if not tcp(5173):
    warn("vite не запущен (браузерный тест сейчас невозможен)")
else:
    r = requests.get(f"{VITE}/api/v1/images/by-slug/{slug}", timeout=90)
    info(f"через vite /images/by-slug/{slug} -> HTTP {r.status_code}")
    if r.status_code == 502 and tcp(8000):
        fail("vite вернул 502 при живом backend: прокси оборвался (backend падал посреди запроса?)")
    elif r.status_code == 502 and not tcp(8000):
        fail("vite вернул 502, потому что backend недоступен: запусти backend/app.py")

cfg_path = FRONT / "vite.config.js"
cfg = cfg_path.read_text(encoding="utf-8") if cfg_path.exists() else ""
if "/api" in cfg and "8000" in cfg:
    ok("proxy /api -> localhost:8000 настроен")
else:
    fail("в vite.config.js нет proxy /api -> 8000")

src_text = ""
for p in list((FRONT / "src").rglob("*.jsx")) + list((FRONT / "src").rglob("*.js")):
    src_text += p.read_text(encoding="utf-8")
if "by-slug" in src_text:
    warn("фронтенд ВСЁ ЕЩЁ дёргает /images/by-slug (старый BottleImage/api.js) — откат не применён до конца")
if "image_url" in src_text:
    ok("фронтенд использует image_url из карточки")

# -------------------------------------------------------------- СЛОЙ 4: сайт
print("=== СЛОЙ 4: САЙТ vino-svoe.ru (напрямую, без бэкенда) ===")
s = requests.Session()
s.headers.update(BROWSER)
page = f"{SITE}/wines/{slug}"
page_statuses = []
for _ in range(3):
    try:
        page_statuses.append(s.get(page, timeout=15).status_code)
    except Exception as e:
        page_statuses.append(f"EXC:{type(e).__name__}")
info(f"GET страницы карточки x3: {page_statuses}")
if any(isinstance(x, int) and x >= 500 for x in page_statuses):
    warn("сайт отдаёт 5xx на часть запросов страницы (flaky CDN)")

img = None
try:
    rp = s.get(page, timeout=15)
    m = re.search(r'<img\b[^>]*class="[^"]*wine-hero-block__bottle[^"]*"[^>]*>', rp.text, re.S)
    if m:
        m2 = re.search(r'\b(?:src|data-src)="([^"]+)"', m.group(0))
        img = m2.group(1) if m2 else None
except Exception:
    pass

if img:
    if img.startswith("//"):
        img = "https:" + img
    img_results = []
    for _ in range(3):
        try:
            ri = s.get(img, timeout=20)
            img_results.append((ri.status_code, ri.headers.get("Content-Type"), len(ri.content)))
        except Exception as e:
            img_results.append(f"EXC:{type(e).__name__}")
    info(f"GET картинки x3: {img_results}")
    if any(isinstance(x, tuple) and x[0] >= 500 for x in img_results):
        warn("CDN картинок отдаёт 5xx для requests: браузер проходит, скрипт — нет (хотлинк/WAF)")
else:
    warn("не удалось извлечь URL картинки со страницы (разметка изменилась?)")

# ------------------------------------------------------------------- вердикт
print("\n=== ВЕРДИКТ ===")
if not problems:
    print("Все слои здоровы. Ошибка в браузере была транзитной — повтори замер.")
else:
    print("Найдено проблем:")
    for p in problems:
        print("  -", p)
    print("\nЧастые комбинации и лечение:")
    print("  * FAIL 'backend НЕ слушает 8000' + 502 в браузере  ->  запусти backend/app.py")
    print("  * WARN 'фронтенд ВСЁ ЕЩЁ дёргает by-slug'        ->  откат: BottleImage(src=wine.image_url), убрать imageUrl()")
    print("  * WARN 'slug НЕТ в catalog.jsonl'                ->  вино не скачано/не в каталоге: докачай fetch_references или покажи заглушку")
    print("  * WARN 'CDN картинок отдаёт 5xx'                 ->  рантайм-парсинг ненадёжен: живи на статике из references/, on-demand выключи")