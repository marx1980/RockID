import hashlib
import os
from io import BytesIO
from typing import Literal

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from PIL import Image, ImageOps, UnidentifiedImageError
from pydantic import BaseModel

from services.identifier.quality import RETAKE_PROMPTS, assess

MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", str(15 * 1024 * 1024)))
Image.MAX_IMAGE_PIXELS = int(os.getenv("MAX_IMAGE_PIXELS", str(50_000_000)))
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}

app = FastAPI(title="Rock ID API", version="0.2.0")
# Set to a services.identifier.pipeline.Identifier once an encoder and reference index exist.
app.state.identifier = None


class Candidate(BaseModel):
    taxon_id: str
    name: str
    probability: float
    evidence: list[str] = []


class Identification(BaseModel):
    status: Literal["identified", "uncertain", "unknown", "need_more_evidence"]
    top_candidates: list[Candidate]
    visible_features: dict = {}
    image_quality: dict = {}
    uncertainty_reason: str | None = None
    best_follow_up: dict | None = None
    model_version: str
    taxonomy_version: str
    input_sha256: str


@app.get("/health")
def health():
    return {
        "status": "ok",
        "challenge_credentials_present": any(k.startswith("CHALLENGE_") for k in os.environ),
        "model_loaded": app.state.identifier is not None,
    }


def _decode(raw: bytes) -> Image.Image:
    if not raw:
        raise HTTPException(422, "Empty upload.")
    try:
        with Image.open(BytesIO(raw)) as probe:
            fmt = probe.format
            probe.verify()
        if fmt not in ALLOWED_FORMATS:
            raise HTTPException(415, f"Unsupported image format {fmt}; use JPEG, PNG or WebP.")
        img = Image.open(BytesIO(raw))
        img.load()
    except Image.DecompressionBombError:
        raise HTTPException(413, "Image has too many pixels.")
    except (UnidentifiedImageError, OSError, SyntaxError):
        raise HTTPException(422, "Upload is not a readable image.")
    return ImageOps.exif_transpose(img).convert("RGB")


@app.post("/v1/identify", response_model=Identification)
async def identify(request: Request, image: UploadFile = File(...)):
    raw = await image.read(MAX_UPLOAD_BYTES + 1)
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, f"Image larger than {MAX_UPLOAD_BYTES} bytes.")
    sha = hashlib.sha256(raw).hexdigest()
    img = _decode(raw)
    quality = assess(img)

    identifier = request.app.state.identifier
    base = dict(
        model_version=identifier.model_version if identifier else os.getenv("MODEL_VERSION", "baseline-0"),
        taxonomy_version=os.getenv("TAXONOMY_VERSION", "mvp21-v1"),
        input_sha256=sha,
        image_quality=quality.as_dict(),
    )

    if not quality.ok:
        first = quality.issues[0]
        return Identification(
            status="need_more_evidence",
            top_candidates=[],
            uncertainty_reason=f"Image quality: {', '.join(quality.issues)}.",
            best_follow_up={"type": "retake_photo", "issue": first, "prompt": RETAKE_PROMPTS[first]},
            **base,
        )

    if identifier is None:
        # Honest Phase-0 behaviour: no fake classifier is substituted for a model.
        return Identification(
            status="need_more_evidence",
            top_candidates=[],
            uncertainty_reason="No trained geological vision model is installed in baseline-0.",
            best_follow_up={"type": "model_required", "prompt": "Install and benchmark the approved visual encoder."},
            **base,
        )

    return Identification(**identifier.identify(img), **base)
