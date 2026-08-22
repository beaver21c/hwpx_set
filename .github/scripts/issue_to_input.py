#!/usr/bin/env python3
"""이슈 폼 본문 → 마커 텍스트 파일 + 빌드 설정.

이슈 본문은 신뢰할 수 없는 입력이다. 셸을 거치지 않도록 환경변수(ISSUE_BODY)로
받아 파일과 GITHUB_OUTPUT으로만 내보낸다.
"""

from __future__ import annotations

import os
from pathlib import Path

NO_RESPONSE = "_No response_"
PROFILES = {"policy-default", "gov-3level", "narrative"}
RENDERS = {"table", "image"}


def parse_sections(body: str) -> dict[str, str]:
    """'### 라벨' 단위로 쪼갠다."""
    sections: dict[str, str] = {}
    label = None
    buf: list[str] = []
    for line in body.replace("\r\n", "\n").split("\n"):
        if line.startswith("### "):
            if label is not None:
                sections[label] = "\n".join(buf).strip()
            label = line[4:].strip()
            buf = []
        elif label is not None:
            buf.append(line)
    if label is not None:
        sections[label] = "\n".join(buf).strip()
    return {k: ("" if v == NO_RESPONSE else v) for k, v in sections.items()}


def strip_code_fence(text: str) -> str:
    """이슈 폼의 `render: text` 칸은 코드 펜스로 감싸여 온다."""
    lines = text.split("\n")
    if lines and lines[0].lstrip().startswith("```"):
        lines = lines[1:]
        while lines and not lines[-1].strip():
            lines.pop()
        if lines and lines[-1].strip().startswith("```"):
            lines.pop()
    return "\n".join(lines)


def emit(**values: str) -> None:
    path = os.environ.get("GITHUB_OUTPUT")
    if not path:
        for key, value in values.items():
            print(f"{key}={value}")
        return
    with open(path, "a", encoding="utf-8") as fh:
        for key, value in values.items():
            fh.write(f"{key}={value}\n")


def main() -> int:
    sections = parse_sections(os.environ.get("ISSUE_BODY", ""))
    body_text = strip_code_fence(sections.get("본문 (마커 텍스트)", "")).strip()
    if not body_text:
        emit(ok="false", reason="본문이 비어 있습니다")
        return 1

    Path("issue_input.md").write_text(body_text + "\n", encoding="utf-8")

    profile = sections.get("서식 프로파일", "").strip()
    profile = profile if profile in PROFILES else "policy-default"

    name = Path(sections.get("결과 파일 이름", "").strip() or "보고서.hwpx").name
    if not name.endswith(".hwpx"):
        name += ".hwpx"

    render = sections.get("도식 렌더 방식", "").strip()
    render = render if render in RENDERS else ""

    options = sections.get("옵션", "")
    checked = [line for line in options.split("\n") if line.strip().startswith("- [x]")]
    strict = any("strict" in line for line in checked)
    preview = any("미리보기" in line for line in checked)

    emit(ok="true", profile=profile, output_name=name, diagram_render=render,
         strict=str(strict).lower(), preview=str(preview).lower(),
         lines=str(len(body_text.split("\n"))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
