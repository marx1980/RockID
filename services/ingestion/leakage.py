"""Duplicate and train/test leakage detection.

Image-level checks (sha256, rotation/mirror-invariant pHash) catch copies.
Group-level checks (specimen_id, source page) catch the more dangerous leak:
a *different* photo of the *same* specimen on both sides of the split.
Crops are not caught by pHash; they are covered by the specimen/source checks.
"""
import hashlib
from dataclasses import dataclass, field
from io import BytesIO

import imagehash
from PIL import Image, ImageOps

DEFAULT_PHASH_THRESHOLD = 8  # uncalibrated; tune on the real corpus (PHASE0_TODO)


@dataclass(frozen=True)
class Fingerprint:
    sha256: str
    phash: str
    phash_variants: tuple[str, ...] = field(default=())  # 8 dihedral variants incl. phash


def _dihedral(image: Image.Image) -> list[Image.Image]:
    out = []
    for base in (image, ImageOps.mirror(image)):
        for angle in (0, 90, 180, 270):
            out.append(base.rotate(angle, expand=True) if angle else base)
    return out


def fingerprint_bytes(raw: bytes) -> Fingerprint:
    with Image.open(BytesIO(raw)) as img:
        rgb = img.convert("RGB")
    variants = tuple(str(imagehash.phash(v)) for v in _dihedral(rgb))
    return Fingerprint(hashlib.sha256(raw).hexdigest(), variants[0], variants)


def fingerprint(path: str) -> Fingerprint:
    with open(path, "rb") as fh:
        return fingerprint_bytes(fh.read())


def phash_distance(a: str, b: str) -> int:
    return imagehash.hex_to_hash(a) - imagehash.hex_to_hash(b)


def min_phash_distance(a: Fingerprint, b: Fingerprint) -> int:
    variants = b.phash_variants or (b.phash,)
    return min(phash_distance(a.phash, v) for v in variants)


def requires_duplicate_review(
    a: Fingerprint, b: Fingerprint, phash_threshold: int = DEFAULT_PHASH_THRESHOLD
) -> bool:
    return a.sha256 == b.sha256 or min_phash_distance(a, b) <= phash_threshold


@dataclass(frozen=True)
class AssetRecord:
    asset_id: str
    specimen_id: str
    source_url: str
    sha256: str
    phash: str
    phash_variants: tuple[str, ...] = ()

    @property
    def fingerprint(self) -> Fingerprint:
        return Fingerprint(self.sha256, self.phash, self.phash_variants)


@dataclass(frozen=True)
class LeakageFinding:
    reference_asset: str
    challenge_asset: str
    reason: str  # exact_duplicate | near_duplicate | same_specimen | same_source_page


def _source_page(url: str) -> str:
    return url.split("#", 1)[0].split("?", 1)[0].rstrip("/").lower()


def find_split_leakage(
    reference: list[AssetRecord],
    challenge: list[AssetRecord],
    phash_threshold: int = DEFAULT_PHASH_THRESHOLD,
) -> list[LeakageFinding]:
    """Every reason a challenge asset must be quarantined against the reference set."""
    by_specimen: dict[str, list[str]] = {}
    by_source: dict[str, list[str]] = {}
    by_sha: dict[str, list[str]] = {}
    for r in reference:
        by_specimen.setdefault(r.specimen_id, []).append(r.asset_id)
        by_source.setdefault(_source_page(r.source_url), []).append(r.asset_id)
        by_sha.setdefault(r.sha256, []).append(r.asset_id)

    findings: list[LeakageFinding] = []
    for c in challenge:
        for ref_id in by_sha.get(c.sha256, []):
            findings.append(LeakageFinding(ref_id, c.asset_id, "exact_duplicate"))
        for ref_id in by_specimen.get(c.specimen_id, []):
            findings.append(LeakageFinding(ref_id, c.asset_id, "same_specimen"))
        if c.source_url:
            for ref_id in by_source.get(_source_page(c.source_url), []):
                findings.append(LeakageFinding(ref_id, c.asset_id, "same_source_page"))
        for r in reference:
            if r.sha256 != c.sha256 and min_phash_distance(c.fingerprint, r.fingerprint) <= phash_threshold:
                findings.append(LeakageFinding(r.asset_id, c.asset_id, "near_duplicate"))
    return findings
