from dataclasses import dataclass

import numpy as np
from PIL import Image


DETECTOR_MODEL_ID = "hustvl/yolos-small"


@dataclass(frozen=True)
class Box:
    left: int
    top: int
    right: int
    bottom: int

    @property
    def width(self) -> int:
        return self.right - self.left

    @property
    def height(self) -> int:
        return self.bottom - self.top

    def as_list(self) -> list[int]:
        return [self.left, self.top, self.right, self.bottom]


@dataclass(frozen=True)
class Detection:
    box: Box
    score: float


@dataclass
class Localization:
    image: Image.Image
    label_box: Box
    bottle_box: Box | None
    bottle_count: int


def select_center_bottle(
    detections: list[Detection], image_size: tuple[int, int]
) -> Detection | None:
    """Choose the bottle whose bbox centre is nearest to the image centre."""
    if not detections:
        return None
    width, height = image_size

    def rank(detection: Detection):
        box = detection.box
        dx = ((box.left + box.right) / 2 - width / 2) / max(width, 1)
        dy = ((box.top + box.bottom) / 2 - height / 2) / max(height, 1)
        # Score is only a deterministic tie-breaker; position has priority.
        return dx * dx + dy * dy, -detection.score

    return min(detections, key=rank)


def _intersection_over_union(first: Box, second: Box) -> float:
    width = max(0, min(first.right, second.right) - max(first.left, second.left))
    height = max(0, min(first.bottom, second.bottom) - max(first.top, second.top))
    intersection = width * height
    union = first.width * first.height + second.width * second.height - intersection
    return intersection / union if union > 0 else 0.0


def filter_bottle_detections(
    detections: list[Detection], *, relative_score: float = .35, nms_iou: float = .55
) -> list[Detection]:
    """Drop weak multi-bottle boxes and duplicate predictions before centring."""
    if not detections:
        return []
    cutoff = max(.05, max(item.score for item in detections) * relative_score)
    candidates = sorted(
        (item for item in detections if item.score >= cutoff),
        key=lambda item: item.score,
        reverse=True,
    )
    kept = []
    for candidate in candidates:
        if all(_intersection_over_union(candidate.box, item.box) < nms_iou for item in kept):
            kept.append(candidate)
    return kept


def _clip_box(box: Box, image_size: tuple[int, int]) -> Box:
    width, height = image_size
    left = min(max(box.left, 0), max(width - 1, 0))
    top = min(max(box.top, 0), max(height - 1, 0))
    right = min(max(box.right, left + 1), width)
    bottom = min(max(box.bottom, top + 1), height)
    return Box(left, top, right, bottom)


def _integral(values: np.ndarray) -> np.ndarray:
    return np.pad(values.cumsum(0).cumsum(1), ((1, 0), (1, 0)))


def _rect_mean(integral: np.ndarray, left: int, top: int, right: int, bottom: int) -> float:
    total = (
        integral[bottom, right]
        - integral[top, right]
        - integral[bottom, left]
        + integral[top, left]
    )
    return float(total) / ((right - left) * (bottom - top))


def find_label_box(image: Image.Image, bottle_box: Box) -> Box:
    """Find a high-detail, label-shaped region inside a detected bottle."""
    bottle_box = _clip_box(bottle_box, image.size)
    bottle = image.crop(bottle_box.as_list()).convert("L")
    scale = min(1.0, 180 / max(bottle.width, 1), 260 / max(bottle.height, 1))
    small_size = (
        max(16, round(bottle.width * scale)),
        max(24, round(bottle.height * scale)),
    )
    gray = np.asarray(bottle.resize(small_size, Image.Resampling.BILINEAR), dtype=np.float32) / 255
    texture = np.zeros_like(gray)
    texture[:, 1:] += np.abs(gray[:, 1:] - gray[:, :-1])
    texture[1:, :] += np.abs(gray[1:, :] - gray[:-1, :])
    detail = _integral(texture)
    brightness = _integral(gray)
    brightness_sq = _integral(gray * gray)
    height, width = gray.shape

    best_score = -float("inf")
    best = (0, round(height * .25), width, round(height * .85))
    for width_fraction in (.55, .7, .85):
        candidate_width = max(8, round(width * width_fraction))
        for height_fraction in (.22, .32, .42):
            candidate_height = max(8, round(height * height_fraction))
            for center_x in (.42, .5, .58):
                for center_y in (.58, .68, .78):
                    left = min(max(round(width * center_x - candidate_width / 2), 0), width - candidate_width)
                    top = min(max(round(height * center_y - candidate_height / 2), 0), height - candidate_height)
                    right, bottom = left + candidate_width, top + candidate_height
                    mean = _rect_mean(brightness, left, top, right, bottom)
                    variance = max(
                        0.0,
                        _rect_mean(brightness_sq, left, top, right, bottom) - mean * mean,
                    )
                    edge_score = _rect_mean(detail, left, top, right, bottom)
                    spatial_penalty = .08 * ((center_x - .5) ** 2 + (center_y - .68) ** 2)
                    score = edge_score + .35 * variance ** .5 - spatial_penalty
                    if score > best_score:
                        best_score = score
                        best = (left, top, right, bottom)

    left, top, right, bottom = best
    # The score often locks onto the text-heavy middle of a label. Keep generous
    # context so the brand name, vintage and label border are not cut away.
    vertical_padding = round(height * .18)
    # A detected bottle is already narrow; retain nearly all of its width so
    # curved label edges and side text remain visible.
    left = round(width * .03)
    top = max(0, top - vertical_padding)
    right = round(width * .97)
    bottom = min(height, bottom + vertical_padding)
    x_scale = bottle_box.width / width
    y_scale = bottle_box.height / height
    return _clip_box(Box(
        bottle_box.left + round(left * x_scale),
        bottle_box.top + round(top * y_scale),
        bottle_box.left + round(right * x_scale),
        bottle_box.top + round(bottom * y_scale),
    ), image.size)


class BottleDetector:
    def __init__(
        self,
        model_id: str = DETECTOR_MODEL_ID,
        device: str = "auto",
        threshold: float = .05,
    ):
        import torch
        from transformers import AutoImageProcessor, AutoModelForObjectDetection

        self.torch = torch
        self.device = "cuda" if device == "auto" and torch.cuda.is_available() else (
            "cpu" if device == "auto" else device
        )
        self.processor = AutoImageProcessor.from_pretrained(model_id, backend="pil")
        self.model = AutoModelForObjectDetection.from_pretrained(model_id).to(self.device).eval()
        self.threshold = threshold

    def detect(self, image: Image.Image) -> list[Detection]:
        inputs = self.processor(images=image, return_tensors="pt").to(self.device)
        with self.torch.inference_mode():
            outputs = self.model(**inputs)
        target_sizes = self.torch.tensor([image.size[::-1]], device=self.device)
        result = self.processor.post_process_object_detection(
            outputs, threshold=self.threshold, target_sizes=target_sizes
        )[0]
        detections = []
        for score, label, coords in zip(result["scores"], result["labels"], result["boxes"]):
            name = self.model.config.id2label[int(label)].lower()
            if name == "bottle":
                left, top, right, bottom = (round(value) for value in coords.tolist())
                detections.append(Detection(_clip_box(Box(left, top, right, bottom), image.size), float(score)))
        return filter_bottle_detections(detections)


class LabelLocalizer:
    def __init__(self, detector):
        self.detector = detector

    @classmethod
    def load(cls, device: str = "auto", model_id: str = DETECTOR_MODEL_ID):
        return cls(BottleDetector(model_id=model_id, device=device))

    def localize(self, image: Image.Image) -> Localization:
        bottles = self.detector.detect(image)
        selected = select_center_bottle(bottles, image.size)
        if selected is None:
            full = Box(0, 0, image.width, image.height)
            return Localization(image.copy(), full, None, 0)
        label_box = find_label_box(image, selected.box)
        return Localization(image.crop(label_box.as_list()), label_box, selected.box, len(bottles))
