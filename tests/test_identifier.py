import numpy as np
from PIL import Image

from packages.taxonomy.loader import confusion_pairs, load_taxonomy
from services.identifier.encoders import EncoderProvenance
from services.identifier.knn import ReferenceIndex, ReferenceItem, aggregate, decide
from services.identifier.pipeline import Identifier
from services.identifier.quality import assess


def test_taxonomy_loads_with_feldspar_and_confusion_pairs():
    tax = load_taxonomy()
    assert len(tax) == 21 and "min.k-feldspar" in tax
    pairs = confusion_pairs(tax)
    assert ("min.quartz", "rock.chert") in pairs
    assert ("min.quartz", "rock.quartzite") in pairs


def test_one_specimen_with_many_photos_cannot_outvote_many_specimens():
    items, vecs = [], []
    for i in range(30):  # 30 photos of ONE calcite specimen, all fairly close
        items.append(ReferenceItem(f"c{i}", "calcite-1", "min.calcite"))
        vecs.append([0.90, 0.44, 0])
    for i in range(3):  # 3 different quartz specimens, slightly closer
        items.append(ReferenceItem(f"q{i}", f"quartz-{i}", "min.quartz"))
        vecs.append([0.92, 0.39, 0])
    idx = ReferenceIndex(items, np.array(vecs))
    scores = aggregate(idx.search(np.array([1.0, 0.0, 0.0]), k=50))
    assert scores[0].taxon_id == "min.quartz"
    assert len(scores[0].supporting_specimens) == 3
    assert scores[1].supporting_specimens == ("calcite-1",)


def _index():
    items, vecs = [], []
    for t, axis in (("min.quartz", 0), ("min.calcite", 1)):
        for s in range(3):
            items.append(ReferenceItem(f"{t}-{s}", f"{t}-spec{s}", t))
            v = np.zeros(4)
            v[axis] = 1.0
            v[3] = 0.05 * s
            vecs.append(v)
    return ReferenceIndex(items, np.array(vecs))


def test_decide_identifies_abstains_and_rejects_ood():
    idx = _index()
    assert decide(aggregate(idx.search(np.array([1, 0, 0, 0])))).status == "identified"
    assert decide(aggregate(idx.search(np.array([1, 1, 0, 0])))).status == "uncertain"
    assert decide(aggregate(idx.search(np.array([0, 0, 1, 0])))).status == "unknown"


class FakeEncoder:
    provenance = EncoderProvenance("test", "fake", "0", 4, "n/a")

    def __init__(self, vec):
        self.vec = np.array(vec, dtype=np.float32)

    def embed(self, image):
        return self.vec


def test_pipeline_output_shape():
    ident = Identifier(FakeEncoder([1, 0, 0, 0]), _index(), load_taxonomy())
    out = ident.identify(Image.new("RGB", (8, 8)))
    assert out["status"] == "identified"
    assert out["top_candidates"][0]["name"] == "Quartz"
    assert ident.model_version == "test:fake@0"


def test_quality_gate():
    rng = np.random.default_rng(0)
    sharp = Image.fromarray(rng.integers(40, 215, (400, 400, 3), dtype=np.uint8))
    assert assess(sharp).ok
    assert "too_small" in assess(sharp.resize((100, 100))).issues
    assert "blurry" in assess(Image.new("RGB", (400, 400), (120, 120, 120))).issues
    assert "too_dark" in assess(Image.new("RGB", (400, 400), (5, 5, 5))).issues
