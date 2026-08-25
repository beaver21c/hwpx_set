"""서식 없는 hwpx → 마커 텍스트 되돌리기(`read_hwpx.py`) 시험.

이 되돌리기가 서비스 ③(내용만 있는 한글 파일을 양식에 맞게 다시 만들기)의 앞단이다.
가장 센 확인은 **왕복**이다. 마커 텍스트로 문서를 만들고 다시 읽어 같은 텍스트가
나오면, 읽기와 쓰기가 서로를 검산한 셈이다.

계층 추정은 추정이다. 시험은 '무엇을 근거로 그렇게 보았는지 말하는가'까지만 건다.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from formfixtures import plain_form, without_symbols
from hwpx_studio.export_form import READER, build_bundle

ASSETS = Path(__file__).resolve().parent.parent / "hwpx_studio" / "assets"


def _reader():
    spec = importlib.util.spec_from_file_location("read_hwpx", ASSETS / READER)
    module = importlib.util.module_from_spec(spec)
    # dataclass가 자기 모듈을 sys.modules에서 찾는다. 먼저 등록해 둔다.
    sys.modules["read_hwpx"] = module
    spec.loader.exec_module(module)
    return module


def _bundle(tmp_path: Path, data: bytes = None, name: str = "평범") -> Path:
    files, _ = build_bundle(data if data is not None else plain_form(), name=name)
    out = tmp_path / name
    out.mkdir(parents=True, exist_ok=True)
    for filename, blob in files.items():
        (out / filename).write_bytes(blob)
    return out


def _make_hwpx(tmp_path: Path, source: str) -> Path:
    """마커 텍스트로 문서 하나를 만들어 둔다(되돌리기의 재료)."""
    from hwpx_studio.engine import build_document
    from hwpx_studio.parser import parse_text
    from hwpx_studio.profile import load_profile

    profile = load_profile(str(Path(__file__).resolve().parent.parent
                               / "hwpx_studio" / "profiles" / "policy-default.json"))
    parsed = parse_text(source, profile)
    path = tmp_path / "원본.hwpx"
    path.write_bytes(build_document(profile, parsed.items).data)
    return path


ROUND_TRIP = """# 각주 시험
## 근거를 붙인 본문
□ 노인 빈곤율은 40.4%로 가장 높다[^1]
○ 한 문단에 둘[^2]을 달아도 번호는 이어진다[^3]
- 각주를 달지 않는 줄은 그대로 둔다

[^1]: 통계청(2024), 「가계금융복지조사」.
[^2]: 앞의 책, 91쪽.
[^3]: OECD(2024), Pensions at a Glance, p.32.
"""


def test_marker_text_survives_a_full_round_trip(tmp_path):
    """마커 텍스트 → hwpx → 마커 텍스트. 읽기와 쓰기가 서로를 검산한다."""
    reader = _reader()
    source = _make_hwpx(tmp_path, ROUND_TRIP)
    blocks = reader.read_blocks(source)
    reader.classify(blocks)
    markers = ["#", "##", "□", "○", "-", "·", "※"]
    assert reader.to_marker_text(blocks, markers) == ROUND_TRIP


def test_footnote_numbers_are_renumbered_in_document_order(tmp_path):
    reader = _reader()
    source = _make_hwpx(tmp_path, ROUND_TRIP)
    blocks = reader.read_blocks(source)
    reader.classify(blocks)
    text = reader.to_marker_text(blocks, ["#", "##", "□", "○", "-"])
    body = [line for line in text.splitlines() if "[^" in line and not line.startswith("[^")]
    assert "둘[^2]을" in body[1], "번호는 글 안에서 나온 순서대로 매겨야 한다"
    assert "[^2]: 앞의 책, 91쪽." in text


def test_tables_come_back_as_pipe_tables(tmp_path):
    reader = _reader()
    source = _make_hwpx(tmp_path, """□ 실적

| 구분 | 2024년 | 2025년 |
|---|---|---|
| 처리 건수 | 1,204건 | 1,388건 |
""")
    blocks = reader.read_blocks(source)
    reader.classify(blocks)
    text = reader.to_marker_text(blocks, ["□"])
    assert "| 구분 | 2024년 | 2025년 |" in text
    assert "|---|---|---|" in text
    assert "| 처리 건수 | 1,204건 | 1,388건 |" in text


def test_read_back_text_builds_again_through_the_bundle(tmp_path):
    """되돌린 텍스트가 그대로 빌더에 들어간다. ③의 두 단계가 이어진다."""
    bundle = _bundle(tmp_path)
    source = _make_hwpx(tmp_path, ROUND_TRIP)
    done = subprocess.run(
        [sys.executable, str(bundle / READER), str(source), "-o", "원고.md"],
        cwd=bundle, capture_output=True, text=True, timeout=120)
    assert done.returncode == 0, done.stderr
    built = subprocess.run(
        [sys.executable, str(bundle / "build_form.py"), "원고.md", "-o", "결과.hwpx"],
        cwd=bundle, capture_output=True, text=True, timeout=120)
    assert built.returncode == 0, built.stdout + built.stderr
    with zipfile.ZipFile(bundle / "결과.hwpx") as z:
        section = z.read("Contents/section0.xml").decode("utf-8")
    assert section.count("<hp:footNote ") == 3


def test_report_says_what_the_guess_was_based_on(tmp_path):
    reader = _reader()
    source = _make_hwpx(tmp_path, ROUND_TRIP)
    blocks = reader.read_blocks(source)
    notes = reader.classify(blocks)
    report = reader.render_report(blocks, ["#", "##", "□", "○", "-"], notes)
    assert "추정이다" in report
    assert "기호 `□`" in report or "기호 `○`" in report


def test_report_warns_when_only_font_size_was_available(tmp_path):
    """기호도 번호도 없으면 글자 크기로 가른다. 그 사실을 숨기지 않는다."""
    reader = _reader()
    source = tmp_path / "민짜.hwpx"
    source.write_bytes(without_symbols(
        _make_hwpx(tmp_path, "□ 기호 없는 줄\n○ 또 다른 줄\n").read_bytes()))
    blocks = reader.read_blocks(source)
    notes = reader.classify(blocks)
    assert any("글자 크기만으로" in note for note in notes)


def test_binary_hwp_is_refused(tmp_path):
    reader = _reader()
    path = tmp_path / "옛문서.hwp"
    path.write_bytes(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"0" * 64)
    with pytest.raises(SystemExit) as err:
        reader.read_blocks(path)
    assert "HWPX 문서" in str(err.value)


def test_reader_needs_no_third_party_package():
    import re

    source = (ASSETS / READER).read_text(encoding="utf-8")
    imported = set(re.findall(r"^\s*(?:import|from)\s+([\w.]+)", source, re.M))
    allowed = {"argparse", "json", "re", "sys", "xml.etree.ElementTree", "zipfile",
               "dataclasses", "pathlib", "typing", "__future__"}
    assert imported <= allowed, f"바깥 의존성: {imported - allowed}"
