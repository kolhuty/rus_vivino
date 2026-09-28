"""Convert the scraped CSV and its local images into the retrieval catalog."""
import argparse
import csv
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path

from PIL import Image, ImageOps

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from wine_recognition.images import read_image


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", type=Path, default=Path("catalog_scraped.csv"))
    parser.add_argument("--images", type=Path, default=Path("data/scraped/images"))
    parser.add_argument("--output", type=Path, default=Path("data/catalog.jsonl"))
    args = parser.parse_args()
    with args.csv.open(encoding="utf-8-sig", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        required = {"slug", "image_local"}
        missing_columns = required.difference(reader.fieldnames or ())
        if missing_columns:
            raise SystemExit(f"Missing CSV columns: {', '.join(sorted(missing_columns))}")
        rows = list(reader)
    rows_by_slug = defaultdict(list)
    for row in rows:
        rows_by_slug[row["slug"].strip()].append(row)

    files_by_name = defaultdict(list)
    for path in args.images.rglob("*"):
        if path.is_file():
            files_by_name[path.name].append(path)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    references = args.output.parent / "references"
    references.mkdir(exist_ok=True)
    report, catalog, manifest = [], [], []
    pixel_hashes = {}
    for slug, duplicate_rows in rows_by_slug.items():
        if not slug:
            report.append({"slug": slug, "problem": "empty_slug"})
            continue
        # Collapse exact duplicate records while rejecting conflicting slug records.
        signatures = {tuple(sorted(row.items())) for row in duplicate_rows}
        if len(signatures) != 1:
            report.append({"slug": slug, "problem": "conflicting_duplicate_slug"})
            continue
        row = duplicate_rows[0]
        image_local = row["image_local"].strip()
        photo_name = Path(image_local.replace("\\", "/")).name
        candidates = files_by_name.get(photo_name, []) if photo_name else []
        if len(candidates) != 1:
            report.append({"slug": slug, "problem": "missing_or_ambiguous_image",
                           "candidates": [str(p) for p in candidates]})
            continue
        source = candidates[0]
        try:
            image = read_image(source, query=False)
            digest = hashlib.sha256(image.tobytes() + str(image.size).encode()).hexdigest()
            filename = hashlib.sha256(slug.encode()).hexdigest() + ".png"
            # The RGB copy is used for retrieval, but display assets must retain
            # the source alpha channel instead of baking transparent pixels into
            # an opaque grey background.
            with Image.open(source) as display_image:
                display_image.load()
                ImageOps.exif_transpose(display_image).save(references / filename)
            image.close()
        except ValueError as exc:
            report.append({"slug": slug, "problem": str(exc)})
            continue
        if digest in pixel_hashes:
            report.append({"slug": slug, "problem": "identical_pixels",
                           "other_slug": pixel_hashes[digest]})
        pixel_hashes[digest] = slug
        catalog.append({"slug": slug, "reference_images": [f"references/{filename}"],
                        "name": row.get("name"), "producer": row.get("producer")})
        manifest.append({"slug": slug, "source_path": str(source.resolve()),
                         "source_csv": str(args.csv.resolve()),
                         "source_url": row.get("image_url") or None})
    for path, records in [(args.output, catalog),
                          (args.output.with_name("catalog_report.jsonl"), report),
                          (args.output.with_name("sources.jsonl"), manifest)]:
        path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records), encoding="utf-8")
    print(f"Catalog: {len(catalog)}; report entries: {len(report)}")
    if not catalog:
        raise SystemExit("No usable catalog entries; inspect catalog_report.jsonl")


if __name__ == "__main__":
    main()
