import re
import zipfile
from io import BytesIO

import pytest

from hwpx_studio.diagram import build_grid, parse_block, parse_text as parse_diagram
from hwpx_studio.engine import build_document

ORG = """대표
  기획부
    기획팀
    예산팀
  운영부
  연구부"""


def boxes(grid):
    return {c.text: c for c in grid.cells if c.text}


def test_tree_parsing_depths():
    spec = parse_block("type=org", ORG.splitlines())
    grid = build_grid(spec, __import__("hwpx_studio.profile", fromlist=["x"]).load_profile(
        "policy-default"))
    assert set(boxes(grid)) == {"대표", "기획부", "기획팀", "예산팀", "운영부", "연구부"}
    assert boxes(grid)["대표"].row == 0
    assert boxes(grid)["기획부"].row == 3
    assert boxes(grid)["기획팀"].row == 6


def test_parent_box_is_centered_over_children(policy):
    grid = build_grid(parse_block("type=org", ORG.splitlines()), policy)
    b = boxes(grid)
    span = b["대표"].col_span
    def center(cell):
        return cell.col + span // 2 - 1
    child_centers = sorted(center(b[n]) for n in ("기획부", "운영부", "연구부"))
    assert center(b["대표"]) == (child_centers[0] + child_centers[-1]) // 2
    assert center(b["기획부"]) == (center(b["기획팀"]) + center(b["예산팀"])) // 2


def test_connectors_join_parent_and_children(policy):
    grid = build_grid(parse_block("type=org", ORG.splitlines()), policy)
    b = boxes(grid)
    half = b["대표"].col_span // 2
    parent_center = b["대표"].col + half - 1
    connectors = [c for c in grid.cells if not c.text and not c.fill]
    verticals = {(c.row, c.col) for c in connectors if "right" in c.borders}
    bus = {(c.row, c.col) for c in connectors if "top" in c.borders}
    assert (1, parent_center) in verticals            # 부모 아래 세로선
    for name in ("기획부", "운영부", "연구부"):
        col = b[name].col + half - 1
        assert (2, col) in verticals                  # 자식 위 세로선
    assert bus, "가로 버스가 없음"
    # 연결선은 상자 행(0·3·6)이 아니라 연결 행(1·2·4·5)에만 놓인다
    assert {row for row, _ in bus} == {2, 5}
    assert {row for row, _ in verticals} <= {1, 2, 4, 5}


def test_bus_touches_parent_vertical(policy):
    """가로 버스는 부모 세로선이 끝나는 경계(연결 행의 위쪽 변)에 놓여야 한다.

    프로토타입은 버스를 아래쪽 변에 그려 세로선과 한 행 어긋났고, 한글 화면에서
    선이 끊겨 보였다. 그 회귀를 막는다.
    """
    grid = build_grid(parse_block("type=org", ORG.splitlines()), policy)
    b = boxes(grid)
    half = b["대표"].col_span // 2
    parent_center = b["대표"].col + half - 1
    connectors = [c for c in grid.cells if not c.text and not c.fill]

    vertical_rows = {c.row for c in connectors
                     if "right" in c.borders and c.col == parent_center}
    bus_cells = [c for c in connectors if "top" in c.borders]
    bus_rows = {c.row for c in bus_cells}

    assert vertical_rows == {1}                      # 부모 상자 바로 아래 행
    assert min(bus_rows) == max(vertical_rows) + 1   # 버스는 그 다음 행의 '위쪽 변'
    assert all("bottom" not in c.borders for c in bus_cells)


def test_all_columns_are_uniform_width(policy):
    grid = build_grid(parse_block("type=org", ORG.splitlines()), policy)
    assert len(set(round(w, 6) for w in grid.col_widths_mm)) == 1


def test_wide_diagram_falls_back_to_image(policy):
    lines = ["총괄"] + [f"  부서{i}" for i in range(12)]
    grid = build_grid(parse_block("type=org width=60", lines), policy)
    assert grid.fallback_to_image
    assert grid.warnings


def test_flow_and_matrix_grids(policy):
    flow = build_grid(parse_diagram(":::diagram type=flow\n가 → 나 → 다\n:::"), policy)
    assert flow.rows == 1 and flow.cols == 5
    assert [c.text for c in flow.cells] == ["가", "→", "나", "→", "다"]

    down = build_grid(parse_diagram(
        ":::diagram type=flow direction=down\n가 → 나\n:::"), policy)
    assert down.cols == 1 and down.rows == 3

    matrix = build_grid(parse_diagram(
        ":::diagram type=matrix\n| | 중앙 | 지방 |\n|---|---|---|\n| 기획 | 본부 | 지역 |\n:::"),
        policy)
    assert (matrix.rows, matrix.cols) == (2, 3)


def test_diagram_table_is_emitted_with_merged_boxes(policy):
    spec = parse_block("type=org", ORG.splitlines())
    data = build_document(policy, [("diagram", spec.to_dict())]).data
    section = zipfile.ZipFile(BytesIO(data)).read("Contents/section0.xml").decode("utf-8")
    table = re.search(r"<hp:tbl.*?</hp:tbl>", section, re.S).group()
    merged = re.findall(r'<hp:cellSpan colSpan="(\d+)"', table)
    assert merged.count("6") == 6                      # 상자 6개가 6열씩 병합
    assert "대표" in table and "예산팀" in table


def test_diagram_border_fills_cover_line_cells(policy):
    spec = parse_block("type=org", ORG.splitlines())
    data = build_document(policy, [("diagram", spec.to_dict())]).data
    header = zipfile.ZipFile(BytesIO(data)).read("Contents/header.xml").decode("utf-8")
    edges = []
    for m in re.finditer(r"<hh:borderFill id=\"\d+\".*?</hh:borderFill>", header, re.S):
        block = m.group()
        active = tuple(e for e in ("left", "right", "top", "bottom")
                       if re.search(rf'<hh:{e}Border type="(?!NONE)', block))
        edges.append(active)
    assert ("right",) in edges                          # 세로선
    assert ("top",) in edges                            # 가로 버스
    assert ("right", "top") in edges                    # 버스 + 세로선
    assert () in edges                                  # 투명 셀
