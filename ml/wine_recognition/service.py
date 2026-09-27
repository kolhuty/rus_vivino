from threading import Lock
from time import perf_counter

from .encoder import SiglipEncoder
from .images import read_image
from .index import SearchIndex


class WineRecognizer:
    def __init__(self, index: SearchIndex, encoder):
        self.index = index
        self.encoder = encoder
        self.lock = Lock()

    @classmethod
    def load(cls, path, device="auto"):
        index = SearchIndex.load(path)
        encoder = SiglipEncoder(index.metadata["model_id"], index.metadata["revision"], device)
        return cls(index, encoder)

    def predict(self, source, diagnostic=False):
        start = perf_counter()
        image = read_image(source)
        try:
            with self.lock:
                query = self.encoder.encode([image])[0]
            top5 = self.index.search(query)
        finally:
            image.close()
        if not diagnostic:
            return {"slug": top5[0]["slug"]}
        return {
            "status": "matched", "slug": top5[0]["slug"], "score": top5[0]["score"],
            "margin": top5[0]["score"] - top5[1]["score"] if len(top5) > 1 else None,
            "confidence": None, "top5": top5,
            "model_version": self.index.metadata["model_version"],
            "catalog_version": self.index.metadata["catalog_version"],
            "latency_ms": round((perf_counter() - start) * 1000, 2),
        }
