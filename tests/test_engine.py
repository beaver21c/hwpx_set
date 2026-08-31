import re
import zipfile
from io import BytesIO
from pathlib import Path

from hwpx_studio.engine import build_document, normalize_contents, plan_ids
from hwpx_studio.parser import parse_text
from hwpx_studio.profile import load_profile, merge_profile


def read_part(data, name):
    return zipfile.ZipFile(BytesIO(data)).read(name).decode("utf-8")


def test_normalize_legacy_tuples(policy):
    items = normalize_contents(
        [("title", "장"), (1, "네모"), (0, ""), ("table", [1, 2, ["가", "나"]]),
         ("image", "a.png")], policy)
    assert [i["type"] for i in items] == ["para", "para", "blank", "table", "image"]
    assert items[1]["key"] == "L1"


def test_ids_are_allocated_after_template_items(policy):
    header = ('<hh:charProperties itemCnt="7"><hh:charPr id="6"/></hh:charProperties>'
              '<hh:paraProperties itemCnt="20"><hh:paraPr id="19"/></hh:paraProperties>'
              '<hh:borderFills itemCnt="2"><hh:borderFill id="2"/></hh:borderFills>')
    ids = plan_ids(header, policy)
    assert min(ids.chars.values()) == 7
    assert min(ids.paras.values()) == 20
    assert ids.border_base == 3
    assert len(set(ids.chars.values())) == len(ids.chars)   # 중복 없음


def test_itemcnt_matches_actual_items(policy):
    data = build_document(policy, [("title", "제목")]).data
    header = read_part(data, "Contents/header.xml")
    for container, item in (("charProperties", "hh:charPr"),
                            ("paraProperties", "hh:paraPr"),
                            ("borderFills", "hh:borderFill"),
                            ("styles", "hh:style")):
        cnt = int(re.search(rf'<hh:{container}[^>]*itemCnt="(\d+)"', header).group(1))
        block = re.search(rf"<hh:{container}\b.*?</hh:{container}>", header, re.S).group()
        assert cnt == len(re.findall(rf'<{item} id="', block)), container


def test_auto_numbering_resets_per_chapter(policy):
    contents = [("title", "가"), ("title2", "하나"), ("title2", "둘"),
                ("title", "나"), ("title2", "셋")]
    data = build_document(policy, contents).data
    texts = re.findall(r"<hp:t>(.*?)</hp:t>", read_part(data, "Contents/section0.xml"))
    assert texts == ["Ⅰ. 가", "1. 하나", "2. 둘", "Ⅱ. 나", "1. 셋"]


def test_table_header_row_uses_table_top_style(policy):
    data = build_document(policy, [("table", [2, 2, ["머리1", "머리2", "값1", "값2"]])]).data
    section = read_part(data, "Contents/section0.xml")
    header_cell = re.search(r'<hp:tc\b[^>]*>(?:(?!</hp:tc>).)*rowAddr="0"'
                            r'(?:(?!</hp:tc>).)*</hp:tc>', section, re.S)
    assert header_cell is not None


def test_variable_level_count_builds(policy):
    trimmed = merge_profile({**policy, "levels": policy["levels"][:3],
                             "table": {**policy["table"], "anchor_level": "L1"},
                             "rules": {"min_children": {}}})
    data = build_document(trimmed, [("title", "장"), (1, "주제")]).data
    assert len(data) > 0
    header = read_part(data, "Contents/header.xml")
    # 바탕글 + 레벨 3 + 표 3 + 본문 + 각주 = 9
    assert re.search(r'<hh:styles itemCnt="9"', header)


def test_signature_is_off_by_default(policy):
    data = build_document(policy, [("title", "장")]).data
    ids_used = read_part(data, "Contents/header.xml")
    assert "signature" not in ids_used
    section = read_part(data, "Contents/section0.xml")
    assert len(re.findall(r"<hp:t>", section)) == 1


# ──────────────────────────────────────────────────────────────
# 연구보고서 서식 — 장·절 번호와 표·그림 번호
# ──────────────────────────────────────────────────────────────
_PROFILES = Path(__file__).resolve().parent.parent / "hwpx_studio" / "profiles"


def _research_profile():
    return load_profile(str(_PROFILES / "kihasa-research.json"))


def _research_texts(source: str):
    profile = _research_profile()
    parsed = parse_text(source, profile)
    data = build_document(profile, parsed.items).data
    with zipfile.ZipFile(BytesIO(data)) as zf:
        section = zf.read("Contents/section0.xml").decode("utf-8")
    return [t for t in re.findall(r"<hp:t>([^<]*)</hp:t>", section) if t], section, parsed


def test_chapter_and_section_numbers_are_written():
    texts, _section, _parsed = _research_texts(
        "# 배경\n## 필요성\n### 문제\n#### 갈래\n##### 세부\n")
    assert texts[:5] == ["제1장 배경", "제1절 필요성", "1. 문제", "가. 갈래", "1) 세부"]


def test_table_number_follows_the_chapter():
    """〈표 1-1〉의 앞자리는 장 번호다. 장이 바뀌면 표 번호도 다시 센다."""
    texts, _section, _parsed = _research_texts(
        "# 첫 장\n표) 첫 표\n표) 둘째 표\n# 둘째 장\n표) 셋째 표\n그림) 첫 그림\n")
    captions = [t for t in texts if t.startswith(("〈표", "〔그림"))]
    assert captions == ["〈표 1-1〉 첫 표", "〈표 1-2〉 둘째 표",
                        "〈표 2-1〉 셋째 표", "〔그림 2-1〕 첫 그림"]


def test_body_text_needs_no_marker_and_is_not_warned():
    """이 서식은 본문에 기호를 쓰지 않는다. 마커 없는 줄이 제자리를 찾는다."""
    texts, _section, parsed = _research_texts("### 문제\n본문 내용이다.\n")
    assert "본문 내용이다." in texts
    assert not any("마커 없는 줄" in w for w in parsed.warnings), parsed.warnings


def test_table_note_lines_drop_the_input_marker():
    """※는 입력에서 부르는 이름일 뿐, 문서에는 '주:'·'출처:'만 남는다."""
    texts, _section, _parsed = _research_texts("※ 주: 12월 말 기준이다.\n")
    assert "주: 12월 말 기준이다." in texts
    assert not any(t.startswith("※") for t in texts)


def test_unnumbered_levels_do_not_trip_the_outline_check():
    """본문·주는 어느 제목 밑에나 온다. 레벨 점프로 잡으면 안 된다."""
    from hwpx_studio.lint import lint_items

    profile = _research_profile()
    parsed = parse_text("# 장\n본문이다.\n#### 가 제목\n※ 주: 딸린 줄이다.\n", profile)
    issues = lint_items(parsed.items, profile, parsed.line_of, parsed.warnings)
    assert not [i for i in issues if i.code == "jump"], [i.format() for i in issues]


# ──────────────────────────────────────────────────────────────
# 문단·글자 모양이 실제로 XML까지 가는가
# ──────────────────────────────────────────────────────────────
def _para_and_char(profile, source, needle):
    """`needle`이 든 문단의 (paraPr XML, charPr XML)."""
    parsed = parse_text(source, profile)
    data = build_document(profile, parsed.items).data
    header = read_part(data, "Contents/header.xml")
    section = read_part(data, "Contents/section0.xml")
    look = r"(?=(?:(?!</hp:p>).)*" + re.escape(needle) + ")"
    tag = re.search(r"<hp:p [^>]*>" + look, section, re.S).group(0)
    pid = re.search(r'paraPrIDRef="(\d+)"', tag).group(1)
    cid = re.search(r'<hp:run charPrIDRef="(\d+)"' + look, section, re.S).group(1)
    return (re.search(r'<hh:paraPr id="%s"[ >].*?</hh:paraPr>' % pid, header, re.S).group(0),
            re.search(r'<hh:charPr id="%s"[ >].*?</hh:charPr>' % cid, header, re.S).group(0))


def test_body_first_line_indent_reaches_the_document():
    """`first_line_indent_pt`가 선언만 되고 버려지면 서술식 서식이 무너진다."""
    profile = load_profile(str(_PROFILES / "narrative.json"))
    para, _char = _para_and_char(profile, "# 제목\n\n서술식 본문이다.\n", "서술식 본문이다.")
    intent = int(re.search(r'<hc:intent value="(-?\d+)"', para).group(1))
    assert intent == 1000, f"첫 줄 들여쓰기 10pt가 안 들어갔다: {intent}"


def test_hanging_indent_goes_in_negative():
    """내어쓰기는 음수 intent다. 첫 줄 들여쓰기와 한 값을 다툰다."""
    profile = merge_profile(load_profile(str(_PROFILES / "narrative.json")))
    profile["body"]["indent_pt"] = 12
    para, _char = _para_and_char(profile, "# 제목\n\n서술식 본문이다.\n", "서술식 본문이다.")
    assert '<hc:intent value="-1200"' in para


def test_letter_spacing_and_space_above_reach_the_document():
    profile = merge_profile(load_profile(str(_PROFILES / "narrative.json")))
    profile["body"]["letter_spacing"] = -2
    profile["body"]["spacing_above_pt"] = 15
    para, char = _para_and_char(profile, "# 제목\n\n서술식 본문이다.\n", "서술식 본문이다.")
    assert '<hh:spacing hangul="-2"' in char
    assert '<hc:prev value="1500"' in para


def test_page_size_from_the_profile_reaches_the_document():
    """용지 이름이 선언만 되고 안 쓰이면 크라운판이 A4로 나간다."""
    from hwpx_studio.units import mm

    profile = _research_profile()
    parsed = parse_text("### 제목\n본문이다.\n", profile)
    section = read_part(build_document(profile, parsed.items).data, "Contents/section0.xml")
    width, height = re.search(r'width="(\d+)" height="(\d+)"', section).groups()
    assert (int(width), int(height)) == (mm(166), mm(241)), "용지가 크라운판이 아니다"


def test_paper_names_cover_the_korean_report_sizes():
    from hwpx_studio.engine import paper_mm

    assert paper_mm({"size": "크라운판"}) == (166.0, 241.0)
    assert paper_mm({"size": "A4"}) == (210.0, 297.0)
    assert paper_mm({"width_mm": 166, "height_mm": 241}) == (166.0, 241.0)
    assert paper_mm({"size": "없는판형"}) is None      # 모르면 손대지 않는다
