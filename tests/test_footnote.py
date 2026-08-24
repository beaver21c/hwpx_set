"""각주: 문법 · 서식(8pt 회색) · 번호 자리 · 산출물 재확인."""

import re
import zipfile
from io import BytesIO

import pytest

from hwpx_studio.engine import build_document
from hwpx_studio.lint import lint_items
from hwpx_studio.parser import parse_text
from hwpx_studio.profile import merge_profile, validate_profile

SAMPLE = """□ 노인 빈곤율은 40.4%로 가장 높다[^1]
○ 두 번째 근거[^2]와 세 번째 근거[^3]

[^1]: 통계청(2024), 「가계금융복지조사」.
[^2]: 보건복지부(2025).
[^3]: OECD(2024), Pensions at a Glance.
"""


def part(data: bytes, name: str) -> str:
    with zipfile.ZipFile(BytesIO(data)) as zf:
        return zf.read(name).decode("utf-8")


def notes_of(data: bytes):
    """산출물에서 (번호, 각주 본문) 목록을 다시 읽는다."""
    section = part(data, "Contents/section0.xml")
    out = []
    for note in re.findall(r"<hp:footNote .*?</hp:footNote>", section, re.S):
        number = re.search(r'number="(\d+)"', note).group(1)
        body = re.search(r"<hp:t>(.*?)</hp:t>", note, re.S)
        out.append((number, body.group(1) if body else ""))
    return out


def codes(issues, code="footnote"):
    return [i.message for i in issues if i.code == code]


# ──────────────────────────────────────────────────────────────
# 문법
# ──────────────────────────────────────────────────────────────
def test_reference_and_definition_are_joined(policy):
    result = parse_text(SAMPLE, policy)
    first = result.items[0]
    assert first["text"] == "노인 빈곤율은 40.4%로 가장 높다"      # 자리표는 본문에서 빠진다
    assert [n["text"] for n in first["notes"]] == ["통계청(2024), 「가계금융복지조사」."]
    assert not result.warnings


def test_offset_marks_where_the_number_goes(policy):
    result = parse_text("□ 앞말[^1] 뒷말\n\n[^1]: 내용\n", policy)
    note = result.items[0]["notes"][0]
    assert result.items[0]["text"] == "앞말 뒷말"
    assert note["offset"] == 2 and note["before"] == "말" and note["after"] == " "


def test_two_notes_in_one_paragraph_keep_their_order(policy):
    notes = parse_text(SAMPLE, policy).items[1]["notes"]
    assert [n["label"] for n in notes] == ["2", "3"]
    assert [n["offset"] for n in notes] == [7, 16]


def test_definition_line_makes_no_paragraph(policy):
    items = parse_text(SAMPLE, policy).items
    assert all("통계청" not in str(item.get("text", "")) for item in items)
    assert [i["type"] for i in items] == ["para", "para", "blank"]


def test_missing_definition_is_reported_and_left_in_place(policy):
    result = parse_text("□ 근거 없음[^9]\n", policy)
    assert result.items[0]["text"] == "근거 없음[^9]"      # 조용히 지우지 않는다
    assert "notes" not in result.items[0]
    assert any("찾지 못함" in w for w in result.warnings)


def test_unused_definition_is_reported(policy):
    result = parse_text("□ 본문\n\n[^1]: 안 쓰는 각주\n", policy)
    assert any("부르지 않음" in w for w in result.warnings)


def test_definition_written_twice_is_reported(policy):
    result = parse_text("□ 글[^1]\n\n[^1]: 처음\n[^1]: 나중\n", policy)
    assert any("두 번 적힘" in w for w in result.warnings)
    assert result.items[0]["notes"][0]["text"] == "나중"


def test_calling_the_same_note_twice_is_reported(policy):
    result = parse_text("□ 하나[^1]와 둘[^1]\n\n[^1]: 같은 출처\n", policy)
    assert len(result.items[0]["notes"]) == 2
    assert any("두 번 이상 부름" in w for w in result.warnings)


def test_footnote_inside_a_table_is_refused_with_a_reason(policy):
    result = parse_text("| 구분 | 값 |\n| 계[^1] | 3 |\n\n[^1]: 내용\n", policy)
    assert any("표 안에는 각주를 달 수 없음" in w for w in result.warnings)


def test_footnote_inside_a_diagram_box_is_refused(policy):
    text = ":::diagram type=org\n추진단[^1]\n:::\n\n[^1]: 내용\n"
    result = parse_text(text, policy)
    assert any("도식 상자 안에는" in w for w in result.warnings)


# ──────────────────────────────────────────────────────────────
# 서식 — 8포인트 회색
# ──────────────────────────────────────────────────────────────
def test_note_text_is_8pt_grey(policy):
    data = build_document(policy, parse_text(SAMPLE, policy).items).data
    header = part(data, "Contents/header.xml")
    style = re.search(r'<hh:style id="(\d+)"[^>]*name="각주"[^>]*'
                      r'paraPrIDRef="(\d+)" charPrIDRef="(\d+)"', header)
    assert style, "각주 스타일이 header.xml에 없음"
    char = re.search(rf'<hh:charPr id="{style.group(3)}".*?</hh:charPr>', header, re.S).group()
    assert 'height="800"' in char                     # 8pt = 800 HWPUNIT
    assert 'textColor="#808080"' in char

    section = part(data, "Contents/section0.xml")
    note = re.search(r"<hp:footNote .*?</hp:footNote>", section, re.S).group()
    assert f'styleIDRef="{style.group(1)}"' in note    # 각주 본문이 그 스타일을 쓴다
    assert f'charPrIDRef="{style.group(3)}"' in note


def test_note_style_is_named_so_hangul_can_find_it(policy):
    """python-hwpx는 각주 스타일을 '이름'으로 찾는다. 없으면 없는 ID(15번)로 떨어진다."""
    header = part(build_document(policy, [("body", "글")]).data, "Contents/header.xml")
    assert re.search(r'name="각주" engName="Footnote"', header)


def test_note_size_and_colour_follow_the_profile(policy):
    profile = merge_profile({**policy, "footnote": {**policy["footnote"],
                                                    "size_pt": 9, "color": "#595959"}})
    data = build_document(profile, parse_text(SAMPLE, profile).items).data
    header = part(data, "Contents/header.xml")
    char_id = re.search(r'<hh:style id="\d+"[^>]*name="각주"[^>]*charPrIDRef="(\d+)"',
                        header).group(1)
    char = re.search(rf'<hh:charPr id="{char_id}".*?</hh:charPr>', header, re.S).group()
    assert 'height="900"' in char and 'textColor="#595959"' in char


@pytest.mark.parametrize("bad, needle", [
    ({"color": "회색"}, "footnote.color"),
    ({"size_pt": 0}, "footnote.size_pt"),
    ({"align": "MIDDLE"}, "footnote.align"),
])
def test_bad_footnote_profile_is_caught(policy, bad, needle):
    profile = merge_profile({**policy, "footnote": {**policy["footnote"], **bad}})
    assert any(needle in e for e in validate_profile(profile))


# ──────────────────────────────────────────────────────────────
# 산출물 재확인
# ──────────────────────────────────────────────────────────────
def test_document_carries_every_note_numbered_in_order(policy):
    data = build_document(policy, parse_text(SAMPLE, policy).items).data
    assert notes_of(data) == [
        ("1", "통계청(2024), 「가계금융복지조사」."),
        ("2", "보건복지부(2025)."),
        ("3", "OECD(2024), Pensions at a Glance."),
    ]


def test_number_lands_where_it_was_written(policy):
    """각주 앞 토막과 뒤 토막이 서로 다른 run으로 갈라져야 자리가 지켜진다."""
    items = parse_text("□ 앞말[^1] 뒷말\n\n[^1]: 내용\n", policy).items
    section = part(build_document(policy, items).data, "Contents/section0.xml")
    assert section.count("<hp:footNote ") == 1
    assert (section.index("<hp:t>□ 앞말</hp:t>")
            < section.index("<hp:footNote ")
            < section.index("</hp:footNote>")
            < section.index("<hp:t> 뒷말</hp:t>"))


def test_notes_read_back_with_python_hwpx(policy, tmp_path):
    """직접 만든 XML이 아니라, 표준 판독기로 다시 읽어 확인한다."""
    from hwpx.document import HwpxDocument

    out = tmp_path / "fn.hwpx"
    build_document(policy, parse_text(SAMPLE, policy).items, str(out))
    doc = HwpxDocument.open(str(out))
    found = [note for para in doc.sections[0].paragraphs for note in para.footnotes]
    assert len(found) == 3
    assert "가계금융복지조사" in found[0].text


def test_auto_numbered_heading_prefix_does_not_shift_the_number(policy):
    """'Ⅰ. ' 같은 자동 접두어가 붙어도 번호 자리는 그대로여야 한다."""
    items = parse_text("# 제목\n\n□ 본문 끝말[^1]\n\n[^1]: 내용\n", policy).items
    section = part(build_document(policy, items).data, "Contents/section0.xml")
    assert "<hp:t>□ 본문 끝말</hp:t><hp:ctrl><hp:footNote " in section


def test_document_without_notes_is_unchanged(policy):
    section = part(build_document(policy, [("body", "각주 없는 글")]).data,
                   "Contents/section0.xml")
    assert "<hp:footNote " not in section


# ──────────────────────────────────────────────────────────────
# 번호 자리 검사
# ──────────────────────────────────────────────────────────────
def lint_text(text, profile):
    result = parse_text(text, profile)
    return lint_items(result.items, profile, result.line_of, result.warnings)


def test_number_after_the_full_stop_is_flagged(policy):
    assert any("마침표 앞에 붙일 것" in m
               for m in codes(lint_text("□ 문장이다.[^1]\n\n[^1]: 내용\n", policy)))


def test_number_before_the_full_stop_is_accepted(policy):
    assert codes(lint_text("□ 문장이다[^1].\n\n[^1]: 내용\n", policy)) == []


def test_chicago_style_can_be_chosen(policy):
    profile = merge_profile({**policy, "rules": {**policy["rules"],
                                                 "footnote_position": "after_period"}})
    assert any("마침표 뒤에 붙일 것" in m
               for m in codes(lint_text("□ 문장이다[^1].\n\n[^1]: 내용\n", profile)))
    assert codes(lint_text("□ 문장이다.[^1]\n\n[^1]: 내용\n", profile)) == []


def test_space_before_the_number_is_flagged(policy):
    assert any("붙여 쓸 것" in m
               for m in codes(lint_text("□ 앞말 [^1]\n\n[^1]: 내용\n", policy)))


def test_both_sides_of_a_quotation_mark_are_left_alone(policy):
    """각주가 인용문을 가리키는지 문장을 가리키는지는 도구가 알 수 없다 → 검사하지 않는다."""
    inside = '□ 그는 "구조적 문제다[^1]"라고 한다\n\n[^1]: 내용\n'
    outside = '□ 그는 "구조적 문제"[^1]라는 진단을 한다\n\n[^1]: 내용\n'
    assert codes(lint_text(inside, policy)) == []
    assert codes(lint_text(outside, policy)) == []


def test_number_inside_a_quotation_lands_inside_the_quotation(policy):
    """따옴표 안에 쓴 번호는 닫는 따옴표 앞에 그대로 놓여야 한다."""
    items = parse_text('□ 그는 "구조적 문제다[^1]"라고 한다\n\n[^1]: 내용\n', policy).items
    assert items[0]["text"] == '그는 "구조적 문제다"라고 한다'
    section = part(build_document(policy, items).data, "Contents/section0.xml")
    assert (section.index('<hp:t>□ 그는 "구조적 문제다</hp:t>')
            < section.index("<hp:footNote ")
            < section.index("</hp:footNote>")
            < section.index('<hp:t>"라고 한다</hp:t>'))


def test_note_on_a_heading_is_flagged(policy):
    assert any("제목에 각주" in m
               for m in codes(lint_text("# 제목[^1]\n\n[^1]: 내용\n", policy)))


def test_label_that_disagrees_with_the_printed_number_is_flagged(policy):
    text = "□ 하나[^2]\n○ 둘[^1]\n\n[^1]: 가\n[^2]: 나\n"
    assert any("문서 순서로는" in m for m in codes(lint_text(text, policy)))


def test_labels_written_in_order_raise_nothing(policy):
    assert codes(lint_text(SAMPLE, policy)) == []


def test_position_check_can_be_switched_off(policy):
    profile = merge_profile({**policy, "rules": {**policy["rules"],
                                                 "footnote_position": "off"}})
    assert not any("마침표" in m
                   for m in codes(lint_text("□ 문장이다.[^1]\n\n[^1]: 내용\n", profile)))
