import json
import tempfile
import unittest
from io import BytesIO
from pathlib import Path

import numpy as np
from PIL import Image

from wine_recognition.catalog import load_catalog
from wine_recognition.images import InvalidImage, read_image
from wine_recognition.index import SearchIndex
from wine_recognition.service import WineRecognizer


class BaselineTests(unittest.TestCase):
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

    def test_corrupt_and_webp_queries_rejected(self):
        with self.assertRaises(InvalidImage):
            read_image(b"broken")
        buffer = BytesIO()
        Image.new("RGB", (4, 4)).save(buffer, format="WEBP")
        with self.assertRaises(InvalidImage):
            read_image(buffer.getvalue())
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
