import numpy as np
from PIL import Image

SIGLIP_MODEL_ID = "google/siglip2-base-patch16-224"
QWEN_MODEL_ID = "Qwen/Qwen3-VL-Embedding-2B"
MODEL_ID = SIGLIP_MODEL_ID
QWEN_INSTRUCTION = (
    "Represent this wine bottle or wine label image for exact product retrieval. "
    "Pay special attention to visible brand, wine name, grape variety, vintage, and label design."
)


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


class QwenVlEncoder:
    recommended_batch_size = 1

    def __init__(self, model_id: str = QWEN_MODEL_ID, revision: str = "main", device: str = "auto"):
        import torch
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise RuntimeError(
                "Qwen3-VL requires sentence-transformers, qwen-vl-utils and sentencepiece; "
                "install requirements.txt first"
            ) from exc

        self.torch = torch
        self.device = resolve_device(torch, device)
        self.model = SentenceTransformer(
            model_id,
            revision=revision,
            device=self.device,
            trust_remote_code=True,
            model_kwargs={"torch_dtype": torch.float32 if self.device == "cpu" else torch.bfloat16},
        )
        self.model_id = model_id
        self.revision = revision
        self.model_version = f"{model_id.rsplit('/', 1)[-1].lower()}-v1"

    def encode(self, images: list[Image.Image]) -> np.ndarray:
        inputs = [{"image": image} for image in images]
        features = self.model.encode(
            inputs,
            prompt=QWEN_INSTRUCTION,
            batch_size=self.recommended_batch_size,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return np.asarray(features, dtype=np.float32)


def create_encoder(model_id: str, revision: str = "main", device: str = "auto"):
    if "qwen3-vl-embedding" in model_id.lower():
        return QwenVlEncoder(model_id, revision, device)
    return SiglipEncoder(model_id, revision, device)
