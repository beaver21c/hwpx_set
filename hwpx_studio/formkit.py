"""양식 hwpx 해부 → `form.json`(양식 카드).

기존 `extractor.py`는 서식을 **프로파일로 옮겨 적어 새 문서를 처음부터 짓는다.**
그래서 한글의 자동 글머리표·번호매기기처럼 프로파일에 담기지 않는 것은 잃는다.

이 모듈은 반대로 간다. 양식 파일을 **템플릿으로 그대로 두고**, 그 안의 스타일
번호만 읽어 적는다. 문서를 만들 때는 `header.xml`을 1바이트도 바꾸지 않고
`section0.xml`의 본문 문단만 갈아 끼운다(`build_form.py`). 따라서 자동 글머리표,
번호매기기, 글꼴, 테두리, 쪽 설정이 원본 그대로 살아 있다.

해부 결과는 **추정**이다. `form.json`은 사람이 읽고 고치라고 있는 파일이고,
`report`는 무엇을 왜 그렇게 보았는지를 남긴다.
"""

from __future__ import annotations

import json
import re
import zipfile
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .extractor import (
    NS,
    _char_props,
    _et,
    _font_faces,
    _para_props,
    _read_parts,
    _styles,
    guess_prefix,
)
from .units import MM, PT

SCHEMA_ID = "hwpx-studio/form@1"

HEADER_PATH = "Contents/header.xml"

#: 자동 글머리표로 쓰이는 문자 → 입력 마커. 한글이 붙이는 기호를 그대로 마커로 쓴다.
BULLET_MARKERS = "□○-·･•▪◦∙※◇◆▶"

#: 제목 레벨에 매기는 마커(깊이 순). 마크다운 관례를 따른다.
HEADING_MARKERS = ["#", "##", "###", "####"]

#: 기호 근거가 없는 레벨에 임의로 줄 마커. 입력에서 부를 수단일 뿐 찍히지는 않는다.
FALLBACK_MARKERS = "□○-·※▪◇▶"

#: 줄머리 기호를 **누가** 붙이는가. 양식마다 다르므로 고를 수 있어야 한다.
#:
#:   auto   — 양식을 보고 정한다(한글이 붙이면 한글에, 텍스트에 적혀 있으면 도구에)
#:   hangul — 한글에 맡긴다. 도구는 본문에 기호를 적지 않는다
#:   text   — 도구가 본문 텍스트에 적어 넣는다
BULLET_SOURCES = ("auto", "hangul", "text")

#: 1행이면서 셀이 이 수 이하인 표는 데이터 표가 아니라 제목 상자로 본다
LAYOUT_TABLE_MAX_CELLS = 3

#: 본문 레벨을 셀 때 통째로 건너뛰는 가지. 각주 본문을 본문 레벨로 세면 안 된다.
_SKIP_SUBTREES = {"footNote", "endNote", "caption", "header", "footer"}


# ──────────────────────────────────────────────────────────────
# 결과 자료구조
# ──────────────────────────────────────────────────────────────
@dataclass
class LevelGuess:
    """양식에서 찾아낸 본문 한 레벨."""

    key: str
    marker: str
    name: str
    style: int
    para: int
    char: int
    auto_bullet: Optional[str] = None      # 한글이 자동으로 붙이는 기호
    auto_number: Optional[str] = None      # 한글이 자동으로 붙이는 번호 서식
    prefix: Optional[str] = None           # 본문 텍스트에 직접 적힌 번호 유형
    symbol_in_text: Optional[str] = None   # 본문 텍스트에 직접 적힌 기호
    invented: bool = False                 # 근거 없이 도구가 정해 준 마커인가
    write_override: Optional[bool] = None  # 기호를 누가 붙이는지 사람이 고른 값
    heading_level: Optional[int] = None
    size_pt: float = 12.0
    left_pt: float = 0.0
    count: int = 0
    samples: List[str] = field(default_factory=list)

    @property
    def write_marker(self) -> bool:
        """마커 기호를 본문 텍스트에 적어 넣어야 하는가.

        고른 값(`write_override`)이 있으면 그것을 따른다. 없으면 양식을 보고 정한다 —
        양식이 원래 기호를 텍스트에 적어 두었을 때만 도구가 적는다. 한글이 자동으로
        붙이는 양식에 또 적으면 이중이 되고, 애초에 기호가 없던 레벨에 적으면 없던
        기호가 생긴다.
        """
        if self.write_override is not None:
            return self.write_override
        return self.symbol_in_text is not None

    @property
    def numbering(self) -> Optional[str]:
        """도구가 매겨서 텍스트에 넣을 번호 유형. 한글이 매기면 None."""
        if self.auto_number:
            return None
        return self.prefix if (self.prefix or "").startswith("AUTO_") else None

    def as_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "marker": self.marker,
            "name": self.name,
            "style": self.style,
            "para": self.para,
            "char": self.char,
            "write_marker": self.write_marker,
            "numbering": self.numbering,
            "marker_invented": self.invented,
            "auto_bullet": self.auto_bullet,
            "auto_number": self.auto_number,
            "size_pt": self.size_pt,
            "left_pt": self.left_pt,
            "seen": self.count,
            "samples": self.samples[:2],
        }


@dataclass
class FormResult:
    form: Dict[str, Any]
    report: str
    notes: List[str] = field(default_factory=list)


# ──────────────────────────────────────────────────────────────
# header.xml에서 자동 글머리표·번호 읽기
# ──────────────────────────────────────────────────────────────
def _bullet_chars(head) -> Dict[int, str]:
    """글머리표 id → 기호 문자."""
    out: Dict[int, str] = {}
    for bullet in head.iter(f"{{{NS['hh']}}}bullet"):
        char = bullet.get("char") or ""
        if char:
            out[int(bullet.get("id", "0"))] = char
    return out


def _numbering_formats(head) -> Dict[int, Dict[int, str]]:
    """번호매기기 id → {수준: 서식 문자열}. 서식은 '^1.' 같은 한글 표기 그대로."""
    out: Dict[int, Dict[int, str]] = {}
    for numbering in head.iter(f"{{{NS['hh']}}}numbering"):
        nid = int(numbering.get("id", "0"))
        levels: Dict[int, str] = {}
        for head_node in numbering.iter(f"{{{NS['hh']}}}paraHead"):
            level = int(head_node.get("level", "1"))
            text = (head_node.text or "").strip()
            if text:
                levels[level] = text
        if levels:
            out[nid] = levels
    return out


def _headings(head) -> Dict[int, Dict[str, Any]]:
    """paraPr id → 문단 머리(자동 글머리표·번호) 설정."""
    out: Dict[int, Dict[str, Any]] = {}
    for pp in head.iter(f"{{{NS['hh']}}}paraPr"):
        node = pp.find(f"{{{NS['hh']}}}heading")
        if node is None:
            continue
        out[int(pp.get("id", "0"))] = {
            "type": node.get("type", "NONE"),
            "id_ref": int(node.get("idRef", "0")),
            "level": int(node.get("level", "0")),
        }
    return out


# ──────────────────────────────────────────────────────────────
# section0.xml 읽기
# ──────────────────────────────────────────────────────────────
def top_level_paragraphs(section_xml: str) -> List[Tuple[int, int, str]]:
    """(시작, 끝, 여는 태그) 목록. 표 안에 중첩된 `hp:p`는 세지 않는다."""
    depth = 0
    tops: List[List[Any]] = []
    for m in re.finditer(r"<hp:p[ >][^>]*>|<hp:p/>|</hp:p>", section_xml):
        token = m.group(0)
        if token.startswith("</"):
            depth -= 1
            if depth == 0 and tops:
                tops[-1][1] = m.end()
        elif token.endswith("/>") and token.startswith("<hp:p/"):
            if depth == 0:
                tops.append([m.start(), m.end(), token])
        else:
            if depth == 0:
                tops.append([m.start(), None, token])
            depth += 1
    return [(s, e, t) for s, e, t in tops if e is not None]


@dataclass
class ParaRecord:
    style: int
    para: int
    char: int
    text: str
    in_table: bool
    index: int
    after_table: bool = False      # 바로 앞 형제가 표였나(표 주를 가려내는 근거)


def _paragraph_records(section_xml: str) -> List[ParaRecord]:
    root = _et(section_xml)
    records: List[ParaRecord] = []
    counter = [0]

    def record(p, in_table: bool) -> None:
        char_id = None
        texts: List[str] = []
        for run in p.findall(f"{{{NS['hp']}}}run"):
            if char_id is None and run.get("charPrIDRef") is not None:
                char_id = int(run.get("charPrIDRef"))
            for t in run.iter(f"{{{NS['hp']}}}t"):
                texts.append("".join(t.itertext()))
        counter[0] += 1
        records.append(ParaRecord(
            style=int(p.get("styleIDRef", "0")),
            para=int(p.get("paraPrIDRef", "0")),
            char=char_id if char_id is not None else 0,
            text="".join(texts).strip()[:80],
            in_table=in_table,
            index=counter[0],
        ))

    def walk(node, in_table: bool) -> None:
        just_after_table = False       # 형제 순서에서 바로 앞이 표였나
        for child in node:
            tag = child.tag.split("}")[-1]
            if tag in _SKIP_SUBTREES:
                # 각주·미주 본문, 표 캡션, 머리말·꼬리말은 본문 레벨이 아니다
                continue
            if tag == "p":
                has_table = child.find(f".//{{{NS['hp']}}}tbl") is not None
                # 그리기 개체(container) 안 글자는 본문이 아니라 도형의 글자다.
                # 장 표지가 그렇게 만들어져 있어, 세면 보존 구간이 잘려 나간다.
                has_obj = (has_table
                           or child.find(f".//{{{NS['hp']}}}pic") is not None
                           or child.find(f".//{{{NS['hp']}}}container") is not None)
                if not has_obj:
                    record(child, in_table)
                    if records and records[-1].text:
                        # 빈 문단은 표와 주 사이의 간격일 뿐이라 표시를 먹지 않는다
                        records[-1].after_table = just_after_table
                        just_after_table = False
                elif has_table:
                    just_after_table = True
                walk(child, in_table)
            elif tag == "tbl":
                rows = child.findall(f"{{{NS['hp']}}}tr")
                cells = len(child.findall(f".//{{{NS['hp']}}}tc"))
                is_data = len(rows) > 1 or cells > LAYOUT_TABLE_MAX_CELLS
                for tr in rows:
                    walk(tr, is_data)
            else:
                walk(child, in_table)

    walk(root, False)
    return records


# ──────────────────────────────────────────────────────────────
# 쪽 설정·각주 모양·장 표지
# ──────────────────────────────────────────────────────────────
#: 흔한 용지. (이름, 너비 mm, 높이 mm)
_PAPERS = [("A4", 210, 297), ("B5", 182, 257), ("A5", 148, 210),
           ("A3", 297, 420), ("B4", 257, 364), ("Letter", 216, 279)]


def _paper_name(width_mm: float, height_mm: float) -> str:
    """가로·세로를 흔한 용지 이름으로. 못 맞추면 치수를 그대로 적는다."""
    for name, w, h in _PAPERS:
        if (abs(width_mm - w) <= 2 and abs(height_mm - h) <= 2) or \
           (abs(width_mm - h) <= 2 and abs(height_mm - w) <= 2):
            return name
    return f"{width_mm:g}×{height_mm:g}mm"


def _page_setup(section_xml: str) -> Dict[str, Any]:
    """용지·여백·머리말. 이 값들은 보존 구간에 들어 있어 그대로 지켜진다."""
    page = re.search(r"<hp:pagePr\b([^>]*)>", section_xml)
    margin = re.search(r"<hp:margin\b([^>]*)/>", section_xml)
    width = int(_attr(page.group(), "hp:pagePr", "width", "59528")) if page else 59528
    height = int(_attr(page.group(), "hp:pagePr", "height", "84186")) if page else 84186

    def side(name: str) -> float:
        if not margin:
            return 0.0
        m = re.search(rf'{name}="(-?\d+)"', margin.group(1))
        return round(int(m.group(1)) / MM, 1) if m else 0.0

    return {
        "size": _paper_name(round(width / MM, 1), round(height / MM, 1)),
        "width": width,
        "height": height,
        "orientation": "가로" if width > height else "세로",
        "margin_mm": {name: side(name) for name in
                      ("left", "right", "top", "bottom", "header", "footer")},
        "has_header": "<hp:header" in section_xml,
        "has_footer": "<hp:footer" in section_xml,
        "has_page_number": "<hp:pageNum" in section_xml,
    }


def _footnote_shape(section_xml: str) -> Optional[Dict[str, Any]]:
    """각주 번호 모양과 구분선. 구역 설정(`footNotePr`)에 들어 있다."""
    block = re.search(r"<hp:footNotePr\b.*?</hp:footNotePr>", section_xml, re.S)
    if not block:
        return None
    body = block.group()
    fmt = re.search(r"<hp:autoNumFormat\b([^>]*)/>", body)
    line = re.search(r"<hp:noteLine\b([^>]*)/>", body)
    numbering = re.search(r"<hp:numbering\b([^>]*)/>", body)
    place = re.search(r"<hp:placement\b([^>]*)/>", body)
    return {
        "number_format": attrof(fmt, "type", "DIGIT"),
        "prefix_char": attrof(fmt, "prefixChar", ""),
        "suffix_char": attrof(fmt, "suffixChar", ""),
        "superscript": attrof(fmt, "supscript", "0") in ("1", "true"),
        "line_type": attrof(line, "type", "SOLID"),
        "line_length": attrof(line, "length", "-1"),
        "line_color": attrof(line, "color", "#000000"),
        "restart": attrof(numbering, "type", "CONTINUOUS"),
        "place": attrof(place, "place", ""),
    }


def attrof(match: "Optional[re.Match[str]]", name: str, fallback: str = "") -> str:
    if not match:
        return fallback
    found = re.search(rf'{name}="([^"]*)"', match.group(1))
    return found.group(1) if found else fallback


#: 장 번호로 쓰는 로마자
ROMAN_CHARS = "ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩⅪⅫ"


def _chapter_cover(preamble: str) -> Optional[Dict[str, Any]]:
    """장 표지(보존 구간 안). 로마자와 'Ⅱ. 제목' 꼴 제목을 찾는다."""
    alone = re.search(rf"<hp:t>([{ROMAN_CHARS}])</hp:t>", preamble)
    titled = re.search(rf"<hp:t>([{ROMAN_CHARS}])\.\s*([^<]*)</hp:t>", preamble)
    if not alone and not titled:
        return None
    return {
        "roman": (alone or titled).group(1),
        "title": titled.group(2).strip() if titled else None,
        "has_container": "<hp:container" in preamble,
        "title_in_text": bool(titled),
    }


# ──────────────────────────────────────────────────────────────
# 표 골격 읽기
# ──────────────────────────────────────────────────────────────
def _first_data_table(section_xml: str) -> Optional[str]:
    """본문에서 첫 데이터 표의 XML 조각. 없으면 None."""
    depth = 0
    start = None
    for m in re.finditer(r"<hp:tbl[ >]|</hp:tbl>", section_xml):
        if m.group(0).startswith("</"):
            depth -= 1
            if depth == 0 and start is not None:
                chunk = section_xml[start:m.end()]
                rows = chunk.count("<hp:tr>")
                if rows > 1:
                    return chunk
                start = None
        else:
            if depth == 0:
                start = m.start()
            depth += 1
    return None


def _attr(xml: str, tag: str, name: str, default: str = "") -> str:
    m = re.search(rf"<{re.escape(tag)}\b[^>]*\b{re.escape(name)}=\"([^\"]*)\"", xml)
    return m.group(1) if m else default


def _table_skeleton(section_xml: str, notes: List[str]) -> Dict[str, Any]:
    """양식이 쓰는 표 골격. 없으면 한글 기본값에 가까운 값으로 채운다."""
    chunk = _first_data_table(section_xml)
    if chunk is None:
        notes.append("본문에서 데이터 표를 찾지 못해 표 골격은 기본값으로 채웠다 "
                     "→ 표를 쓸 양식이면 form.json의 table을 손으로 맞출 것")
        return {
            "border_fill": 1, "header_fill": 1, "body_fill": 1,
            "width": 39456, "row_min_height": 1182,
            "cell_margin": {"left": 494, "right": 494, "top": 0, "bottom": 0},
            "in_margin": {"left": 141, "right": 141, "top": 141, "bottom": 141},
            "cell_para": {"style": 0, "para": 0, "char": 0},
            "caption": None,
            "guessed": True,
        }

    rows = re.findall(r"<hp:tr>.*?</hp:tr>", chunk, re.S)
    first_cells = re.findall(r"<hp:tc\b[^>]*borderFillIDRef=\"(\d+)\"", rows[0]) if rows else []
    rest_cells: List[str] = []
    for row in rows[1:]:
        rest_cells += re.findall(r"<hp:tc\b[^>]*borderFillIDRef=\"(\d+)\"", row)

    def common(values: Sequence[str], fallback: int) -> int:
        if not values:
            return fallback
        return int(max(set(values), key=list(values).count))

    body_fill = common(rest_cells, common(first_cells, 1))
    header_fill = common(first_cells, body_fill)
    if header_fill == body_fill and len(rows) > 1:
        notes.append("표 머리행과 본문행의 테두리·배경이 같다 → 머리행 강조가 없는 양식으로 본다")

    cell_para = {"style": 0, "para": 0, "char": 0}
    inner = re.search(r"<hp:tc\b.*?</hp:tc>", chunk, re.S)
    if inner:
        p = re.search(r"<hp:p\b[^>]*>", inner.group())
        if p:
            cell_para = {
                "style": int(_attr(p.group(), "hp:p", "styleIDRef", "0")),
                "para": int(_attr(p.group(), "hp:p", "paraPrIDRef", "0")),
                "char": int(re.search(r'charPrIDRef="(\d+)"', inner.group()).group(1))
                if re.search(r'charPrIDRef="(\d+)"', inner.group()) else 0,
            }

    margin = re.search(r"<hp:cellMargin\b[^>]*>", chunk)
    in_margin = re.search(r"<hp:inMargin\b[^>]*>", chunk)

    def sides(node: Optional[re.Match], default: Dict[str, int]) -> Dict[str, int]:
        if node is None:
            return dict(default)
        text = node.group()
        out = {}
        for side, fallback in default.items():
            m = re.search(rf'{side}="(-?\d+)"', text)
            out[side] = int(m.group(1)) if m else fallback
        return out

    size = re.search(r"<hp:sz\b[^>]*>", chunk)
    width = int(_attr(size.group(), "hp:sz", "width", "39456")) if size else 39456
    cell_sz = re.search(r"<hp:cellSz\b[^>]*>", chunk)
    row_h = int(_attr(cell_sz.group(), "hp:cellSz", "height", "1182")) if cell_sz else 1182

    return {
        "border_fill": int(_attr(chunk, "hp:tbl", "borderFillIDRef", "1")),
        "header_fill": header_fill,
        "body_fill": body_fill,
        "width": width,
        "row_min_height": row_h,
        "cell_margin": sides(margin, {"left": 494, "right": 494, "top": 0, "bottom": 0}),
        "in_margin": sides(in_margin, {"left": 141, "right": 141, "top": 141, "bottom": 141}),
        "cell_para": cell_para,
        "caption": _caption_shape(chunk),
        "guessed": False,
    }


def _caption_shape(table_xml: str) -> Optional[Dict[str, Any]]:
    """표 캡션(제목) 문단의 스타일과 자동 번호 여부."""
    m = re.search(r"<hp:caption\b.*?</hp:caption>", table_xml, re.S)
    if not m:
        return None
    cap = m.group()
    p = re.search(r"<hp:p\b[^>]*>", cap)
    char = re.search(r'charPrIDRef="(\d+)"', cap)
    texts = re.findall(r"<hp:t>([^<]*)</hp:t>", cap)
    auto = re.search(r'<hp:autoNum\b[^>]*numType="(\w+)"', cap)
    fmt = re.search(r"<hp:autoNumFormat\b[^>]*>", cap)
    before = _unescape(texts[0]) if texts else ""
    roman = re.search(rf"[{ROMAN_CHARS}]", before)
    return {
        "side": _attr(cap, "hp:caption", "side", "TOP"),
        "chapter_roman": roman.group() if roman else None,
        "width": int(_attr(cap, "hp:caption", "width", "8504")),
        "gap": int(_attr(cap, "hp:caption", "gap", "850")),
        "style": int(_attr(p.group(), "hp:p", "styleIDRef", "0")) if p else 0,
        "para": int(_attr(p.group(), "hp:p", "paraPrIDRef", "0")) if p else 0,
        "char": int(char.group(1)) if char else 0,
        "auto_num": auto.group(1) if auto else None,
        "auto_num_format": fmt.group() if fmt else None,
        # 양식에 들어 있던 표본 제목("> 옛 제목")은 버리고 구분 기호만 남긴다.
        # 그러지 않으면 새 제목이 옛 제목 뒤에 붙는다.
        "before": before if auto else "",
        "after": _caption_tail(texts[1]) if (auto and len(texts) > 1) else "",
        "sample": _unescape(texts[-1]).strip() if texts else "",
    }


def _caption_tail(text: str) -> str:
    """`> 옛 표 제목` → `> `. 번호 뒤에 오는 구분 기호만 남긴다."""
    head = re.match(r"^([^\w가-힣]*\s*)", _unescape(text))
    return head.group(1) if head else ""


def _unescape(text: str) -> str:
    return (text.replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"')
            .replace("&apos;", "'").replace("&amp;", "&"))


# ──────────────────────────────────────────────────────────────
# 표 주(표 바로 아래 자료 줄)
# ──────────────────────────────────────────────────────────────
#: 표 주 스타일에 흔히 붙는 이름
_TABLE_NOTE_NAMES = ("표 주", "표주", "자료", "출처", "주석", "표 자료")


def _pick_table_note(levels: List[LevelGuess], records: Sequence[ParaRecord],
                     notes: List[str]) -> Optional[LevelGuess]:
    """표 바로 아래에 붙는 '자료：…' 줄의 레벨을 골라 낸다.

    이름(`표 주`·`자료`)이 맞거나, 실제로 표 뒤에 자주 나오면 그렇게 본다.
    골라낸 레벨은 본문 레벨에서 **빼낸다.** 그래야 `※` 마커가 겹치지 않는다.
    """
    after = {}
    total = {}
    for rec in records:
        if rec.in_table or not rec.text:
            continue
        key = (rec.style, rec.para, rec.char)
        total[key] = total.get(key, 0) + 1
        if rec.after_table:
            after[key] = after.get(key, 0) + 1

    best: Optional[LevelGuess] = None
    reason = ""
    for level in levels:
        # 제목은 표 주가 아니다(prefix에는 기호도 담기므로 번호 유형만 본다)
        if (level.marker in HEADING_MARKERS or level.auto_number
                or (level.prefix or "").startswith("AUTO_")):
            continue
        key = (level.style, level.para, level.char)
        seen = total.get(key, 0)
        hits = after.get(key, 0)
        by_name = any(name in level.name for name in _TABLE_NOTE_NAMES)
        # 자리만으로 볼 때는 확실할 때만 — 나온 것이 **전부** 표 바로 뒤여야 한다
        by_place = seen >= 2 and hits == seen
        if not by_name and not by_place:
            continue
        if best is None or hits > after.get((best.style, best.para, best.char), 0):
            best = level
            reason = ("스타일 이름" if by_name else f"표 바로 뒤에 {hits}/{seen}번 나옴")

    if best is None:
        return None
    levels.remove(best)
    notes.append(f"'{best.name}' 레벨을 **표 주**로 본다({reason}). "
                 f"`{best.marker or '※'} 자료：…`처럼 표 바로 아래에 쓴다")
    return best


# ──────────────────────────────────────────────────────────────
# 프리앰블(보존 구간) 경계
# ──────────────────────────────────────────────────────────────
def preamble_cut(section_xml: str, body_styles: Sequence[int]) -> int:
    """본문 스타일이 처음 나오는 최상위 문단의 시작 위치.

    그 앞(용지 설정 `secPr`, 표지, 장 제목 상자)은 그대로 두고 뒤만 갈아 끼운다.
    """
    wanted = {str(s) for s in body_styles}
    for start, _end, tag in top_level_paragraphs(section_xml):
        m = re.search(r'styleIDRef="(\d+)"', tag)
        if m and m.group(1) in wanted:
            return start
    end = section_xml.rfind("</hs:sec>")
    return end if end >= 0 else len(section_xml)


# ──────────────────────────────────────────────────────────────
# 레벨 추정
# ──────────────────────────────────────────────────────────────
_KEY_BY_MARKER = {
    "□": "box", "○": "circle", "-": "hyphen", "·": "dot", "･": "dot",
    "•": "dot", "▪": "dot", "◦": "dot", "∙": "dot", "※": "note",
    "◇": "diamond", "◆": "diamond", "▶": "arrow",
}


def _level_key(marker: str, index: int, used: Sequence[str]) -> str:
    base = _KEY_BY_MARKER.get(marker)
    if base is None:
        base = f"h{len(marker)}" if set(marker) == {"#"} else f"level{index}"
    key, n = base, 2
    while key in used:
        key, n = f"{base}{n}", n + 1
    return key


def _guess_levels(records: Sequence[ParaRecord], styles, para_props, char_props,
                  headings, bullets, numberings, notes: List[str]) -> List[LevelGuess]:
    """(스타일, 문단모양, 글자모양) 묶음마다 한 레벨로 본다."""
    groups: Dict[Tuple[int, int, int], List[ParaRecord]] = {}
    for rec in records:
        if rec.in_table or not rec.text:
            continue
        groups.setdefault((rec.style, rec.para, rec.char), []).append(rec)

    guesses: List[LevelGuess] = []
    for (style_id, para_id, char_id), items in groups.items():
        style = styles.get(style_id, {})
        pp = para_props.get(para_id, {})
        cp = char_props.get(char_id, {})
        heading = headings.get(para_id, {})

        auto_bullet = None
        auto_number = None
        heading_level = None
        if heading.get("type") == "BULLET":
            auto_bullet = bullets.get(heading["id_ref"])
            heading_level = heading.get("level")
        elif heading.get("type") == "NUMBER":
            levels = numberings.get(heading["id_ref"], {})
            heading_level = heading.get("level")
            auto_number = levels.get((heading_level or 0) + 1) or levels.get(1)

        leads = [r.text[:1] for r in items
                 if r.text[:1] in BULLET_MARKERS and r.text[1:2] in (" ", "\u3000")]
        symbol_in_text = (max(set(leads), key=leads.count)
                          if len(leads) >= max(1, len(items) // 2) else None)

        prefixes = [guess_prefix(r.text) for r in items]
        prefix = None
        named = [p for p in prefixes if p]
        if named and len(named) >= max(1, len(items) // 2):
            prefix = max(set(named), key=named.count)

        guesses.append(LevelGuess(
            key="", marker="", name=style.get("name", "") or f"스타일{style_id}",
            style=style_id, para=para_id, char=char_id,
            auto_bullet=auto_bullet, auto_number=auto_number, prefix=prefix,
            symbol_in_text=symbol_in_text,
            heading_level=heading_level,
            size_pt=cp.get("size_pt", 12.0), left_pt=pp.get("left_pt", 0.0),
            count=len(items), samples=[r.text for r in items[:3]],
        ))

    # 깊이 순: 들여쓰기 → 글자 크기 큰 것부터
    guesses.sort(key=lambda g: (g.left_pt, -g.size_pt))
    _assign_markers(guesses, notes)
    return guesses


def _assign_markers(guesses: List[LevelGuess], notes: List[str]) -> None:
    """레벨마다 입력 마커를 정한다. 한글이 붙이는 기호가 있으면 그 기호를 쓴다."""
    used_keys: List[str] = []
    used_markers: set = set()
    heading_seq = 0
    for i, g in enumerate(guesses):
        marker = ""
        if g.auto_bullet and g.auto_bullet[0] in BULLET_MARKERS:
            marker = g.auto_bullet[0]
        elif g.auto_number or (g.prefix or "").startswith("AUTO_"):
            marker = HEADING_MARKERS[min(heading_seq, len(HEADING_MARKERS) - 1)]
            heading_seq += 1
        elif g.samples:
            lead = g.samples[0][:1]
            if lead in BULLET_MARKERS and g.samples[0][1:2] in (" ", " "):
                marker = lead
        if marker and marker in used_markers:
            notes.append(f"마커 {marker!r}가 두 레벨에 겹친다"
                         f"(스타일 {g.style}·{g.name}) → form.json에서 하나를 바꿀 것")
            marker = ""
        if not marker:
            # 근거가 없는 레벨. 그래도 입력에서 부를 수단은 있어야 한다.
            marker = next((c for c in FALLBACK_MARKERS if c not in used_markers), "")
            if marker:
                g.invented = True
                notes.append(f"'{g.name}' 레벨에는 기호·번호 근거가 없어 마커를 "
                             f"`{marker}`로 임의로 정했다. 이 마커로 부르면 그 스타일이 "
                             "붙고 기호는 찍히지 않는다 → form.json에서 바꿔도 된다")
        if marker:
            used_markers.add(marker)
        g.marker = marker
        g.key = _level_key(marker or g.name, i, used_keys)
        used_keys.append(g.key)


# ──────────────────────────────────────────────────────────────
# 조립
# ──────────────────────────────────────────────────────────────
def _pick(styles: Dict[int, Dict[str, Any]], *names: str) -> Optional[int]:
    """스타일 이름으로 찾기(한글은 각주 같은 특수 스타일을 이름으로 찾는다)."""
    for sid, st in styles.items():
        label = (st.get("name") or "").strip()
        eng = (st.get("eng_name") or "").strip()
        if label in names or eng in names:
            return sid
    return None


def apply_bullet_source(levels: Sequence[LevelGuess], source: str,
                        notes: List[str]) -> None:
    """줄머리 기호를 누가 붙일지 정한다.

    고른 값이 양식과 어긋나면 **말한다.** 조용히 넘기면 기호가 두 번 찍히거나
    아예 사라진 문서가 나온다.
    """
    if source not in BULLET_SOURCES:
        raise ValueError(f"글머리표 담당은 {'·'.join(BULLET_SOURCES)} 중 하나여야 한다: "
                         f"{source!r}")
    if source == "auto":
        return

    for level in levels:
        if level.marker in HEADING_MARKERS or not level.marker:
            continue                                    # 제목·마커 없는 레벨은 그대로
        if source == "hangul":
            level.write_override = False
            if not level.auto_bullet:
                notes.append(
                    f"'{level.name}' 레벨을 한글에 맡겼지만 이 양식에는 자동 글머리표가 "
                    f"걸려 있지 않다 → `{level.marker}` 기호가 아무 데서도 찍히지 않는다. "
                    "한글에서 이 스타일에 글머리표를 걸거나 '도구가 붙임'으로 바꿀 것")
        else:                                           # text
            level.write_override = True
            if level.auto_bullet:
                notes.append(
                    f"'{level.name}' 레벨은 한글이 `{level.auto_bullet}`를 자동으로 붙이는데 "
                    "도구까지 적도록 골랐다 → 기호가 두 번 찍힌다. "
                    "한글에서 이 스타일의 글머리표를 끄거나 '한글에 맡김'으로 바꿀 것")


def analyze(source: Any, name: str = "", bullets: str = "auto") -> FormResult:
    """양식 hwpx를 읽어 `form.json`에 담을 dict와 근거 보고서를 만든다.

    `bullets`로 줄머리 기호를 누가 붙일지 고른다(`auto`·`hangul`·`text`).
    """
    parts = _read_parts(source)
    if HEADER_PATH not in parts:
        raise ValueError("hwpx 안에 Contents/header.xml이 없다 — 한글 문서가 맞는지 확인할 것")
    section_names = sorted(n for n in parts if re.match(r"Contents/section\d+\.xml$", n))
    if not section_names:
        raise ValueError("hwpx 안에 본문(section0.xml)이 없다")
    if len(section_names) > 1:
        pass  # 아래 notes에서 알린다

    header_xml = parts[HEADER_PATH]
    section_xml = parts[section_names[0]]
    head = _et(header_xml)

    notes: List[str] = []
    if len(section_names) > 1:
        notes.append(f"구역이 {len(section_names)}개다 → 첫 구역({section_names[0]})만 본문으로 쓴다. "
                     "나머지 구역은 템플릿에 그대로 남는다")

    styles = _styles(head)
    para_props = _para_props(head)
    char_props = _char_props(head)
    faces = _font_faces(head)
    headings = _headings(head)
    bullet_chars = _bullet_chars(head)
    numberings = _numbering_formats(head)

    records = _paragraph_records(section_xml)
    levels = _guess_levels(records, styles, para_props, char_props,
                           headings, bullet_chars, numberings, notes)

    if not levels:
        notes.append("본문 문단을 하나도 찾지 못했다 → 내용이 든 양식 파일인지 확인할 것")
    table_note = _pick_table_note(levels, records, notes)
    apply_bullet_source(levels, bullets, notes)

    body_styles = [g.style for g in levels]
    if table_note is not None:
        body_styles.append(table_note.style)
    cut = preamble_cut(section_xml, body_styles)
    table = _table_skeleton(section_xml, notes)

    footnote_style = _pick(styles, "각주", "Footnote")
    if footnote_style is None:
        notes.append("각주 스타일(이름 '각주')이 없다 → 각주를 쓰면 한글에서 서식이 흐트러질 수 있다")

    blank_style = 0
    blank_para = styles.get(0, {}).get("para_pr", 0)
    blank_char = styles.get(0, {}).get("char_pr", 0)
    wrap = _table_wrap_shape(section_xml) or {
        "style": blank_style, "para": blank_para, "char": blank_char}

    page = _page_setup(section_xml)
    note_shape = _footnote_shape(section_xml)
    chapter = _chapter_cover(section_xml[:cut])
    if chapter and not chapter["title_in_text"]:
        notes.append("장 표지에 로마자는 있으나 'Ⅱ. 제목' 꼴 제목을 찾지 못했다 "
                     "→ [장: 제목]으로는 번호만 바뀐다")

    form = {
        "schema": SCHEMA_ID,
        "name": name or _default_name(source),
        "template": "template.hwpx",
        "bullet_source": bullets,
        "section": section_names[0],
        "header": HEADER_PATH,
        "preamble_bytes": cut,
        "levels": [g.as_dict() for g in levels],
        "blank": {"style": blank_style, "para": blank_para, "char": blank_char},
        "table_wrap": wrap,
        "table": table,
        "page": page,
        "chapter": chapter,
        "table_note": (None if table_note is None else {
            "key": table_note.key,
            "marker": table_note.marker or "※",
            "name": table_note.name,
            "style": table_note.style,
            "para": table_note.para,
            "char": table_note.char,
            "write_marker": table_note.write_marker,
        }),
        "footnote": ({"style": footnote_style,
                      "para": styles[footnote_style]["para_pr"],
                      "char": styles[footnote_style]["char_pr"],
                      "size_pt": char_props.get(
                          styles[footnote_style]["char_pr"], {}).get("size_pt"),
                      "color": char_props.get(
                          styles[footnote_style]["char_pr"], {}).get("color"),
                      "shape": note_shape}
                     if footnote_style is not None else None),
        "fonts": sorted({faces.get(cp.get("font_id", 0), "") for cp in char_props.values()} - {""}),
        "notes": notes,
    }
    return FormResult(form=form, report=render_report(form, levels), notes=notes)


def _table_wrap_shape(section_xml: str) -> Optional[Dict[str, int]]:
    """표를 담고 있는 바깥 문단의 스타일(표 정렬이 여기에 걸려 있다)."""
    m = re.search(r'<hp:p\b[^>]*>(?=(?:(?!</hp:p>).)*?<hp:tbl\b)', section_xml, re.S)
    if not m:
        return None
    tag = m.group()
    char = re.search(r'charPrIDRef="(\d+)"', section_xml[m.end():m.end() + 200])
    return {
        "style": int(_attr(tag, "hp:p", "styleIDRef", "0")),
        "para": int(_attr(tag, "hp:p", "paraPrIDRef", "0")),
        "char": int(char.group(1)) if char else 0,
    }


def _default_name(source: Any) -> str:
    if isinstance(source, (str, Path)):
        return Path(str(source)).stem
    return "양식"


def pt(value: float) -> str:
    """11.0 대신 11로 적는다. 브라우저 쪽 표기와 같아야 한다."""
    return f"{float(value):g}"


def render_report(form: Dict[str, Any], levels: Sequence[LevelGuess]) -> str:
    """무엇을 왜 그렇게 보았는지. 사람이 확인하라고 남긴다."""
    out = [f"# 양식 해부 결과 — {form['name']}", "",
           "이 결과는 **추정**이다. 마커와 레벨이 뜻대로 잡혔는지 보고, ",
           "다르면 `form.json`을 고친 뒤 다시 빌드하면 된다.", "",
           "## 찾아낸 레벨", "",
           "| 마커 | 레벨 | 스타일 | 크기 | 들여쓰기 | 기호·번호를 붙이는 쪽 | 나온 횟수 | 예시 |",
           "|---|---|---|---|---|---|---|---|"]
    for g in levels:
        if g.auto_bullet:
            who = f"한글이 자동으로 `{g.auto_bullet}`"
        elif g.auto_number:
            who = f"한글이 자동으로 번호(`{g.auto_number}`)"
        elif g.numbering:
            who = f"도구가 번호({g.numbering})"
        elif g.write_marker:
            who = f"도구가 `{g.marker}`"
        else:
            who = "없음"
        sample = (g.samples[0][:24] + "…") if g.samples and len(g.samples[0]) > 24 else (
            g.samples[0] if g.samples else "")
        out.append(f"| `{g.marker or '(없음)'}` | {g.key} | {g.name}({g.style}) | "
                   f"{pt(g.size_pt)}pt | {pt(g.left_pt)}pt | {who} | {g.count} | {sample} |")

    table = form["table"]
    out += ["", "## 표 골격", "",
            f"- 표 테두리 채움 `{table['border_fill']}`, "
            f"머리행 `{table['header_fill']}`, 본문행 `{table['body_fill']}`",
            f"- 표 폭 {table['width']} HWPUNIT, 행 최소 높이 {table['row_min_height']}",
            f"- 셀 안 문단: 스타일 {table['cell_para']['style']} / "
            f"문단모양 {table['cell_para']['para']} / 글자모양 {table['cell_para']['char']}"]
    if table.get("guessed"):
        out.append("- **표를 찾지 못해 기본값이다.** 표를 쓸 양식이면 손으로 맞출 것")
    caption = table.get("caption")
    out.append(f"- 캡션: {'있음 (' + (caption.get('before') or '') + '…)' if caption else '없음'}")

    page = form.get("page") or {}
    margin = page.get("margin_mm") or {}
    out += ["", "## 쪽 설정 (그대로 지켜진다)", "",
            f"- 용지 {page.get('size', '?')} {page.get('orientation', '')}",
            f"- 여백(mm): 위 {margin.get('top', 0)} · 아래 {margin.get('bottom', 0)} · "
            f"왼 {margin.get('left', 0)} · 오른 {margin.get('right', 0)} · "
            f"머리말 {margin.get('header', 0)} · 꼬리말 {margin.get('footer', 0)}"]
    marks = [name for name, flag in (("머리말", page.get("has_header")),
                                     ("꼬리말", page.get("has_footer")),
                                     ("쪽 번호", page.get("has_page_number"))) if flag]
    out.append(f"- {', '.join(marks)}이(가) 있다" if marks
               else "- 머리말·꼬리말·쪽 번호는 없다")

    note = form.get("table_note")
    chapter = form.get("chapter")
    if note or chapter:
        out += ["", "## 그 밖의 자리", ""]
        if note:
            out.append(f"- **표 주**: `{note['marker']} 자료：…`를 표 바로 아래에 쓰면 "
                       f"'{note['name']}' 스타일이 붙는다")
        if chapter:
            title = chapter.get("title")
            out.append(f"- **장 표지**: 지금 `{chapter.get('roman')}"
                       + (f". {title}`" if title else "`")
                       + ". `[장: 제목]`과 `--chapter N`으로 바꾼다")
    caption = (form.get("table") or {}).get("caption") or {}
    if caption.get("auto_num"):
        prefix = caption.get("before", "") + "n" + caption.get("after", "")
        out.append(f"- **표 번호**: `{prefix.strip()}` 꼴로 한글이 매긴다"
                   + (f" (장 번호 {caption['chapter_roman']})"
                      if caption.get("chapter_roman") else ""))

    footnote = form.get("footnote") or {}
    shape = footnote.get("shape") or {}
    if footnote:
        out += ["", "## 각주", "",
                f"- 스타일 {footnote['style']}번 · {pt(footnote.get('size_pt') or 0)}pt · "
                f"{footnote.get('color') or '?'}",
                f"- 번호 모양 `{shape.get('prefix_char', '')}n"
                f"{shape.get('suffix_char', '')}` ({shape.get('number_format', 'DIGIT')})"
                + (", 위 첨자" if shape.get("superscript") else ""),
                f"- 구분선 {shape.get('line_type', '?')} {shape.get('line_color', '')}"
                f", 번호 매김 {shape.get('restart', '?')}"]

    out += ["", "## 보존 구간", "",
            f"- `{form['section']}`의 앞 {form['preamble_bytes']}바이트(용지 설정·표지·머리글)를 "
            "그대로 두고 그 뒤 본문만 갈아 끼운다",
            f"- `{form['header']}`는 **손대지 않는다.** 자동 글머리표·번호매기기·글꼴이 그대로 산다"]

    if form.get("fonts"):
        out += ["", "## 쓰인 글꼴", "", ", ".join(form["fonts"])]
    if form["notes"]:
        out += ["", "## 살펴볼 것", ""] + [f"- {n}" for n in form["notes"]]
    return "\n".join(out) + "\n"


def dump_form(form: Dict[str, Any]) -> str:
    return json.dumps(form, ensure_ascii=False, indent=2) + "\n"
