"""실제 한글 작성 문서에서 드러난 패턴에 대한 회귀 검사(M3).

검사 대상 파일은 저장소에 넣지 않는다. 실제 문서에서 확인된 구조를 합성 문서로
재현해 고정한다.

  1. 제목이 '제목 상자'(1행짜리 표) 안에 들어 있음
  2. 굵기를 bold 속성이 아니라 글꼴 이름(… Bold / … Light)으로 구분함
  3. 쪽번호·셀 번호처럼 한두 글자짜리 문단이 다수 섞여 있음
  4. 한글 바이너리(.hwp)를 그대로 넘기는 경우
"""

import pytest

from hwpx_studio.engine import build_document
from hwpx_studio.extractor import extract_profile
from hwpx_studio.profile import merge_profile


@pytest.fixture
def real_world_doc(policy, tmp_path):
    """제목 상자(1x1 표) + 데이터 표(3행) + 쪽번호가 섞인 문서."""
    from io import BytesIO
    import zipfile

    from hwpx.document import HwpxDocument

    from hwpx_studio.engine import (
        _template_header_xml, patch_template_bytes, plan_ids,
    )

    profile = merge_profile(policy)
    ids = plan_ids(_template_header_xml(), profile)
    doc = HwpxDocument.open(BytesIO(patch_template_bytes(profile, ids)))
    sec = doc.sections[0]

    def para(key, text):
        sid, cid, pid = ids.refs(key)
        doc.add_paragraph(text, section=sec, style_id_ref=sid,
                          char_pr_id_ref=cid, para_pr_id_ref=pid)

    # 제목 상자: 1행 1열 표 안에 title 스타일 문단
    title_box = doc.add_table(1, 1, section=sec)
    sid, cid, pid = ids.refs("title")
    title_box.cell(0, 0).add_paragraph("Ⅰ. 장 제목", style_id_ref=sid,
                                       char_pr_id_ref=cid, para_pr_id_ref=pid)
    for i in range(3):
        para("L1", f"□ 주제 {i}")
        para("L2", f"○ 주요 {i}")
        para("L3", f"- 설명 {i}")
    # 데이터 표(3행): 머리행은 표(위), 나머지는 표(중간) 스타일
    table = doc.add_table(3, 2, section=sec)
    for r in range(3):
        key = "table_top" if r == 0 else "table_mid"
        sid, cid, pid = ids.styles[key], ids.chars[key], ids.paras[key]
        for c in range(2):
            table.cell(r, c).add_paragraph(f"셀{r}{c}", style_id_ref=sid,
                                           char_pr_id_ref=cid, para_pr_id_ref=pid)
    for n in range(1, 5):          # 쪽번호처럼 짧은 문단
        doc.add_paragraph(str(n), section=sec)

    path = tmp_path / "real_like.hwpx"
    path.write_bytes(doc.to_bytes())
    return path


def test_title_inside_layout_table_is_recovered(real_world_doc):
    """1행짜리 표(제목 상자) 안의 제목도 레벨로 잡아야 한다."""
    result = extract_profile(str(real_world_doc))
    keys = [lv["key"] for lv in result.profile["levels"]]
    prefixes = [lv["prefix"] for lv in result.profile["levels"]]
    assert "title" in keys
    assert "AUTO_ROMAN" in prefixes


def test_data_table_styles_are_not_levels(real_world_doc):
    """여러 행짜리 데이터 표의 셀 스타일은 레벨 목록에 들어가면 안 된다."""
    result = extract_profile(str(real_world_doc))
    names = [lv["name"] for lv in result.profile["levels"]]
    assert not [n for n in names if n.startswith("표(")]
    assert "top" in (result.profile.get("table") or {})


def test_page_number_cluster_is_dropped(real_world_doc):
    result = extract_profile(str(real_world_doc))
    assert any("번호" in note for note in result.notes)
    for level in result.profile["levels"]:
        assert level["size_pt"] > 0


def test_font_role_from_face_name_without_bold_flag(policy, tmp_path):
    """bold 속성 없이 글꼴 이름으로만 굵기를 구분한 문서."""
    profile = merge_profile(policy)
    for level in profile["levels"]:
        level["bold"] = False           # 굵기 속성 제거, 글꼴 이름은 유지
    path = tmp_path / "byname.hwpx"
    build_document(profile, [("title", "장"), (1, "□ 주제"), (2, "○ 주요")], str(path))

    got = extract_profile(str(path)).profile
    assert got["fonts"]["bold"] == profile["fonts"]["bold"]
    assert got["fonts"]["light"] == profile["fonts"]["light"]
    # Bold 글꼴을 쓰는 레벨은 bold 속성이 없어도 font 역할이 bold여야 한다
    by_key = {lv["key"]: lv for lv in got["levels"]}
    assert by_key["title"]["font"] == "bold"


def test_binary_hwp_gives_actionable_error(tmp_path):
    path = tmp_path / "old.hwp"
    path.write_bytes(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 64)
    with pytest.raises(ValueError) as excinfo:
        extract_profile(str(path))
    message = str(excinfo.value)
    assert ".hwpx" in message and "다른 이름으로 저장" in message


def test_non_hwpx_file_is_rejected_clearly(tmp_path):
    path = tmp_path / "notes.txt"
    path.write_text("그냥 텍스트", encoding="utf-8")
    with pytest.raises(ValueError, match="zip"):
        extract_profile(str(path))
