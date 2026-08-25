import re
import zipfile
from io import BytesIO

from hwpx_studio.engine import build_document, normalize_contents, plan_ids
from hwpx_studio.profile import merge_profile


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
