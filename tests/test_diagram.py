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


def test_too_many_siblings_switch_to_the_side_layout(policy):
    """가로로 안 들어가면 이미지로 밀어내지 말고 세로 목록형으로 바꾼다."""
    lines = ["총괄"] + [f"  부서{i}" for i in range(12)]
    grid = build_grid(parse_block("type=org", lines), policy)
    assert not grid.fallback_to_image
    assert grid.total_width_mm <= policy["diagram"]["max_width_mm"] + 0.01
    assert grid.rows > grid.cols                      # 가로가 아니라 세로로 길어진다
    assert any("세로 목록형" in w for w in grid.warnings)


def test_diagram_still_falls_back_to_image_when_even_side_cannot_fit(policy):
    lines = ["총괄", "  가국", "    가과", "      가팀", "        가반"]
    grid = build_grid(parse_block("type=org layout=side width=20", lines), policy)
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


# ──────────────────────────────────────────────────────────────
# 노드별 스타일(M1)
# ──────────────────────────────────────────────────────────────
STYLED = """대표 {fill=#C00000 color=#fff}
  기획부 {fill=#2E75B6}
  감사실 {border=#BF8F00 link=dash link_color=#808080}"""


def test_node_attributes_are_parsed_and_normalized(policy):
    grid = build_grid(parse_block("type=org", STYLED.splitlines()), policy)
    b = boxes(grid)
    assert b["대표"].fill == "#C00000"
    assert b["대표"].text_color == "#FFFFFF"          # #fff → #FFFFFF
    assert b["기획부"].fill == "#2E75B6"
    assert b["감사실"].border_color == "#BF8F00"
    assert b["감사실"].fill == policy["diagram"]["box_fill"]   # 지정 없으면 프로파일 값


def test_attribute_block_is_stripped_from_the_label(policy):
    grid = build_grid(parse_block("type=org", STYLED.splitlines()), policy)
    assert "{" not in "".join(c.text for c in grid.cells)


def test_child_link_style_applies_to_that_branch_only(policy):
    grid = build_grid(parse_block("type=org", STYLED.splitlines()), policy)
    dashed = [c for c in grid.cells if c.border_type == "DASH"]
    assert dashed, "점선 연결선이 없음"
    assert all(c.border_color == "#808080" for c in dashed)
    solid = [c for c in grid.cells if not c.text and not c.fill and c.border_type is None]
    assert solid, "나머지 연결선은 실선이어야 함"


def test_block_options_override_profile_colors(policy):
    spec = parse_block("type=org box_fill=#F2F2F2 root_fill=#404040 line_style=dash",
                       ["총괄", "  가부서", "  나부서"])
    grid = build_grid(spec, policy)
    b = boxes(grid)
    assert b["총괄"].fill == "#404040"
    assert b["가부서"].fill == "#F2F2F2"
    assert all(c.border_type == "DASH" for c in grid.cells if not c.text and not c.fill)
    assert policy["diagram"]["box_fill"] == "#DCE6F1"   # 원본 프로파일은 그대로


def test_flow_and_matrix_take_cell_attributes(policy):
    flow = build_grid(parse_block("type=flow", ["접수 → 통보 {fill=#C00000 color=#FFF}"]), policy)
    assert boxes(flow)["통보"].fill == "#C00000"
    assert boxes(flow)["통보"].text_color == "#FFFFFF"
    matrix = build_grid(parse_block("type=matrix", ["| | 중앙 |", "| 기획 | 본부 {fill=#FFF2CC} |"]),
                        policy)
    assert boxes(matrix)["본부"].fill == "#FFF2CC"


def test_unknown_colors_are_ignored_not_crashed(policy):
    grid = build_grid(parse_block("type=org", ["대표 {fill=하늘색 color=#GGGGGG}"]), policy)
    assert boxes(grid)["대표"].fill == policy["diagram"]["root_fill"]
    assert boxes(grid)["대표"].text_color is None


def test_styled_diagram_reaches_the_hwpx_file(policy, tmp_path):
    out = tmp_path / "styled.hwpx"
    build_document(policy, [{"type": "diagram",
                             "spec": parse_block("type=org", STYLED.splitlines()).to_dict()}],
                   str(out))
    with zipfile.ZipFile(str(out)) as zf:
        header = zf.read("Contents/header.xml").decode("utf-8")
        section = zf.read("Contents/section0.xml").decode("utf-8")

    used = set(re.findall(r'borderFillIDRef="(\d+)"', section))
    designs = {}
    for m in re.finditer(r'<hh:borderFill id="(\d+)"(.*?)</hh:borderFill>', header, re.S):
        fill = re.search(r'faceColor="(#\w+)"', m.group(2))
        edges = re.findall(r'type="(\w+)" width="[^"]*" color="(#\w+)"', m.group(2))
        designs[m.group(1)] = (fill.group(1) if fill else None, edges)

    fills = {designs[i][0] for i in used if i in designs}
    assert {"#C00000", "#2E75B6"} <= fills                      # 노드별 배경색
    assert any(t == "DASH" and c == "#808080"                    # 점선 연결선
               for i in used if i in designs for t, c in designs[i][1])

    # 글자색은 charPr로 등록되어 본문이 그것을 참조한다
    white = [m.group(1) for m in
             re.finditer(r'<hh:charPr id="(\d+)"[^>]*textColor="#FFFFFF"', header)]
    assert set(white) & set(re.findall(r'charPrIDRef="(\d+)"', section))


def test_diagram_table_has_no_outer_frame(policy, tmp_path):
    """표 자체의 테두리는 꺼져 있어야 한다(검은 사각형이 도식을 감싸면 안 됨)."""
    out = tmp_path / "frame.hwpx"
    build_document(policy, [{"type": "diagram",
                             "spec": parse_block("type=org", ["대표", "  가부서"]).to_dict()}],
                   str(out))
    with zipfile.ZipFile(str(out)) as zf:
        header = zf.read("Contents/header.xml").decode("utf-8")
        section = zf.read("Contents/section0.xml").decode("utf-8")
    ref = re.search(r'<hp:tbl\b[^>]*borderFillIDRef="(\d+)"', section).group(1)
    block = re.search(rf'<hh:borderFill id="{ref}".*?</hh:borderFill>', header, re.S).group()
    edges = re.findall(r'<hh:(?:left|right|top|bottom)Border type="(\w+)"', block)
    assert set(edges) == {"NONE"}, f"표 바깥 테두리가 켜져 있음: {edges}"


# ──────────────────────────────────────────────────────────────
# 세로 목록형 배치(M3)
# ──────────────────────────────────────────────────────────────
SIDE = """원장
  기획조정실
    기획팀
    예산팀
  감사실 {link=dash}"""


def side_grid(policy, header="type=org layout=side", lines=None):
    return build_grid(parse_block(header, (lines or SIDE).splitlines()), policy)


def test_side_layout_stacks_boxes_one_per_row(policy):
    grid = side_grid(policy)
    rows = [c.row for c in grid.cells if c.text]
    assert len(rows) == len(set(rows)) == 5           # 상자마다 자기 행
    assert all(c.row_span == 2 for c in grid.cells if c.text)


def test_side_layout_indents_by_depth(policy):
    b = boxes(side_grid(policy))
    assert b["원장"].col == 0
    assert b["기획조정실"].col == 2
    assert b["기획팀"].col == 4
    assert b["감사실"].col == 2


def test_side_layout_width_does_not_grow_with_box_count(policy):
    narrow = side_grid(policy, lines="본부\n" + "\n".join(f"  국{i}" for i in range(3)))
    wide = side_grid(policy, lines="본부\n" + "\n".join(f"  국{i}" for i in range(30)))
    assert narrow.total_width_mm == wide.total_width_mm
    assert wide.rows > narrow.rows


def test_side_connectors_meet_the_box_centres(policy):
    """세로선은 자식 중심에서 끝나고, 가로 이음선은 그 지점에서 상자로 들어간다."""
    grid = side_grid(policy)
    b = boxes(grid)
    spine = {(c.row, c.col) for c in grid.cells if not c.text and "right" in c.borders}
    stubs = {(c.row, c.col) for c in grid.cells if not c.text and "top" in c.borders}

    for name in ("기획조정실", "감사실"):
        centre = b[name].row + 1                      # 두 행 중 아래 행의 위쪽 = 중심
        assert (centre, 1) in stubs                   # 이음선은 세로선(0열) 다음 칸
        assert (centre - 1, 0) in spine               # 세로선은 그 지점까지 내려온다

    deep = b["기획팀"].row + 1
    assert (deep, 3) in stubs                         # 한 단계 안쪽 세로선에서 나온다
    assert (deep - 1, 2) in spine


def test_side_layout_keeps_node_styles(policy):
    grid = side_grid(policy, lines="원장 {fill=#1F3864 color=#FFF}\n  감사실 {link=dash}")
    b = boxes(grid)
    assert b["원장"].fill == "#1F3864" and b["원장"].text_color == "#FFFFFF"
    assert any(c.border_type == "DASH" for c in grid.cells if not c.text)


def test_side_layout_reaches_the_document(policy, tmp_path):
    out = tmp_path / "side.hwpx"
    spec = parse_block("type=org layout=side", SIDE.splitlines())
    build_document(policy, [{"type": "diagram", "spec": spec.to_dict()}], str(out))
    with zipfile.ZipFile(str(out)) as zf:
        section = zf.read("Contents/section0.xml").decode("utf-8")
    assert "원장" in section and "기획팀" in section
    assert re.search(r'<hp:cellSpan colSpan="\d+" rowSpan="2"', section)
