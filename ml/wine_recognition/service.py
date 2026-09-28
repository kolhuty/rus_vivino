from threading import Lock
from time import perf_counter

from .encoder import create_encoder
from .images import read_image
from .index import SearchIndex
from .localizer import LabelLocalizer


class WineRecognizer:
    def __init__(self, index: SearchIndex, encoder, localizer=None):
        self.index = index
        self.encoder = encoder
        self.localizer = localizer
        self.lock = Lock()

    @classmethod
    def load(cls, path, device="auto", localize=True, detector_model=None):
        index = SearchIndex.load(path)
        encoder = create_encoder(
            index.metadata["model_id"], index.metadata["revision"], device
        )
        if not localize:
            localizer = None
        else:
            localizer = LabelLocalizer.load(device, detector_model) if detector_model else (
                LabelLocalizer.load(device)
            )
        return cls(index, encoder, localizer)

    def predict(self, source, diagnostic=False):
        start = perf_counter()
        image = read_image(source)
        localized = None
        bottle_image = None
        try:
            with self.lock:
                localized = self.localizer.localize(image) if self.localizer else None
                model_images = [image]
                if localized is not None and localized.bottle_box is not None:
                    bottle_image = image.crop(localized.bottle_box.as_list())
                    # Once localization succeeds, the full shelf photo is harmful:
                    # cosine scores from different views are not directly calibrated.
                    model_images = [bottle_image, localized.image]
                queries = self.encoder.encode(model_images)
            top5 = self.index.search_many(queries)
        finally:
            if bottle_image is not None:
                bottle_image.close()
            if localized is not None:
                localized.image.close()
            image.close()
        if not diagnostic:
            return {"slug": top5[0]["slug"]}
        result = {
            "status": "matched", "slug": top5[0]["slug"], "score": top5[0]["score"],
            "margin": top5[0]["score"] - top5[1]["score"] if len(top5) > 1 else None,
            "confidence": None, "top5": top5,
            "model_version": self.index.metadata["model_version"],
            "catalog_version": self.index.metadata["catalog_version"],
            "latency_ms": round((perf_counter() - start) * 1000, 2),
        }
        if localized is not None:
            result["localization"] = {
                "bottle_count": localized.bottle_count,
                "bottle_box": localized.bottle_box.as_list() if localized.bottle_box else None,
                "label_box": localized.label_box.as_list(),
                "views_used": 2 if localized.bottle_box else 1,
                "strategy": "bottle+label" if localized.bottle_box else "full-frame-fallback",
            }
        return result
