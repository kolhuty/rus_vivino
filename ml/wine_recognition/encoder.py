import numpy as np
from PIL import Image

SIGLIP_MODEL_ID = "google/siglip2-base-patch16-224"
MODEL_ID = SIGLIP_MODEL_ID


def resolve_device(torch, device: str) -> str:
    return "cuda" if device == "auto" and torch.cuda.is_available() else (
        "cpu" if device == "auto" else device
    )


class SiglipEncoder:
    model_version = "siglip2-baseline-v1"
    recommended_batch_size = 8

    def __init__(self, model_id: str = SIGLIP_MODEL_ID, revision: str = "main", device: str = "auto"):
        import torch
        from transformers import AutoImageProcessor, AutoModel

        self.torch = torch
        self.device = resolve_device(torch, device)
        self.processor = AutoImageProcessor.from_pretrained(
            model_id, revision=revision, backend="pil"
        )
        self.model = AutoModel.from_pretrained(model_id, revision=revision).to(self.device).eval()
        self.model_id = model_id
        self.revision = self.model.config._commit_hash or revision

    def encode(self, images: list[Image.Image]) -> np.ndarray:
        inputs = self.processor(images=images, return_tensors="pt").to(self.device)
        with self.torch.inference_mode():
            features = self.model.get_image_features(**inputs)
            if hasattr(features, "pooler_output"):
                features = features.pooler_output
            features = self.torch.nn.functional.normalize(features.float(), dim=-1)
        return features.cpu().numpy()


def create_encoder(model_id: str, revision: str = "main", device: str = "auto"):
    return SiglipEncoder(model_id, revision, device)
