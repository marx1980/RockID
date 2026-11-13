"""Append private-source vectors (embedded in a workflow, images never committed) to a reference embedding.

  python -m services.model.private <reference prefix> <private prefix> [<private prefix> ...]

Rewrites the reference prefix (.f32 and .json) in place. Refuses a private set embedded with another model."""
import json
import sys
from pathlib import Path

import numpy as np


def merge(ref_prefix: str, private_prefixes: list[str]) -> dict:
    meta = json.loads(Path(f"{ref_prefix}.json").read_text())
    dim = meta["dim"]
    vec = np.fromfile(f"{ref_prefix}.f32", dtype=np.float32).reshape(len(meta["items"]), dim)
    chunks, items, added = [vec], list(meta["items"]), 0
    for prefix in private_prefixes:
        pm = json.loads(Path(f"{prefix}.json").read_text())
        if (pm["model"], pm["dtype"], pm["dim"]) != (meta["model"], meta["dtype"], dim):
            raise SystemExit(f"{prefix}: embedded with {pm['model']} {pm['dtype']}, reference uses {meta['model']} {meta['dtype']}")
        chunks.append(np.fromfile(f"{prefix}.f32", dtype=np.float32).reshape(len(pm["items"]), dim))
        items += pm["items"]
        added += len(pm["items"])
    np.concatenate(chunks).astype(np.float32).tofile(f"{ref_prefix}.f32")
    meta["items"] = items
    meta["private_items"] = added
    Path(f"{ref_prefix}.json").write_text(json.dumps(meta))
    return {"reference": len(meta["items"]) - added, "private": added}


if __name__ == "__main__":
    print(merge(sys.argv[1], sys.argv[2:]))
