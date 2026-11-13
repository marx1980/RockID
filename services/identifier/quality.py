"""Image quality gate run before any model. Thresholds are placeholders until calibrated
against the low-quality challenge suite."""
from dataclasses import dataclass, field

import numpy as np
from PIL import Image

MIN_SIDE_PX = 224
MIN_SHARPNESS = 20.0  # variance of Laplacian on a 512px grayscale copy
MIN_MEAN_BRIGHTNESS = 35.0
MAX_MEAN_BRIGHTNESS = 225.0
MAX_CLIPPED_FRACTION = 0.25


@dataclass(frozen=True)
class QualityReport:
    width: int
    height: int
    sharpness: float
    mean_brightness: float
    clipped_fraction: float
    issues: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.issues

    def as_dict(self) -> dict:
        return {
            "width": self.width,
            "height": self.height,
            "sharpness": round(self.sharpness, 1),
            "mean_brightness": round(self.mean_brightness, 1),
            "clipped_fraction": round(self.clipped_fraction, 3),
            "issues": list(self.issues),
        }


def _laplacian_variance(gray: np.ndarray) -> float:
    g = gray.astype(np.float32)
    lap = -4 * g[1:-1, 1:-1] + g[:-2, 1:-1] + g[2:, 1:-1] + g[1:-1, :-2] + g[1:-1, 2:]
    return float(lap.var())


def assess(image: Image.Image) -> QualityReport:
    w, h = image.size
    gray = image.convert("L")
    gray.thumbnail((512, 512))
    arr = np.asarray(gray)
    sharp = _laplacian_variance(arr) if min(arr.shape) >= 3 else 0.0
    mean = float(arr.mean())
    clipped = float(((arr <= 2) | (arr >= 253)).mean())

    issues = []
    if min(w, h) < MIN_SIDE_PX:
        issues.append("too_small")
    if sharp < MIN_SHARPNESS:
        issues.append("blurry")
    if mean < MIN_MEAN_BRIGHTNESS:
        issues.append("too_dark")
    elif mean > MAX_MEAN_BRIGHTNESS:
        issues.append("too_bright")
    if clipped > MAX_CLIPPED_FRACTION:
        issues.append("clipped_exposure")
    return QualityReport(w, h, sharp, mean, clipped, issues)


RETAKE_PROMPTS = {
    "too_small": "Retake closer so the specimen fills the frame.",
    "blurry": "Retake in focus; hold steady or tap to focus on the specimen.",
    "too_dark": "Retake in brighter, even light (daylight works best).",
    "too_bright": "Retake out of direct glare.",
    "clipped_exposure": "Retake out of direct glare.",
}
