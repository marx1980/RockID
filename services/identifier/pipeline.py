"""Image -> ranked candidates. Pure function of image bytes + reference domain:
no challenge store, no labels, no request metadata."""
from dataclasses import dataclass

from PIL import Image

from packages.taxonomy.loader import Taxon
from services.identifier.encoders import Encoder
from services.identifier.knn import ReferenceIndex, aggregate, decide


@dataclass
class Identifier:
    encoder: Encoder
    index: ReferenceIndex
    taxonomy: dict[str, Taxon]
    k: int = 50

    @property
    def model_version(self) -> str:
        return self.encoder.provenance.version

    def identify(self, image: Image.Image) -> dict:
        neighbors = self.index.search(self.encoder.embed(image), k=self.k)
        decision = decide(aggregate(neighbors))
        candidates = [
            {
                "taxon_id": c.taxon_id,
                "name": self.taxonomy[c.taxon_id].canonical_name if c.taxon_id in self.taxonomy else c.taxon_id,
                "probability": round(c.probability, 4),
                "evidence": [f"similar reference specimen {s}" for s in c.supporting_specimens],
            }
            for c in decision.candidates
        ]
        follow_up = None
        if decision.status == "uncertain" and len(candidates) > 1:
            follow_up = {
                "type": "distinguish",
                "between": [c["taxon_id"] for c in candidates[:2]],
                "prompt": "Add a close-up of a fresh surface or a second angle.",
            }
        return {
            "status": decision.status,
            "top_candidates": candidates,
            "uncertainty_reason": decision.reason,
            "best_follow_up": follow_up,
        }
