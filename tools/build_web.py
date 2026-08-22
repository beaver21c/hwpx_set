#!/usr/bin/env python3
"""웹 앱이 쓸 자산(docs/assets.js)을 만든다.

브라우저 엔진은 서버 없이 도므로, 빈 템플릿 hwpx와 내장 프로파일을 자바스크립트
파일 하나에 넣어 둔다. 파이썬 쪽 프로파일이 단일 원본이며, 이 스크립트로만
복제한다(수기 편집 금지).

    python tools/build_web.py            # 생성
    python tools/build_web.py --check    # 최신 상태인지 검사(CI용)
"""

from __future__ import annotations

import argparse
import base64
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hwpx.templates import blank_document_bytes  # noqa: E402

TARGET = ROOT / "docs" / "assets.js"
PROFILE_DIR = ROOT / "hwpx_studio" / "profiles"
ORDER = ["policy-default", "gov-3level", "narrative"]

HEADER = """/**
 * 자동 생성 파일 — 직접 고치지 말 것.
 * `python tools/build_web.py`로 다시 만든다.
 *
 * 담고 있는 것
 *  - HWPX_TEMPLATE_B64: python-hwpx의 빈 문서 템플릿(base64)
 *  - HWPX_PROFILES:     hwpx_studio/profiles/*.json 사본
 */
"""


def build() -> str:
    template = base64.b64encode(blank_document_bytes()).decode("ascii")
    profiles = {}
    for name in ORDER:
        path = PROFILE_DIR / f"{name}.json"
        if path.exists():
            profiles[name] = json.loads(path.read_text(encoding="utf-8"))

    lines = [HEADER]
    lines.append(f'export const HWPX_TEMPLATE_B64 = "{template}";\n')
    lines.append("export const HWPX_PROFILES = "
                 + json.dumps(profiles, ensure_ascii=False, indent=2) + ";\n")
    lines.append("""
if (typeof window !== 'undefined') {
  window.HWPX_TEMPLATE_B64 = HWPX_TEMPLATE_B64;
  window.HWPX_PROFILES = HWPX_PROFILES;
}
""")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="파일이 최신인지 검사만 한다(다르면 종료 코드 1)")
    args = ap.parse_args()

    content = build()
    if args.check:
        if not TARGET.exists():
            print(f"{TARGET}가 없습니다. python tools/build_web.py 를 실행하세요.")
            return 1
        if TARGET.read_text(encoding="utf-8") != content:
            print(f"{TARGET}가 최신이 아닙니다. python tools/build_web.py 를 실행하세요.")
            return 1
        print(f"{TARGET.relative_to(ROOT)} 최신 상태")
        return 0

    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(content, encoding="utf-8")
    print(f"생성: {TARGET.relative_to(ROOT)} ({TARGET.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
