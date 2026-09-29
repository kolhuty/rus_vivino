#!/usr/bin/env python3

# THIS FILE PERFORMES INTERNAL DEV EVALUATION AND IS NOT INTENDED TO BE USED BY THE CASEHOLDER 

import argparse
import csv
import json
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
REPORTS = ROOT / "reports"


def load_manifest(path: Path):
    """Манифест JSONL, формат ТЗ:
    {"query_id":"q-000001","image_path":"public_test/q-000001.jpg",
     "slug":"fanagoriya-...","split":"test_real","conditions":["glare"]}
    Для вина вне каталога slug = null.
    """
    items = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                items.append(json.loads(line))
    return items


def load_queries_tsv(path: Path):
    items = []
    with open(path, encoding="utf-8") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            low = {(k or "").strip().lower(): (v or "").strip() for k, v in row.items()}
            img = low.get("image_path") or low.get("image") or low.get("path") or ""
            slug = low.get("slug") or low.get("answer") or low.get("gt") or ""
            if img:
                items.append({
                    "query_id": low.get("query_id") or img,
                    "image_path": img,
                    "slug": slug or None,
                    "split": low.get("split") or "external",
                    "conditions": [],
                })

    return items


def resolve_image(rel: str) -> Path:
    p = Path(rel)
    if p.is_absolute() and p.exists():
        return p
    for base in (DATA, ROOT):
        cand = base / rel
        if cand.exists():
            return cand
        
    raise FileNotFoundError(rel)



def ask_service(base_url: str, mode: str, image_path: Path, timeout: int):
    """Один запрос. Возвращает (top1, top5, status, server_latency_ms)."""
    with open(image_path, "rb") as f:
        content_type = {
            ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
            ".png": "image/png", ".webp": "image/webp",
        }.get(image_path.suffix.lower(), "application/octet-stream")
        files = {"image": (image_path.name, f, content_type)}

        if mode == "scan":          # контракт организатора: строго {"slug": ...}
            r = requests.post(f"{base_url}/api/v1/scan", files=files, timeout=timeout)
            r.raise_for_status()
            slug = r.json().get("slug")
            return slug, ([slug] if slug else []), None, None

        if mode == "recognize":     # продуктовый эндпоинт backend
            r = requests.post(f"{base_url}/api/v1/recognize", files=files, timeout=timeout)
            r.raise_for_status()
            d = r.json()
            top5 = ([d["main"]["slug"]] if d.get("main") else [])
            top5 += [o["slug"] for o in (d.get("others") or [])]
            return (top5[0] if top5 else None), top5, d.get("status"), d.get("latency_ms")

        # mode == "ml": напрямую в ml-сервис, минуя backend
        r = requests.post(f"{base_url}/v1/predict", files=files, timeout=timeout)
        r.raise_for_status()
        d = r.json()
        top5 = [c["slug"] for c in (d.get("top5") or [])]
        return d.get("slug"), top5, d.get("status"), d.get("latency_ms")


def percentile(xs, q):
    if not xs:
        return None
    xs = sorted(xs)
    k = max(0, min(len(xs) - 1, int(round(q * (len(xs) - 1)))))
    return round(xs[k], 1)




def main():
    ap = argparse.ArgumentParser(description="Оценка качества распознавания")
    ap.add_argument("--manifest", default=str(DATA / "public_test" / "manifest.jsonl"))
    ap.add_argument("--queries-tsv", default=None, help="адаптер к queries.tsv организатора")
    ap.add_argument("--base-url", default="http://127.0.0.1:8000")
    ap.add_argument("--mode", choices=["scan", "recognize", "ml"], default="recognize")
    ap.add_argument("--timeout", type=int, default=30)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--split", default=None, help="фильтр по полю split манифеста")
    args = ap.parse_args()

    if args.mode == "ml" and args.base_url.rstrip("/").endswith(":8000"):
        print("ПОДСКАЗКА: mode=ml обычно означает порт 8001: --base-url http://127.0.0.1:8001")

    items = (load_queries_tsv(Path(args.queries_tsv)) if args.queries_tsv
             else load_manifest(Path(args.manifest)))
    if args.split:
        items = [it for it in items if it.get("split") == args.split]
    if args.limit:
        items = items[: args.limit]
    if not items:
        sys.exit(f"Пустой набор запросов: {args.manifest}")

    preds, errors = [], 0
    for i, it in enumerate(items, 1):
        qid = it.get("query_id") or f"q-{i:04d}"
        expected = it.get("slug")
        try:
            img = resolve_image(it["image_path"])
            t0 = time.perf_counter()
            top1, top5, status, server_ms = ask_service(args.base_url, args.mode, img, args.timeout)
            client_ms = (time.perf_counter() - t0) * 1000.0
        except Exception as e:
            errors += 1
            print(f"[{i}/{len(items)}] {qid}: ERROR {type(e).__name__}: {e}")
            preds.append({"query_id": qid, "expected": expected, "top1": None, "top5": [],
                          "status": "error", "client_ms": None, "server_ms": None,
                          "conditions": it.get("conditions") or []})
            continue
        verdict = "OK" if top1 == expected else ("MISS" if expected else f"status={status}")
        print(f"[{i}/{len(items)}] {qid}: pred={top1} expected={expected} {verdict}")
        preds.append({"query_id": qid, "expected": expected, "top1": top1, "top5": top5,
                      "status": status, "client_ms": round(client_ms, 1),
                      "server_ms": server_ms, "conditions": it.get("conditions") or []})


    # metrics
    pos = [p for p in preds if p["expected"] and p["status"] != "error"]
    neg = [p for p in preds if p["expected"] is None and p["status"] != "error"]

    top1_acc = (sum(1 for p in pos if p["top1"] == p["expected"]) / len(pos)) if pos else None
    recall5 = (sum(1 for p in pos if p["expected"] in (p["top5"] or [])) / len(pos)) \
        if pos and args.mode != "scan" else None

    classes = sorted({p["expected"] for p in pos} | {p["top1"] for p in pos if p["top1"]})
    per_class = {}
    for c in classes:
        tp = sum(1 for p in pos if p["expected"] == c and p["top1"] == c)
        fp = sum(1 for p in pos if p["expected"] != c and p["top1"] == c)
        fn = sum(1 for p in pos if p["expected"] == c and p["top1"] != c)
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
        support = sum(1 for p in pos if p["expected"] == c)
        if support:
            per_class[c] = {"support": support, "precision": round(prec, 3),
                            "recall": round(rec, 3), "f1": round(f1, 3)}
    macro_f1 = (sum(v["f1"] for v in per_class.values()) / len(per_class)) if per_class else None

    client_ms = [p["client_ms"] for p in preds if p["client_ms"] is not None]
    server_ms = [p["server_ms"] for p in preds if p["server_ms"] is not None]

    if neg and args.mode == "scan":
        neg_stats = {"n": len(neg),
                     "note": "scan всегда возвращает slug: отказы по контракту неизмеримы"}
    elif neg:
        neg_stats = {
            "n": len(neg),
            "correct_refusals": sum(1 for p in neg if p["status"] in ("not_found", "ambiguous")),
            "false_accepts": sum(1 for p in neg if p["status"] == "matched"),
        }
    else:
        neg_stats = None

    by_cond = {}
    for c in sorted({c for p in preds for c in p["conditions"]}):
        sub = [p for p in pos if c in p["conditions"]]
        if sub:
            by_cond[c] = {"n": len(sub),
                          "top1_accuracy": round(
                              sum(1 for p in sub if p["top1"] == p["expected"]) / len(sub), 3)}

    confusion = Counter((p["expected"], p["top1"]) for p in pos if p["top1"] != p["expected"])

    result = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "mode": args.mode,
        "base_url": args.base_url,
        "manifest": str(Path(args.manifest)),
        "split_filter": args.split,
        "n_queries": len(preds),
        "n_positives": len(pos),
        "n_negatives": len(neg),
        "n_errors": errors,
        "top1_accuracy": round(top1_acc, 4) if top1_acc is not None else None,
        "recall_at_5": round(recall5, 4) if recall5 is not None else None,
        "macro_f1": round(macro_f1, 4) if macro_f1 is not None else None,
        "latency_client_ms": {"median": percentile(client_ms, 0.5),
                              "p95": percentile(client_ms, 0.95)},
        "latency_server_ms": ({"median": percentile(server_ms, 0.5),
                               "p95": percentile(server_ms, 0.95)} if server_ms else None),
        "negatives": neg_stats,
        "by_condition": by_cond,
        "per_class": per_class,
        "top_confusion_pairs": [{"expected": e, "predicted": g, "count": n}
                                for (e, g), n in confusion.most_common(10)],
    }

    REPORTS.mkdir(parents=True, exist_ok=True)
    out = REPORTS / "eval_results.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    preds_out = REPORTS / "eval_predictions.jsonl"
    preds_out.write_text("\n".join(json.dumps(p, ensure_ascii=False) for p in preds) + "\n",
                         encoding="utf-8")

    print("\n=== ИТОГИ ===")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"\Saved: {out}\n           {preds_out}")




if __name__ == "__main__":
    main()
