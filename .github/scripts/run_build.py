#!/usr/bin/env python3
"""워크플로에서 마커 텍스트 → hwpx를 만든다.

입력은 모두 환경변수로 받는다(셸 인자 주입을 피하기 위함).

    INPUT_PATH      마커 텍스트 파일 경로
    PROFILE         프로파일 이름 또는 경로
    OUTPUT_NAME     결과 파일 이름
    DIAGRAM_RENDER  '', 'table', 'image'
    STRICT          'true'면 경고도 오류로 취급
    PREVIEW         'true'면 HTML 미리보기도 생성
    OUT_DIR         결과를 모을 폴더
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from hwpx_studio.engine import build_document          # noqa: E402
from hwpx_studio.lint import format_issues, has_blocking, lint_items  # noqa: E402
from hwpx_studio.parser import parse_file              # noqa: E402
from hwpx_studio.preview import render_preview         # noqa: E402
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
    input_path = Path(env("INPUT_PATH", "examples/input_outline.md"))
    if not input_path.exists():
        summary(f"### ❌ 입력 파일을 찾을 수 없음\n\n`{input_path}`")
        return 2

    out_dir = Path(env("OUT_DIR", "out"))
    out_dir.mkdir(parents=True, exist_ok=True)

    name = env("OUTPUT_NAME", "보고서.hwpx") or "보고서.hwpx"
    name = Path(name).name                      # 경로 요소 제거
    if not name.endswith(".hwpx"):
        name += ".hwpx"
    out_path = out_dir / name

    profile = load_profile(env("PROFILE", "policy-default"))
    render = env("DIAGRAM_RENDER")
    if render in ("table", "image"):
        profile["diagram"]["render"] = render

    parsed = parse_file(str(input_path), profile)
    issues = lint_items(parsed.items, profile, parsed.line_of, parsed.warnings)
    strict = env("STRICT").lower() == "true"

    lines = [f"## 보고서 생성: `{input_path}` → `{name}`", ""]
    lines.append(f"- 프로파일: `{env('PROFILE', 'policy-default')}` "
                 f"(레벨 {len(profile['levels'])}개, {profile['mode']})")
    lines.append(f"- 항목 {len(parsed.items)}개 / 검사 지적 {len(issues)}건"
                 + (" · `--strict`" if strict else ""))
    lines.append("")
    if issues:
        lines.append("<details><summary>본문 검사 결과</summary>\n")
        lines.append("```")
        lines.append(format_issues(issues))
        lines.append("```\n</details>\n")

    if has_blocking(issues, strict):
        summary("\n".join(lines) + "\n### ❌ 검사에서 중단됨\n\n위 지적 사항을 고친 뒤 다시 실행하세요.")
        return 1

    result = build_document(profile, parsed.items, str(out_path))
    for warn in result.warnings:
        lines.append(f"> ⚠ {warn}")
    if result.warnings:
        lines.append("")

    if env("PREVIEW").lower() == "true":
        html_path = out_dir / (out_path.stem + "_preview.html")
        render_preview(str(out_path), str(html_path))
        lines.append(f"- 미리보기: `{html_path.name}` (근사값 — 최종 확인은 한글에서)")

    size = out_path.stat().st_size
    lines.append("")
    lines.append(f"### ✅ 생성 완료 — `{name}` ({size:,} bytes)")
    lines.append("")
    lines.append("**Artifacts** 항목에서 내려받으세요.")
    summary("\n".join(lines))

    meta = {"output": str(out_path), "size": size,
            "warnings": result.warnings, "issues": len(issues)}
    Path(out_dir / "build-info.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
