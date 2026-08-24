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
        '절차도는 :::diagram type=flow 안에 "A → B → C" 한 줄로, '
        "전략체계도는 :::diagram type=strategy 안에 "
        '"단이름 | 칸 | 칸" 줄로(라벨 없이 |로 시작하면 위 단의 다음 줄).\n'
        "상자 색은 이름 뒤에 {fill=#RRGGBB color=#RRGGBB}로 적을 수 있음.\n"
        "각주: 근거가 되는 말 바로 뒤에 붙여 [^1], 내용은 [^1]: 출처 줄로. "
        "번호는 앞말에 붙여 쓰고, 문장 전체의 근거면 마침표 앞에 둔다. "
        "인용문 자체가 각주 대상이면 닫는 따옴표 안에 넣는다.\n"
        "확인되지 않은 수치·출처는 쓰지 말고 [확인 필요]로 표시.\n"
    )


SKILL_TEMPLATE = """---
name: {slug}
description: {description}
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
- 도식: `:::diagram type=org|flow|matrix|strategy` … `:::`
- 각주: 본문에 `[^1]`, 내용은 `[^1]: 출처` 줄

## 3. 계층 균형

{balance}

## 4. 각주

근거·출처는 본문에 괄호로 적지 말고 각주로 단다. 근거가 되는 말 **바로 뒤에 붙여**
`[^라벨]`을 적고, 내용은 아무 데나 `[^라벨]: …` 줄로 적는다.

```
○ 노인 빈곤율은 40.4%로 가장 높다[^1]

[^1]: 통계청(2024), 「가계금융복지조사」.
```

한글의 진짜 각주(쪽 아래 + 자동 번호)로 들어가고 **8pt 회색**이다. 라벨은 이름표일
뿐이고, 인쇄되는 번호는 한글이 문서 순서대로 매긴다.

**번호를 놓는 자리** — 따옴표 규칙 말고는 어기면 `[경고:footnote]`가 뜬다.

| 규칙 | 맞는 예 | 틀린 예 |
|---|---|---|
| 앞말에 붙여 쓴다 | `40.4%다[^1]` | `40.4%다 [^1]` |
| 문장 전체의 근거면 마침표 **앞** | `…이어졌다[^2].` | `…이어졌다.[^2]` |
| 인용문 자체가 대상이면 따옴표 **안** | `"…구조적 문제다[^3]"라고` | — 도구가 검사하지 않는다 |
| 낱말 하나면 그 낱말 뒤 | `기초연금[^4]은` | 문장 끝까지 끌고 가기 |

따옴표는 각주가 무엇을 가리키는지로 갈린다. 인용문 자체의 출처이면 닫는 따옴표
**안**, 인용을 쓴 문장 쪽의 근거이면 따옴표 밖이다. 헷갈리면 따옴표 안.

제목·표 안·도식 상자 안에는 달지 않는다. 표에 주석이 필요하면 표 아래 `※ ` 줄로 쓴다.

## 5. 도식(조직도·체계도·절차도)

도식은 한글에서 **편집 가능한 표**로 들어간다. 본문 아무 곳에나 블록으로 쓰면 된다.

### 5.1 네 가지 유형

```
:::diagram type=org title="추진 체계"      # 조직도·체계도(2칸 들여쓰기 = 한 단계 아래)
총괄
  기획부
    기획팀
  운영부
:::

:::diagram type=flow title="처리 절차"     # 절차도(세로는 direction=down)
접수 → 검토 → 심의 → 통보
:::

:::diagram type=matrix title="역할 분담"   # 격자(첫 행·첫 열이 제목 칸)
| | 중앙 | 지방 |
| 기획 | 본부 | 지역본부 |
:::

:::diagram type=strategy title="경영전략 체계도"   # 단이 쌓이는 전략체계도
미션 | 국민의 삶의 질 향상에 기여한다
핵심가치 | 공감 | 안전 | 공정 | 신뢰
4대 전략방향 | 분쟁해결 | 안전환경 | 거래환경 | 혁신경영
| 세부과제1 | 세부과제2 | 세부과제3 | 세부과제4
:::
```

`strategy`에서 **라벨 없이 `|`로 시작한 줄은 위 단의 다음 줄**이다.

### 5.2 색·선

상자 뒤에 `{{ }}`로 적는다. 원본 도식의 색을 옮겨 담을 때 쓴다.

```
대표 {{fill=#C00000 color=#FFFFFF}}
  기획부 {{fill=#2E75B6 color=#FFFFFF}}
  감사실 {{fill=#FFF2CC border=#BF8F00 link=dash link_color=#808080}}
```

| 속성 | 뜻 |
|---|---|
| `fill` / `color` / `border` | 채움색 / 글자색 / 테두리색(`border=none`이면 상자 없이 글자만) |
| `link` / `link_color` | 이 상자로 내려오는 연결선의 종류(`dash` `dot` `none`) / 색 |

블록 첫 줄에 쓰면 그 도식 전체에 적용된다: `:::diagram type=org box_fill=#F2F2F2 line_style=dash`

### 5.3 상자가 많을 때

같은 단계 상자가 8개를 넘으면 **세로 목록형으로 자동 전환**된다(폭이 늘지 않는다).
직접 지정하려면 `layout=side`, 가로를 고집하려면 `layout=wide`.

### 5.4 이미 있는 도식을 옮길 때

**Mermaid·SVG·HTML 파일이면** 도구가 읽는다. 색과 점선은 원본 값 그대로 가져온다.

```bash
python scripts/capture.py 조직도.svg --title "조직 체계"        # 도식 블록만 출력
python scripts/capture.py 조직도.svg --hwpx 조직도.hwpx         # 문서까지 한 번에
```

**그림·캡처(PNG·스캔)뿐이면 도구가 읽지 못한다.** 이때는 **에이전트가 직접 그림을 보고**
위 형식으로 받아쓴다. 상자의 계층·순서·색을 눈으로 읽어 블록으로 옮긴 뒤,
사용자에게 그 블록을 보여 주고 확인을 받는다. 색은 원본과 비슷한 `#RRGGBB`로 적는다.

받아쓴 결과는 그냥 텍스트라, 틀린 곳은 한 줄 고치면 된다.

## 6. 주의

- 확인되지 않은 수치·출처는 `[확인 필요]`로 표시한다. **출처를 지어내 각주로 달지 않는다**
- 도식의 계층을 **추정으로 채우지 않는다.** 원본에서 읽히지 않으면 사용자에게 묻는다
- 결과는 한글(뷰어)에서 한 번 확인할 것을 권한다. 연결선·칸 폭은 화면에서 봐야 안다
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
    ap.add_argument("--strict", action="store_true",
                    help="검사 경고도 오류로 취급해 중단")
    ap.add_argument("--preview", help="HTML 근사 미리보기도 함께 생성")
    ap.add_argument("--no-lint", action="store_true", help="본문 검사 건너뛰기")
    args = ap.parse_args()

    try:
        from hwpx_studio.cli import run_build
    except ImportError:
        print("hwpx-studio가 필요합니다: pip install hwpx-studio", file=sys.stderr)
        return 2
    return run_build(args.input, args.profile, args.out, strict=args.strict,
                     preview_path=args.preview, lint=not args.no_lint)


if __name__ == "__main__":
    raise SystemExit(main())
'''


CAPTURE_SCRIPT = '''#!/usr/bin/env python3
"""남의 도식(Mermaid·SVG·HTML) → 도식 블록 [+ hwpx].

    python scripts/capture.py 조직도.svg --title "조직 체계"
    python scripts/capture.py 조직도.mmd --hwpx 조직도.hwpx

그림(PNG·스캔)은 읽지 못한다 — 그때는 에이전트가 보고 받아쓴다(SKILL.md 4.4).
"""

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROFILE = HERE.parent / "{profile_file}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("source", help="원본 파일(.mmd/.svg/.html/.md) 또는 -(표준입력)")
    ap.add_argument("-o", "--out", help="도식 블록을 저장할 텍스트 파일")
    ap.add_argument("--kind", default="auto",
                    choices=["auto", "mermaid", "svg", "html"])
    ap.add_argument("--title", default="")
    ap.add_argument("--hwpx", help="곧바로 hwpx로도 생성")
    args = ap.parse_args()

    try:
        from hwpx_studio.cli import run_capture
    except ImportError:
        print("hwpx-studio가 필요합니다: pip install hwpx-studio", file=sys.stderr)
        return 2
    return run_capture(args.source, args.out, args.kind, args.title,
                       args.hwpx, str(PROFILE))


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
        "근거는 [^1] 표기로 8pt 회색 한글 각주가 된다. "
        "조직도·체계도·절차도·전략체계도를 한글에서 편집 가능한 **표**로 그려 넣고, "
        "그림·Mermaid·SVG로 된 기존 도식을 읽어 같은 모양으로 옮긴다. "
        "'한글 보고서', '.hwpx', '보고서로 만들어줘', '조직도', '체계도', '절차도', "
        "'전략체계도', '각주', '출처 표시', '이 도식을 한글로' 요청 시 사용."
    )

    description = " ".join(description.split())        # 프론트매터는 한 줄이어야 한다
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
    (out / "scripts" / "capture.py").write_text(
        CAPTURE_SCRIPT.format(profile_file=profile_file), encoding="utf-8")
    (out / "prompt.txt").write_text(prompt_text(profile), encoding="utf-8")

    created = [str(out / "SKILL.md"), str(out / profile_file),
               str(out / "scripts" / "build.py"),
               str(out / "scripts" / "capture.py"), str(out / "prompt.txt")]

    if standalone:
        pkg_dir = out / "scripts" / "hwpx_studio"
        if pkg_dir.exists():
            shutil.rmtree(pkg_dir)
        shutil.copytree(_PKG, pkg_dir,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        created.append(str(pkg_dir))
    return created
