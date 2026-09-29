import json
import tempfile
import unittest
from unittest.mock import patch
from io import BytesIO
from pathlib import Path

import numpy as np
from PIL import Image

from wine_recognition.catalog import load_catalog
from wine_recognition.encoder import create_encoder
from wine_recognition.images import InvalidImage, read_image
from wine_recognition.index import SearchIndex
from wine_recognition.localizer import (
    Box, Detection, Localization, filter_bottle_detections, select_center_bottle,
)
from wine_recognition.service import WineRecognizer


class BaselineTests(unittest.TestCase):
    def test_encoder_factory_creates_siglip(self):
        with patch("wine_recognition.encoder.SiglipEncoder") as siglip:
            create_encoder("google/siglip2-base-patch16-224", "rev", "cpu")
            siglip.assert_called_once_with("google/siglip2-base-patch16-224", "rev", "cpu")

    def test_bottle_nearest_image_center_is_selected(self):
        bottles = [
            Detection(Box(0, 10, 20, 90), .99),
            Detection(Box(42, 5, 62, 95), .75),
            Detection(Box(80, 10, 100, 90), .98),
        ]
        selected = select_center_bottle(bottles, (100, 100))
        self.assertEqual(selected.box, Box(42, 5, 62, 95))

    def test_weak_large_detection_is_removed_before_center_selection(self):
        detections = [
            Detection(Box(35, 20, 85, 90), .13),
            Detection(Box(49, 25, 62, 85), .99),
            Detection(Box(50, 26, 63, 84), .91),
            Detection(Box(65, 25, 78, 85), .95),
        ]
        filtered = filter_bottle_detections(detections)
        self.assertEqual(len(filtered), 2)
        self.assertNotIn(detections[0], filtered)
        self.assertEqual(
            select_center_bottle(filtered, (120, 100)).box,
            Box(49, 25, 62, 85),
        )

    def test_service_encodes_localized_label(self):
        class Encoder:
            def __init__(self):
                self.seen_sizes = None

            def encode(self, images):
                self.seen_sizes = [image.size for image in images]
                return np.repeat(np.array([[1, 0]], dtype=np.float32), len(images), axis=0)

        class Localizer:
            def localize(self, image):
                box = Box(2, 3, 8, 9)
                return Localization(image.crop(box.as_list()), box, Box(1, 1, 9, 10), 2)

        index = SearchIndex(np.eye(2), ["a", "b"], {
            "model_version": "test", "catalog_version": "test",
        })
        encoder = Encoder()
        service = WineRecognizer(index, encoder, Localizer())
        buffer = BytesIO()
        Image.new("RGB", (12, 14)).save(buffer, format="PNG")
        result = service.predict(buffer.getvalue(), diagnostic=True)
        self.assertEqual(encoder.seen_sizes, [(8, 9), (6, 6)])
        self.assertEqual(result["localization"]["bottle_count"], 2)
        self.assertEqual(result["localization"]["label_box"], [2, 3, 8, 9])
        self.assertEqual(result["localization"]["views_used"], 2)
        self.assertEqual(result["localization"]["strategy"], "bottle+label")

    def test_prediction_contract(self):
        class Encoder:
            def encode(self, images):
                return np.array([[1, 0]], dtype=np.float32)
        index = SearchIndex(np.eye(2), ["a", "b"], {
            "model_version": "test", "catalog_version": "test",
        })
        service = WineRecognizer(index, Encoder())
        buffer = BytesIO()
        Image.new("RGB", (4, 4)).save(buffer, format="PNG")
        self.assertEqual(service.predict(buffer.getvalue()), {"slug": "a"})
        result = service.predict(buffer.getvalue(), diagnostic=True)
        self.assertIsNone(result["confidence"])
        self.assertEqual(len(result["top5"]), 2)
        json.dumps(result, allow_nan=False)

    def test_unique_slug_ranking_and_roundtrip(self):
        index = SearchIndex(np.array([[1, 0], [.9, .1], [0, 1]]), ["a", "a", "b"], {})
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "index.npz"
            index.save(path)
            top = SearchIndex.load(path).search(np.array([1, 0]))
        self.assertEqual([r["slug"] for r in top], ["a", "b"])
        self.assertAlmostEqual(top[0]["score"], 1)

    def test_multi_view_search_uses_best_view_per_slug(self):
        index = SearchIndex(np.eye(2), ["a", "b"], {})
        top = index.search_many(np.array([[.1, 1], [1, .1]], dtype=np.float32))
        self.assertEqual({item["slug"] for item in top}, {"a", "b"})
        self.assertGreater(top[0]["score"], .99)

    def test_corrupt_query_rejected_and_webp_normalized(self):
        with self.assertRaises(InvalidImage):
            read_image(b"broken")
        buffer = BytesIO()
        Image.new("RGB", (4, 4)).save(buffer, format="WEBP")
        self.assertEqual(read_image(buffer.getvalue()).mode, "RGB")
        self.assertEqual(read_image(buffer.getvalue(), query=False).mode, "RGB")

    def test_duplicate_catalog_slugs_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            Image.new("RGB", (4, 4)).save(root / "a.png")
            row = json.dumps({"slug": "a", "reference_images": ["a.png"]})
            path = root / "catalog.jsonl"
            path.write_text(row + "\n" + row, encoding="utf-8")
            with self.assertRaises(ValueError):
                load_catalog(path)


if __name__ == "__main__":
    unittest.main()
