"""서식(프로파일) → Claude·ChatGPT 채팅창에 올리는 스킬 zip.

스킬 안에는 **표준 라이브러리만 쓰는 빌더**(`assets/hwpx_build.py`)가 들어간다.
채팅창의 코드 실행 환경은 `pip install`이 막혀 있을 수 있어서다. 서식은
`profile.json`에, 빈 문서 틀은 `template.hwpx`에 담는다.

    <스킬 이름>/
      SKILL.md              채팅 AI가 읽는 지시문(마커 표는 서식에서 만든다)
      README.md             사람이 읽는 안내(올리는 곳, 서식 고치는 법)
      profile.json          서식
      template.hwpx         빈 문서 틀
      예시.md               이 서식의 마커로 쓴 짧은 원고
      scripts/hwpx_build.py 원고 → .hwpx

브라우저(`docs/js/skillpack.js`)가 같은 틀·같은 규칙으로 같은 파일을 만든다.
틀은 `docs/assets.js`로 복제되고(`tools/build_web.py`), 두 쪽이 같은 결과를 내는지는
테스트가 대조한다.
"""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path
from typing import Any, Dict, List

from .export_form import _short, _slug
from .profile import merge_profile

_ASSETS = Path(__file__).resolve().parent / "assets"
SKILL_BUILDER = "hwpx_build.py"

#: 내장 서식별 스킬 영문 이름(웹 앱 skill-ui.js의 PRESET_IDS와 같다)
PRESET_IDS = {
    "kihasa-research": "hwpx-crown-report", "policy-default": "hwpx-policy-report",
    "gov-3level": "hwpx-gov-report", "narrative": "hwpx-narrative-report",
}

#: 자동 번호 → 사람이 읽을 모양
AUTO_LABELS = {
    "AUTO_ROMAN": "Ⅰ. Ⅱ. Ⅲ.",
    "AUTO_NUM": "1. 2. 3.",
    "AUTO_ALPHA": "A. B. C.",
    "AUTO_HANGUL": "가. 나. 다.",
    "AUTO_CIRCLED": "① ② ③",
    "AUTO_CHAPTER": "제1장 제2장",
    "AUTO_SECTION": "제1절 제2절",
    "AUTO_PAREN": "1) 2) 3)",
    "AUTO_TABLE": "〈표 1-1〉 (표 제목)",
    "AUTO_FIGURE": "〔그림 1-1〕 (그림 제목)",
}

PERIOD_RULES = {
    "single_sentence_no_period": "한 문장이면 온점을 찍지 않고, 두 문장 이상이면 찍는다",
    "always_period": "모든 문장을 온점으로 끝낸다",
    "never_period": "온점을 찍지 않는다",
    "off": "온점은 검사하지 않는다",
}


def fmt_num(value: Any) -> str:
    """숫자를 사람이 읽을 모양으로. 브라우저 `String(n)`과 같게 맞춘다."""
    number = float(value)
    if number == int(number):
        return str(int(number))
    return repr(round(number, 4)).rstrip("0").rstrip(".")


def _head(level: Dict[str, Any]) -> str:
    prefix = str(level.get("prefix", ""))
    if prefix.startswith("AUTO_"):
        return AUTO_LABELS.get(prefix, prefix) + " (도구가 매김)"
    if prefix.strip():
        return f"`{prefix.strip()}` (도구가 붙임)"
    return "없음"


def marker_rows(profile: Dict[str, Any]) -> str:
    rows = ["| 입력 마커 | 단계 | 문서에 찍히는 머리 | 글자 |", "|---|---|---|---|"]
    for lv in profile["levels"]:
        marker = f"`{lv['marker']}`" if lv.get("marker") else "(마커 없이 쓴 줄)"
        size = fmt_num(lv.get("size_pt", 0)) + "pt" + (" 굵게" if lv.get("bold") else "")
        rows.append(f"| {marker} | {lv.get('name') or lv['key']} | {_head(lv)} | {size} |")
    if profile.get("mode") == "narrative":
        rows.append(f"| (마커 없이 쓴 줄) | 본문 | 없음 | "
                    f"{fmt_num(profile['body'].get('size_pt', 0))}pt |")
    return "\n".join(rows)


def _caption_marker(profile: Dict[str, Any], kind: str) -> str:
    for lv in profile["levels"]:
        if lv.get("prefix") == kind and lv.get("marker"):
            return str(lv["marker"])
    return ""


def caption_lines(profile: Dict[str, Any]) -> str:
    table = _caption_marker(profile, "AUTO_TABLE")
    figure = _caption_marker(profile, "AUTO_FIGURE")
    out = []
    if table:
        out.append(f"- 표 제목: 표 바로 위에 `{table} 제목` 한 줄. 번호(〈표 1-1〉)는 도구가 매긴다")
    if figure:
        out.append(f"- 그림·도식 제목: 도식 바로 위에 `{figure} 제목` 한 줄. 번호는 도구가 매긴다")
    if not out:
        out.append("- 이 서식에는 표·그림 번호 단계가 없다. 도식 제목은 블록의 `title=\"…\"`로 준다")
    return "\n".join(out)


def page_line(profile: Dict[str, Any]) -> str:
    page = profile["page"]
    margin = page.get("margin_mm", {})
    size = str(page.get("size", ""))
    if page.get("width_mm") and page.get("height_mm"):
        size = f"{size} {fmt_num(page['width_mm'])}×{fmt_num(page['height_mm'])}mm".strip()
    return (f"{size}, 여백 왼쪽 {fmt_num(margin.get('left', 0))}·오른쪽 "
            f"{fmt_num(margin.get('right', 0))}·위 {fmt_num(margin.get('top', 0))}·아래 "
            f"{fmt_num(margin.get('bottom', 0))}mm")


def skill_fields(profile: Dict[str, Any], name: str, skill_id: str = "") -> Dict[str, str]:
    """틀에 채워 넣을 값. 브라우저와 같은 값을 만들어야 한다."""
    profile = merge_profile(profile)
    name = " ".join(str(name or profile.get("name") or "보고서").split())
    narrative = profile.get("mode") == "narrative"
    rules = profile.get("rules") or {}
    return {
        "name": name,
        "slug": _slug(skill_id.strip() or name),
        "short": _short(name),
        "mode": ("서술식 — `#`·`##` 제목 밖의 줄은 모두 본문 문단이 된다"
                 if narrative else "개조식 — 줄머리 마커로 단계를 가른다"),
        "markers": marker_rows(profile),
        "captions": caption_lines(profile),
        "page": page_line(profile),
        "fonts": (f"제목 {profile['fonts'].get('bold', '')} / "
                  f"본문 {profile['fonts'].get('light', '')}"),
        "period": PERIOD_RULES.get(rules.get("period_policy", ""), "기본 규칙"),
    }


def sample_text(profile: Dict[str, Any]) -> str:
    """이 서식의 마커로 쓴 짧은 원고. 단계마다 한 줄 + 표 + 도식 + 각주."""
    profile = merge_profile(profile)
    lines: List[str] = []
    captions = {"AUTO_TABLE", "AUTO_FIGURE"}
    for lv in profile["levels"]:
        if lv.get("prefix") in captions:
            continue
        label = lv.get("name") or lv["key"]
        text = f"{label} 단계의 예시 문장이다."
        lines.append(f"{lv['marker']} {text}" if lv.get("marker") else text)
    if profile.get("mode") == "narrative":
        lines.append("본문 문단의 예시다. 근거가 되는 말 뒤에 각주를 단다[^1].")
    else:
        body = [lv for lv in profile["levels"]
                if not str(lv.get("prefix", "")).startswith("AUTO_")]
        head = f"{body[0]['marker']} " if body and body[0].get("marker") else ""
        lines.append(f"{head}근거가 되는 말 뒤에 각주를 단다[^1]")

    table = _caption_marker(profile, "AUTO_TABLE")
    figure = _caption_marker(profile, "AUTO_FIGURE")
    lines.append("")
    if table:
        lines += [f"{table} 연도별 실적", ""]
    lines += ["| 구분 | 2024년 | 2025년 |", "|---|---|---|",
              "| 처리 건수 | 1,204 | 1,388 |", "| 처리 기간(일) | 14 | 11 |", ""]
    if figure:
        lines += [f"{figure} 추진 체계", ""]
    lines += [':::diagram type=org title="추진 체계"', "총괄", "  기획부", "  운영부", ":::",
              "", "[^1]: ○○청. (2025). 『행정통계』. 12쪽.", ""]
    return "\n".join(lines)


def _profile_json(profile: Dict[str, Any]) -> str:
    return json.dumps(profile, ensure_ascii=False, indent=2) + "\n"


def render(template: str, fields: Dict[str, str]) -> str:
    out = template
    for key, value in fields.items():
        out = out.replace("{{" + key + "}}", value)
    return out


def template_bytes() -> bytes:
    """빈 문서 틀. python-hwpx의 빈 문서와 같다(웹 앱의 HWPX_TEMPLATE_B64)."""
    from hwpx.templates import blank_document_bytes   # 개발 쪽에서만 필요하다
    return blank_document_bytes()


def build_skill(profile: Dict[str, Any], name: str = "",
                template: bytes = b"", skill_id: str = "") -> Dict[str, bytes]:
    """서식 → {스킬 안 경로: 내용}."""
    fields = skill_fields(profile, name, skill_id)
    return {
        "SKILL.md": render(SKILL_TEMPLATE, fields).encode("utf-8"),
        "README.md": render(README_TEMPLATE, fields).encode("utf-8"),
        "profile.json": _profile_json(profile).encode("utf-8"),
        "template.hwpx": template or template_bytes(),
        "예시.md": sample_text(profile).encode("utf-8"),
        f"scripts/{SKILL_BUILDER}": (_ASSETS / SKILL_BUILDER).read_bytes(),
    }


def pack_skill(files: Dict[str, bytes], root: str) -> bytes:
    """zip으로 묶는다. 맨 위 폴더 이름 = 스킬 이름(claude.ai 조건)."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for path, data in files.items():
            z.writestr(f"{root}/{path}", data)
    return buf.getvalue()


SKILL_TEMPLATE = """---
name: {{slug}}
description: >-
  {{short}} 서식으로 한국어 보고서를 한글 문서(.hwpx)로 만든다. 마커 텍스트로 본문을
  쓰면 표·도식·각주까지 넣은 hwpx가 나온다. '{{short}}', '한글 보고서', '.hwpx',
  '조직도', '체계도' 요청 시 사용.
---

# {{name}} — 한글 문서 만들기

사용자가 보고서·문서를 요청하면 본문을 **마커 텍스트**로 쓰고, 이 스킬에 든
`scripts/hwpx_build.py`로 한글 문서(.hwpx)를 만들어 건넨다. 빌더는 파이썬 표준
라이브러리만 쓴다. 설치할 것이 없다.

## 절차

1. 요구를 확인한다. 분량이 길면 목차와 첫 절 초안을 먼저 보여 주고 승인을 받는다
2. 본문을 `원고.md`로 쓴다(아래 규칙). 서식 설명은 쓰지 않는다 — 서식은 `profile.json`에 있다
3. 검사: `python scripts/hwpx_build.py 원고.md --check-only`
   경고를 보고 원고를 고친다. 경고는 대부분 실제 구조 문제다
4. 생성: `python scripts/hwpx_build.py 원고.md -o 결과.hwpx`
5. 결과 파일을 사용자에게 건네고, 한글에서 열어 확인하라고 알린다
   (줄바꿈·쪽 나눔·표 높이는 한글이 열 때 다시 계산한다)

코드를 실행할 수 없는 환경이면 원고(마커 텍스트)만 건네고, 사용자가 웹 앱
<https://beaver21c.github.io/hwpx_set/>의 **여기서 바로 쓰기**에 붙여 넣게 안내한다.

## 이 서식

- 문체: {{mode}}
- 용지: {{page}}
- 글꼴: {{fonts}}
- 온점: {{period}}

## 마커

{{markers}}

- 마커 뒤에는 공백 한 칸. `-3%`처럼 붙여 쓴 것은 마커로 읽지 않는다
- 번호·기호는 도구가 붙인다. 본문에 겹쳐 쓰지 않는다
- 빈 줄은 문단 사이 간격. 표·도식 앞뒤에는 빈 줄을 둔다

## 표

```
| 구분 | 2024년 | 2025년 |
|---|---|---|
| 처리 건수 | 1,204 | 1,388 |
```

첫 행이 머리행이다.

{{captions}}

## 도식 — 한글에서 편집 가능한 표로 들어간다

```
:::diagram type=org title="추진 체계"
총괄
  기획부
  운영부
:::

:::diagram type=flow title="처리 절차"
접수 → 검토 → 심의 → 통보
:::

:::diagram type=matrix title="역할 분담"
| | 중앙 | 지방 |
| 기획 | 본부 | 지역본부 |
:::

:::diagram type=strategy title="전략 체계"
미션 | 국민의 삶의 질 향상
핵심가치 | 존중 | 연계 | 신뢰
전략과제 | 발굴 | 연계 | 전달체계
:::

:::diagram type=db title="DB 구성"
[대상자]
  *대상자ID
  이름
[서비스]
  *서비스ID
  +대상자ID
대상자 -> 서비스
:::
```

- 조직도는 2칸 들여쓰기가 한 단계 아래. 상자가 많으면 `layout=side`(세로 목록형)
- 절차도를 세로로: `direction=down`
- 상자 색: `기획부 {fill=#2E75B6 color=#FFFFFF}`, 점선 연결: `{link=dash}`, 테두리 없음: `{border=none}`
- 그림(PNG·캡처)뿐인 도식은 직접 보고 위 형식으로 받아쓴 뒤, 사용자에게 블록을 보여 주고 확인받는다

## 각주

근거가 되는 말 **바로 뒤에 붙여** `[^1]`, 내용은 아무 데나 `[^1]: 출처` 줄로 쓴다.
문장 전체의 근거면 마침표 앞에 둔다. 제목·표 안·도식 상자 안에는 달지 않는다.

## 지킬 것

- 확인되지 않은 수치·출처는 쓰지 않고 `[확인 필요]`로 둔다. 출처를 지어내 각주로 달지 않는다
- 도식의 계층을 추정으로 채우지 않는다. 원본에서 읽히지 않으면 묻는다
- `예시.md`가 이 서식으로 쓴 짧은 원고다. 처음이면 한 번 읽는다
"""

README_TEMPLATE = """# {{name}} — 한글 문서 스킬

Claude·ChatGPT 채팅창에서 이 서식으로 한글 문서(.hwpx)를 만드는 스킬이다.
<https://beaver21c.github.io/hwpx_set/>에서 만들었다.

## 올리는 법 — zip을 풀지 말고 그대로

| | 올리는 곳 |
|---|---|
| Claude | Settings → Capabilities에서 **Code execution and file creation**을 켠 뒤, Customize → Skills → + → Create skill → **Upload a skill** |
| ChatGPT | Skills → Create → **Upload from your computer** |
| Claude Code | `unzip 이파일.zip -d ~/.claude/skills/` |

올린 뒤 "이 스킬로 ○○ 보고서를 한글 파일로 만들어 줘"라고 하면 된다.

## 이 서식

- 문체: {{mode}}
- 용지: {{page}}
- 글꼴: {{fonts}}

{{markers}}

## 서식을 고치려면

웹 앱의 **스킬 만들기**에서 고쳐 다시 받는 것이 가장 쉽다. 손으로 고친다면 zip을 풀어
`profile.json`을 고친 뒤, 맨 위 폴더(`{{slug}}`)째 다시 zip으로 묶는다.
규격: <https://github.com/beaver21c/hwpx_set/blob/main/docs/profile-spec.md>

## 손으로 돌려 보기

```bash
python scripts/hwpx_build.py 예시.md -o 예시.hwpx
```

파이썬 3.9 이상, 표준 라이브러리만 쓴다.
"""

TEMPLATES = {"SKILL.md": SKILL_TEMPLATE, "README.md": README_TEMPLATE}
