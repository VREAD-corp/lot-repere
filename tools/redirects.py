"""Redirect pages for lot-repere.jalonel.com after the merge into ao-formation (2026-10-24).

GitHub Pages cannot answer a 301 for a custom domain, so every former page gets a small HTML page instead
(same mechanism as the vin-cc.github.io/dollar-filer stubs of 2026-10-16): canonical to the new URL, an instant
meta refresh, a location.replace() that keeps the query and fragment, and a visible link. 404.html sends any other
path to the same path under the new base.

Usage: python -m lotrepere build --out /tmp/old   (the former site, to list its pages)
       python tools/redirects.py /tmp/old redirects
"""

from __future__ import annotations

import html
import re
import shutil
import sys
from pathlib import Path

NEW_BASE = "https://ao-formation.jalonel.com/secteurs/"
INDEXNOW_KEY = "5be19f56d46ca3d2553bee28ebfa8edd"
TITLE_RE = re.compile(r"<title>(.*?)</title>", re.S)

STUB = """<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Page déplacée : {title}</title>
<link rel="canonical" href="{url}">
<meta http-equiv="refresh" content="0;url={url}">
<script>location.replace({js} + location.search + location.hash);</script>
</head>
<body>
<p>Lot Repéré a rejoint Veille AO. Cette page est maintenant ici : <a href="{url}">{url}</a>.</p>
</body>
</html>
"""

NOT_FOUND = """<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Lot Repéré a rejoint Veille AO</title>
<meta name="robots" content="noindex">
<link rel="canonical" href="{base}">
<script>location.replace({js} + location.pathname.replace(/^\\/+/, "") + location.search + location.hash);</script>
</head>
<body>
<p>Lot Repéré a rejoint Veille AO : <a href="{base}">{base}</a>.</p>
</body>
</html>
"""


def target(rel: str) -> str:
    """Former path (relative, e.g. 'nettoyage/index.html') -> new URL, same path under NEW_BASE."""
    path = rel[:-len("index.html")] if rel.endswith("index.html") else rel
    return NEW_BASE + path


def main(old: Path, out: Path) -> int:
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    pages = sorted(p for p in old.rglob("*.html") if p.name != "404.html")
    for page in pages:
        rel = page.relative_to(old).as_posix()
        m = TITLE_RE.search(page.read_text(encoding="utf-8"))
        title = html.unescape(m.group(1)).strip() if m else "Veille AO"
        url = target(rel)
        dest = out / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(STUB.format(title=html.escape(title, quote=False), url=html.escape(url),
                                    js='"' + url.replace("\\", "\\\\").replace('"', '\\"') + '"'), encoding="utf-8")
    (out / "404.html").write_text(NOT_FOUND.format(base=NEW_BASE, js='"' + NEW_BASE + '"'), encoding="utf-8")
    (out / "robots.txt").write_text("User-agent: *\nAllow: /\n", encoding="utf-8")
    (out / f"{INDEXNOW_KEY}.txt").write_text(INDEXNOW_KEY, encoding="utf-8")
    (out / "CNAME").write_text("lot-repere.jalonel.com\n", encoding="utf-8")
    (out / "paths.txt").write_text("".join(p.relative_to(old).as_posix() + "\n" for p in pages), encoding="utf-8")
    print(f"{len(pages)} redirect pages in {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1]), Path(sys.argv[2])))
