#!/usr/bin/env python3
"""워크플로에서 남의 도식(Mermaid·SVG·HTML) → 도식 블록 + hwpx를 만든다.

입력은 모두 환경변수로 받는다(셸 인자 주입을 피하기 위함).

    SOURCE_PATH  원본 파일 경로(.mmd / .svg / .html / .md)
    TITLE        도식 제목
    KIND         auto | mermaid | svg | html
    PROFILE      프로파일 이름 또는 경로
    OUTPUT_NAME  결과 파일 이름
    OUT_DIR      결과를 모을 폴더
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from hwpx_studio.capture import capture                # noqa: E402
from hwpx_studio.engine import build_document          # noqa: E402
from hwpx_studio.profile import load_profile           # noqa: E402


def env(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).strip()


def summary(text: str) -> None:
    print(text)
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if path:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(text + "\n")


def main() -> int:
    source = Path(env("SOURCE_PATH", "examples/capture/org.mmd"))
    if not source.exists():
        summary(f"### ❌ 원본 파일을 찾을 수 없음\n\n`{source}`")
        return 2

    out_dir = Path(env("OUT_DIR", "out"))
    out_dir.mkdir(parents=True, exist_ok=True)

    name = Path(env("OUTPUT_NAME", "도식.hwpx") or "도식.hwpx").name
    if not name.endswith(".hwpx"):
        name += ".hwpx"

    result = capture(str(source), env("KIND", "auto"), env("TITLE"))
    if not result.spec.lines:
        lines = "\n".join(f"- {w}" for w in result.warnings) or "- 상자를 찾지 못했다"
        summary(f"### ❌ 도식을 읽지 못함\n\n`{source}`\n\n{lines}")
        return 2

    block = result.to_text()
    (out_dir / "도식블록.txt").write_text(block + "\n", encoding="utf-8")

    profile = load_profile(env("PROFILE", "policy-default"))
    built = build_document(profile, [{"type": "diagram", "spec": result.spec.to_dict()}],
                           str(out_dir / name))

    notes = list(result.warnings) + list(built.warnings)
    body = [
        f"### ✅ 도식을 읽었습니다 — `{source}` ({result.source})",
        "",
        f"유형 `{result.spec.type}` · 줄 {len(result.spec.lines)}개 · "
        f"`{name}` {len(built.data):,} bytes",
        "",
        "```",
        block,
        "```",
        "",
        "**Artifacts**의 `가져온-도식`에서 hwpx와 도식 블록을 내려받을 수 있습니다.",
        "블록을 본문에 붙여 넣으면 보고서 안에 그대로 들어갑니다.",
    ]
    if notes:
        body += ["", "#### 확인할 점", *[f"- {n}" for n in notes]]
    summary("\n".join(body))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
