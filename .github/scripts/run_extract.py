#!/usr/bin/env python3
"""워크플로에서 hwpx → 프로파일 JSON + 근거 리포트를 만든다.

    SOURCE_PATH  기준이 될 .hwpx 경로
    PROFILE_NAME 프로파일 이름(문서에 들어가지 않음)
    OUT_DIR      결과 폴더
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from hwpx_studio.extractor import extract_profile, write_outputs  # noqa: E402


def summary(text: str) -> None:
    print(text)
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if path:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(text + "\n")


def main() -> int:
    source = Path((os.environ.get("SOURCE_PATH") or "").strip())
    if not source.exists():
        summary(f"### ❌ 파일을 찾을 수 없음\n\n`{source}`\n\n"
                "저장소에 올린 `.hwpx` 경로를 넣어야 합니다.")
        return 2

    out_dir = Path((os.environ.get("OUT_DIR") or "out").strip())
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = source.stem

    try:
        result = extract_profile(str(source),
                                 name=(os.environ.get("PROFILE_NAME") or "추출 프로파일").strip())
    except ValueError as exc:
        summary(f"### ❌ 읽을 수 없음\n\n{exc}")
        return 1

    profile_path = out_dir / f"{stem}.profile.json"
    report_path = out_dir / f"{stem}.report.md"
    write_outputs(result, str(profile_path), str(report_path))

    summary(f"## 서식 추출: `{source.name}`\n")
    summary(result.report)
    summary("\n> 추정 결과입니다. 위 '접두 후보'와 레벨 순서를 확인한 뒤 사용하세요. "
            "결과 파일은 **Artifacts**에 있습니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
