"""양식 해부(formkit)와 양식 보존 빌더(build_form) 시험.

이 방식의 주장은 하나다. **양식의 서식을 재현하지 않고 보존한다.**
그래서 시험도 거기에 걸려 있다.

  - `header.xml`이 한 바이트도 바뀌지 않는가
  - 용지 설정·표지가 든 앞부분이 그대로 남는가
  - 한글이 기호를 자동으로 붙이는 양식에서 기호가 두 번 찍히지 않는가
  - 만든 문서를 표준 판독기로 다시 읽을 수 있는가

한글에서 실제로 열어 보는 일은 이 시험이 대신하지 못한다.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from formfixtures import (
    auto_bullet_form, chapter_form, plain_form, table_note_form)
from hwpx_studio import formkit
from hwpx_studio.export_form import BUILDER, FORM_JSON, TEMPLATE, build_bundle, pack_bundle

SAMPLE_INPUT = """# 사업 추진 현황
## 추진 개요
□ 추진 배경 및 목적
○ 처리 기간이 길어 이용자 불편이 누적되었다[^1]

| 구분 | 2024년 | 2025년 |
|---|---|---|
| 처리 건수 | 1,204건 | 1,388건 |

[^1]: 통계청(2025), 「행정통계」, 87쪽.
"""


# ──────────────────────────────────────────────────────────────
# 해부
# ──────────────────────────────────────────────────────────────
def test_auto_bullet_is_found_in_the_form():
    """한글이 자동으로 붙이는 글머리표를 찾아낸다. 이 방식의 존재 이유다."""
    result = formkit.analyze(auto_bullet_form(), "자동")
    box = next(lv for lv in result.form["levels"] if lv["name"] == "네모")
    assert box["auto_bullet"] == "□"
    assert box["marker"] == "□"
    assert box["write_marker"] is False, "한글이 붙이는데 도구도 붙이면 이중이 된다"


def test_auto_numbering_is_found_in_the_form():
    result = formkit.analyze(auto_bullet_form(), "자동")
    top = next(lv for lv in result.form["levels"] if lv["name"] == "로마자")
    assert top["auto_number"], "한글 번호매기기를 읽어야 한다"
    assert top["numbering"] is None, "한글이 매기면 도구는 매기지 않는다"


def test_symbol_written_in_text_is_kept_that_way():
    """기호가 본문 텍스트에 적힌 양식은 도구가 그대로 적어 넣는다."""
    result = formkit.analyze(plain_form(), "평범")
    box = next(lv for lv in result.form["levels"] if lv["name"] == "네모")
    assert box["auto_bullet"] is None
    assert box["write_marker"] is True


def test_levels_without_evidence_get_a_marker_and_a_warning():
    """근거가 없어도 부를 수단은 준다. 다만 지어냈다고 말한다."""
    result = formkit.analyze(auto_bullet_form(), "자동")
    dot = next(lv for lv in result.form["levels"] if lv["name"] == "점")
    assert dot["marker"], "입력에서 부를 마커가 있어야 한다"
    assert dot["marker_invented"] is True
    assert dot["write_marker"] is False, "없던 기호를 새로 찍으면 안 된다"
    assert any("임의로 정했다" in note for note in result.form["notes"])


def test_footnote_paragraphs_are_not_counted_as_body_levels():
    """각주 본문은 본문 레벨이 아니다."""
    result = formkit.analyze(plain_form(), "평범")
    assert not any(lv["name"] == "각주" for lv in result.form["levels"])


def test_table_skeleton_separates_header_row():
    result = formkit.analyze(plain_form(), "평범")
    table = result.form["table"]
    assert table["guessed"] is False
    assert table["header_fill"] != table["body_fill"], "머리행 강조를 읽어야 한다"
    assert table["width"] > 0


def test_footnote_style_is_found_by_name():
    """한글은 각주 스타일을 이름으로 찾는다. 해부도 이름으로 찾는다."""
    result = formkit.analyze(plain_form(), "평범")
    assert result.form["footnote"] is not None


def test_binary_hwp_is_refused_with_a_useful_message():
    data = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"0" * 64
    with pytest.raises(ValueError) as err:
        formkit.analyze(data, "이상한파일")
    assert "hwpx" in str(err.value)


# ──────────────────────────────────────────────────────────────
# 꾸러미
# ──────────────────────────────────────────────────────────────
def _bundle(tmp_path: Path, data: bytes, name: str) -> Path:
    files, _ = build_bundle(data, name=name)
    out = tmp_path / name
    out.mkdir(parents=True, exist_ok=True)
    for filename, blob in files.items():
        (out / filename).write_bytes(blob)
    return out


def test_bundle_carries_everything_needed_to_run_elsewhere(tmp_path):
    files, _ = build_bundle(plain_form(), name="평범")
    for need in (TEMPLATE, FORM_JSON, BUILDER, "SKILL.md", "AGENTS.md", "README.md"):
        assert need in files, f"{need}가 빠지면 다른 곳에서 못 쓴다"


def test_skill_frontmatter_is_valid(tmp_path):
    files, _ = build_bundle(plain_form(), name="평범 보고서")
    text = files["SKILL.md"].decode("utf-8")
    assert text.startswith("---\n")
    front = text.split("---", 2)[1]
    assert re.search(r"^name: [a-z0-9-]+$", front, re.M), "스킬 이름은 소문자·하이픈만"
    assert "description:" in front


def test_packed_bundle_opens_as_a_zip():
    files, result = build_bundle(plain_form(), name="평범")
    data = pack_bundle(files, result.form["name"])
    with zipfile.ZipFile(__import__("io").BytesIO(data)) as z:
        names = z.namelist()
    assert f"평범/{BUILDER}" in names


# ──────────────────────────────────────────────────────────────
# 빌드 — 보존이 지켜지는가
# ──────────────────────────────────────────────────────────────
def _run(bundle: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(bundle / BUILDER), *args],
        cwd=bundle, capture_output=True, text=True, timeout=120)


def _build(tmp_path: Path, data: bytes, name: str,
           source: str = SAMPLE_INPUT) -> tuple[Path, Path]:
    bundle = _bundle(tmp_path, data, name)
    (bundle / "원고.md").write_text(source, encoding="utf-8")
    done = _run(bundle, "원고.md", "-o", "결과.hwpx")
    assert done.returncode == 0, done.stdout + done.stderr
    return bundle, bundle / "결과.hwpx"


def test_header_is_not_touched_at_all(tmp_path):
    """이 방식의 핵심 주장. 서식 정의는 한 바이트도 바뀌지 않는다."""
    bundle, out = _build(tmp_path, plain_form(), "평범")
    with zipfile.ZipFile(bundle / TEMPLATE) as a, zipfile.ZipFile(out) as b:
        assert a.read("Contents/header.xml") == b.read("Contents/header.xml")


def test_preamble_of_the_section_is_preserved(tmp_path):
    """용지 설정(secPr)과 표지가 든 앞부분이 그대로 남는다."""
    bundle, out = _build(tmp_path, plain_form(), "평범")
    form = json.loads((bundle / FORM_JSON).read_text(encoding="utf-8"))
    with zipfile.ZipFile(bundle / TEMPLATE) as a, zipfile.ZipFile(out) as b:
        head = a.read(form["section"]).decode("utf-8")[:form["preamble_bytes"]]
        assert b.read(form["section"]).decode("utf-8").startswith(head)
    assert "<hp:secPr" in head


def test_auto_bullet_form_does_not_write_the_symbol(tmp_path):
    """기호를 한글이 붙이는 양식에서는 본문에 기호를 넣지 않는다."""
    _bundle_dir, out = _build(tmp_path, auto_bullet_form(), "자동")
    with zipfile.ZipFile(out) as z:
        texts = re.findall(r"<hp:t>([^<]*)</hp:t>",
                           z.read("Contents/section0.xml").decode("utf-8"))
    body = [t for t in texts if t]
    assert "추진 배경 및 목적" in body
    assert not any(t.startswith(("□ ", "○ ")) for t in body), body


def test_plain_form_does_write_the_symbol(tmp_path):
    _bundle_dir, out = _build(tmp_path, plain_form(), "평범")
    with zipfile.ZipFile(out) as z:
        texts = re.findall(r"<hp:t>([^<]*)</hp:t>",
                           z.read("Contents/section0.xml").decode("utf-8"))
    assert "□ 추진 배경 및 목적" in texts


def test_double_symbol_is_caught_before_the_file_is_written(tmp_path):
    """한글이 붙이는 양식에 기호를 또 쓰면 1층에서 알린다."""
    bundle = _bundle(tmp_path, auto_bullet_form(), "자동")
    (bundle / "원고.md").write_text("□ □ 기호를 두 번 썼다\n", encoding="utf-8")
    done = _run(bundle, "원고.md", "--check-only")
    assert "기호를 또 쓰지 말 것" in done.stdout
    assert done.returncode == 1


def test_unknown_style_id_stops_the_build(tmp_path):
    """양식에 없는 번호를 가리키면 파일을 만들지 않는다."""
    bundle = _bundle(tmp_path, plain_form(), "평범")
    form = json.loads((bundle / FORM_JSON).read_text(encoding="utf-8"))
    form["levels"][2]["style"] = 9999
    (bundle / FORM_JSON).write_text(json.dumps(form, ensure_ascii=False), encoding="utf-8")
    (bundle / "원고.md").write_text("□ 내용\n", encoding="utf-8")
    done = _run(bundle, "원고.md", "-o", "결과.hwpx")
    assert done.returncode == 2, done.stdout
    assert "참조 오류" in done.stdout
    assert not (bundle / "결과.hwpx").exists(), "검사에 걸리면 파일을 남기지 않는다"


def test_table_and_footnote_survive_a_round_trip(tmp_path):
    """만든 문서를 표준 판독기로 다시 읽어 확인한다."""
    from hwpx.document import HwpxDocument

    _bundle_dir, out = _build(tmp_path, plain_form(), "평범")
    doc = HwpxDocument.open(str(out))
    paragraphs = list(doc.paragraphs)
    notes = [n for p in paragraphs for n in getattr(p, "footnotes", [])]
    assert len(notes) == 1
    assert "통계청" in notes[0].text
    with zipfile.ZipFile(out) as z:
        section = z.read("Contents/section0.xml").decode("utf-8")
    assert section.count("<hp:tbl ") == 1
    assert "1,204건" in section


def test_footnote_number_lands_where_it_was_written(tmp_path):
    """번호 앞뒤가 서로 다른 run으로 갈라져야 자리가 지켜진다."""
    source = '□ 보고서는 "구조적 문제다[^1]"라고 진단했다\n\n[^1]: 출처.\n'
    _bundle_dir, out = _build(tmp_path, plain_form(), "평범", source)
    with zipfile.ZipFile(out) as z:
        section = z.read("Contents/section0.xml").decode("utf-8")
    assert "<hp:t>□ 보고서는 &quot;구조적 문제다</hp:t>" in section \
        or "<hp:t>□ 보고서는 \"구조적 문제다</hp:t>" in section
    note = section.index("<hp:footNote ")
    tail = section.index("라고 진단했다")
    assert note < tail, "각주는 닫는 따옴표 앞에 놓여야 한다"


def test_markers_can_be_listed_without_writing_anything(tmp_path):
    bundle = _bundle(tmp_path, plain_form(), "평범")
    done = _run(bundle, "--markers")
    assert done.returncode == 0
    assert "| 마커 |" in done.stdout
    assert "□" in done.stdout


def test_builder_needs_no_third_party_package(tmp_path):
    """다른 사람의 컴퓨터·AI 샌드박스에서 그냥 돌아야 한다."""
    source = (Path(__file__).resolve().parent.parent
              / "hwpx_studio" / "assets" / BUILDER).read_text(encoding="utf-8")
    imported = set(re.findall(r"^\s*(?:import|from)\s+([\w.]+)", source, re.M))
    allowed = {"argparse", "io", "json", "re", "sys", "xml.dom.minidom", "zipfile",
               "dataclasses", "pathlib", "typing", "__future__"}
    assert imported <= allowed, f"바깥 의존성: {imported - allowed}"


def test_extract_points_at_formkit_when_the_form_uses_auto_bullets():
    """프로파일 방식이 못 옮기는 양식이면 그 사실을 말하고 다른 길을 알려 준다."""
    from hwpx_studio.extractor import extract_profile

    warned = extract_profile(auto_bullet_form()).notes
    assert any("formkit" in note for note in warned)
    assert not any("formkit" in note for note in extract_profile(plain_form()).notes)


# ──────────────────────────────────────────────────────────────
# 줄머리 기호를 누가 붙이나 — 고를 수 있어야 한다
# ──────────────────────────────────────────────────────────────
def test_bullet_source_can_be_chosen_against_the_evidence():
    """해부가 정한 값을 사람이 뒤집을 수 있다."""
    auto = formkit.analyze(auto_bullet_form(), "자동", bullets="auto")
    box = next(lv for lv in auto.form["levels"] if lv["name"] == "네모")
    assert box["write_marker"] is False

    forced = formkit.analyze(auto_bullet_form(), "자동", bullets="text")
    box = next(lv for lv in forced.form["levels"] if lv["name"] == "네모")
    assert box["write_marker"] is True
    assert forced.form["bullet_source"] == "text"


def test_choosing_text_on_an_auto_bullet_form_says_it_will_double():
    result = formkit.analyze(auto_bullet_form(), "자동", bullets="text")
    assert any("두 번 찍힌다" in note for note in result.form["notes"])


def test_choosing_hangul_on_a_form_without_bullets_says_it_will_vanish():
    result = formkit.analyze(plain_form(), "평범", bullets="hangul")
    assert any("찍히지 않는다" in note for note in result.form["notes"])
    box = next(lv for lv in result.form["levels"] if lv["name"] == "네모")
    assert box["write_marker"] is False


def test_heading_levels_are_untouched_by_the_choice():
    """제목은 번호매기기가 따로 있다. 글머리표 선택이 건드리면 안 된다."""
    for mode in ("auto", "hangul", "text"):
        result = formkit.analyze(auto_bullet_form(), "자동", bullets=mode)
        top = next(lv for lv in result.form["levels"] if lv["name"] == "로마자")
        assert top["write_marker"] is False, mode
        assert top["numbering"] is None, mode


def test_unknown_bullet_source_is_refused():
    with pytest.raises(ValueError) as err:
        formkit.analyze(plain_form(), "평범", bullets="아무거나")
    assert "auto" in str(err.value)


def test_builder_can_change_the_choice_at_build_time(tmp_path):
    """꾸러미를 다시 만들지 않고 --bullets로 바꿀 수 있다."""
    bundle = _bundle(tmp_path, auto_bullet_form(), "자동")
    (bundle / "원고.md").write_text("□ 기호 없이 쓴 줄\n", encoding="utf-8")

    done = _run(bundle, "원고.md", "-o", "맡김.hwpx")
    assert done.returncode == 0, done.stdout
    with zipfile.ZipFile(bundle / "맡김.hwpx") as z:
        texts = re.findall(r"<hp:t>([^<]*)</hp:t>",
                           z.read("Contents/section0.xml").decode("utf-8"))
    assert "기호 없이 쓴 줄" in texts, "한글에 맡기면 기호를 적지 않는다"

    forced = _run(bundle, "원고.md", "-o", "도구가.hwpx", "--bullets", "text")
    assert forced.returncode == 2, forced.stdout
    assert "두 번 찍힌다" in forced.stdout
    assert "이중 기호" in forced.stdout
    assert not (bundle / "도구가.hwpx").exists(), "기호가 겹치는 문서를 남기지 않는다"


def test_builder_warns_when_the_symbol_would_vanish(tmp_path):
    bundle = _bundle(tmp_path, plain_form(), "평범")
    (bundle / "원고.md").write_text("□ 내용\n", encoding="utf-8")
    done = _run(bundle, "원고.md", "--check-only", "--bullets", "hangul")
    assert "찍히지 않는다" in done.stdout


def test_marker_table_reflects_the_choice(tmp_path):
    bundle = _bundle(tmp_path, plain_form(), "평범")
    listed = _run(bundle, "--markers", "--bullets", "hangul")
    assert listed.returncode == 0
    assert "찍히지 않는다" in listed.stdout


# ──────────────────────────────────────────────────────────────
# 표 번호·표 주·장 표지·쪽 설정
# ──────────────────────────────────────────────────────────────
def test_page_setup_is_read_and_reported():
    """쪽 설정은 보존 구간에 있어 그대로 지켜진다. 무엇이 지켜지는지 보여 준다."""
    result = formkit.analyze(plain_form(), "평범")
    page = result.form["page"]
    assert page["size"] == "A4"
    assert page["orientation"] == "세로"
    assert page["margin_mm"]["left"] == 20.0
    assert "용지 A4 세로" in result.report


def test_footnote_shape_is_read_from_the_section():
    """각주 번호 모양·구분선은 구역 설정에 있다. 문단 스타일이 아니다."""
    result = formkit.analyze(plain_form(), "평범")
    shape = result.form["footnote"]["shape"]
    assert shape["suffix_char"] == ")"
    assert shape["number_format"] == "DIGIT"
    assert result.form["footnote"]["size_pt"] == 8.0
    assert result.form["footnote"]["color"] == "#808080"
    assert "번호 모양 `n)`" in result.report


def test_table_note_style_is_taken_out_of_the_levels():
    """표 주는 본문 레벨이 아니다. 빼내지 않으면 ※ 마커가 겹친다."""
    result = formkit.analyze(table_note_form(), "표주")
    note = result.form["table_note"]
    assert note is not None
    assert note["name"] == "표 주"
    assert note["marker"] == "※"
    assert "※" not in [lv["marker"] for lv in result.form["levels"]]
    assert any("표 주" in text for text in result.form["notes"])


def test_ordinary_form_has_no_table_note():
    """자리도 이름도 근거가 없으면 표 주로 보지 않는다."""
    assert formkit.analyze(plain_form(), "평범").form["table_note"] is None


def test_chapter_cover_is_found_in_the_preamble():
    result = formkit.analyze(chapter_form(), "장양식")
    chapter = result.form["chapter"]
    assert chapter["roman"] == "Ⅱ"
    assert chapter["title"] == "옛 장 제목"
    assert chapter["has_container"] is True
    assert "장 표지" in result.report


def test_drawing_container_text_is_not_a_body_level():
    """표지 글자를 본문으로 세면 보존 구간이 통째로 잘려 나간다."""
    result = formkit.analyze(chapter_form(), "장양식")
    assert not any(lv["name"] == "바탕글" for lv in result.form["levels"])
    assert result.form["preamble_bytes"] > 3000


def test_caption_keeps_the_chapter_roman_and_drops_the_sample_title():
    caption = formkit.analyze(chapter_form(), "장양식").form["table"]["caption"]
    assert caption["chapter_roman"] == "Ⅱ"
    assert caption["before"] == "<표 Ⅱ-"
    assert caption["after"] == "> ", "양식의 표본 제목이 새 제목 앞에 남으면 안 된다"


def test_chapter_number_changes_cover_and_table_number(tmp_path):
    bundle = _bundle(tmp_path, chapter_form(), "장양식")
    (bundle / "원고.md").write_text(
        "[장: 정책 추진 현황]\n\n□ 실적\n\n[표: 연도별 실적]\n"
        "| 구분 | 값 |\n|---|---|\n| 합계 | 100 |\n\n", encoding="utf-8")
    done = _run(bundle, "원고.md", "-o", "결과.hwpx", "--chapter", "4")
    assert done.returncode == 0, done.stdout

    with zipfile.ZipFile(bundle / "결과.hwpx") as z:
        section = z.read("Contents/section0.xml").decode("utf-8")
    assert "<hp:t>Ⅳ</hp:t>" in section, "표지 로마자가 바뀌어야 한다"
    assert "<hp:t>Ⅳ. 정책 추진 현황</hp:t>" in section
    assert "&lt;표 Ⅳ-" in section, "표 번호 접두도 같이 바뀌어야 한다"
    assert "&gt; 연도별 실적" in section
    assert "옛 표 제목" not in section


def test_table_note_lands_in_its_own_style(tmp_path):
    bundle = _bundle(tmp_path, table_note_form(), "표주")
    (bundle / "원고.md").write_text(
        "□ 실적\n\n| 구분 | 값 |\n|---|---|\n| 합계 | 100 |\n"
        "※ 자료：통계청(2025).\n\n", encoding="utf-8")
    done = _run(bundle, "원고.md", "-o", "결과.hwpx")
    assert done.returncode == 0, done.stdout
    assert "표 뒤에 빈 줄이 없다" not in done.stdout, "표 주는 표에 딸린 줄이다"

    form = json.loads((bundle / FORM_JSON).read_text(encoding="utf-8"))
    with zipfile.ZipFile(bundle / "결과.hwpx") as z:
        section = z.read("Contents/section0.xml").decode("utf-8")
    note_style = form["table_note"]["style"]
    assert re.search(rf'styleIDRef="{note_style}"[^>]*>.*?자료：통계청', section, re.S)


def test_table_note_away_from_a_table_is_reported(tmp_path):
    bundle = _bundle(tmp_path, table_note_form(), "표주")
    (bundle / "원고.md").write_text("□ 표가 없는데 자료 줄\n※ 자료：어디에도 안 붙는다\n",
                                    encoding="utf-8")
    done = _run(bundle, "원고.md", "--check-only")
    assert "표 바로 아래에 두는 줄" in done.stdout


def test_caption_without_a_place_in_the_form_is_reported(tmp_path):
    """캡션 자리가 없는 양식에서 [표: …]를 쓰면 조용히 버리지 않는다."""
    bundle = _bundle(tmp_path, plain_form(), "평범")
    (bundle / "원고.md").write_text(
        "□ 실적\n\n[표: 넣을 데가 없는 제목]\n| 구분 | 값 |\n|---|---|\n| 합계 | 100 |\n\n",
        encoding="utf-8")
    done = _run(bundle, "원고.md", "--check-only")
    assert "표 제목(캡션) 자리가 없어" in done.stdout


def test_chapter_directive_without_a_cover_is_reported(tmp_path):
    bundle = _bundle(tmp_path, plain_form(), "평범")
    (bundle / "원고.md").write_text("[장: 없는 표지]\n\n□ 내용\n", encoding="utf-8")
    done = _run(bundle, "원고.md", "--check-only")
    assert "장 표지가 없다" in done.stdout


def test_chapter_number_out_of_range_stops(tmp_path):
    bundle = _bundle(tmp_path, chapter_form(), "장양식")
    (bundle / "원고.md").write_text("□ 내용\n", encoding="utf-8")
    done = _run(bundle, "원고.md", "-o", "결과.hwpx", "--chapter", "99")
    assert done.returncode != 0
    assert "1~12" in done.stdout + done.stderr
