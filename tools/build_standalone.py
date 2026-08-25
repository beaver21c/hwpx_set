#!/usr/bin/env python3
"""웹 앱을 파일 하나로 묶는다(dist/hwpx-studio.html).

인터넷 없이도 열리고, 어디에 올려도 그대로 도는 단일 HTML을 만든다.
GitHub Pages용 docs/와 같은 소스에서 생성하므로 내용이 어긋나지 않는다.

    python tools/build_standalone.py [-o dist/hwpx-studio.html]

## 어떻게 묶나

ES 모듈을 그냥 이어 붙이면 모듈마다 있는 같은 이름의 내부 함수가 부딪친다
(`const num`이 두 곳에 있으면 `Identifier 'num' has already been declared`).
그래서 **모듈마다 제 범위를 준다.**

    const __mod_capture = (() => { …모듈 본문…; return { captureText, specToText }; })();
    const { captureText, specToText } = __mod_capture;

내보낸 이름만 바깥으로 나오므로 내부 이름은 부딪치지 않는다. 내보낸 이름끼리
겹치면 그것은 진짜 충돌이므로 **여기서 멈춘다**(조용히 깨진 파일을 내놓지 않는다).
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"

#: 의존 순서대로 이어 붙인다(모듈 간 import는 제거된다)
MODULES = ["js/zip.js", "js/xml.js", "js/hwpx-studio.js", "js/capture.js", "assets.js",
           "js/formkit.js", "js/readback.js", "js/bundle.js", "js/app.js"]

IMPORT_RE = re.compile(r"^\s*import\s[^;]*;\s*$", re.M)
EXPORT_DEFAULT_RE = re.compile(r"^\s*export default .*;\s*$", re.M)
EXPORT_LIST_RE = re.compile(r"^\s*export\s*\{([^}]*)\}\s*;\s*$", re.M)
EXPORT_DECL_RE = re.compile(
    r"^(\s*)export\s+(const|let|class|async function\*?|function\*?)\s+([\w$]+)", re.M)


def exported_names(source: str) -> List[str]:
    """이 모듈이 내보내는 이름들. 순서는 나온 차례를 지킨다."""
    names: List[str] = []
    for _indent, _kind, name in EXPORT_DECL_RE.findall(source):
        if name not in names:
            names.append(name)
    for group in EXPORT_LIST_RE.findall(source):
        for piece in group.split(","):
            name = piece.split(" as ")[-1].strip()
            if name and name not in names:
                names.append(name)
    return names


def strip_module_syntax(source: str) -> str:
    source = IMPORT_RE.sub("", source)
    source = EXPORT_DEFAULT_RE.sub("", source)
    source = EXPORT_LIST_RE.sub("", source)
    source = EXPORT_DECL_RE.sub(r"\1\2 \3", source)
    return source


def module_alias(name: str) -> str:
    return "__mod_" + re.sub(r"\W", "_", Path(name).stem)


def bundle_modules(sources: Dict[str, str]) -> str:
    seen: Dict[str, str] = {}
    chunks: List[str] = []

    for name, source in sources.items():
        names = exported_names(source)
        for exported in names:
            if exported in seen:
                raise SystemExit(
                    f"[중단] 내보낸 이름이 겹칩니다: {exported!r} "
                    f"({seen[exported]} ↔ {name}). 한쪽 이름을 바꾸거나 "
                    "공용 모듈(js/xml.js)로 합치세요.")
            seen[exported] = name

        alias = module_alias(name)
        body = strip_module_syntax(source)
        chunks.append(f"// ── {name} " + "─" * max(0, 60 - len(name)))
        if names:
            chunks.append(f"const {alias} = (() => {{\n{body}\n"
                          f"return {{ {', '.join(names)} }};\n}})();")
            chunks.append(f"const {{ {', '.join(names)} }} = {alias};")
        else:
            chunks.append(f"(() => {{\n{body}\n}})();")
    return "\n".join(chunks)


def build() -> str:
    html = (DOCS / "index.html").read_text(encoding="utf-8")
    css = (DOCS / "css" / "style.css").read_text(encoding="utf-8")
    sources = {name: (DOCS / name).read_text(encoding="utf-8") for name in MODULES}
    scripts = bundle_modules(sources)

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
    try:
        shown = out.relative_to(ROOT)
    except ValueError:                              # 저장소 밖 경로로도 만들 수 있다
        shown = out
    print(f"생성: {shown} ({len(html.encode('utf-8')):,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
