"""양식 hwpx → 꾸러미(파이썬 빌더 + 스킬 + codex 지시문).

꾸러미 하나면 Claude·GPT·codex 어디서든 그 양식대로 한글 문서를 만들 수 있다.

    양식이름/
      template.hwpx     양식 원본(서식의 원천. 고치지 않는다)
      form.json         양식 카드(스타일 번호·표 골격·마커)
      build_form.py     빌더(표준 라이브러리만 씀)
      SKILL.md          Claude 스킬
      AGENTS.md         codex·GPT용 지시문
      README.md         사람이 읽는 사용법
      해부보고서.md      무엇을 어떻게 보았는지
      예시.md           이 양식 마커 텍스트 예시
"""

from __future__ import annotations

import io
import json
import shutil
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .formkit import FormResult, analyze, dump_form

_ASSETS = Path(__file__).resolve().parent / "assets"

#: 꾸러미 파일 이름. 웹·CLI가 같은 이름을 쓴다.
BUILDER = "build_form.py"
FORM_JSON = "form.json"
TEMPLATE = "template.hwpx"


def _marker_rows(form: Dict[str, Any]) -> str:
    rows = ["| 마커 | 뜻 | 기호·번호를 붙이는 쪽 |", "|---|---|---|"]
    for lv in form.get("levels", []):
        if lv.get("auto_bullet"):
            who = f"한글이 자동으로 `{lv['auto_bullet']}` — 본문에 쓰지 말 것"
        elif lv.get("auto_number"):
            who = "한글이 자동으로 번호 — 본문에 쓰지 말 것"
        elif lv.get("numbering"):
            who = f"도구가 번호를 매김({lv['numbering']})"
        elif lv.get("write_marker"):
            who = f"도구가 `{lv['marker']}`를 붙임"
        else:
            who = "없음"
        rows.append(f"| `{lv.get('marker') or '(마커 없음)'}` | "
                    f"{lv.get('name', '')} {lv.get('size_pt', '')}pt | {who} |")
    return "\n".join(rows)


def _sample_text(form: Dict[str, Any]) -> str:
    """이 양식의 마커로 쓴 짧은 예시. 마커가 실제로 무엇인지 보여 준다."""
    lines: List[str] = []
    bodies = [
        "추진 배경 및 목적",
        "제도 개선 요구가 이어져 개선 방안을 마련",
        "기존 절차의 처리 기간이 길어 이용자 불편이 누적",
        "현장 실사 대상은 무작위 층화 표본으로 뽑음",
        "실사 기간은 2025년 9월~11월",
    ]
    for i, lv in enumerate(form.get("levels", [])):
        marker = lv.get("marker")
        if not marker:
            continue
        text = bodies[i % len(bodies)]
        if marker.startswith("#"):
            text = ["사업 추진 현황", "추진 개요", "세부 내용", "참고"][
                min(marker.count("#") - 1, 3)]
        lines.append(f"{marker} {text}")
    if not lines:
        lines = ["내용을 한 줄에 하나씩 적는다"]

    table = form.get("table") or {}
    lines += ["", "[표: 연도별 처리 실적]", "{cols=30,35,35}",
              "| 구분 | 2024년 | 2025년 |", "|---|---|---|",
              "| 처리 건수 | 1,204건 | 1,388건 |",
              "| 평균 처리 기간 | 14일 | 11일 |", ""]
    if not table.get("caption"):
        lines.insert(-8 if len(lines) > 8 else 0, "")
    first_marker = next((lv["marker"] for lv in form.get("levels", [])
                         if lv.get("marker") and not lv["marker"].startswith("#")), "")
    if form.get("footnote"):
        lines += [f"{first_marker} 처리 기간이 3일 줄었다[^1]".strip(), "",
                  "[^1]: 통계청(2025), 「행정통계」, 87쪽."]
    return "\n".join(lines) + "\n"


def _readme(form: Dict[str, Any]) -> str:
    name = form.get("name", "양식")
    return f"""# {name} — 한글 문서 꾸러미

이 폴더 하나로 **{name} 서식 그대로** 한글 문서(.hwpx)를 만든다.

## 어떻게 서식이 지켜지나

`template.hwpx`(양식 원본)를 고치지 않는다. 스타일·글꼴·자동 글머리표·번호매기기·
쪽 설정이 들어 있는 `header.xml`은 **한 바이트도 건드리지 않고**, 본문 문단만 새로
만들어 갈아 끼운다. 그래서 서식이 재현이 아니라 **보존**된다.

## 쓰는 법

```bash
python build_form.py 원고.md -o 결과.hwpx
python build_form.py 원고.md --check-only    # 입력 검사만
python build_form.py --markers               # 마커 목록
```

AI(Claude·GPT·codex)에게는 이 폴더를 통째로 주고 "원고를 마커 텍스트로 쓴 뒤
`build_form.py`로 만들어 달라"고 하면 된다. 지시문은 `SKILL.md`(Claude)와
`AGENTS.md`(codex·GPT)에 들어 있다.

## 마커

{_marker_rows(form)}

## 공통 문법

| 쓰는 법 | 결과 |
|---|---|
| (빈 줄) | 문단 사이 간격 |
| `\\| 구분 \\| 값 \\|` | 표. 첫 행이 머리행. `\\|---\\|` 줄은 무시 |
| `[표: 제목]` | 바로 다음 표의 제목 |
| `{{cols=30,35,35}}` | 바로 다음 표의 열 너비 백분율 |
| 셀 안 `<br>` | 셀 안에서 줄 나눔 |
| `앞말[^1]` | 각주 번호 자리 |
| `[^1]: 내용` | 각주 내용(문서 어디에 적어도 된다) |

## 확인할 것

- 만든 문서를 **한글에서 한 번 열어 볼 것.** 줄바꿈·쪽 나눔·표 높이는 한글이 열 때
  다시 계산한다
- 마커가 뜻대로 잡혔는지는 `해부보고서.md`에 근거가 있다. 다르면 `form.json`의
  `levels`를 고치면 된다
"""


def _skill_md(form: Dict[str, Any]) -> str:
    name = form.get("name", "양식")
    slug = _slug(name)
    footnote = "각주는 근거가 되는 말 뒤에 `[^1]`로 단다. " if form.get("footnote") else ""
    return f"""---
name: {slug}
description: >-
  {name} 서식 그대로 한글 문서(.hwpx)를 만든다. 마커를 붙인 텍스트로 본문을 쓰면
  양식의 스타일·글꼴·자동 글머리표를 그대로 지킨 hwpx가 나온다. {footnote}'{name}',
  '이 양식으로', '한글 보고서', '.hwpx로 만들어줘' 요청 시 사용.
---

# {name} 문서 만들기

## 무엇을 하는 스킬인가

`{name}` 양식 원본을 고치지 않고 본문만 갈아 끼워 한글 문서를 만든다. 서식을
흉내 내는 것이 아니라 **양식 파일 자체를 쓰기 때문에** 글꼴·자동 글머리표·
번호매기기·쪽 설정이 원본 그대로다.

## 절차

1. 사용자에게 무엇을 쓸지 듣는다. 자료가 있으면 먼저 읽는다
2. 아래 마커로 **본문만** 텍스트로 쓴다. 서식 설명·코드블록을 넣지 않는다
3. `python build_form.py 원고.md --check-only`로 검사한다
4. 경고를 고친 뒤 `python build_form.py 원고.md -o 결과.hwpx`
5. 사용자에게 파일을 주고 **한글에서 한 번 열어 보라고** 말한다

## 마커

{_marker_rows(form)}

**기호를 두 번 쓰지 않는다.** 위 표에서 '한글이 자동으로'라고 적힌 레벨은 마커만
쓰고 본문에 기호를 또 적으면 안 된다. 이중으로 찍힌다.

## 공통 문법

```
(빈 줄)            문단 사이 간격
| 구분 | 값 |      표. 첫 행이 머리행
[표: 제목]         바로 다음 표의 제목
{{cols=30,35,35}}    바로 다음 표의 열 너비 백분율
셀 안 <br>         셀 안에서 줄 나눔
앞말[^1]           각주 번호 자리
[^1]: 내용         각주 내용
```

표 앞뒤에는 빈 줄을 둔다.

## 각주 번호를 놓는 자리

- 근거가 되는 **말 바로 뒤**에 빈칸 없이 붙인다
- 문장 전체의 근거이면 **마침표 앞**(`…이어졌다[^1].`) — 국내 학술·정부 보고서 관행
- 인용문 **자체**가 각주 대상이면 닫는 **따옴표 안**(`"…이다[^2]"라고`),
  인용을 쓴 문장 쪽의 근거이면 따옴표 밖
- 제목·표 안에는 달지 않는다
- 번호는 한글이 문서 순서대로 매긴다. `[^1]`의 숫자는 이름표일 뿐이다

## 지켜야 할 것

- **출처를 지어내지 않는다.** 확인한 자료만 적고, 확인하지 못했으면 `[확인 필요]`로
  남겨 사용자에게 묻는다
- 한 항목은 한 줄. 단문은 온점을 생략하고 두 문장 이상이면 온점을 찍는다
- 검사에서 나온 경고를 그냥 지나치지 않는다. 고치거나, 왜 두는지 사용자에게 말한다
- 만든 문서의 최종 모양은 **한글에서 열어야** 확인된다. 그 사실을 숨기지 않는다
"""


def _agents_md(form: Dict[str, Any]) -> str:
    name = form.get("name", "양식")
    return f"""# {name} 한글 문서 만들기 (codex·GPT용)

이 폴더에는 `{name}` 양식으로 한글 문서(.hwpx)를 만드는 도구가 들어 있다.

## 실행

```bash
python build_form.py 원고.md -o 결과.hwpx
```

파이썬 3.9 이상, 표준 라이브러리만 쓴다. 설치할 것이 없다.

## 네가 할 일

1. 사용자의 요구대로 **본문만** `원고.md`에 마커 텍스트로 쓴다
2. `python build_form.py 원고.md --check-only`로 검사하고 경고를 고친다
3. 문서를 만들고 파일을 사용자에게 준다
4. 한글에서 열어 확인해야 한다고 알린다

## 마커

{_marker_rows(form)}

'한글이 자동으로'라고 적힌 레벨은 마커만 쓴다. 본문에 기호를 또 적으면 이중이 된다.

## 공통 문법

```
(빈 줄)            문단 사이 간격
| 구분 | 값 |      표. 첫 행이 머리행
[표: 제목]         표 제목
{{cols=30,35,35}}    열 너비 백분율
셀 안 <br>         셀 안 줄 나눔
앞말[^1]           각주 번호 자리
[^1]: 내용         각주 내용
```

## 금지

- 출처를 지어내지 말 것. 확인하지 못한 것은 `[확인 필요]`로 남길 것
- `form.json`의 스타일 번호를 임의로 바꾸지 말 것. 양식에 없는 번호를 쓰면 빌더가
  2층 검사에서 멈춘다
- `template.hwpx`를 고치지 말 것
"""


def _slug(name: str) -> str:
    """스킬 이름은 소문자·숫자·하이픈만 쓴다."""
    out = []
    for ch in name.lower():
        if ch.isascii() and (ch.isalnum()):
            out.append(ch)
        elif ch in " _-.":
            out.append("-")
    slug = "".join(out).strip("-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug or "hwpx-form"


def build_bundle(source: Any, name: str = "") -> Tuple[Dict[str, bytes], FormResult]:
    """양식 hwpx → {파일 이름: 내용} 꾸러미."""
    template_bytes = _read_bytes(source)
    result = analyze(template_bytes if isinstance(source, (bytes, bytearray)) else source,
                     name=name)
    form = result.form
    files: Dict[str, bytes] = {
        TEMPLATE: template_bytes,
        FORM_JSON: dump_form(form).encode("utf-8"),
        BUILDER: (_ASSETS / BUILDER).read_bytes(),
        "SKILL.md": _skill_md(form).encode("utf-8"),
        "AGENTS.md": _agents_md(form).encode("utf-8"),
        "README.md": _readme(form).encode("utf-8"),
        "해부보고서.md": result.report.encode("utf-8"),
        "예시.md": _sample_text(form).encode("utf-8"),
    }
    return files, result


def _read_bytes(source: Any) -> bytes:
    if isinstance(source, (bytes, bytearray)):
        return bytes(source)
    return Path(str(source)).read_bytes()


def write_bundle(files: Dict[str, bytes], out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, data in files.items():
        (out_dir / name).write_bytes(data)
    return out_dir


def pack_bundle(files: Dict[str, bytes], root: str) -> bytes:
    """`.skill`·`.zip`으로 묶는다. 폴더 이름을 한 겹 두어 그대로 풀 수 있게 한다."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in files.items():
            z.writestr(f"{root}/{name}", data)
    return buf.getvalue()
