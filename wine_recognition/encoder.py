import numpy as np
from PIL import Image

MODEL_ID = "google/siglip2-base-patch16-224"


class SiglipEncoder:
    def __init__(self, model_id: str = MODEL_ID, revision: str = "main", device: str = "auto"):
        import torch
        from transformers import AutoImageProcessor, AutoModel

        self.torch = torch
        self.device = "cuda" if device == "auto" and torch.cuda.is_available() else (
            "cpu" if device == "auto" else device
        )
        self.processor = AutoImageProcessor.from_pretrained(model_id, revision=revision)
        self.model = AutoModel.from_pretrained(model_id, revision=revision).to(self.device).eval()
        self.model_id = model_id
        self.revision = self.model.config._commit_hash or revision

    def encode(self, images: list[Image.Image]) -> np.ndarray:
        inputs = self.processor(images=images, return_tensors="pt").to(self.device)
        with self.torch.inference_mode():
            features = self.model.get_image_features(**inputs)
            features = self.torch.nn.functional.normalize(features.float(), dim=-1)
        return features.cpu().numpy()
