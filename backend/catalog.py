
import json
import os
from typing import Optional, Dict, Any
from config import DATA_DIR

_catalog: Dict[str, Dict[str, Any]] = {}
_source_images: Dict[str, str] = {}


def load_catalog(data_dir: str) -> Dict[str, Dict[str, Any]]:
    global _catalog, _source_images
    _catalog = {}
    _source_images = {}
    path = os.path.join(data_dir, "catalog.jsonl")

    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            slug = rec.get("slug")
            if slug:
                _catalog[slug] = rec

    sources_path = os.path.join(data_dir, "sources.jsonl")
    if os.path.exists(sources_path):
        data_root = os.path.realpath(data_dir)
        with open(sources_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                slug = rec.get("slug")
                source = rec.get("source_path")
                if not slug or not source:
                    continue
                source = os.path.realpath(source)
                if os.path.commonpath([data_root, source]) != data_root or not os.path.isfile(source):
                    continue
                _source_images[slug] = os.path.relpath(source, data_root).replace(os.sep, "/")
    
    return _catalog


def get_catalog() -> Dict[str, Dict[str, Any]]:
    return _catalog


def _display_image_url(slug: str, refs: list, image_base: str):
    source = _source_images.get(slug)
    if source:
        return f"{image_base}/{source}"
    vino = os.path.join(DATA_DIR, "vino")
    if os.path.isdir(vino):
        for name in sorted(os.listdir(vino)):
            if name.startswith(slug + ".") and not name.endswith(".part"):
                return f"{image_base}/vino/{name}"
    if refs:
        return f"{image_base}/{refs[0]}"
    return None


def card(slug: str, image_base: str = "/api/v1/images"):
    rec = _catalog.get(slug)
    if not rec:
        return None
    refs = rec.get("reference_images") or []
    return {
        "slug": slug,
        "name": rec.get("name"),
        "producer": rec.get("producer"),
        "year": rec.get("year"),
        "category": rec.get("category"),
        "series": rec.get("series"),
        "duplicate_group": rec.get("duplicate_group"),
        "image_url": _display_image_url(slug, refs, image_base),
    }
