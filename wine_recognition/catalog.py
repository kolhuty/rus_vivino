import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Reference:
    slug: str
    path: Path


def load_catalog(path: Path) -> list[Reference]:
    references = []
    seen = set()
    root = path.parent.resolve()
    for line_no, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        slug, images = row.get("slug"), row.get("reference_images")
        if not isinstance(slug, str) or not slug.strip() or slug in seen:
            raise ValueError(f"Invalid or duplicate slug at line {line_no}")
        if not isinstance(images, list) or not images:
            raise ValueError(f"No reference_images at line {line_no}")
        seen.add(slug)
        for image in images:
            if not isinstance(image, str) or not image:
                raise ValueError(f"Invalid reference path at line {line_no}")
            relative = Path(image)
            resolved = (root / relative).resolve()
            if relative.is_absolute() or not resolved.is_relative_to(root):
                raise ValueError(f"Reference must be relative to data: {image}")
            if not resolved.is_file():
                raise ValueError(f"Missing reference: {resolved}")
            references.append(Reference(slug, resolved))
    if not references:
        raise ValueError("Catalog is empty")
    return references
