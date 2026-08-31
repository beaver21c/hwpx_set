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
from hwpx_studio.formkit import top_level_paragraphs
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


TABLE_NOTE_SAMPLE = """# 사업 추진 현황
## 추진 개요
□ 추진 배경 및 목적
○ 제도 개선 요구가 이어져 개선 방안을 마련

| 구분 | 2024년 | 2025년 |
|---|---|---|
| 처리 건수 | 1,204건 | 1,388건 |
※ 자료：○○청(2025), 「행정통계」.

□ 두 번째 표
○ 아래에도 자료 줄이 붙는다

| 구분 | 값 |
|---|---|
| 합계 | 100 |
※ 자료：○○부(2025).
"""


def table_note_form(text: str = TABLE_NOTE_SAMPLE) -> bytes:
    """표 바로 아래에 '자료：…' 줄이 붙는 양식.

    `참고` 스타일의 이름을 `표 주`로 바꿔, 이름으로도 자리로도 알아볼 수 있게 한다.
    """
    parts = _unzip(plain_form(text))
    header = parts["Contents/header.xml"].decode("utf-8")
    header = header.replace('name="참고" engName="L5"', 'name="표 주" engName="TableNote"')
    parts["Contents/header.xml"] = header.encode("utf-8")
    return _zip(parts)


#: 장 표지 흉내. 진짜 한글 표지는 그림 상자와 표로 되어 있지만, 여기서는 바꿔치기
#: 로직(로마자·'Ⅱ. 제목' 찾기)을 시험할 만큼만 둔다.
_CHAPTER_COVER = (
    '<hp:p id="0" paraPrIDRef="0" styleIDRef="0" pageBreak="0" columnBreak="0" '
    'merged="0"><hp:run charPrIDRef="0">'
    '<hp:container><hp:t>Ⅱ</hp:t>'
    '<hp:t>Ⅱ. 옛 장 제목</hp:t></hp:container></hp:run></hp:p>'
)

#: 표 캡션 흉내. `<표 Ⅱ-` + 자동 표번호 + `> 제목`
_CAPTION = (
    '<hp:caption side="TOP" fullSz="0" width="8504" gap="850" lastWidth="39456">'
    '<hp:subList id="" textDirection="HORIZONTAL" lineWrap="BREAK" vertAlign="TOP" '
    'linkListIDRef="0" linkListNextIDRef="0" textWidth="0" textHeight="0" '
    'hasTextRef="0" hasNumRef="0">'
    '<hp:p id="0" paraPrIDRef="27" styleIDRef="8" pageBreak="0" columnBreak="0" '
    'merged="0"><hp:run charPrIDRef="14"><hp:t>&lt;표 Ⅱ-</hp:t>'
    '<hp:ctrl><hp:autoNum num="1" numType="TABLE">'
    '<hp:autoNumFormat type="DIGIT" userChar="" prefixChar="" suffixChar="" '
    'supscript="0"/></hp:autoNum></hp:ctrl>'
    '<hp:t>&gt; 옛 표 제목</hp:t></hp:run></hp:p></hp:subList></hp:caption>'
)


#: 스타일 이름을 기관 서식처럼 바꾼다(빈 양식 시험용).
_STYLE_RENAMES = [
    ('name="제목1"', 'name="타이틀-장제목"'),
    ('name="제목2"', 'name="절"'),
    ('name="네모"', 'name="요약_네모"'),
    ('name="원"', 'name="요약_원"'),
    ('name="하이픈"', 'name="요약_하이픈"'),
]


def styles_only_form(text: str = SAMPLE) -> bytes:
    """스타일만 있고 **본문이 빈** 양식.

    기관이 나눠 주는 '빈 서식 파일'이 대개 이렇다 — `header.xml`에 스타일이 다
    들어 있고 본문은 비어 있다. 문단을 근거로 레벨을 찾으면 하나도 못 찾으므로,
    `formkit`이 스타일 이름으로 읽는 길을 시험한다.

    용지 설정(`hp:secPr`)을 진 문단 하나만 남긴다. 그 문단까지 본문으로 보고
    잘라 내면 용지가 통째로 날아가므로, 그 회귀도 여기서 잡는다.
    """
    parts = _unzip(auto_bullet_form(text))
    header = parts["Contents/header.xml"].decode("utf-8")
    for old, new in _STYLE_RENAMES:
        header = header.replace(old, new)
    parts["Contents/header.xml"] = header.encode("utf-8")

    section = parts["Contents/section0.xml"].decode("utf-8")
    keep = [section[a:b] for a, b, _tag in top_level_paragraphs(section)
            if "<hp:secPr" in section[a:b]]
    if not keep:
        raise AssertionError("용지 설정을 진 문단을 찾지 못했다")
    head = section[:section.index("<hp:p")]
    parts["Contents/section0.xml"] = (head + "".join(keep) + "</hs:sec>").encode("utf-8")
    return _zip(parts)


def chapter_form(text: str = SAMPLE) -> bytes:
    """장 표지와 표 번호(`<표 Ⅱ-n>`)가 있는 양식.

    올려 받은 `build_yangsik2.py`가 다루던 양식의 성질을 흉내 낸 것이다.
    **손으로 꾸민 표본**이라 한글에서 여는 것까지 보장하지 않는다. 여기서 시험하는
    것은 장 번호·표 번호를 바꿔 넣는 로직이다.
    """
    parts = _unzip(plain_form(text))
    section = parts["Contents/section0.xml"].decode("utf-8")
    # 표지는 본문 스타일이 아니라 보존 구간에 남는다(styleIDRef="0")
    first_body = re.search(r'<hp:p [^>]*styleIDRef="[1-7]"', section)
    cut = first_body.start() if first_body else len(section)
    section = section[:cut] + _CHAPTER_COVER + section[cut:]
    section = section.replace('<hp:inMargin ', _CAPTION + '<hp:inMargin ', 1)
    parts["Contents/section0.xml"] = section.encode("utf-8")
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
