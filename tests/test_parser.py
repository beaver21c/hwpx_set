from hwpx_studio.parser import parse_text


def keys(items):
    return [i.get("key") for i in items if i["type"] == "para"]


def test_markers_map_to_levels(policy):
    r = parse_text("# 장\n## 절\n□ 주제\n○ 주요\n- 설명\n· 세부\n※ 참고\n", policy)
    assert keys(r.items) == ["title", "title2", "L1", "L2", "L3", "L4", "L5"]


def test_negative_number_is_not_a_marker(policy):
    r = parse_text("○ 전년 대비 -3% 감소\n", policy)
    assert keys(r.items) == ["L2"]
    assert r.items[0]["text"] == "전년 대비 -3% 감소"


def test_duplicated_marker_warns_and_strips_once(policy):
    r = parse_text("□ □ 주제\n", policy)
    assert r.items[0]["text"] == "주제"
    assert any("중복" in w for w in r.warnings)


def test_markdown_table(policy):
    r = parse_text("\n| 구분 | 값 |\n|---|---|\n| 가 | 1 |\n\n", policy)
    tables = [i for i in r.items if i["type"] == "table"]
    assert len(tables) == 1
    assert tables[0]["rows"] == 2 and tables[0]["cols"] == 2
    assert tables[0]["data"] == ["구분", "값", "가", "1"]


def test_image_and_diagram_blocks(policy):
    text = "![](a.png)\n\n:::diagram type=org title=\"체계\"\n대표\n  기획부\n:::\n"
    r = parse_text(text, policy)
    kinds = [i["type"] for i in r.items]
    assert "image" in kinds and "diagram" in kinds
    spec = [i for i in r.items if i["type"] == "diagram"][0]["spec"]
    assert spec["type"] == "org" and spec["title"] == "체계"
    assert spec["lines"] == ["대표", "  기획부"]


def test_unmarked_line_falls_back_by_indent(policy):
    r = parse_text("주제 없음\n    깊은 줄\n", policy)
    assert keys(r.items) == ["L1", "L3"]
    assert len(r.warnings) == 2


def test_narrative_mode_keeps_body(narrative):
    r = parse_text("# 제목\n첫 문단이다.\n\n둘째 문단이다.\n", narrative)
    assert keys(r.items) == ["title", "body", "body"]
