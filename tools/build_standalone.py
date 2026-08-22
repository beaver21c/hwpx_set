#!/usr/bin/env python3
"""웹 앱을 파일 하나로 묶는다(dist/hwpx-studio.html).

인터넷 없이도 열리고, 어디에 올려도 그대로 도는 단일 HTML을 만든다.
GitHub Pages용 docs/와 같은 소스에서 생성하므로 내용이 어긋나지 않는다.

    python tools/build_standalone.py [-o dist/hwpx-studio.html]
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"

#: 의존 순서대로 이어 붙인다(모듈 간 import는 제거된다)
MODULES = ["js/zip.js", "js/hwpx-studio.js", "assets.js", "js/app.js"]

IMPORT_RE = re.compile(r"^\s*import\s[^;]*;\s*$", re.M)
EXPORT_DEFAULT_RE = re.compile(r"^\s*export default .*;\s*$", re.M)
EXPORT_KEYWORD_RE = re.compile(r"^(\s*)export\s+(const|function|async function|class|let)\b", re.M)


def strip_module_syntax(source: str) -> str:
    source = IMPORT_RE.sub("", source)
    source = EXPORT_DEFAULT_RE.sub("", source)
    source = EXPORT_KEYWORD_RE.sub(r"\1\2", source)
    return source


def build() -> str:
    html = (DOCS / "index.html").read_text(encoding="utf-8")
    css = (DOCS / "css" / "style.css").read_text(encoding="utf-8")
    scripts = "\n".join(strip_module_syntax((DOCS / name).read_text(encoding="utf-8"))
                        for name in MODULES)

    html = html.replace('<link rel="stylesheet" href="./css/style.css">',
                        f"<style>\n{css}\n</style>")
    html = html.replace('<script type="module" src="./js/app.js"></script>',
                        f"<script type=\"module\">\n{scripts}\n</script>")
    note = ('<p class="hint">이 파일은 단일 HTML 버전입니다. '
            '인터넷 연결 없이도 그대로 동작합니다.</p>')
    html = html.replace("</main>", f'  <section class="panel">{note}</section>\n</main>')
    return html


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("-o", "--out", default="dist/hwpx-studio.html")
    args = ap.parse_args()

    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    html = build()
    out.write_text(html, encoding="utf-8")
    print(f"생성: {out.relative_to(ROOT)} ({len(html.encode('utf-8')):,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
