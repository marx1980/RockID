"""Challenge set C: stones (specimens) with 2 to 5 photos each, to test multi-photo identification.
Rules, numbers and the runbook: docs/CHALLENGE_C.md. Steps (offline = agent shell, runner = Actions):

  pool    candidates.csv decisions.json reference.csv review_c.csv out_pool.csv vault/*.csv   offline
  sheets  pool.csv out_dir                                                                     runner
  decide  sheets/index.json review_c.csv taxon --keep 1-4,7 [--views "2:1-3;5:1,3"] [--reasons "6:not_same_stone"]
          [--tumbled 3] [--polished 7] [--missing sheets/missing.json]                         offline
  draft   pool.csv review_c.csv out_draft.csv                                                  offline
  check   draft.csv reference.csv out_report.json [--vectors emb/draft] [other set csvs]       runner
  freeze  draft.csv report.json decisions.json out_challenge_c.csv                             offline

Leakage is checked globally: a stone shares no individual photographer, specimen or source page with any
reference-side photo (reference.csv plus every approved or reserved candidate, any taxon) or with any
vault set (A, B, OOD, form hold-out). Institutions credited as author are exempt from the photographer
rule (they have no photographer key) but are capped and flagged `institution=1`.
"""
import argparse
import csv
import hashlib
import json
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from types import SimpleNamespace

from packages.taxonomy.loader import load_taxonomy
from services.curation.apply import CHALLENGE_COLUMNS
from services.curation.challenge_b import _keys
from services.ingestion.candidates import read_candidates
from services.ingestion.decisions import load_decisions, save_decisions

MIN_VIEWS, TARGET_VIEWS, MAX_VIEWS, POOL_MAX_VIEWS = 2, 3, 5, 8
POOL_STONES_PER_TAXON = {"live": 25, "extra": 12}  # review load: about 150 sheets at most
PER_AUTHOR_TAXON, PER_AUTHOR_TOTAL = 3, 8
PER_INSTITUTION_TAXON, INSTITUTION_SHARE = 5, 0.50
MAX_STONES = {"live": 15, "extra": 8}
TARGET_STONES = {"live": 10, "extra": 5}
MIN_REPORT_STONES = 5
NON_NATURAL_SHARE = 0.25
EXTRA_MIN_PHOTOS, EXTRA_MIN_COLLECTIONS = 10, 2
PHASH_DUP, COS_DUP = 8, 0.95
FREEZE_MIN_LIVE_STONES, FREEZE_MIN_LIVE_CLASSES = 60, 10
UNDERPOWERED_MIN_LIVE_STONES = 40  # pre-registered fallback; every result is then labelled underpowered
POOL_COLUMNS = ["stone_id", "view", "candidate_id", "taxon_id", "scope", "institution", "specimen_id", "source_name",
                "source_url", "media_url", "author", "license", "title"]
REVIEW_COLUMNS = ["candidate_id", "taxon_id", "stone_id", "view", "decision", "reason", "form", "reviewer", "sheet"]
C_COLUMNS = CHALLENGE_COLUMNS + ["stone_id", "view", "form", "institution", "scope"]
EXTRA = Path(__file__).resolve().parents[2] / "packages" / "taxonomy" / "extra_minerals.csv"


def _author(author: str, source: str) -> str:
    a = (author or "").strip()
    return "" if a in ("", source) else a.lower()


def _collection(author: str, source: str) -> str:
    return _author(author, source) or source


def _h(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def _natural(s: str) -> list:
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", s)]


def stone_id(taxon: str, specimen_hint: str, collection: str) -> str:
    return "cs:" + _h(f"{taxon}|{specimen_hint}|{collection}")[:12]


def _rows(path) -> list[dict]:
    if not path or not Path(path).exists():
        return []
    with Path(path).open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _write(path, columns, rows) -> None:
    with Path(path).open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=columns, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def reference_side(cands: dict, decisions: dict, reference_csv) -> list[tuple[str, str, str, str, str]]:
    """(taxon, author, source, specimen, url) of every photo that is or will be a reference photo or a test case."""
    out = [(r["taxon_id"], r["author"], r["source_name"], r["specimen_id"], r["source_url"]) for r in _rows(reference_csv)]
    for cid, d in decisions.items():
        c = cands.get(cid)
        if c and (d.startswith("approve") or d == "reserve"):
            out.append((c.taxon_id, c.author, c.source_name, c.specimen_hint, c.source_url))
    return out


def blocked_keys(side, other_csvs=()) -> set[str]:
    keys = set()
    for _, author, source, specimen, url in side:
        keys |= _keys(author, source, specimen, url)
    for path in other_csvs:
        for r in _rows(path):
            keys |= _keys(r.get("author", ""), r.get("source_name", ""), r.get("specimen_id", ""), r.get("source_url", ""))
    return keys


def class_scope(side) -> dict[str, str]:
    """Live classes always; an extra mineral only with >= 10 reference-side photos from >= 2 collections."""
    scope = {t: "live" for t in load_taxonomy()}
    extra = {r["taxon_id"] for r in _rows(EXTRA)}
    photos, colls = Counter(), defaultdict(set)
    for taxon, author, source, _, _ in side:
        photos[taxon] += 1
        colls[taxon].add(_collection(author, source))
    for t in sorted(extra):
        if photos[t] >= EXTRA_MIN_PHOTOS and len(colls[t]) >= EXTRA_MIN_COLLECTIONS:
            scope[t] = "extra"
    return scope


def pool(candidates_csv, decisions_path, reference_csv, review_c_csv, out_csv, other_csvs=(), taxa=None) -> dict:
    cands = {c.candidate_id: c for c in read_candidates(candidates_csv)}
    decisions = load_decisions(decisions_path)
    reviewed = {r["candidate_id"] for r in _rows(review_c_csv)}
    side = reference_side(cands, decisions, reference_csv)
    blocked = blocked_keys(side, other_csvs)
    scope = class_scope(side)
    groups: dict[tuple, list] = defaultdict(list)
    for c in cands.values():
        if c.taxon_id not in scope or (taxa and c.taxon_id not in taxa) or c.proposed_usage == "rejected":
            continue
        if c.candidate_id in decisions or c.candidate_id in reviewed:
            continue
        groups[(c.taxon_id, c.specimen_hint, _collection(c.author, c.source_name))].append(c)
    hint_taxa = defaultdict(set)
    for taxon, hint, _ in groups:
        hint_taxa[hint].add(taxon)
    by_taxon: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))
    dropped = Counter()
    for (taxon, hint, coll), items in groups.items():
        if len(items) < MIN_VIEWS:
            continue
        if len(hint_taxa[hint]) > 1:
            dropped["hint_under_two_taxa"] += 1
            continue
        if any(c.other_taxa_in_title for c in items):  # an associated live taxon is named: identity ambiguous
            dropped["other_taxon_in_title"] += 1
            continue
        if set().union(*(_keys(c.author, c.source_name, c.specimen_hint, c.source_url) for c in items)) & blocked:
            dropped["shares_key_with_reference_or_vault"] += 1
            continue
        by_taxon[taxon][coll].append((stone_id(taxon, hint, coll), sorted(items, key=lambda c: _natural(c.candidate_id))))
    rows, report = [], {"dropped": dict(dropped), "classes": {}}
    for taxon in sorted(by_taxon):
        colls = sorted(by_taxon[taxon].items(), key=lambda kv: _h(taxon + kv[0]))
        queues = [sorted(st, key=lambda s: _h(s[0])) for _, st in colls]
        picked, i, cap = [], 0, POOL_STONES_PER_TAXON[scope[taxon]]
        while len(picked) < cap and any(i < len(q) for q in queues):  # round-robin over collections
            picked += [q[i] for q in queues if i < len(q)][:cap - len(picked)]
            i += 1
        for sid, items in picked:
            for v, c in enumerate(items[:POOL_MAX_VIEWS], start=1):
                rows.append({"stone_id": sid, "view": v, "candidate_id": c.candidate_id, "taxon_id": taxon,
                             "scope": scope[taxon], "institution": int(not _author(c.author, c.source_name)),
                             "specimen_id": c.specimen_hint, "source_name": c.source_name, "source_url": c.source_url,
                             "media_url": c.media_url, "author": c.author, "license": c.license, "title": c.title})
        report["classes"][taxon] = {"scope": scope[taxon], "stones_eligible": sum(len(s) for s in by_taxon[taxon].values()),
                                    "stones_in_pool": len(picked), "collections": len(colls)}
    earlier = [r for r in _rows(out_csv) if r["candidate_id"] in reviewed]  # a later round keeps reviewed stones' rows
    _write(out_csv, POOL_COLUMNS, earlier + rows)
    report["scope"] = {k: sum(v == k for v in scope.values()) for k in ("live", "extra")}
    return report


# ---- review sheets (runner) -------------------------------------------------------------------------------
STONES_PER_SHEET, VIEW_TILE, LABEL_W, HEADER = 5, 170, 70, 40


def sheets(pool_csv, out_dir, client, skip_csv=None, delay=0.25) -> dict:
    """One row per stone (S<n>), views numbered 1..8; index.json: sheet -> stone number -> stone_id and views.
    Stones already in the C review file are skipped."""
    from PIL import Image, ImageDraw

    from services.curation.contact_sheet import _font, fetch

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    stones: dict[str, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
    skip = {r["candidate_id"] for r in _rows(skip_csv)}
    for r in _rows(pool_csv):
        if r["candidate_id"] not in skip:
            stones[r["taxon_id"]][r["stone_id"]].append(r)
    index, missing = {}, []
    for taxon, by_stone in sorted(stones.items()):
        ordered = list(by_stone.items())
        for s in range(0, len(ordered), STONES_PER_SHEET):
            chunk = ordered[s:s + STONES_PER_SHEET]
            name = f"c-{taxon}-{s // STONES_PER_SHEET + 1}"
            sheet = Image.new("RGB", (LABEL_W + POOL_MAX_VIEWS * VIEW_TILE, HEADER + len(chunk) * VIEW_TILE), (20, 20, 20))
            d = ImageDraw.Draw(sheet)
            d.text((10, 8), f"{taxon}  stones {s + 1}-{s + len(chunk)} of {len(ordered)}", fill=(255, 255, 255), font=_font(22))
            index[name] = {}
            for k, (sid, views) in enumerate(chunk):
                num, y = s + k + 1, HEADER + k * VIEW_TILE
                d.rectangle([0, y, LABEL_W - 4, y + VIEW_TILE - 4], fill=(255, 220, 0))
                d.text((6, y + 60), f"S{num}", fill=(0, 0, 0), font=_font(26))
                index[name][str(num)] = {"stone_id": sid, "views": {}}
                for r in sorted(views, key=lambda r: int(r["view"])):
                    v = int(r["view"])
                    index[name][str(num)]["views"][str(v)] = r["candidate_id"]
                    im = fetch(client, SimpleNamespace(media_url=r["media_url"]))
                    if "wikimedia.org" in r["media_url"]:
                        time.sleep(delay)
                    x = LABEL_W + (v - 1) * VIEW_TILE
                    if im is None:
                        missing.append(r["candidate_id"])
                        d.text((x + 40, y + 70), "missing", fill=(200, 80, 80), font=_font(18))
                    else:
                        im.thumbnail((VIEW_TILE - 6, VIEW_TILE - 6))
                        sheet.paste(im, (x + (VIEW_TILE - im.width) // 2, y + (VIEW_TILE - im.height) // 2))
                    d.rectangle([x, y, x + 30, y + 24], fill=(255, 255, 255))
                    d.text((x + 4, y + 1), str(v), fill=(0, 0, 0), font=_font(20))
            sheet.save(out / f"{name}.jpg", quality=82)
    (out / "index.json").write_text(json.dumps(index, indent=1))
    (out / "missing.json").write_text(json.dumps(sorted(missing)))
    return {"sheets": len(index), "stones": sum(len(v) for v in index.values()), "missing": len(missing)}


# ---- review decisions (offline) -----------------------------------------------------------------------------
def _expand(spec: str) -> set[int]:
    out = set()
    for part in filter(None, (p.strip() for p in re.split(r"[,+]", spec or ""))):
        a, _, b = part.partition("-")
        out |= set(range(int(a), int(b or a) + 1))
    return out


def _per_stone(spec: str) -> dict[int, str]:
    """'2:1-3;5:1,3' -> {2: '1-3', 5: '1,3'}"""
    return {int(k): v for k, _, v in (p.partition(":") for p in filter(None, (s.strip() for s in (spec or "").split(";"))))}


def decide(index_json, review_c_csv, taxon, keep="", views="", reasons="", tumbled="", polished="",
           default="not_same_stone_or_unusable", reviewer="agent:visual-review-c", missing_json=None) -> dict:
    index = json.loads(Path(index_json).read_text())
    missing = set(json.loads(Path(missing_json).read_text())) if missing_json and Path(missing_json).exists() else set()
    keep_s, view_over, reason_over = _expand(keep), {k: _expand(v) for k, v in _per_stone(views).items()}, _per_stone(reasons)
    tum, pol = _expand(tumbled), _expand(polished)
    done = {r["candidate_id"] for r in _rows(review_c_csv)}
    rows = []
    for sheet, stones in index.items():
        if not sheet.startswith(f"c-{taxon}-"):
            continue
        for num, st in stones.items():
            n = int(num)
            form = "tumbled" if n in tum else "polished" if n in pol else "natural"
            wanted = view_over.get(n, {int(v) for v in st["views"]})
            kept = [v for v in st["views"] if n in keep_s and int(v) in wanted and st["views"][v] not in missing]
            if n in keep_s and len(kept) < MIN_VIEWS:
                raise ValueError(f"{taxon} S{n}: kept with fewer than {MIN_VIEWS} usable views")
            for v, cid in st["views"].items():
                if cid in done:
                    raise ValueError(f"{cid} already in {review_c_csv}")
                if v in kept:
                    dec, why = "keep", "usable_view"
                elif n in keep_s:
                    dec, why = "drop", "missing_image" if cid in missing else reason_over.get(n, "view_dropped")
                else:
                    dec, why = "drop", reason_over.get(n, default)
                rows.append({"candidate_id": cid, "taxon_id": taxon, "stone_id": st["stone_id"], "view": v, "decision": dec,
                             "reason": why, "form": form, "reviewer": reviewer, "sheet": sheet})
    if not rows:
        raise ValueError(f"no sheets for {taxon} in {index_json}")
    new = not Path(review_c_csv).exists()
    with Path(review_c_csv).open("a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=REVIEW_COLUMNS)
        if new:
            w.writeheader()
        w.writerows(rows)
    return {"taxon": taxon, "stones_kept": len({r["stone_id"] for r in rows if r["decision"] == "keep"}),
            "photos_kept": sum(r["decision"] == "keep" for r in rows), "photos_dropped": sum(r["decision"] == "drop" for r in rows)}


# ---- draft, check, freeze -----------------------------------------------------------------------------------
def draft(pool_csv, review_c_csv, out_csv) -> dict:
    meta = {r["candidate_id"]: r for r in _rows(pool_csv)}
    kept = [r for r in _rows(review_c_csv) if r["decision"] == "keep"]
    rows = []
    for r in kept:
        p = meta[r["candidate_id"]]
        rows.append({**{k: p[k] for k in ("candidate_id", "specimen_id", "source_name", "source_url", "media_url", "author",
                                          "license", "stone_id", "institution", "scope")},
                     "case_id": "", "ground_truth_id": p["taxon_id"], "view": r["view"], "form": r["form"]})
    rows.sort(key=lambda r: (r["ground_truth_id"], r["stone_id"], int(r["view"])))
    _write(out_csv, C_COLUMNS, rows)
    return {"photos": len(rows), "stones": len({r["stone_id"] for r in rows})}


def near_duplicates(stone_views: list[tuple[str, object, object]], cos=None) -> dict[str, str]:
    """stone_views: (candidate_id, fingerprint, vector or None) in view order. A later view is dropped if it is
    within PHASH_DUP (any rotation/mirror) or COS_DUP of an earlier kept view."""
    from services.ingestion.leakage import min_phash_distance

    drop, kept = {}, []
    for cid, fp, vec in stone_views:
        for _, kfp, kvec in kept:
            if fp is not None and kfp is not None and (fp.sha256 == kfp.sha256 or min_phash_distance(fp, kfp) <= PHASH_DUP):
                drop[cid] = "near_duplicate_view_phash"
                break
            if vec is not None and kvec is not None and float(vec @ kvec) >= COS_DUP:
                drop[cid] = "near_duplicate_view_cosine"
                break
        else:
            kept.append((cid, fp, vec))
    return drop


def check(draft_csv, reference_csv, out_json, client, other_csvs=(), vectors=None, delay=0.25) -> dict:
    """Runner step: fingerprint every draft photo; within a stone drop near-duplicate views; drop photos that are
    copies (sha256 or pHash <= PHASH_DUP) of a reference photo or of a photo in another set. Report holds ids only."""
    import numpy as np

    from services.ingestion.http import get_with_backoff
    from services.ingestion.leakage import Fingerprint, fingerprint_bytes, min_phash_distance

    def fp_of(url):
        r = get_with_backoff(client, url, attempts=5, min_interval=0, sleep=time.sleep, timeout=60)
        if "wikimedia.org" in url:
            time.sleep(delay)
        if r is None or r.status_code != 200:
            return None
        try:
            return fingerprint_bytes(r.content)
        except Exception:
            return None

    rows = _rows(draft_csv)
    vec = {}
    if vectors:
        meta = json.loads(Path(f"{vectors}.json").read_text())
        arr = np.fromfile(f"{vectors}.f32", dtype=np.float32).reshape(len(meta["items"]), meta["dim"])
        arr /= np.linalg.norm(arr, axis=1, keepdims=True)
        vec = {it["id"]: arr[i] for i, it in enumerate(meta["items"])}
    fps = {r["candidate_id"]: fp_of(r["media_url"]) for r in rows}
    others = [Fingerprint(r["sha256"], r["phash"]) for r in _rows(reference_csv) if r.get("phash")]
    for path in other_csvs:
        others += [f for f in (fp_of(r["media_url"]) for r in _rows(path)) if f is not None]
    drop = {cid: "not_fetched" for cid, fp in fps.items() if fp is None}
    for cid, fp in fps.items():
        if fp is not None and cid not in drop and any(fp.sha256 == o.sha256 or min_phash_distance(fp, o) <= PHASH_DUP for o in others):
            drop[cid] = "copy_of_reference_or_other_set"
    by_stone = defaultdict(list)
    for r in rows:
        if r["candidate_id"] not in drop:
            by_stone[r["stone_id"]].append((int(r["view"]), r["candidate_id"]))
    for sid, views in by_stone.items():
        drop.update(near_duplicates([(cid, fps[cid], vec.get(cid)) for _, cid in sorted(views)]))
    report = {"checked": len(rows), "embedded": len(vec), "drop": dict(sorted(drop.items())),
              "by_reason": dict(Counter(drop.values()))}
    Path(out_json).write_text(json.dumps(report, indent=1))
    return {k: v for k, v in report.items() if k != "drop"}


def freeze(draft_csv, report_json, decisions_path, out_csv, dry_run=False, underpowered=False, reference_commit="") -> dict:
    """Apply the check report, cap views and stones (deterministic hash order), number the cases, mark the photos
    `reserve` in decisions.json and write the vault file."""
    report = json.loads(Path(report_json).read_text()) if report_json else {"drop": {}}
    stones: dict[str, list[dict]] = defaultdict(list)
    for r in _rows(draft_csv):
        if r["candidate_id"] not in report["drop"]:
            stones[r["stone_id"]].append(r)
    stones = {s: sorted(v, key=lambda r: int(r["view"]))[:MAX_VIEWS] for s, v in stones.items() if len(v) >= MIN_VIEWS}
    order = sorted(stones, key=lambda s: _h(stones[s][0]["ground_truth_id"] + s))
    per_class, per_author_t, per_author, per_inst_t = Counter(), Counter(), Counter(), Counter()
    chosen = []
    for s in order:
        v0 = stones[s][0]
        t, coll, inst = v0["ground_truth_id"], _collection(v0["author"], v0["source_name"]), v0["institution"] == "1"
        if per_class[t] >= MAX_STONES[v0["scope"]]:
            continue
        if inst and per_inst_t[(coll, t)] >= PER_INSTITUTION_TAXON:
            continue
        if not inst and (per_author_t[(coll, t)] >= PER_AUTHOR_TAXON or per_author[coll] >= PER_AUTHOR_TOTAL):
            continue
        chosen.append(s)
        per_class[t] += 1
        (per_inst_t if inst else per_author_t)[(coll, t)] += 1
        per_author[coll] += not inst
    # Global shares among live stones: institutions <= 50 %, tumbled + polished <= 25 %; trim the latest in hash order.
    for test, share in ((lambda r: r["institution"] == "1", INSTITUTION_SHARE), (lambda r: r["form"] != "natural", NON_NATURAL_SHARE)):
        live = [s for s in chosen if stones[s][0]["scope"] == "live"]
        flagged = [s for s in live if test(stones[s][0])]
        while flagged and len(flagged) > share * len(live):
            chosen.remove(flagged.pop())
            live = [s for s in chosen if stones[s][0]["scope"] == "live"]
    rows = [r for s in chosen for r in stones[s]]
    rows.sort(key=lambda r: (r["ground_truth_id"], r["stone_id"], int(r["view"])))
    for n, r in enumerate(rows, start=1):
        r["case_id"] = f"s{n:04d}"
    live_classes = Counter(stones[s][0]["ground_truth_id"] for s in chosen if stones[s][0]["scope"] == "live")
    summary = {"stones": len(chosen), "photos": len(rows),
               "live_stones": sum(live_classes.values()), "live_classes": len(live_classes),
               "classes_reportable": sorted(t for t, n in Counter(stones[s][0]["ground_truth_id"] for s in chosen).items() if n >= MIN_REPORT_STONES),
               "per_class": dict(sorted(Counter(stones[s][0]["ground_truth_id"] for s in chosen).items())),
               "views": dict(sorted(Counter(len(stones[s]) for s in chosen).items()))}
    gate = UNDERPOWERED_MIN_LIVE_STONES if underpowered else FREEZE_MIN_LIVE_STONES
    summary["freeze_ok"] = summary["live_stones"] >= gate and summary["live_classes"] >= FREEZE_MIN_LIVE_CLASSES
    summary["underpowered"] = summary["live_stones"] < FREEZE_MIN_LIVE_STONES
    if dry_run:
        return summary
    if not summary["freeze_ok"]:
        raise ValueError(f"below the freeze gate ({gate} live stones in {FREEZE_MIN_LIVE_CLASSES} classes): {summary}")
    _write(out_csv, C_COLUMNS, rows)
    meta = {**summary, "reference_commit": reference_commit, "check_report": str(report_json or ""),
            "rules": {k: v for k, v in globals().items() if k.isupper() and isinstance(v, (int, float, dict))}}
    Path(out_csv).with_name("challenge_c_meta.json").write_text(json.dumps(meta, indent=1))
    decisions = load_decisions(decisions_path)
    clash = [r["candidate_id"] for r in rows if decisions.get(r["candidate_id"], "reserve") != "reserve"]
    if clash:
        raise ValueError(f"already decided on main: {clash[:5]}")
    decisions.update({r["candidate_id"]: "reserve" for r in rows})
    save_decisions(decisions_path, decisions)
    return summary


def main(argv=None):
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("pool"); p.add_argument("candidates"); p.add_argument("decisions"); p.add_argument("reference")
    p.add_argument("review_c"); p.add_argument("out"); p.add_argument("other", nargs="*"); p.add_argument("--taxa", nargs="*")
    p = sub.add_parser("sheets"); p.add_argument("pool"); p.add_argument("out"); p.add_argument("--skip-reviewed")
    p = sub.add_parser("decide"); p.add_argument("index"); p.add_argument("review_c"); p.add_argument("taxon")
    for opt in ("keep", "views", "reasons", "tumbled", "polished", "missing"):
        p.add_argument(f"--{opt}", default="")
    p.add_argument("--default", default="not_same_stone_or_unusable")
    p = sub.add_parser("draft"); p.add_argument("pool"); p.add_argument("review_c"); p.add_argument("out")
    p = sub.add_parser("check"); p.add_argument("draft"); p.add_argument("reference"); p.add_argument("out")
    p.add_argument("other", nargs="*"); p.add_argument("--vectors")
    p = sub.add_parser("freeze"); p.add_argument("draft"); p.add_argument("report"); p.add_argument("decisions")
    p.add_argument("out"); p.add_argument("--dry-run", action="store_true"); p.add_argument("--underpowered", action="store_true")
    p.add_argument("--reference-commit", default="")
    a = ap.parse_args(argv)
    if a.cmd == "pool":
        res = pool(a.candidates, a.decisions, a.reference, a.review_c, a.out, a.other, a.taxa)
    elif a.cmd in ("sheets", "check"):
        import httpx
        with httpx.Client(follow_redirects=True) as client:
            res = sheets(a.pool, a.out, client, a.skip_reviewed) if a.cmd == "sheets" else check(a.draft, a.reference, a.out, client, a.other, a.vectors)
    elif a.cmd == "decide":
        res = decide(a.index, a.review_c, a.taxon, a.keep, a.views, a.reasons, a.tumbled, a.polished, a.default,
                     missing_json=a.missing or None)
    elif a.cmd == "draft":
        res = draft(a.pool, a.review_c, a.out)
    else:
        res = freeze(a.draft, a.report or None, a.decisions, a.out, a.dry_run, a.underpowered, a.reference_commit)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    sys.exit(main())
