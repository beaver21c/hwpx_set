"""시험용 양식 hwpx 만들기.

`formkit`/`build_form`이 다뤄야 하는 두 가지 양식을 만든다.

  - `plain_form()` — 기호를 본문 텍스트에 적어 넣는 양식(이 저장소 엔진의 산출물)
  - `auto_bullet_form()` — 한글이 글머리표·번호를 **자동으로** 붙이는 양식

두 번째가 이 방식의 존재 이유다. 자동 글머리표는 문단 속성(`hh:paraPr`의
`hh:heading`)에 걸려 있어 프로파일로 옮겨 적을 수 없다. 양식을 템플릿으로 그대로
두어야만 살아남는다.

이 파일이 만드는 것은 **손으로 꾸민 표본**이다. 실제 기관 양식으로 확인하는 일을
대신하지 못한다.
"""

from __future__ import annotations

import io
import re
import zipfile
from pathlib import Path
from typing import Dict

from hwpx_studio.engine import build_document
from hwpx_studio.parser import parse_text
from hwpx_studio.profile import load_profile

_PROFILES = Path(__file__).resolve().parent.parent / "hwpx_studio" / "profiles"

SAMPLE = """# 사업 추진 현황
## 추진 개요
□ 추진 배경 및 목적
○ 제도 개선 요구가 이어져 개선 방안을 마련
- 기존 절차의 처리 기간이 길어 이용자 불편이 누적
· 현장 실사 대상은 무작위 층화 표본으로 뽑음
※ 실사 기간은 2025년 9월~11월

| 구분 | 2024년 | 2025년 |
|---|---|---|
| 처리 건수 | 1,204건 | 1,388건 |
| 평균 처리 기간 | 14일 | 11일 |

## 세부 내용
□ 처리 기간이 3일 줄었다
"""

#: (스타일 이름, paraPr id, 자동으로 붙일 기호)
_BULLET_LEVELS = [("네모", 22, "□"), ("원", 23, "○"), ("하이픈", 24, "-")]

_BULLET_BLOCK = (
    '<hh:bullets itemCnt="{n}">{items}</hh:bullets>'
)
_BULLET_ITEM = (
    '<hh:bullet id="{id}" char="{char}" useImage="0" checkable="0">'
    '<hh:paraHead start="1" level="1" align="LEFT" useInstWidth="1" autoIndent="1" '
    'widthAdjust="0" textOffsetType="PERCENT" textOffset="50" numFormat="DIGIT" '
    'charPrIDRef="4294967295" checkable="0"/></hh:bullet>'
)


def plain_form(text: str = SAMPLE) -> bytes:
    """기호가 본문 텍스트에 들어 있는 평범한 양식."""
    profile = load_profile(str(_PROFILES / "policy-default.json"))
    parsed = parse_text(text, profile)
    return build_document(profile, parsed.items).data


def auto_bullet_form(text: str = SAMPLE) -> bytes:
    """한글이 글머리표를 자동으로 붙이는 양식.

    `plain_form()`의 산출물을 고쳐 만든다. `hh:paraPr`에 `hh:heading type="BULLET"`을
    걸고, 본문 텍스트에서는 기호를 뺀다. 한글에서 열면 기호는 한글이 붙인다.
    """
    parts = _unzip(plain_form(text))
    parts["Contents/header.xml"] = _patch_header(
        parts["Contents/header.xml"].decode("utf-8")).encode("utf-8")
    parts["Contents/section0.xml"] = _strip_symbols(
        parts["Contents/section0.xml"].decode("utf-8")).encode("utf-8")
    return _zip(parts)


def without_symbols(data: bytes) -> bytes:
    """본문 텍스트에서 줄머리 기호·번호를 뺀 문서.

    'AI가 서식 없이 뽑아낸 한글 파일'에 가깝다. 되돌리기가 무엇을 근거로 계층을
    추정하는지 시험할 때 쓴다.
    """
    parts = _unzip(data)
    parts["Contents/section0.xml"] = _strip_symbols(
        parts["Contents/section0.xml"].decode("utf-8")).encode("utf-8")
    return _zip(parts)


def _patch_header(header: str) -> str:
    items = "".join(_BULLET_ITEM.format(id=i + 1, char=char)
                    for i, (_name, _pp, char) in enumerate(_BULLET_LEVELS))
    block = _BULLET_BLOCK.format(n=len(_BULLET_LEVELS), items=items)
    header = header.replace("</hh:refList>", block + "</hh:refList>", 1)

    for i, (_name, para_id, _char) in enumerate(_BULLET_LEVELS):
        header = _set_heading(header, para_id, f'type="BULLET" idRef="{i + 1}" level="0"')
    # 제목 두 레벨은 한글 번호매기기로
    header = _set_heading(header, 20, 'type="NUMBER" idRef="1" level="0"')
    header = _set_heading(header, 21, 'type="NUMBER" idRef="1" level="1"')
    return header


def _set_heading(header: str, para_id: int, attrs: str) -> str:
    pattern = re.compile(
        rf'(<hh:paraPr id="{para_id}"[ >].*?)<hh:heading\b[^>]*/>', re.S)
    replaced, n = pattern.subn(rf'\g<1><hh:heading {attrs}/>', header, count=1)
    if not n:
        raise AssertionError(f"paraPr {para_id}의 heading을 찾지 못했다")
    return replaced


_SYMBOLS = ("□ ", "○ ", "- ", "· ", "※ ")


def _strip_symbols(section: str) -> str:
    def drop(m: "re.Match[str]") -> str:
        text = m.group(1)
        for sym in _SYMBOLS:
            if text.startswith(sym):
                return f"<hp:t>{text[len(sym):]}</hp:t>"
        text = re.sub(r"^[ⅠⅡⅢⅣⅤ]\.\s+|^\d+\.\s+", "", text)
        return f"<hp:t>{text}</hp:t>"

    return re.sub(r"<hp:t>([^<]*)</hp:t>", drop, section)


def _unzip(data: bytes) -> Dict[str, bytes]:
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        return {name: z.read(name) for name in z.namelist()}


def _zip(parts: Dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        if "mimetype" in parts:
            z.writestr("mimetype", parts["mimetype"], compress_type=zipfile.ZIP_STORED)
        for name, data in parts.items():
            if name != "mimetype":
                z.writestr(name, data)
    return buf.getvalue()
