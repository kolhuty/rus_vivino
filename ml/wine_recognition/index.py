import json
from pathlib import Path

import numpy as np

from .catalog import load_catalog
from .images import read_image


class SearchIndex:
    def __init__(self, vectors: np.ndarray, slugs: list[str], metadata: dict):
        vectors = np.asarray(vectors, dtype=np.float32)
        if vectors.ndim != 2 or not len(slugs) or len(vectors) != len(slugs):
            raise ValueError("Invalid or empty index")
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        if not np.isfinite(vectors).all() or (norms <= 0).any():
            raise ValueError("Invalid index vectors")
        self.vectors = vectors / norms
        self.slugs = slugs
        self.metadata = metadata

    def search(self, query: np.ndarray, k: int = 5) -> list[dict]:
        return self.search_many(np.asarray(query).reshape(1, -1), k)

    def search_many(self, queries: np.ndarray, k: int = 5) -> list[dict]:
        """Rank slugs by their best score across full-frame and cropped views."""
        queries = np.asarray(queries, dtype=np.float32)
        if queries.ndim != 2 or not len(queries):
            raise ValueError("Invalid query embeddings")
        norms = np.linalg.norm(queries, axis=1, keepdims=True)
        if not np.isfinite(queries).all() or (norms <= 0).any():
            raise ValueError("Invalid query embeddings")
        scores = (self.vectors @ (queries / norms).T).max(axis=1)
        # Multiple reference images contribute their maximum similarity per slug.
        best = {}
        for slug, score in zip(self.slugs, scores):
            best[slug] = max(best.get(slug, -float("inf")), float(score))
        ranked = sorted(best.items(), key=lambda item: (-item[1], item[0]))[:k]
        return [{"slug": slug, "score": score} for slug, score in ranked]

    def save(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("wb") as file:
            np.savez_compressed(file, vectors=self.vectors, slugs=np.array(self.slugs),
                                metadata=np.array(json.dumps(self.metadata)))

    @classmethod
    def load(cls, path: Path):
        with np.load(path, allow_pickle=False) as data:
            return cls(data["vectors"], data["slugs"].tolist(), json.loads(str(data["metadata"])))


def build_index(catalog: Path, encoder, batch_size: int, catalog_version: str) -> SearchIndex:
    if batch_size < 1:
        raise ValueError("batch_size must be positive")
    references = load_catalog(catalog)
    batches = []
    for start in range(0, len(references), batch_size):
        images = [read_image(ref.path, query=False) for ref in references[start:start + batch_size]]
        try:
            batches.append(encoder.encode(images))
        finally:
            for image in images:
                image.close()
        print(f"Indexed {min(start + batch_size, len(references))}/{len(references)}")
    return SearchIndex(np.concatenate(batches), [ref.slug for ref in references], {
        "model_id": encoder.model_id, "revision": encoder.revision,
        "model_version": encoder.model_version, "catalog_version": catalog_version,
        "score": "cosine similarity; maximum over references per slug",
    })
