"""프로파일 → 에이전트 스킬 폴더(SKILL.md + 빌드 스크립트 + 지시문)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, Dict, List

from .profile import body_levels, merge_profile

_PKG = Path(__file__).resolve().parent


def level_table(profile: Dict[str, Any]) -> str:
    rows = ["| 마커 | 레벨 | 용도 | 크기 | 예시 |", "|---|---|---|---|---|"]
    for lv in profile["levels"]:
        marker = lv.get("marker") or "-"
        sample = f"{lv.get('prefix') if not str(lv.get('prefix','')).startswith('AUTO_') else ''}내용"
        rows.append(f"| `{marker}` | {lv['key']} | {lv.get('name', '')} | "
                    f"{lv.get('size_pt')}pt | {marker} {sample} |")
    return "\n".join(rows)


def prompt_text(profile: Dict[str, Any]) -> str:
    """타 AI에게 그대로 붙여넣을 300자 내외 지시문."""
    marks = []
    for lv in profile["levels"]:
        if lv.get("marker"):
            marks.append(f'"{lv["marker"]} "={lv.get("name") or lv["key"]}')
    rules = profile.get("rules", {}).get("min_children", {})
    balance = " ".join(
        f"{k} 아래 하위 항목 {v}개 이상." for k, v in rules.items()) or ""
    return (
        "아래 규칙으로 보고서 본문만 텍스트로 작성. 서식 설명·코드블록 금지.\n"
        f"줄머리 마커: {', '.join(marks)}. 마커 뒤 공백 1칸.\n"
        "마커로 쓰는 번호·기호는 본문 안에 쓰지 말 것.\n"
        f"{balance}\n"
        "한 항목 한 줄, 단문은 온점 생략, 두 문장 이상이면 온점. 경어체 금지.\n"
        "표는 | 구분 | 값 | 형식, 앞뒤 빈 줄.\n"
        "조직도·체계도는 :::diagram type=org 와 ::: 사이에 2칸 들여쓰기 트리로, "
        '절차도는 :::diagram type=flow 안에 "A → B → C" 한 줄로.\n'
        "확인되지 않은 수치·출처는 쓰지 말고 [확인 필요]로 표시.\n"
    )


SKILL_TEMPLATE = """---
name: {slug}
description: >-
  {description}
---

# {name}

프로파일 `{profile_file}`의 서식으로 한국어 보고서를 `.hwpx`로 만든다.
본문은 아래 마커 규칙으로 쓰고, `scripts/build.py`가 변환한다.

## 1. 절차

1. 사용자 요구를 확인하고 본문을 마커 텍스트로 작성한다(`input.md`)
2. `python scripts/build.py input.md -o 결과.hwpx` 실행
3. 경고(lint)가 있으면 본문을 고쳐 다시 실행한다
4. 결과 파일 경로를 사용자에게 알린다

## 2. 마커 규칙

{level_table}

- 마커 뒤에는 공백 1칸. `-3%` 같은 표현은 마커로 인식되지 않는다
- 빈 줄은 블록 구분. 표·도식 앞뒤에는 빈 줄을 둔다
- 표: `| 구분 | 값 |` 형식(첫 행이 머리행)
- 그림: `![](경로.png)`
- 도식: `:::diagram type=org|flow|matrix` … `:::`

## 3. 계층 균형

{balance}

## 4. 도식 예시

```
:::diagram type=org title="추진 체계"
총괄
  기획부
  운영부
:::
```

## 5. 주의

- 확인되지 않은 수치·출처는 `[확인 필요]`로 표시한다
- 결과는 한글(뷰어)에서 한 번 확인할 것을 권한다
"""

BUILD_SCRIPT = '''#!/usr/bin/env python3
"""마커 텍스트 → hwpx (이 스킬에 동봉된 프로파일 사용)."""

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROFILE = HERE.parent / "{profile_file}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("input", help="마커 텍스트 파일")
    ap.add_argument("-o", "--out", default="report.hwpx")
    ap.add_argument("-p", "--profile", default=str(PROFILE))
    ap.add_argument("--strict", action="store_true")
    args = ap.parse_args()

    try:
        from hwpx_studio.cli import run_build
    except ImportError:
        print("hwpx-studio가 필요합니다: pip install hwpx-studio", file=sys.stderr)
        return 2
    return run_build(args.input, args.profile, args.out, strict=args.strict)


if __name__ == "__main__":
    raise SystemExit(main())
'''


def export_skill(profile: Dict[str, Any], out_dir: str,
                 slug: str = "hwpx-report", standalone: bool = False) -> List[str]:
    """스킬 폴더를 만들고 생성된 파일 목록을 돌려준다."""
    profile = merge_profile(profile)
    out = Path(out_dir)
    (out / "scripts").mkdir(parents=True, exist_ok=True)

    profile_file = "profile.json"
    (out / profile_file).write_text(
        json.dumps(profile, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    rules = profile.get("rules", {}).get("min_children", {})
    balance = "\n".join(f"- `{k}` 아래 하위 항목 {v}개 이상" for k, v in rules.items()) \
        or "- 특별한 제약 없음"
    markers = " ".join(lv.get("marker", "") for lv in body_levels(profile) if lv.get("marker"))
    description = (
        f"{profile.get('name', '보고서')} 서식으로 한국어 보고서를 .hwpx로 생성한다. "
        f"마커({markers}) 텍스트를 쓰면 변환한다. "
        "'한글 보고서', '.hwpx', '보고서로 만들어줘' 요청 시 사용."
    )

    (out / "SKILL.md").write_text(SKILL_TEMPLATE.format(
        slug=slug,
        name=profile.get("name", "보고서 생성기"),
        description=description,
        profile_file=profile_file,
        level_table=level_table(profile),
        balance=balance,
    ), encoding="utf-8")

    (out / "scripts" / "build.py").write_text(
        BUILD_SCRIPT.format(profile_file=profile_file), encoding="utf-8")
    (out / "prompt.txt").write_text(prompt_text(profile), encoding="utf-8")

    created = [str(out / "SKILL.md"), str(out / profile_file),
               str(out / "scripts" / "build.py"), str(out / "prompt.txt")]

    if standalone:
        pkg_dir = out / "scripts" / "hwpx_studio"
        if pkg_dir.exists():
            shutil.rmtree(pkg_dir)
        shutil.copytree(_PKG, pkg_dir,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        created.append(str(pkg_dir))
    return created
