from dataclasses import dataclass
import hashlib
from PIL import Image
import imagehash

@dataclass
class Fingerprint:
    sha256: str
    phash: str

def fingerprint(path: str) -> Fingerprint:
    raw = open(path, "rb").read()
    with Image.open(path) as image:
        p = str(imagehash.phash(image.convert("RGB")))
    return Fingerprint(hashlib.sha256(raw).hexdigest(), p)

def phash_distance(a: str, b: str) -> int:
    return imagehash.hex_to_hash(a) - imagehash.hex_to_hash(b)

def requires_duplicate_review(a: Fingerprint, b: Fingerprint, phash_threshold: int = 8) -> bool:
    return a.sha256 == b.sha256 or phash_distance(a.phash, b.phash) <= phash_threshold
