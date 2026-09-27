"""Convert the local CSV and Strapi images into the specification's catalog."""
import argparse
import csv
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from wine_recognition.images import read_image


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", type=Path, default=Path("data/dataset_vino.csv"))
    parser.add_argument("--images", type=Path, default=Path("data/vino"))
    parser.add_argument("--output", type=Path, default=Path("data/catalog.jsonl"))
    args = parser.parse_args()
    rows = list(csv.DictReader(args.csv.open(encoding="utf-8-sig", newline="")))
    counts = Counter(row["Slug"] for row in rows)
    files = {}
    for path in args.images.rglob("*"):
        if path.is_file():
            stem = re.sub(r"^(thumbnail_|small_|medium_|large_)", "", path.stem)
            stem = re.sub(r"_[0-9a-f]{10}$", "", stem)
            files.setdefault(stem, []).append(path)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    references = args.output.parent / "references"
    references.mkdir(exist_ok=True)
    report, catalog, manifest = [], [], []
    pixel_hashes = {}
    for row in rows:
        slug = row["Slug"]
        if not slug or counts[slug] != 1:
            report.append({"slug": slug, "problem": "empty_or_duplicate_slug"})
            continue
        candidates = files.get(Path(row["Название фото"]).stem, [])
        if len(candidates) != 1:
            report.append({"slug": slug, "problem": "missing_or_ambiguous_image",
                           "candidates": [str(p) for p in candidates]})
            continue
        source = candidates[0]
        try:
            image = read_image(source, query=False)
            digest = hashlib.sha256(image.tobytes() + str(image.size).encode()).hexdigest()
            filename = hashlib.sha256(slug.encode()).hexdigest() + ".png"
            image.save(references / filename)
            image.close()
        except ValueError as exc:
            report.append({"slug": slug, "problem": str(exc)})
            continue
        if digest in pixel_hashes:
            report.append({"slug": slug, "problem": "identical_pixels",
                           "other_slug": pixel_hashes[digest]})
        pixel_hashes[digest] = slug
        catalog.append({"slug": slug, "reference_images": [f"references/{filename}"],
                        "name": row.get("Название вина"), "producer": row.get("Винодельня")})
        manifest.append({"slug": slug, "source_path": str(source.resolve()),
                         "source_csv": str(args.csv.resolve()), "source_url": None})
    for path, records in [(args.output, catalog),
                          (args.output.with_name("catalog_report.jsonl"), report),
                          (args.output.with_name("sources.jsonl"), manifest)]:
        path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records), encoding="utf-8")
    print(f"Catalog: {len(catalog)}; report entries: {len(report)}")
    if not catalog:
        raise SystemExit("No usable catalog entries; inspect catalog_report.jsonl")


if __name__ == "__main__":
    main()
