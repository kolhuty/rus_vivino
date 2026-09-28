#!/usr/bin/env python3

import argparse
import csv
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
import scraper

SITE_BASE = os.getenv("SITE_BASE_URL", "https://vino-svoe.ru")
DATA = ROOT / "data"
VINO = DATA / "vino"


def load_slugs():
    cat = DATA / "catalog.jsonl"
    if cat.exists() and cat.stat().st_size > 0:
        return [json.loads(l)["slug"]
                for l in cat.read_text(encoding="utf-8").splitlines() if l.strip()]

    with open(DATA / "dataset_vino.csv", encoding="utf-8") as f:
        return [(row.get("slug") or row.get("Slug") or "").strip()
                for row in csv.DictReader(f)
                if (row.get("slug") or row.get("Slug"))]


def existing(slug):
    for p in VINO.glob(f"{slug}.*"):
        if p.suffix != ".part" and p.stat().st_size > 0:
            return p
    return None


def process(slug, sleep):
    hit = existing(slug)
    if hit:
        return {"slug": slug, "status": "skipped", "file": hit.name}

    session = scraper.new_session()
    meta = scraper.fetch_bottle_image_url(slug, SITE_BASE, session)
    if not meta["image_url"]:
        return {"slug": slug, "status": meta["error"] or "no_image_url", **meta}

    ok, err = False, "no_image_url"
    dest = None
    for url in scraper.candidate_image_urls(meta["image_url"]):
        dest = VINO / f"{slug}{scraper.ext_for(url)}"
        ok, err = scraper.download_image(url, str(dest), session)
        if ok:
            meta["image_url"] = url
            break
    time.sleep(sleep)

    if not ok:
        return {"slug": slug, "status": "download_failed", **meta, "error": err}
    
    return {"slug": slug, "status": "ok", "file": dest.name, **meta}



def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--sleep", type=float, default=0.6)
    ap.add_argument("--limit", type=int, default=0, help="обработать только N первых slug")
    args = ap.parse_args()

    VINO.mkdir(parents=True, exist_ok=True)
    slugs = load_slugs()
    if args.limit:
        slugs = slugs[: args.limit]

    sources, report = [], []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futs = [pool.submit(process, s, args.sleep) for s in slugs]
        for i, fut in enumerate(futs, 1):
            res = fut.result()
            print(f"[{i}/{len(slugs)}] {res['slug']}: {res['status']}")
            res["fetched_at"] = datetime.now(timezone.utc).isoformat()
            (sources if res["status"] in ("ok", "skipped") else report).append(res)

    (DATA / "sources.jsonl").write_text(
        "\n".join(json.dumps(x, ensure_ascii=False) for x in sources) + "\n", encoding="utf-8")
    (DATA / "scrape_report.jsonl").write_text(
        "\n".join(json.dumps(x, ensure_ascii=False) for x in report) + "\n", encoding="utf-8")
    print(f"ok/skipped: {len(sources)}, ошибок: {len(report)} -> data/scrape_report.jsonl")




if __name__ == "__main__":
    main()