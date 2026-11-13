"""Visual encoder adapters.

Each adapter records the exact weights it loaded (model id + revision) so every benchmark
result can be traced to model-weight provenance. torch/transformers are optional
(requirements-ml.txt) and imported lazily, so the baseline image stays small.
"""
from dataclasses import dataclass
from typing import Protocol

import numpy as np
from PIL import Image


class Encoder(Protocol):
    @property
    def provenance(self) -> "EncoderProvenance": ...
    def embed(self, image: Image.Image) -> np.ndarray: ...  # L2-normalised 1-D vector


@dataclass(frozen=True)
class EncoderProvenance:
    family: str  # dinov2 | siglip2 | test
    model_id: str
    revision: str
    dim: int
    license: str

    @property
    def version(self) -> str:
        return f"{self.family}:{self.model_id}@{self.revision}"


def _l2(v: np.ndarray) -> np.ndarray:
    v = np.asarray(v, dtype=np.float32).reshape(-1)
    n = float(np.linalg.norm(v))
    return v / n if n else v


class DinoV2Encoder:
    """CLS embedding from DINOv2. Weights: Apache-2.0 (verify on the model card before use)."""

    def __init__(self, model_id: str = "facebook/dinov2-base", revision: str = "main", device: str = "cpu"):
        import torch
        from transformers import AutoImageProcessor, AutoModel

        self._torch = torch
        self._proc = AutoImageProcessor.from_pretrained(model_id, revision=revision)
        self._model = AutoModel.from_pretrained(model_id, revision=revision).to(device).eval()
        self._device = device
        self.provenance = EncoderProvenance(
            "dinov2", model_id, revision, self._model.config.hidden_size, "Apache-2.0"
        )

    def embed(self, image: Image.Image) -> np.ndarray:
        with self._torch.inference_mode():
            inputs = self._proc(images=image.convert("RGB"), return_tensors="pt").to(self._device)
            out = self._model(**inputs)
            return _l2(out.last_hidden_state[:, 0].cpu().numpy())


class SigLIP2Encoder:
    """Image embedding from SigLIP2. Weights: Apache-2.0 (verify on the model card before use)."""

    def __init__(self, model_id: str = "google/siglip2-base-patch16-224", revision: str = "main", device: str = "cpu"):
        import torch
        from transformers import AutoModel, AutoProcessor

        self._torch = torch
        self._proc = AutoProcessor.from_pretrained(model_id, revision=revision)
        self._model = AutoModel.from_pretrained(model_id, revision=revision).to(device).eval()
        self._device = device
        dim = self._model.config.vision_config.hidden_size
        self.provenance = EncoderProvenance("siglip2", model_id, revision, dim, "Apache-2.0")

    def embed(self, image: Image.Image) -> np.ndarray:
        with self._torch.inference_mode():
            inputs = self._proc(images=image.convert("RGB"), return_tensors="pt").to(self._device)
            return _l2(self._model.get_image_features(**inputs).cpu().numpy())
