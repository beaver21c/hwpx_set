"""프로파일 주입 → 생성 → 재추출 왕복 일치 검사(SPEC 실험 5·2)."""

from hwpx_studio.engine import build_document
from hwpx_studio.extractor import extract_profile, guess_prefix
from hwpx_studio.profile import merge_profile

SAMPLE = [
    ("title", "장 제목"), ("title2", "절 제목"), (1, "주제"), (2, "주요"),
    (3, "설명"), (4, "세부"), (5, "참고"), (0, ""),
    ("table", [2, 2, ["구분", "값", "가", "1"]]),
]


def test_roundtrip_restores_level_styles(policy, tmp_path):
    out = tmp_path / "rt.hwpx"
    build_document(policy, SAMPLE, str(out))
    result = extract_profile(str(out))
    restored = merge_profile(result.profile)

    assert len(restored["levels"]) == len(policy["levels"])
    for src, got in zip(policy["levels"], restored["levels"]):
        assert got["key"] == src["key"]
        assert float(got["size_pt"]) == float(src["size_pt"])
        assert got["bold"] == src["bold"]
        assert got["color"].upper() == src["color"].upper()
        assert float(got["left_pt"]) == float(src["left_pt"])
        assert float(got["indent_pt"]) == float(src["indent_pt"])
        assert float(got["spacing_below_pt"]) == float(src["spacing_below_pt"])
        assert int(got["line_spacing"]) == int(src["line_spacing"])
        assert got["prefix"] == src["prefix"]


def test_roundtrip_restores_fonts_and_margins(policy, tmp_path):
    out = tmp_path / "rt.hwpx"
    build_document(policy, SAMPLE, str(out))
    got = merge_profile(extract_profile(str(out)).profile)
    assert got["fonts"]["bold"] == policy["fonts"]["bold"]
    assert got["fonts"]["light"] == policy["fonts"]["light"]
    for key, value in policy["page"]["margin_mm"].items():
        assert abs(got["page"]["margin_mm"][key] - value) <= 0.2


def test_roundtrip_restores_table_styles(policy, tmp_path):
    out = tmp_path / "rt.hwpx"
    build_document(policy, SAMPLE, str(out))
    got = merge_profile(extract_profile(str(out)).profile)
    assert float(got["table"]["top"]["size_pt"]) == float(policy["table"]["top"]["size_pt"])
    assert got["table"]["top"]["bold"] == policy["table"]["top"]["bold"]
    assert got["table"]["mid"]["align"] == policy["table"]["mid"]["align"]


def test_extract_report_lists_every_level(policy, tmp_path):
    out = tmp_path / "rt.hwpx"
    build_document(policy, SAMPLE, str(out))
    report = extract_profile(str(out)).report
    for level in policy["levels"]:
        assert level["key"] in report
    assert "접두 후보" in report


def test_reextracted_profile_builds_again(policy, tmp_path):
    first = tmp_path / "a.hwpx"
    build_document(policy, SAMPLE, str(first))
    profile = extract_profile(str(first)).profile
    second = tmp_path / "b.hwpx"
    build_document(profile, SAMPLE, str(second))
    assert second.stat().st_size > 0


def test_prefix_guessing():
    assert guess_prefix("Ⅰ. 장") == "AUTO_ROMAN"
    assert guess_prefix("1. 절") == "AUTO_NUM"
    assert guess_prefix("① 항목") == "AUTO_CIRCLED"
    assert guess_prefix("□ 주제") == "□ "
    assert guess_prefix("– 대시 기호") == "– "
    assert guess_prefix("일반 문장입니다") is None


def test_cluster_by_para_char_when_styles_are_zero(policy, tmp_path):
    """styleIDRef가 모두 0인 문서도 (paraPr, charPr)로 레벨을 복원한다."""
    import re
    import zipfile
    from io import BytesIO

    src = tmp_path / "styled.hwpx"
    build_document(policy, SAMPLE, str(src))

    stripped = tmp_path / "nostyle.hwpx"
    with zipfile.ZipFile(str(src)) as zin, zipfile.ZipFile(str(stripped), "w") as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename == "Contents/section0.xml":
                text = data.decode("utf-8")
                text = re.sub(r'styleIDRef="\d+"', 'styleIDRef="0"', text)
                data = text.encode("utf-8")
            zout.writestr(item, data)

    result = extract_profile(str(stripped))
    assert "paraPrIDRef" in " ".join(result.notes)
    assert len(result.profile["levels"]) == len(policy["levels"])
