from fastapi import FastAPI, UploadFile, File
from pydantic import BaseModel
from typing import Literal
import hashlib, os

app = FastAPI(title="Rock ID API", version="0.1.0")

class Candidate(BaseModel):
    taxon_id: str
    name: str
    probability: float
    evidence: list[str] = []

class Identification(BaseModel):
    status: Literal["identified","uncertain","unknown","need_more_evidence"]
    top_candidates: list[Candidate]
    visible_features: dict = {}
    uncertainty_reason: str | None = None
    best_follow_up: dict | None = None
    model_version: str
    taxonomy_version: str
    input_sha256: str

@app.get("/health")
def health():
    return {"status":"ok", "challenge_credentials_present": bool(os.getenv("CHALLENGE_DATABASE_URL"))}

@app.post("/v1/identify", response_model=Identification)
async def identify(image: UploadFile = File(...)):
    raw = await image.read()
    sha = hashlib.sha256(raw).hexdigest()
    # Honest Phase-0 behavior: contract works, but no fake classifier is substituted for a model.
    return Identification(
        status="need_more_evidence",
        top_candidates=[],
        uncertainty_reason="No trained geological vision model is installed in baseline-0.",
        best_follow_up={"type":"model_required","prompt":"Install and benchmark the approved visual encoder."},
        model_version=os.getenv("MODEL_VERSION","baseline-0"),
        taxonomy_version=os.getenv("TAXONOMY_VERSION","mvp20-v0"),
        input_sha256=sha,
    )
