#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""서식 없는 한글 문서 → 마커 텍스트.

AI가 만들었거나 손으로 대충 쓴 `.hwpx`를 읽어, 이 폴더의 양식으로 다시 만들 수 있는
**마커 텍스트**로 되돌린다. 그 텍스트를 손본 뒤 `build_form.py`에 넣으면 양식대로
갖춰진 문서가 나온다.

    python read_hwpx.py 원본.hwpx -o 원고.md
    python build_form.py 원고.md -o 결과.hwpx

## 무엇을 어떻게 알아내나

서식이 없는 문서에는 '이건 2단계 항목'이라는 표시가 없다. 그래서 다음을 근거로
**추정한다.**

  1. 줄머리 기호(`□ ○ - · ※`)
  2. 줄머리 번호(`Ⅰ.` `1.` `가.` `1)`)
  3. 글자 크기와 굵기
  4. 들여쓰기

추정한 결과는 `--report`로 볼 수 있다. **틀릴 수 있다.** 나온 텍스트를 사람이
훑어보는 것을 전제로 만들었다.

표는 파이프 표로, 각주는 `[^n]`과 `[^n]:` 줄로 되돌린다. 그림은 읽지 못하고
`[그림 자리]`로 남긴다.

의존성 없음(파이썬 표준 라이브러리만).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

HERE = Path(__file__).resolve().parent

NS = {
    "hh": "http://www.hancom.co.kr/hwpml/2011/head",
    "hp": "http://www.hancom.co.kr/hwpml/2011/paragraph",
}
HWP_BINARY_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"

#: 줄머리 기호 사다리. 앞에 있을수록 큰 단위다.
SYMBOL_LADDER = ["□", "■", "○", "●", "-", "–", "·", "･", "•", "※"]

#: 줄머리 번호 유형. 앞에 있을수록 큰 단위다.
NUMBER_PATTERNS: List[Tuple[str, "re.Pattern[str]"]] = [
    ("ROMAN", re.compile(r"^[ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩ]+\s*[.)]\s+")),
    ("DIGIT_DOT", re.compile(r"^\d{1,2}\.\s+")),
    ("HANGUL", re.compile(r"^[가-힣]\.\s+")),
    ("DIGIT_PAREN", re.compile(r"^\d{1,2}\)\s+")),
    ("CIRCLED", re.compile(r"^[①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮]\s*")),
]


# ---------------------------------------------------------------------------
# 읽기
# ---------------------------------------------------------------------------
@dataclass
class Block:
    kind: str                    # para / table / picture
    text: str = ""
    rows: List[List[str]] = field(default_factory=list)
    notes: List[Tuple[int, str]] = field(default_factory=list)   # (자리, 내용)
    size_pt: float = 10.0
    bold: bool = False
    left_pt: float = 0.0
    depth: int = 0
    symbol: Optional[str] = None
    number: Optional[str] = None


def _open_parts(path: Path) -> Dict[str, str]:
    head = path.read_bytes()[:8]
    if head.startswith(HWP_BINARY_MAGIC):
        raise SystemExit(
            f"[중단] {path}는 한글 바이너리(.hwp)다. 한글에서 [다른 이름으로 저장] → "
            "'HWPX 문서'로 저장한 뒤 다시 할 것")
    if not head.startswith(b"PK"):
        raise SystemExit(f"[중단] {path}를 hwpx로 열 수 없다(zip이 아니다)")
    with zipfile.ZipFile(path) as z:
        return {name: z.read(name).decode("utf-8", "replace")
                for name in z.namelist() if name.startswith("Contents/")
                and name.endswith(".xml")}


def _char_sizes(header_xml: str) -> Dict[int, Tuple[float, bool]]:
    out: Dict[int, Tuple[float, bool]] = {}
    root = ET.fromstring(header_xml)
    for cp in root.iter(f"{{{NS['hh']}}}charPr"):
        bold = (cp.find(f"{{{NS['hh']}}}bold") is not None
                or cp.get("bold") in ("1", "true"))
        out[int(cp.get("id", "0"))] = (int(cp.get("height", "1000")) / 100.0, bold)
    return out


def _left_margins(header_xml: str) -> Dict[int, float]:
    out: Dict[int, float] = {}
    root = ET.fromstring(header_xml)
    for pp in root.iter(f"{{{NS['hh']}}}paraPr"):
        margin = pp.find(f".//{{{NS['hh']}}}margin")
        left = 0.0
        if margin is not None:
            for child in margin:
                if child.tag.endswith("}left"):
                    left = float(child.get("value", "0")) / 100.0
        out[int(pp.get("id", "0"))] = left
    return out


def read_blocks(path: Path) -> List[Block]:
    parts = _open_parts(path)
    header = parts.get("Contents/header.xml", "<x/>")
    sizes = _char_sizes(header)
    lefts = _left_margins(header)
    blocks: List[Block] = []

    for name in sorted(n for n in parts if re.match(r"Contents/section\d+\.xml$", n)):
        _read_section(ET.fromstring(parts[name]), sizes, lefts, blocks)
    return blocks


def _paragraph_text(node) -> Tuple[str, List[Tuple[int, str]], Optional[int]]:
    """문단의 글자, 각주 자리, 첫 글자모양 번호."""
    text_parts: List[str] = []
    notes: List[Tuple[int, str]] = []
    char_id: Optional[int] = None
    for run in node.findall(f"{{{NS['hp']}}}run"):
        if char_id is None and run.get("charPrIDRef") is not None:
            char_id = int(run.get("charPrIDRef"))
        for child in run:
            tag = child.tag.split("}")[-1]
            if tag == "t":
                text_parts.append("".join(child.itertext()))
            elif tag == "footNote":
                notes.append((sum(len(p) for p in text_parts), _note_text(child)))
            elif tag == "ctrl":
                # 한글은 각주를 hp:ctrl로 감싼다
                for note in child.findall(f"{{{NS['hp']}}}footNote"):
                    notes.append((sum(len(p) for p in text_parts), _note_text(note)))
    return "".join(text_parts), notes, char_id


def _note_text(node) -> str:
    out = []
    for t in node.iter(f"{{{NS['hp']}}}t"):
        out.append("".join(t.itertext()))
    return "".join(out).strip()


def _cell_text(cell) -> str:
    lines = []
    for p in cell.iter(f"{{{NS['hp']}}}p"):
        text, _notes, _c = _paragraph_text(p)
        if text.strip():
            lines.append(text.strip())
    return "<br>".join(lines)


def _read_section(root, sizes, lefts, blocks: List[Block]) -> None:
    def walk(node) -> None:
        for child in node:
            tag = child.tag.split("}")[-1]
            if tag in ("footNote", "endNote", "header", "footer", "caption"):
                continue
            if tag == "tbl":
                rows = []
                for tr in child.findall(f"{{{NS['hp']}}}tr"):
                    rows.append([_cell_text(tc)
                                 for tc in tr.findall(f"{{{NS['hp']}}}tc")])
                if rows:
                    blocks.append(Block("table", rows=rows))
                continue
            if tag == "pic":
                blocks.append(Block("picture"))
                continue
            if tag == "p":
                text, notes, char_id = _paragraph_text(child)
                if text.strip():
                    size, bold = sizes.get(char_id or 0, (10.0, False))
                    blocks.append(Block(
                        "para", text=text.strip(), notes=notes,
                        size_pt=size, bold=bold,
                        left_pt=lefts.get(int(child.get("paraPrIDRef", "0")), 0.0)))
                walk(child)
                continue
            walk(child)

    walk(root)


# ---------------------------------------------------------------------------
# 계층 추정
# ---------------------------------------------------------------------------
def _cut_prefix(block: Block, size: int) -> None:
    """줄머리 기호·번호를 떼면서 각주 자리도 같이 당긴다."""
    rest = block.text[size:]
    dropped = size + len(rest) - len(rest.lstrip())     # 기호 + 뒤따른 빈칸
    block.text = rest.strip()
    block.notes = [(max(offset - dropped, 0), note) for offset, note in block.notes]


def classify(blocks: Sequence[Block]) -> List[str]:
    """각 문단의 깊이를 매긴다. 근거를 문장으로 돌려준다."""
    notes: List[str] = []
    for block in blocks:
        if block.kind != "para":
            continue
        lead = block.text[:1]
        if lead in SYMBOL_LADDER and block.text[1:2] in (" ", "　"):
            block.symbol = lead
            _cut_prefix(block, 2)
            continue
        for kind, pattern in NUMBER_PATTERNS:
            m = pattern.match(block.text)
            if m:
                block.number = kind
                _cut_prefix(block, m.end())
                break

    sizes = sorted({b.size_pt for b in blocks if b.kind == "para"}, reverse=True)
    number_kinds = [k for k, _ in NUMBER_PATTERNS
                    if any(b.number == k for b in blocks if b.kind == "para")]
    symbols = [s for s in SYMBOL_LADDER
               if any(b.symbol == s for b in blocks if b.kind == "para")]

    if number_kinds:
        notes.append("줄머리 번호로 제목을 갈랐다: " + ", ".join(number_kinds))
    if symbols:
        notes.append("줄머리 기호로 본문 단계를 갈랐다: " + " ".join(symbols))
    if not number_kinds and not symbols:
        notes.append("줄머리 기호·번호가 없어 **글자 크기만으로** 갈랐다 "
                     "→ 결과를 반드시 훑어볼 것")

    for block in blocks:
        if block.kind != "para":
            continue
        if block.number:
            block.depth = number_kinds.index(block.number)
        elif block.symbol:
            block.depth = len(number_kinds) + symbols.index(block.symbol)
        else:
            rank = sizes.index(block.size_pt) if block.size_pt in sizes else len(sizes)
            block.depth = len(number_kinds) + len(symbols) + rank
    return notes


# ---------------------------------------------------------------------------
# 마커 텍스트로 쓰기
# ---------------------------------------------------------------------------
def to_marker_text(blocks: Sequence[Block], markers: Sequence[str]) -> str:
    depths = sorted({b.depth for b in blocks if b.kind == "para"})
    mapping = {d: markers[min(i, len(markers) - 1)] if markers else ""
               for i, d in enumerate(depths)}

    lines: List[str] = []
    note_no = 0
    definitions: List[str] = []
    prev_kind = ""

    for block in blocks:
        if block.kind == "picture":
            _blank(lines, prev_kind)
            lines.append("[그림 자리 — 도식이면 :::diagram 블록으로 옮길 것]")
            prev_kind = "picture"
            continue
        if block.kind == "table":
            _blank(lines, prev_kind)
            width = max(len(r) for r in block.rows)
            for i, row in enumerate(block.rows):
                cells = (row + [""] * width)[:width]
                lines.append("| " + " | ".join(cells) + " |")
                if i == 0:
                    lines.append("|" + "---|" * width)
            lines.append("")
            prev_kind = "table"
            continue

        text = block.text
        # 번호는 앞에서부터 매기고, 글자는 뒤에서부터 끼워 넣는다(자리가 밀리지 않게)
        numbered = [(offset, note, note_no + i + 1)
                    for i, (offset, note) in enumerate(sorted(block.notes,
                                                              key=lambda n: n[0]))]
        note_no += len(numbered)
        for offset, note, number in sorted(numbered, key=lambda n: -n[0]):
            cut = min(max(offset, 0), len(text))
            text = f"{text[:cut]}[^{number}]{text[cut:]}"
        definitions += [f"[^{number}]: {note}" for _o, note, number in numbered]
        marker = mapping.get(block.depth, "")
        lines.append(f"{marker} {text}".strip() if marker else text)
        prev_kind = "para"

    if definitions:
        lines.append("")
        lines += sorted(definitions, key=lambda d: int(re.findall(r"\d+", d)[0]))
    return "\n".join(lines).rstrip() + "\n"


def _blank(lines: List[str], prev_kind: str) -> None:
    if lines and lines[-1] != "":
        lines.append("")


def pt(value: float) -> str:
    """11.0 대신 11로 적는다. 브라우저 쪽 표기와 같아야 한다."""
    return f"{float(value):g}"


def render_report(blocks: Sequence[Block], markers: Sequence[str],
                  notes: Sequence[str]) -> str:
    depths = sorted({b.depth for b in blocks if b.kind == "para"})
    out = ["# 읽어 들인 결과", "",
           "**추정이다.** 아래 대응이 뜻과 다르면 나온 텍스트에서 마커를 고치면 된다.",
           "", "| 원본의 단계 | 근거 | 문단 수 | 이 양식의 마커 |", "|---|---|---|---|"]
    for i, depth in enumerate(depths):
        members = [b for b in blocks if b.kind == "para" and b.depth == depth]
        why = (f"번호 {members[0].number}" if members[0].number
               else f"기호 `{members[0].symbol}`" if members[0].symbol
               else f"글자 {pt(members[0].size_pt)}pt")
        marker = markers[min(i, len(markers) - 1)] if markers else "(없음)"
        out.append(f"| {i + 1}단계 | {why} | {len(members)} | `{marker}` |")

    tables = sum(1 for b in blocks if b.kind == "table")
    pics = sum(1 for b in blocks if b.kind == "picture")
    notes_n = sum(len(b.notes) for b in blocks)
    out += ["", f"- 표 {tables}개, 각주 {notes_n}개, 그림 {pics}개"]
    if pics:
        out.append("- **그림은 읽지 못한다.** `[그림 자리]`로 남겼다. 조직도·절차도라면 "
                   "그림을 보고 도식 블록으로 옮겨 적어야 한다")
    out += [""] + [f"- {n}" for n in notes]
    return "\n".join(out) + "\n"


def load_markers(form_path: Optional[Path]) -> Tuple[List[str], str]:
    path = form_path or (HERE / "form.json")
    if not path.exists():
        return [], "(양식 없음 — 기호를 그대로 둔다)"
    form = json.loads(path.read_text(encoding="utf-8"))
    return ([lv.get("marker", "") for lv in form.get("levels", []) if lv.get("marker")],
            form.get("name", "양식"))


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="서식 없는 hwpx → 마커 텍스트")
    ap.add_argument("source", type=Path, help="읽어 들일 .hwpx")
    ap.add_argument("-o", "--output", type=Path, help="저장할 마커 텍스트(.md)")
    ap.add_argument("--form", type=Path, default=None, help="form.json 경로")
    ap.add_argument("--report", type=Path, help="추정 근거를 저장할 경로")
    args = ap.parse_args(argv)

    if not args.source.exists():
        raise SystemExit(f"[중단] 파일이 없다: {args.source}")

    blocks = read_blocks(args.source)
    if not blocks:
        raise SystemExit("[중단] 읽을 내용이 없다")
    notes = classify(blocks)
    markers, form_name = load_markers(args.form)

    text = to_marker_text(blocks, markers)
    report = render_report(blocks, markers, notes)

    if args.output:
        args.output.write_text(text, encoding="utf-8")
        print(f"마커 텍스트 저장 → {args.output}")
    else:
        print(text)
    if args.report:
        args.report.write_text(report, encoding="utf-8")
        print(f"근거 저장 → {args.report}")
    else:
        print(report, file=sys.stderr)
    print(f"양식: {form_name} — 다음은 `python build_form.py "
          f"{args.output or '원고.md'} -o 결과.hwpx`", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
