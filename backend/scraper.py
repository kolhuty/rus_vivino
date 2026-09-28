
from __future__ import annotations

import json
import os
import re
import time
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup


IMG_CLASS = "wine-hero-block__bottle"
TIMEOUT = 15
RETRIES = 3
DOWNLOAD_RETRIES = 1

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "ru,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://vino-svoe.ru/",
    "Connection": "keep-alive",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
}

_IMG_EXT = re.compile(r"\.(jpe?g|png|webp)(\?|#|$)", re.I)
_STRAPI_SIZE = re.compile(r"_(thumbnail|small|medium|large)\.")
_RESIZE = re.compile(r"/\d+/\d+/resize/")
_FLAKY = {502, 503, 504, 429}


def candidate_page_urls(slug: str, site_base: str) -> list[str]:
    urls = []
    head, _, tail = slug.rpartition("-")
    if head and tail.isdigit() and len(tail) == 4:
        urls.append(f"{site_base}/wines/{head}")
    urls.append(f"{site_base}/wines/{slug}")

    return urls


def normalize_image_url(url: str) -> str:
    if url.startswith("//"):
        url = "https:" + url

    return _STRAPI_SIZE.sub(".", url)


def candidate_image_urls(url: str) -> list[str]:
    urls = []
    m = _RESIZE.search(url)
    if m:
        urls.append(url[:m.start()] + "/" + url[m.end():])
        urls.append(url[:m.start()] + "/4000/4000/resize/" + url[m.end():])
    urls.append(url)
    seen, out = set(), []
    for u in urls:
        if u not in seen:
            seen.add(u)
            out.append(u)

    return out


def _looks_like_image(head: bytes) -> bool:
    return (
        head[:4] == b"\x89PNG"
        or head[:3] == b"\xff\xd8\xff"
        or (head[:4] == b"RIFF" and head[8:12] == b"WEBP")
        or head[:6] in (b"GIF87a", b"GIF89a")
    )


def _from_dom(html: str, page_url: str):
    soup = BeautifulSoup(html, "html.parser")
    img = soup.find("img", class_=IMG_CLASS)
    if not img:
        return None
    for attr in ("src", "data-src", "data-lazy-src"):
        val = img.get(attr)
        if val and not val.startswith("data:"):
            return urljoin(page_url, val)
    first = (img.get("srcset") or "").split(",")[0].strip().split(" ")[0]
    if first and not first.startswith("data:"):
        return urljoin(page_url, first)
    
    return None


def _from_raw_regex(html: str, page_url: str):
    m = re.search(r"<img\b[^>]*class=\"[^\"]*" + IMG_CLASS + r"[^\"]*\"[^>]*>", html, re.S)
    if not m:
        return None
    m2 = re.search(r"\b(?:src|data-src)=\"([^\"]+)\"", m.group(0))

    return urljoin(page_url, m2.group(1)) if m2 else None


def _from_nuxt_payload(html: str, page_url: str):
    strings: list[str] = []
    m = re.search(r'<script[^>]+id="__NUXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    if m:
        try:
            data = json.loads(m.group(1))
            if isinstance(data, list):
                strings = [x for x in data if isinstance(x, str)]
        except ValueError:
            pass
    if not strings and "window.__NUXT__" in html:
        idx = html.index("window.__NUXT__")
        strings = re.findall(r'"(https?://[^"]+)"', html[idx:])
    bottle = [s for s in strings if _IMG_EXT.search(s) and "bottle" in s.lower()]
    pool = bottle or [s for s in strings if _IMG_EXT.search(s)]

    return urljoin(page_url, pool[0]) if pool else None


def new_session() -> requests.Session:
    s = requests.Session()
    s.headers.update(HEADERS)

    return s


def fetch_bottle_image_url(slug: str, site_base: str, session: requests.Session | None = None):
    s = session or new_session()
    error = "no_candidates"
    page_url = None
    for page in candidate_page_urls(slug, site_base):
        for attempt in range(RETRIES):
            try:
                resp = s.get(page, timeout=TIMEOUT)
            except requests.RequestException as e:
                error = f"{type(e).__name__}: {e}"
                time.sleep(1.5 * (attempt + 1))
                continue
            if resp.status_code in _FLAKY:
                error = f"http_{resp.status_code}"
                time.sleep(2.0 * (attempt + 1))
                continue
            if resp.status_code == 404:
                error = "http_404"
                break
            if resp.status_code == 403:
                error = "http_403"
                time.sleep(2.0 * (attempt + 1))
                continue
            resp.raise_for_status()
            html = resp.text
            raw = (_from_dom(html, resp.url)
                   or _from_raw_regex(html, resp.url)
                   or _from_nuxt_payload(html, resp.url))
            if raw:
                return {"image_url": normalize_image_url(raw),
                        "page_url": str(resp.url), "error": None}
            error = "no_img_in_html"
            break

    return {"image_url": None, "page_url": page_url, "error": error}


def download_image(image_url: str, dest: str, session: requests.Session | None = None,
                   referer: str | None = None):
    s = session or new_session()
    tmp = dest + ".part"
    last_err = "unknown"
    extra_headers = {}
    if referer:
        extra_headers["Referer"] = referer
        extra_headers["Sec-Fetch-Dest"] = "image"
        extra_headers["Sec-Fetch-Mode"] = "no-cors"
        extra_headers["Sec-Fetch-Site"] = "cross-site"

    for attempt in range(DOWNLOAD_RETRIES):
        try:
            with s.get(image_url, timeout=30, stream=True, headers=extra_headers) as resp:
                if resp.status_code in _FLAKY:
                    last_err = f"http_{resp.status_code}"
                    time.sleep(2.0 * (attempt + 1))
                    continue
                if resp.status_code != 200:
                    last_err = f"http_{resp.status_code}"
                    time.sleep(1.0 * (attempt + 1))
                    continue
                with open(tmp, "wb") as f:
                    for chunk in resp.iter_content(1 << 16):
                        f.write(chunk)
            with open(tmp, "rb") as f:
                head = f.read(12)
            if not _looks_like_image(head):
                os.remove(tmp)
                last_err = f"not_an_image:{head[:8]!r}"
                time.sleep(1.0 * (attempt + 1))
                continue
            os.replace(tmp, dest)
            return True, None
        except requests.RequestException as e:
            last_err = f"{type(e).__name__}: {e}"
            time.sleep(1.5 * (attempt + 1))
        except OSError as e:
            last_err = f"OSError: {e}"
            time.sleep(1.0 * (attempt + 1))
    if os.path.exists(tmp):
        os.remove(tmp)

    return False, last_err


def ext_for(url: str) -> str:
    suffix = os.path.splitext(urlsplit(url).path)[1].lower()

    return suffix if suffix in (".jpg", ".jpeg", ".png", ".webp") else ".jpg"