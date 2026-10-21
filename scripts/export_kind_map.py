#!/usr/bin/env python3
"""
Write the kind map of a snapshot as one self-contained HTML page.

The page is the browser surface's own (`client/web/kinds/`), with its stylesheets and script
inlined and the answer to `si.kind.map` embedded, so it opens from disk with no server. The
answer is asked through `inspector.api.query` like any other consumer's: this script renders, it
does not inspect. A snapshot that does not declare `si.kind.map` cannot be exported, because the
operation set is the snapshot's to declare.

    PYTHONPATH=. python3 scripts/export_kind_map.py --snapshot <snapshot dir> --out <file.html>
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from inspector.api import query

WEB = Path(__file__).resolve().parent.parent / "client" / "web"
PAGE = WEB / "kinds" / "index.html"
STYLESHEETS = {
    '<link rel="stylesheet" href="/css/base.css">': WEB / "css" / "base.css",
    '<link rel="stylesheet" href="css/kinds.css">': WEB / "kinds" / "css" / "kinds.css",
}
SCRIPT = '<script src="js/kind_map.js"></script>'
SCRIPT_FILE = WEB / "kinds" / "js" / "kind_map.js"
NAV_START, NAV_END = '<nav class="screen-nav">', "</nav>"


def _replace_once(page: str, old: str, new: str) -> str:
    """Swap one tag the page is known to carry; a page that no longer carries it is refused."""
    if page.count(old) != 1:
        raise SystemExit(f"export_kind_map: the kind map page no longer carries {old!r} exactly once")
    return page.replace(old, new)


def render(snapshot: Path) -> str:
    try:
        status, result = query("si.kind.map", {}, snapshot)
    except KeyError as missing:
        raise SystemExit(f"export_kind_map: {missing.args[0]}") from None
    if status != "SUCCESS":
        raise SystemExit(f"export_kind_map: si.kind.map answered {status}: {result}")

    page = PAGE.read_text(encoding="utf-8")
    for tag, css in STYLESHEETS.items():
        page = _replace_once(page, tag, f"<style>\n{css.read_text(encoding='utf-8')}</style>")
    # Navigation points at the live surface, which a page opened from disk does not have.
    start, end = page.index(NAV_START), page.index(NAV_END) + len(NAV_END)
    page = page[:start] + page[end:]
    # `</` cannot end the embedding script early once every `/` after `<` is escaped.
    data = json.dumps(result, separators=(",", ":")).replace("</", "<\\/")
    script = SCRIPT_FILE.read_text(encoding="utf-8")
    return _replace_once(page, SCRIPT,
                         f"<script>window.KIND_MAP_RESULT = {data};</script>\n<script>\n{script}</script>")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Write a snapshot's kind map as one HTML page.")
    parser.add_argument("--snapshot", type=Path, required=True, help="assembled snapshot directory")
    parser.add_argument("--out", type=Path, required=True, help="HTML file to write")
    args = parser.parse_args(argv)
    args.out.write_text(render(args.snapshot), encoding="utf-8")
    print(f"wrote the kind map of {args.snapshot} → {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
