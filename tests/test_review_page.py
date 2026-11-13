"""Drives the review page in headless Chrome at phone size against the real candidates.
Skipped unless Playwright and a Chrome binary are available (CI does not install them)."""
import base64
import functools
import http.server
import io
import json
import os
import shutil
import socketserver
import threading
from pathlib import Path

import pytest
from PIL import Image

from services.review.build_site import build_site

sync_api = pytest.importorskip("playwright.sync_api")
CHROME = os.getenv("CHROME_PATH") or shutil.which("google-chrome") or shutil.which("chromium")
pytestmark = pytest.mark.skipif(not CHROME, reason="no Chrome binary")
ROOT = Path(__file__).resolve().parents[1]


def _png() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (800, 600), (70, 90, 120)).save(buf, "PNG")
    return buf.getvalue()


class _Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def test_review_flow_on_phone(tmp_path):
    site = tmp_path / "site"
    build_site(ROOT / "data_manifests/candidates/candidates.csv", site)
    socketserver.TCPServer.allow_reuse_address = True
    srv = socketserver.TCPServer(("127.0.0.1", 0), functools.partial(_Quiet, directory=str(site)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    puts: list[dict] = []
    try:
        with sync_api.sync_playwright() as p:
            browser = p.chromium.launch(executable_path=CHROME, args=["--no-sandbox"])
            ctx = browser.new_context(viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True)
            pg = ctx.new_page()
            pg.route(lambda u: any(h in u for h in ("wikimedia.org", "si.edu")),
                     lambda r: r.fulfill(status=200, content_type="image/png", body=_png()))

            def gh(route):
                req = route.request
                if req.method == "PUT":
                    puts.append(json.loads(req.post_data))
                    route.fulfill(status=200, content_type="application/json", body=json.dumps({"content": {"sha": "x"}}))
                else:
                    route.fulfill(status=404, content_type="application/json", body="{}")

            pg.route("https://api.github.com/**", gh)
            pg.goto(f"http://127.0.0.1:{srv.server_address[1]}/index.html")
            pg.wait_for_selector("#img[src]")
            label = lambda: pg.eval_on_selector("#taxon", "e=>e.options[e.selectedIndex].text")
            assert " 0/" in label()

            first = pg.inner_text("#meta dd >> nth=0")
            assert pg.is_disabled("#d-train")  # first Commons photo is CC BY-SA: reference only
            pg.click("#d-ref")
            pg.wait_for_timeout(150)
            second = pg.inner_text("#meta dd >> nth=0")
            assert second != first and " 1/" in label()
            pg.click("#d-rej")
            pg.click("#undo")
            pg.wait_for_timeout(150)
            assert pg.inner_text("#meta dd >> nth=0") == second and " 1/" in label()

            pg.click("#view")
            pg.wait_for_timeout(500)
            cells = pg.locator(".cell")
            assert cells.count() > 10
            box = cells.nth(0).bounding_box()
            assert abs(box["width"] - box["height"]) < 3  # square cells, not collapsed rows
            assert pg.evaluate("(()=>{const r=[...document.querySelectorAll('.cell')].slice(0,4).map(c=>c.getBoundingClientRect());return r[3].top>=r[0].bottom})()")
            cells.nth(2).click()
            for _ in range(80):
                if not pg.is_disabled("#d-train"):
                    break
                pg.click("#next")
            assert not pg.is_disabled("#d-train")
            pg.click("#d-train")

            pg.click("#gear")
            pg.fill("#token", "ghp_test")
            pg.click("#saveTok")
            pg.wait_for_timeout(800)
            assert len(puts) == 1 and puts[0]["branch"] == "main"
            body = json.loads(base64.b64decode(puts[0]["content"]))
            assert set(body.values()) == {"approve_reference", "approve_train"}
            assert pg.inner_text("#status") == "Synced"

            pg.reload()
            pg.wait_for_selector("#img[src]")
            assert " 2/" in label()
            assert pg.evaluate("document.documentElement.scrollWidth<=window.innerWidth")
            browser.close()
    finally:
        srv.shutdown()
