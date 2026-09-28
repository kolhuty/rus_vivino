
from __future__ import annotations

import json
import logging
import os
import threading
import time
from datetime import datetime, timezone
from typing import Optional

from PIL import Image

from config import ML_BASE_URL, ML_TIMEOUT, DATA_DIR, SITE_BASE_URL, FETCH_DEADLINE, ALLOW_ON_DEMAND_FETCH
from scraper import fetch_bottle_image_url, download_image, new_session, ext_for, candidate_image_urls

_fetch_semaphore = threading.Semaphore(2)


log = logging.getLogger("image_cache")

_locks: dict[str, threading.Lock] = {}
_locks_guard = threading.Lock()


def _slug_lock(slug: str) -> threading.Lock:
    with _locks_guard:
        lock = _locks.get(slug)
        if lock is None:
            lock = threading.Lock()
            _locks[slug] = lock
        
        return lock


def _ref_path(slug: str) -> str:
    return os.path.join(DATA_DIR, "references", f"{slug}.png")


# finds an image (firstly: a png, lastly: raw file from vino/ dir)
def _cached_path(slug: str) -> Optional[str]:
    scraped = os.path.join(DATA_DIR, "scraped", "images")
    for ext in (".webp", ".png", ".jpg", ".jpeg"):
        candidate = os.path.join(scraped, slug + ext)
        if os.path.isfile(candidate) and os.path.getsize(candidate) > 0:
            return candidate

    ref = _ref_path(slug)
    if os.path.exists(ref) and os.path.getsize(ref) > 0:
        return ref

    vino = os.path.join(DATA_DIR, "vino")
    if os.path.isdir(vino):
        for name in os.listdir(vino):
            if name.startswith(slug + ".") and name != f"{slug}.part":
                p = os.path.join(vino, name)
                if os.path.getsize(p) > 0:
                    return p

    return None


def _convert_to_reference(src: str, slug: str) -> str:
    out = _ref_path(slug)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    tmp = out + ".part"
    
    import shutil
    shutil.copy2(src, tmp)
    os.replace(tmp, out)
    
    return out


# logs errors (if any)
def _queue_miss(slug: str, error: str) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    queue_path = os.path.join(DATA_DIR, "scrape_queue.jsonl")
    report_path = os.path.join(DATA_DIR, "scrape_report.jsonl")

    rec = {
        "slug": slug,
        "error": error,
        "source": "ondemand",
        "ts": datetime.now(timezone.utc).isoformat(),
    }

    line = json.dumps(rec, ensure_ascii=False) + "\n"
    
    with _locks_guard:
        with open(queue_path, "a", encoding="utf-8") as f:
            f.write(line)
        with open(report_path, "a", encoding="utf-8") as f:
            f.write(line)


# loadds slug
def _fetch_and_cache(slug: str) -> Optional[str]:
    session = new_session()
    deadline = time.monotonic() + FETCH_DEADLINE

    if time.monotonic() >= deadline:
        return None

    acquired = _fetch_semaphore.acquire(timeout=FETCH_DEADLINE)
    if not acquired:
        _queue_miss(slug, "semaphore_timeout")
        return None
    
    try:
        meta = fetch_bottle_image_url(slug, SITE_BASE_URL, session)
        if not meta["image_url"]:
            _queue_miss(slug, meta["error"] or "no_image_url")
            return None

        if time.monotonic() >= deadline:
            _queue_miss(slug, "deadline_before_download")
            return None

        vino_dir = os.path.join(DATA_DIR, "vino")
        os.makedirs(vino_dir, exist_ok=True)
        
        ok, err = False, "no_image_url"
        for url in candidate_image_urls(meta["image_url"]):
            raw_path = os.path.join(vino_dir, f"{slug}{ext_for(url)}")
            ok, err = download_image(url, raw_path, session, referer=meta.get("page_url"))
            if ok:
                break
        if not ok:
            _queue_miss(slug, f"download_failed: {err}")
            return None
    finally:
        _fetch_semaphore.release()   # освобождаем слот даже при ошибке

    try:
        ref = _convert_to_reference(raw_path, slug)
        return ref
    except Exception as e:
        log.warning("convert failed for %s: %s", slug, e)
        _queue_miss(slug, f"convert_failed: {e}")
        return None


# returns path to a local image OR None if there's no cached file
def get_or_fetch(slug: str) -> Optional[str]:
    path = _cached_path(slug)
    if path:
        return path

    if not ALLOW_ON_DEMAND_FETCH:
        _queue_miss(slug, "fetch_disabled")
        return None

    lock = _slug_lock(slug)
    if not lock.acquire(timeout=FETCH_DEADLINE + 1):
        log.warning("lock timeout for %s", slug)
        _queue_miss(slug, "lock_timeout")
        return None
    try:
        path = _cached_path(slug)
        if path:
            return path
        return _fetch_and_cache(slug)
    finally:
        lock.release()







