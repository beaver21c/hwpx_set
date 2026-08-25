#!/usr/bin/env python3
"""검증용: 노드마다 다른 배경색·테두리색·점선이 hwpx 표로 나오는지 확인한다.

`docs/diagram-capture-review.md`(도식 인식·재현 도구 검토)의 근거 자료다.
현재 구현은 도식 색을 프로파일에서 **문서 전체 하나**로만 정하지만, 실제 파일
형식(OWPML borderFill)과 python-hwpx API는 **셀마다 다른 색·선종류**를 이미
지원한다. 이 스크립트는 그것을 실제 파일로 만들어 확인한다.

    python prototypes/style_capture_poc.py

출력: 생성된 hwpx의 borderFill 목록(색·선종류)과 본문에서 참조된 id.
구현이 아니라 확인용이므로 내부 함수를 임시로 갈아끼운다(monkeypatch).
"""

from __future__ import annotations

import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hwpx_studio import diagram as D            # noqa: E402
from hwpx_studio.engine import build_document   # noqa: E402
from hwpx_studio.profile import load_profile    # noqa: E402
from hwpx_studio.units import mm                # noqa: E402

#: 원본 도식에서 읽어 왔다고 가정한 노드별 색
PALETTE = {
    "대표": "#C00000",
    "기획부": "#2E75B6",
    "운영부": "#70AD47",
    "연구부": "#FFC000",
}
LINE_COLOR = "#C00000"
LINE_TYPE = "DASH"

_orig_build_grid = D.build_grid


def build_grid_with_styles(spec, profile, force=False):
    """격자를 만든 뒤 셀에 노드별 색·선종류를 얹는다(IR 확장 흉내)."""
    grid = _orig_build_grid(spec, profile, force)
    for cell in grid.cells:
        if cell.text in PALETTE:
            cell.fill = PALETTE[cell.text]
            cell.border_color = "#000000"
        elif not cell.fill and cell.borders:      # 연결선 셀
            cell.border_color = LINE_COLOR
            cell.border_type = LINE_TYPE
    return grid


def emit_grid_with_styles(doc, sec, grid, profile, ids, table_plans):
    """emit_grid와 같되 borderFill을 셀별 색·선종류로 만든다."""
    dia = profile["diagram"]
    ensure_bf = doc.styles.ensure_border_fill
    width_hu = mm(grid.total_width_mm)
    tbl = doc.add_table(grid.rows, grid.cols, section=sec, width=width_hu)

    blank = ensure_bf(active_borders=[])
    for r in range(grid.rows):
        for c in range(grid.cols):
            tbl.set_cell_border_fill(r, c, blank)

    plan = {
        (r, c): {"width": mm(grid.col_widths_mm[c]),
                 "height": mm(grid.row_heights_mm[r]), "char": "diagram"}
        for r in range(grid.rows) for c in range(grid.cols)
    }
    for cell in grid.cells:
        tbl.set_cell_border_fill(cell.row, cell.col, ensure_bf(
            border_color=getattr(cell, "border_color", None) or dia["box_border"],
            border_width=f'{float(dia["line_width_mm"])} mm',
            fill_color=cell.fill,
            active_borders=list(cell.borders),
            border_type=getattr(cell, "border_type", "SOLID"),
        ))
        if cell.text:
            tbl.set_cell_text(cell.row, cell.col, cell.text)
        plan[(cell.row, cell.col)] = {
            "width": mm(sum(grid.col_widths_mm[cell.col:cell.col + cell.col_span])),
            "height": mm(sum(grid.row_heights_mm[cell.row:cell.row + cell.row_span])),
            "char": cell.char,
        }
    for cell in grid.cells:
        if cell.col_span > 1 or cell.row_span > 1:
            tbl.merge_cells(cell.row, cell.col,
                            cell.row + cell.row_span - 1, cell.col + cell.col_span - 1)

    table_plans.append({"kind": "diagram", "cells": plan, "width": width_hu,
                        "height": mm(grid.total_height_mm)})


def main(out: str = "poc_style.hwpx") -> int:
    D.CellPlan.border_color = None       # 확장될 IR 필드(기본값)
    D.CellPlan.border_type = "SOLID"
    D.build_grid = build_grid_with_styles
    D.emit_grid = emit_grid_with_styles

    profile = load_profile("policy-default")
    spec = {
        "type": "org", "title": "노드별 색·점선 확인", "options": {},
        "lines": ["대표", "  기획부", "    기획팀", "  운영부", "  연구부"],
    }
    build_document(profile, [{"type": "diagram", "spec": spec}], out)
    print(f"생성: {out}")

    with zipfile.ZipFile(out) as z:
        header = z.read("Contents/header.xml").decode("utf-8")
        body = z.read("Contents/section0.xml").decode("utf-8")

    print(f"{'id':>4}  {'채움색':<10} 선(종류 / 두께 / 색)")
    for m in re.finditer(r'<hh:borderFill id="(\d+)"(.*?)</hh:borderFill>', header, re.DOTALL):
        fill = re.search(r'faceColor="(#?\w+)"', m.group(2))
        lines = sorted({t for t in re.findall(
            r'type="(\w+)" width="([^"]+)" color="(#\w+)"', m.group(2)) if t[0] != "NONE"})
        if not fill and not lines:
            continue
        face = fill.group(1) if fill and fill.group(1) != "none" else "-"
        desc = ", ".join(f"{t}/{w}/{c}" for t, w, c in lines) or "-"
        print(f"{m.group(1):>4}  {face:<10} {desc}")

    used = sorted(set(re.findall(r'borderFillIDRef="(\d+)"', body)), key=int)
    print("본문에서 참조된 borderFill id:", ", ".join(used))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(*sys.argv[1:]))
