#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""양식 보존 방식 한글 문서 빌더.

`form.json`(양식 카드) + `template.hwpx`(양식 원본) + 마커 텍스트 → `.hwpx`.

## 왜 이렇게 만드나

서식을 새로 지어 내면 한글의 자동 글머리표·번호매기기·글꼴·쪽 설정처럼
문단 속성 바깥에 있는 것들을 잃는다. 그래서 이 빌더는 **양식을 고치지 않는다.**

  - `Contents/header.xml` — 한 바이트도 건드리지 않는다
  - `Contents/section0.xml` — 앞부분(용지 설정·표지·머리글)은 그대로 두고
    **본문 문단만** 새로 만들어 갈아 끼운다

따라서 산출물의 서식은 양식과 같다. 재현이 아니라 보존이다.

## 쓰는 법

    python build_form.py 원고.md -o 결과.hwpx

    python build_form.py 원고.md --check-only     # 입력 검사만
    python build_form.py --markers                # 이 양식의 마커 목록 보기

`form.json`·`template.hwpx`는 이 스크립트와 같은 폴더에 있으면 저절로 찾는다.

## 입력 문법

마커는 양식마다 다르다. `--markers`로 확인할 것. 공통 문법은 다음과 같다.

    (빈 줄)             문단 사이 간격
    | a | b |           표. 첫 행이 머리행. `|---|` 줄은 무시
    [표: 제목]          바로 다음 표의 제목
    {cols=20,50,30}     바로 다음 표의 열 너비 백분율
    셀 안 <br>          셀 안에서 줄 나눔
    앞말[^1]            각주 번호 자리
    [^1]: 내용          각주 내용(문서 어디에 적어도 된다)

각주 번호는 한글이 문서 순서대로 매긴다. 라벨은 이름표일 뿐이다.

의존성 없음(파이썬 표준 라이브러리만). 파이썬 3.9 이상.
"""

from __future__ import annotations

import argparse
import io
import json
import re
import sys
import xml.dom.minidom
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

HERE = Path(__file__).resolve().parent

ROMAN = ["Ⅰ", "Ⅱ", "Ⅲ", "Ⅳ", "Ⅴ", "Ⅵ", "Ⅶ", "Ⅷ", "Ⅸ", "Ⅹ", "Ⅺ", "Ⅻ"]
CIRCLED = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮"
HANGUL_ORDER = "가나다라마바사아자차카타파하"

#: 문장 끝으로 보는 문장부호(각주 번호 자리 검사)
SENTENCE_END = ".。!?"

FOOTNOTE_REF_RE = re.compile(r"\[\^([^\]\s]+)\]")
FOOTNOTE_DEF_RE = re.compile(r"^\[\^([^\]\s]+)\]:\s*(.*)$")
CAPTION_RE = re.compile(r"^\[표\s*[:：]\s*(.+?)\]\s*$")
COLS_RE = re.compile(r"^\{cols\s*=\s*([\d.,\s]+)\}\s*$")
SEP_ROW_RE = re.compile(r"^\|[\s:|\-]+\|$")


# ---------------------------------------------------------------------------
# 양식 카드
# ---------------------------------------------------------------------------
class Form:
    """`form.json`을 읽어 쓰기 좋게 감싼 것."""

    def __init__(self, data: Dict[str, Any]) -> None:
        self.data = data
        self.levels: List[Dict[str, Any]] = list(data.get("levels") or [])
        self.by_key = {lv["key"]: lv for lv in self.levels}
        # 긴 마커부터 맞춰 본다('##'가 '#'보다 먼저)
        self.markers: List[Tuple[str, Dict[str, Any]]] = sorted(
            ((lv["marker"], lv) for lv in self.levels if lv.get("marker")),
            key=lambda kv: -len(kv[0]))

    @property
    def name(self) -> str:
        return self.data.get("name") or "양식"

    @property
    def section(self) -> str:
        return self.data.get("section") or "Contents/section0.xml"

    @property
    def body_styles(self) -> List[int]:
        return [int(lv["style"]) for lv in self.levels]

    def fallback(self) -> Optional[Dict[str, Any]]:
        """마커가 없는 줄에 쓸 레벨. 마커 없는 레벨 → 없으면 가장 얕은 레벨."""
        plain = [lv for lv in self.levels if not lv.get("marker")]
        if plain:
            return plain[0]
        return self.levels[-1] if self.levels else None

    def refs(self, block: str) -> Tuple[int, int, int]:
        node = self.data.get(block) or {}
        return int(node.get("style", 0)), int(node.get("para", 0)), int(node.get("char", 0))

    def marker_table(self) -> str:
        rows = ["| 마커 | 레벨 | 스타일 | 기호·번호 |", "|---|---|---|---|"]
        for lv in self.levels:
            if lv.get("auto_bullet"):
                who = f"한글이 자동으로 {lv['auto_bullet']}"
            elif lv.get("auto_number"):
                who = "한글이 자동으로 번호"
            elif lv.get("numbering"):
                who = f"도구가 번호({lv['numbering']})"
            elif lv.get("write_marker"):
                who = f"도구가 {lv['marker']}"
            else:
                who = "없음"
            rows.append(f"| `{lv.get('marker') or '(없음)'}` | {lv['key']} | "
                        f"{lv.get('name', '')} | {who} |")
        return "\n".join(rows)


def load_form(path: Optional[Path] = None) -> Form:
    path = path or (HERE / "form.json")
    if not path.exists():
        raise SystemExit(f"[중단] 양식 카드가 없다: {path}")
    return Form(json.loads(path.read_text(encoding="utf-8")))


# ---------------------------------------------------------------------------
# 입력 파서
# ---------------------------------------------------------------------------
@dataclass
class Item:
    kind: str                                   # para / table / blank
    level: Optional[Dict[str, Any]] = None
    text: str = ""
    notes: List[Dict[str, Any]] = field(default_factory=list)
    rows: List[List[str]] = field(default_factory=list)
    caption: str = ""
    col_pct: Optional[List[float]] = None
    line: int = 0


@dataclass
class Parsed:
    items: List[Item] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


def parse_input(text: str, form: Form) -> Parsed:
    out = Parsed()
    warn = out.warnings.append
    lines = text.splitlines()
    notes: Dict[str, Dict[str, Any]] = {}
    pend_cap, pend_cols = "", None
    i = 0

    while i < len(lines):
        raw = lines[i].rstrip()
        ln = i + 1
        i += 1

        if not raw.strip():
            if out.items and out.items[-1].kind != "blank":
                out.items.append(Item("blank", line=ln))
            continue

        m = FOOTNOTE_DEF_RE.match(raw.strip())
        if m:
            label, body = m.group(1), m.group(2).strip()
            if label in notes:
                warn(f"{ln}행: 각주 [^{label}]의 내용 줄이 두 번 → 뒤엣것을 쓴다")
            if not body:
                warn(f"{ln}행: 각주 [^{label}]의 내용이 비었다")
            notes[label] = {"text": body, "used": 0}
            if out.items and out.items[-1].kind == "blank":
                out.items.pop()
            continue

        m = CAPTION_RE.match(raw.strip())
        if m:
            pend_cap = m.group(1).strip()
            continue
        m = COLS_RE.match(raw.strip())
        if m:
            try:
                pend_cols = [float(x) for x in m.group(1).split(",")]
            except ValueError:
                warn(f"{ln}행: {{cols=…}}의 숫자를 읽지 못했다 → 균등 분배")
                pend_cols = None
            continue

        if raw.lstrip().startswith("|"):
            rows: List[List[str]] = []
            j = i - 1
            while j < len(lines) and lines[j].lstrip().startswith("|"):
                row = lines[j].strip()
                if not SEP_ROW_RE.match(row):
                    rows.append([c.strip() for c in row.strip("|").split("|")])
                j += 1
            i = j
            if rows:
                width = len(rows[0])
                for k, row in enumerate(rows):
                    if len(row) != width:
                        warn(f"{ln}행 표: {k + 1}번째 행의 칸이 {len(row)}개 "
                             f"(머리행은 {width}개) → 빈 칸을 채우거나 잘라 맞췄다")
                        rows[k] = (row + [""] * width)[:width]
                if pend_cols and len(pend_cols) != width:
                    warn(f"{ln}행 표: {{cols}}가 {len(pend_cols)}개인데 칸은 {width}개 "
                         "→ 무시하고 균등 분배")
                    pend_cols = None
                if any(FOOTNOTE_REF_RE.search(c) for row in rows for c in row):
                    warn(f"{ln}행: 표 안에는 각주를 달 수 없다 → 표 아래 문단에 달 것")
                out.items.append(Item("table", rows=rows, caption=pend_cap,
                                      col_pct=pend_cols, line=ln))
            pend_cap, pend_cols = "", None
            continue

        if pend_cap:
            warn(f"{ln}행: [표: {pend_cap}] 다음에 표가 없다 → 제목을 버렸다")
            pend_cap = ""

        level, body = _match_marker(raw, form)
        if level is None:
            level = form.fallback()
            body = raw.strip()
            if out.items and out.items[-1].kind == "para":
                out.items[-1].text += " " + body
                warn(f"{ln}행: 마커가 없는 줄 → 앞 문단에 이어 붙였다")
                continue
            warn(f"{ln}행: 마커가 없는 줄 → "
                 f"'{(level or {}).get('name', '기본')}' 레벨로 넣었다")
        if level is None:
            warn(f"{ln}행: 쓸 수 있는 레벨이 없어 줄을 버렸다")
            continue

        if level.get("auto_bullet") and body[:1] in "□○-·･•▪◦∙※":
            warn(f"{ln}행: 이 양식은 한글이 기호를 자동으로 붙인다"
                 f"('{raw[:8]}…') → 마커 뒤에 기호를 또 쓰지 말 것")
        out.items.append(Item("para", level=level, text=body, line=ln))

    _resolve_notes(out, notes)
    return out


def _match_marker(raw: str, form: Form) -> Tuple[Optional[Dict[str, Any]], str]:
    stripped = raw.strip()
    for marker, level in form.markers:
        if stripped.startswith(marker + " "):
            return level, stripped[len(marker) + 1:].strip()
    return None, stripped


def _resolve_notes(out: Parsed, notes: Dict[str, Dict[str, Any]]) -> None:
    for item in out.items:
        if item.kind != "para":
            continue
        item.text, item.notes = _split_notes(item.text, notes, out.warnings, item.line)
    for label, note in notes.items():
        if not note["used"]:
            out.warnings.append(f"각주 [^{label}]의 내용만 있고 본문에서 부르지 않았다 "
                                "→ 각주를 만들지 않았다")


def _split_notes(text: str, notes: Dict[str, Dict[str, Any]],
                 warnings: List[str], line: int) -> Tuple[str, List[Dict[str, Any]]]:
    out: List[str] = []
    found: List[Dict[str, Any]] = []
    pos = 0
    for m in FOOTNOTE_REF_RE.finditer(text):
        out.append(text[pos:m.start()])
        pos = m.end()
        label = m.group(1)
        note = notes.get(label)
        if note is None:
            warnings.append(f"{line}행: 각주 [^{label}]의 내용을 찾지 못했다 "
                            f"(`[^{label}]: 내용` 줄이 없다) → 본문에 그대로 남긴다")
            out.append(m.group())
            continue
        note["used"] += 1
        if note["used"] > 1:
            warnings.append(f"{line}행: 각주 [^{label}]을 두 번 이상 불렀다 "
                            "→ 한글에는 각주 재사용이 없어 따로 만들어진다")
        before = "".join(out)
        found.append({"label": label, "text": note["text"], "offset": len(before),
                      "before": before[-1:], "after": text[m.end():m.end() + 1]})
    out.append(text[pos:])
    return "".join(out), found


# ---------------------------------------------------------------------------
# 검사
# ---------------------------------------------------------------------------
def lint(parsed: Parsed, form: Form) -> List[str]:
    issues: List[str] = list(parsed.warnings)
    depth = {lv["key"]: i for i, lv in enumerate(form.levels)}
    prev_key: Optional[str] = None
    note_no = 0

    for item in parsed.items:
        if item.kind == "table":
            continue
        if item.kind == "blank":
            continue
        key = (item.level or {}).get("key", "")
        if not item.text.strip():
            issues.append(f"{item.line}행: 내용이 빈 문단")
        if prev_key is not None and key in depth and prev_key in depth:
            if depth[key] - depth[prev_key] > 1:
                issues.append(f"{item.line}행: {prev_key} 다음에 {key}가 왔다 "
                              "→ 중간 레벨을 건너뛰었다")
        prev_key = key

        for note in item.notes:
            note_no += 1
            issues += _note_issues(note, note_no, item.line, item.level or {})

    for idx, item in enumerate(parsed.items):
        if item.kind != "table":
            continue
        before = parsed.items[idx - 1].kind if idx > 0 else "blank"
        after = parsed.items[idx + 1].kind if idx + 1 < len(parsed.items) else "blank"
        if before != "blank":
            issues.append(f"{item.line}행: 표 앞에 빈 줄이 없다")
        if after != "blank":
            issues.append(f"{item.line}행: 표 뒤에 빈 줄이 없다")
    return issues


def _note_issues(note: Dict[str, Any], number: int, line: int,
                 level: Dict[str, Any]) -> List[str]:
    out: List[str] = []
    where = f"각주 {number}"
    before, after = str(note.get("before", "")), str(note.get("after", ""))
    label = str(note.get("label", ""))
    if (level.get("marker") or "") in ("#", "##", "###", "####") or level.get("auto_number"):
        out.append(f"{line}행: {where} — 제목에 각주를 달았다 → 본문 문단으로 옮길 것")
    if not before:
        out.append(f"{line}행: {where} — 문단 맨 앞에 번호가 왔다 → 근거가 되는 말 뒤에 붙일 것")
    elif before.isspace():
        out.append(f"{line}행: {where} — 번호 앞에 빈칸이 있다 → 앞말에 붙여 쓸 것")
    if before and before in SENTENCE_END:
        out.append(f"{line}행: {where} — 마침표 뒤에 번호가 왔다 → 마침표 앞에 붙일 것")
    if label.isdigit() and int(label) != number:
        out.append(f"{line}행: {where} — [^{label}]로 적었지만 문서 순서로는 {number}번째다 "
                   "→ 번호는 한글이 매긴다")
    return out


# ---------------------------------------------------------------------------
# XML 만들기
# ---------------------------------------------------------------------------
def esc(text: str) -> str:
    return (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def _t(text: str) -> str:
    return f"<hp:t>{esc(text)}</hp:t>" if text else "<hp:t/>"


def paragraph(style: int, para: int, char: int, text: str,
              notes: Sequence[Dict[str, Any]] = (), first_note: int = 1,
              note_refs: Tuple[int, int, int] = (0, 0, 0)) -> str:
    if notes:
        runs = _runs_with_notes(char, text, notes, first_note, note_refs)
    else:
        runs = f'<hp:run charPrIDRef="{char}">{_t(text)}</hp:run>'
    return (f'<hp:p id="0" paraPrIDRef="{para}" styleIDRef="{style}" '
            f'pageBreak="0" columnBreak="0" merged="0">{runs}</hp:p>')


_note_instid = [1500000000]


def foot_note_xml(number: int, refs: Tuple[int, int, int], text: str) -> str:
    style, para, char = refs
    _note_instid[0] += 1
    return (
        f'<hp:footNote number="{number}" suffixChar="41" instid="{_note_instid[0]}">'
        f'<hp:subList id="" textDirection="HORIZONTAL" lineWrap="BREAK" vertAlign="TOP" '
        f'linkListIDRef="0" linkListNextIDRef="0" textWidth="0" textHeight="0" '
        f'hasTextRef="0" hasNumRef="0">'
        f'<hp:p id="0" paraPrIDRef="{para}" styleIDRef="{style}" '
        f'pageBreak="0" columnBreak="0" merged="0">'
        f'<hp:run charPrIDRef="{char}"><hp:ctrl>'
        f'<hp:autoNum num="{number}" numType="FOOTNOTE">'
        f'<hp:autoNumFormat type="DIGIT" userChar="" prefixChar="" suffixChar=")" '
        f'supscript="0"/></hp:autoNum></hp:ctrl>'
        f'{_t(text)}</hp:run></hp:p></hp:subList></hp:footNote>')


def _runs_with_notes(char: int, text: str, notes: Sequence[Dict[str, Any]],
                     first_number: int, refs: Tuple[int, int, int]) -> str:
    """각주 번호가 놓일 자리에서 run을 끊는다. 자리가 지켜지는 근거다."""
    marks = sorted(min(max(int(n.get("offset", 0)), 0), len(text)) for n in notes)
    order = sorted(range(len(notes)),
                   key=lambda i: min(max(int(notes[i].get("offset", 0)), 0), len(text)))
    chunks: List[Dict[str, Any]] = [{"text": text[:marks[0]], "notes": []}]
    for pos, idx in enumerate(order):
        chunks[-1]["notes"].append(
            foot_note_xml(first_number + pos, refs, str(notes[idx].get("text", ""))))
        end = marks[pos + 1] if pos + 1 < len(marks) else len(text)
        piece = text[marks[pos]:end]
        if piece:
            chunks.append({"text": piece, "notes": []})
    return "".join(
        f'<hp:run charPrIDRef="{char}">{_t(c["text"])}{"".join(c["notes"])}</hp:run>'
        for c in chunks)


def cell_paragraphs(text: str, refs: Tuple[int, int, int]) -> str:
    style, para, char = refs
    parts = [p.strip() for p in re.split(r"<br\s*/?>", text)] or [""]
    return "".join(paragraph(style, para, char, part) for part in parts)


def caption_xml(title: str, shape: Dict[str, Any], width: int) -> str:
    before = shape.get("before") or "<표 "
    after = shape.get("after") or "> "
    fmt = shape.get("auto_num_format") or (
        '<hp:autoNumFormat type="DIGIT" userChar="" prefixChar="" suffixChar="" '
        'supscript="0"/>')
    number = ("<hp:ctrl><hp:autoNum num=\"1\" numType=\"TABLE\">"
              f"{fmt}</hp:autoNum></hp:ctrl>") if shape.get("auto_num") else ""
    return (
        f'<hp:caption side="{shape.get("side", "TOP")}" fullSz="0" '
        f'width="{shape.get("width", 8504)}" gap="{shape.get("gap", 850)}" '
        f'lastWidth="{width}">'
        f'<hp:subList id="" textDirection="HORIZONTAL" lineWrap="BREAK" vertAlign="TOP" '
        f'linkListIDRef="0" linkListNextIDRef="0" textWidth="0" textHeight="0" '
        f'hasTextRef="0" hasNumRef="0">'
        f'<hp:p id="0" paraPrIDRef="{shape.get("para", 0)}" '
        f'styleIDRef="{shape.get("style", 0)}" pageBreak="0" columnBreak="0" merged="0">'
        f'<hp:run charPrIDRef="{shape.get("char", 0)}">'
        f'{_t(before)}{number}{_t(after + title)}'
        f'</hp:run></hp:p></hp:subList></hp:caption>')


_table_seq = [900000000]


def table_xml(item: Item, form: Form) -> str:
    spec = form.data.get("table") or {}
    cell_refs = (int((spec.get("cell_para") or {}).get("style", 0)),
                 int((spec.get("cell_para") or {}).get("para", 0)),
                 int((spec.get("cell_para") or {}).get("char", 0)))
    width = int(spec.get("width", 39456))
    row_h = int(spec.get("row_min_height", 1182))
    header_fill = int(spec.get("header_fill", 1))
    body_fill = int(spec.get("body_fill", 1))
    margin = spec.get("cell_margin") or {"left": 494, "right": 494, "top": 0, "bottom": 0}
    in_margin = spec.get("in_margin") or {"left": 141, "right": 141, "top": 141, "bottom": 141}

    ncols = len(item.rows[0])
    if item.col_pct:
        total = sum(item.col_pct)
        widths = [int(width * p / total) for p in item.col_pct]
    else:
        widths = [width // ncols] * ncols
    widths[-1] = width - sum(widths[:-1])          # 합이 표 폭과 어긋나지 않게

    _table_seq[0] += 1
    tid = _table_seq[0]

    rows_xml = []
    for r, row in enumerate(item.rows):
        fill = header_fill if r == 0 else body_fill
        cells = []
        for c, cell in enumerate(row):
            cells.append(
                f'<hp:tc name="" header="{1 if r == 0 else 0}" hasMargin="0" protect="0" '
                f'editable="0" dirty="0" borderFillIDRef="{fill}">'
                f'<hp:subList id="" textDirection="HORIZONTAL" lineWrap="BREAK" '
                f'vertAlign="CENTER" linkListIDRef="0" linkListNextIDRef="0" '
                f'textWidth="0" textHeight="0" hasTextRef="0" hasNumRef="0">'
                f'{cell_paragraphs(cell, cell_refs)}</hp:subList>'
                f'<hp:cellAddr colAddr="{c}" rowAddr="{r}"/>'
                f'<hp:cellSpan colSpan="1" rowSpan="1"/>'
                f'<hp:cellSz width="{widths[c]}" height="{row_h}"/>'
                f'<hp:cellMargin left="{margin["left"]}" right="{margin["right"]}" '
                f'top="{margin["top"]}" bottom="{margin["bottom"]}"/></hp:tc>')
        rows_xml.append("<hp:tr>" + "".join(cells) + "</hp:tr>")

    caption_shape = spec.get("caption")
    caption = (caption_xml(item.caption, caption_shape, width)
               if (item.caption and caption_shape) else "")
    if item.caption and not caption_shape:
        caption = ""

    tbl = (
        f'<hp:tbl id="{tid}" zOrder="{tid % 1000}" numberingType="TABLE" '
        f'textWrap="TOP_AND_BOTTOM" textFlow="BOTH_SIDES" lock="0" dropcapstyle="None" '
        f'pageBreak="CELL" repeatHeader="1" rowCnt="{len(item.rows)}" colCnt="{ncols}" '
        f'cellSpacing="0" borderFillIDRef="{spec.get("border_fill", 1)}" noAdjust="0">'
        f'<hp:sz width="{width}" widthRelTo="ABSOLUTE" '
        f'height="{row_h * len(item.rows)}" heightRelTo="ABSOLUTE" protect="0"/>'
        f'<hp:pos treatAsChar="1" affectLSpacing="0" flowWithText="1" allowOverlap="0" '
        f'holdAnchorAndSO="0" vertRelTo="PARA" horzRelTo="PARA" vertAlign="TOP" '
        f'horzAlign="LEFT" vertOffset="0" horzOffset="0"/>'
        f'<hp:outMargin left="0" right="0" top="0" bottom="0"/>'
        f'{caption}'
        f'<hp:inMargin left="{in_margin["left"]}" right="{in_margin["right"]}" '
        f'top="{in_margin["top"]}" bottom="{in_margin["bottom"]}"/>'
        + "".join(rows_xml) + "</hp:tbl>")

    style, para, char = form.refs("table_wrap")
    return (f'<hp:p id="0" paraPrIDRef="{para}" styleIDRef="{style}" '
            f'pageBreak="0" columnBreak="0" merged="0">'
            f'<hp:run charPrIDRef="{char}">{tbl}<hp:t/></hp:run></hp:p>')


class Numbering:
    """도구가 직접 매기는 번호(양식이 한글 번호매기기를 안 쓸 때)."""

    def __init__(self, form: Form) -> None:
        self.depth = {lv["key"]: i for i, lv in enumerate(form.levels)}
        self.counts: Dict[str, int] = {}

    def next(self, key: str, kind: str) -> str:
        self.counts[key] = self.counts.get(key, 0) + 1
        n = self.counts[key]
        for other, level in list(self.counts.items()):     # 아래 레벨은 다시 1부터
            if other != key and self.depth.get(other, 0) > self.depth.get(key, 0):
                self.counts[other] = 0
        if kind == "AUTO_ROMAN":
            return f"{ROMAN[(n - 1) % len(ROMAN)]}. "
        if kind == "AUTO_NUM":
            return f"{n}. "
        if kind == "AUTO_ALPHA":
            return f"{chr(ord('A') + (n - 1) % 26)}. "
        if kind == "AUTO_CIRCLED":
            return f"{CIRCLED[(n - 1) % len(CIRCLED)]} "
        if kind == "AUTO_HANGUL":
            return f"{HANGUL_ORDER[(n - 1) % len(HANGUL_ORDER)]}. "
        return ""


def build_body(parsed: Parsed, form: Form) -> Tuple[str, Dict[str, int]]:
    stats = {"문단": 0, "표": 0, "각주": 0}
    note_refs = form.refs("footnote") if form.data.get("footnote") else (0, 0, 0)
    numbering = Numbering(form)
    note_no = 1
    out: List[str] = []
    for item in parsed.items:
        if item.kind == "blank":
            out.append(paragraph(*form.refs("blank"), ""))
            continue
        if item.kind == "table":
            out.append(table_xml(item, form))
            stats["표"] += 1
            continue
        level = item.level or {}
        text = item.text
        shift = 0
        prefix = ""
        if level.get("numbering"):
            prefix = numbering.next(level["key"], level["numbering"])
        elif level.get("write_marker"):
            prefix = f"{level['marker']} "
        if prefix:
            text = prefix + text
            shift = len(prefix)
        notes = [dict(n, offset=int(n["offset"]) + shift) for n in item.notes]
        out.append(paragraph(int(level.get("style", 0)), int(level.get("para", 0)),
                             int(level.get("char", 0)), text, notes, note_no,
                             note_refs))
        note_no += len(notes)
        stats["각주"] += len(notes)
        stats["문단"] += 1
    return "".join(out), stats


# ---------------------------------------------------------------------------
# 템플릿 조작
# ---------------------------------------------------------------------------
def top_level_paragraphs(section_xml: str) -> List[Tuple[int, int, str]]:
    depth = 0
    tops: List[List[Any]] = []
    for m in re.finditer(r"<hp:p[ >][^>]*>|<hp:p/>|</hp:p>", section_xml):
        token = m.group(0)
        if token.startswith("</"):
            depth -= 1
            if depth == 0 and tops:
                tops[-1][1] = m.end()
        elif token == "<hp:p/>":
            if depth == 0:
                tops.append([m.start(), m.end(), token])
        else:
            if depth == 0:
                tops.append([m.start(), None, token])
            depth += 1
    return [(s, e, t) for s, e, t in tops if e is not None]


def split_preamble(section_xml: str, body_styles: Sequence[int]) -> Tuple[str, str]:
    """(보존할 앞부분, 닫는 꼬리). 본문 스타일이 처음 나오는 문단에서 자른다."""
    wanted = {str(s) for s in body_styles}
    cut = None
    for start, _end, tag in top_level_paragraphs(section_xml):
        m = re.search(r'styleIDRef="(\d+)"', tag)
        if m and m.group(1) in wanted:
            cut = start
            break
    if cut is None:
        cut = section_xml.rfind("</hs:sec>")
        if cut < 0:
            raise SystemExit("[중단] 템플릿 본문에서 </hs:sec>를 찾지 못했다")
    return section_xml[:cut], "</hs:sec>"


# ---------------------------------------------------------------------------
# 산출물 검사
# ---------------------------------------------------------------------------
def check_refs(section_xml: str, header_xml: str) -> List[str]:
    """새로 쓴 본문이 양식에 없는 번호를 가리키지 않는지."""
    pools = {
        "styleIDRef": set(re.findall(r'<hh:style id="(\d+)"', header_xml)),
        "paraPrIDRef": set(re.findall(r'<hh:paraPr id="(\d+)"', header_xml)),
        "charPrIDRef": set(re.findall(r'<hh:charPr id="(\d+)"', header_xml)),
        "borderFillIDRef": set(re.findall(r'<hh:borderFill id="(\d+)"', header_xml)),
    }
    errs = []
    for attr, pool in pools.items():
        missing = set(re.findall(rf'{attr}="(\d+)"', section_xml)) - pool
        if missing:
            errs.append(f"[참조 오류] 양식에 없는 {attr}: {sorted(missing)}")
    return errs


def check_double_bullets(section_xml: str, form: Form) -> List[str]:
    """한글이 기호를 붙이는 문단인데 텍스트도 기호로 시작하면 이중이다."""
    auto = {str(lv["para"]): lv["auto_bullet"] for lv in form.levels if lv.get("auto_bullet")}
    if not auto:
        return []
    errs = []
    for m in re.finditer(r'<hp:p [^>]*paraPrIDRef="(\d+)"[^>]*>(.*?)</hp:p>',
                         section_xml, re.S):
        para_id, body = m.group(1), m.group(2)
        if para_id not in auto:
            continue
        text = "".join(re.findall(r"<hp:t>([^<]*)</hp:t>", body)).lstrip()
        if text[:1] in "□○-·･•▪◦∙※":
            errs.append(f"[이중 기호] 한글이 '{auto[para_id]}'를 붙이는 문단인데 "
                        f"텍스트도 기호로 시작한다: {text[:24]!r}")
    return errs


def check_output(path: Path) -> List[str]:
    errs: List[str] = []
    try:
        with zipfile.ZipFile(path) as z:
            broken = z.testzip()
            if broken:
                errs.append(f"[zip 손상] {broken}")
            names = set(z.namelist())
            for need in ("mimetype", "Contents/header.xml", "Contents/content.hpf",
                         "META-INF/container.xml"):
                if need not in names:
                    errs.append(f"[zip 누락] {need}")
            for name in names:
                if name.endswith((".xml", ".hpf")):
                    try:
                        xml.dom.minidom.parseString(z.read(name))
                    except Exception as exc:                        # noqa: BLE001
                        errs.append(f"[XML 오류] {name}: {exc}")
    except Exception as exc:                                        # noqa: BLE001
        errs.append(f"[열기 실패] {exc}")
    return errs


# ---------------------------------------------------------------------------
# 조립
# ---------------------------------------------------------------------------
def build(form: Form, template: Path, source: Path, out: Path,
          check_only: bool, strict: bool) -> int:
    parsed = parse_input(source.read_text(encoding="utf-8"), form)
    issues = lint(parsed, form)

    print("── 1층 입력 검사 " + "─" * 30)
    for issue in issues:
        print("  [경고]", issue)
    if not issues:
        print("  이상 없음")
    if check_only:
        return 1 if issues else 0
    if issues and strict:
        print("  → --strict라서 생성을 멈춘다")
        return 1

    with zipfile.ZipFile(template) as z:
        entries = {name: z.read(name) for name in z.namelist()}
    if form.section not in entries:
        raise SystemExit(f"[중단] 템플릿에 {form.section}이 없다")
    section_xml = entries[form.section].decode("utf-8")
    header_xml = entries["Contents/header.xml"].decode("utf-8")

    if not form.data.get("footnote") and any(item.notes for item in parsed.items):
        print("  [경고] 이 양식에는 각주 스타일이 없다 → 한글에서 각주 서식이 흐트러질 수 있다")

    preamble, tail = split_preamble(section_xml, form.body_styles)
    body, stats = build_body(parsed, form)
    new_section = preamble + body + tail

    print("── 2층 구조 검사 " + "─" * 30)
    errs = check_refs(new_section, header_xml) + check_double_bullets(new_section, form)
    if errs:
        for err in errs:
            print(" ", err)
        print("  → 생성 중단")
        return 2
    print(f"  참조·이중 기호 이상 없음 "
          f"(문단 {stats['문단']}, 표 {stats['표']}, 각주 {stats['각주']})")

    entries[form.section] = new_section.encode("utf-8")
    entries["Preview/PrvText.txt"] = (
        "build_form.py로 만든 문서 — 한글에서 저장하면 미리보기가 갱신된다"
    ).encode("utf-16-le")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        if "mimetype" in entries:
            z.writestr("mimetype", entries["mimetype"], compress_type=zipfile.ZIP_STORED)
        for name, data in entries.items():
            if name != "mimetype":
                z.writestr(name, data)
    out.write_bytes(buf.getvalue())

    print("── 3층 산출물 검사 " + "─" * 29)
    errs = check_output(out)
    if errs:
        for err in errs:
            print(" ", err)
        return 3
    print("  zip·XML 정상 →", out)
    print("  ※ 줄바꿈·쪽 나눔·표 높이는 한글이 열 때 다시 계산한다")
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        description="양식 보존 방식 한글 문서 빌더",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input", nargs="?", type=Path, help="마커 텍스트 파일")
    ap.add_argument("-o", "--output", type=Path, default=Path("결과.hwpx"))
    ap.add_argument("--form", type=Path, default=None, help="form.json 경로")
    ap.add_argument("--template", type=Path, default=None, help="template.hwpx 경로")
    ap.add_argument("--check-only", action="store_true", help="입력 검사만")
    ap.add_argument("--strict", action="store_true", help="경고가 하나라도 있으면 만들지 않음")
    ap.add_argument("--markers", action="store_true", help="이 양식의 마커 목록")
    args = ap.parse_args(argv)

    form = load_form(args.form)
    if args.markers:
        print(f"# {form.name} 마커\n")
        print(form.marker_table())
        return 0
    if args.input is None:
        ap.error("마커 텍스트 파일을 지정할 것 (또는 --markers)")

    template = args.template or (HERE / (form.data.get("template") or "template.hwpx"))
    if not template.exists():
        raise SystemExit(f"[중단] 양식 원본이 없다: {template}")
    if not args.input.exists():
        raise SystemExit(f"[중단] 입력 파일이 없다: {args.input}")
    return build(form, template, args.input, args.output, args.check_only, args.strict)


if __name__ == "__main__":
    sys.exit(main())
