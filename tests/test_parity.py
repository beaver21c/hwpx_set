"""기존 hwpx_generator.py(v6)와의 서식 패리티 검사.

레거시 생성기는 저장소에 포함하지 않는다. 검사하려면 경로를 넘긴다.

    HWPX_LEGACY_GENERATOR=/path/to/hwpx_generator.py pytest tests/test_parity.py
"""

import importlib.util
import os
import re
import zipfile
from pathlib import Path

import pytest

LEGACY = os.environ.get("HWPX_LEGACY_GENERATOR")
pytestmark = pytest.mark.skipif(
    not LEGACY or not Path(LEGACY).exists(),
    reason="HWPX_LEGACY_GENERATOR 환경변수로 기존 생성기 경로를 지정해야 실행",
)


def _style_attributes(path):
    """스타일명 → 서식 속성(폰트·크기·굵기·색·정렬·줄간격·여백)."""
    with zipfile.ZipFile(str(path)) as zf:
        header = zf.read("Contents/header.xml").decode("utf-8")
    chars = {m.group(1): m.group()
             for m in re.finditer(r'<hh:charPr id="(\d+)".*?</hh:charPr>', header, re.S)}
    paras = {m.group(1): m.group()
             for m in re.finditer(r'<hh:paraPr id="(\d+)".*?</hh:paraPr>', header, re.S)}
    fonts = dict(re.findall(r'<hh:font id="(\d+)" face="([^"]*)"', header))

    out = {}
    pattern = (r'<hh:style id="\d+" type="PARA" name="([^"]*)"[^>]*'
               r'paraPrIDRef="(\d+)" charPrIDRef="(\d+)"')
    for name, para_id, char_id in re.findall(pattern, header):
        char, para = chars.get(char_id, ""), paras.get(para_id, "")
        font_ref = re.search(r'<hh:fontRef hangul="(\d+)"', char)
        margin = re.search(
            r'<hc:intent value="(-?\d+)"[^>]*/><hc:left value="(\d+)"[^>]*/>'
            r'<hc:right value="\d+"[^>]*/><hc:prev value="\d+"[^>]*/>'
            r'<hc:next value="(\d+)"', para)
        out[name] = {
            "height": re.search(r'height="(\d+)"', char).group(1),
            "bold": 'bold="1"' in char,
            "color": re.search(r'textColor="([^"]*)"', char).group(1).upper(),
            "font": fonts.get(font_ref.group(1)) if font_ref else None,
            "align": re.search(r'horizontal="([^"]*)"', para).group(1) if para else None,
            "line_spacing": re.search(r'<hh:lineSpacing[^>]*value="(\d+)"', para).group(1),
            "margin": margin.groups() if margin else None,
        }
    return out


def _texts(path):
    with zipfile.ZipFile(str(path)) as zf:
        section = zf.read("Contents/section0.xml").decode("utf-8")
    return re.findall(r"<hp:t>(.*?)</hp:t>", section)


@pytest.fixture(scope="module")
def legacy_document(tmp_path_factory):
    spec = importlib.util.spec_from_file_location("legacy_generator", LEGACY)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    out = tmp_path_factory.mktemp("legacy") / "legacy.hwpx"
    module.SAVE_PATH = str(out)
    module.create_report()
    return out, module


def test_style_attributes_match(legacy_document, tmp_path, repo_root):
    from hwpx_studio.engine import build_document
    from hwpx_studio.parser import parse_file
    from hwpx_studio.profile import load_profile

    legacy_path, _ = legacy_document
    profile = load_profile("policy-default")   # 내장 프로파일(hwpx_studio/profiles/)
    parsed = parse_file(str(repo_root / "tests" / "fixtures" / "legacy_contents.md"),
                        profile)
    studio_path = tmp_path / "studio.hwpx"
    build_document(profile, parsed.items, str(studio_path))

    legacy_styles = _style_attributes(legacy_path)
    studio_styles = _style_attributes(studio_path)
    for name, attrs in legacy_styles.items():
        assert name in studio_styles, f"{name} 스타일 누락"
        assert studio_styles[name] == attrs, f"{name} 서식 불일치"


def test_body_text_matches(legacy_document, tmp_path, repo_root):
    from hwpx_studio.engine import build_document
    from hwpx_studio.parser import parse_file
    from hwpx_studio.profile import load_profile

    legacy_path, module = legacy_document
    profile = load_profile("policy-default")   # 내장 프로파일(hwpx_studio/profiles/)
    parsed = parse_file(str(repo_root / "tests" / "fixtures" / "legacy_contents.md"),
                        profile)
    studio_path = tmp_path / "studio.hwpx"
    build_document(profile, parsed.items, str(studio_path))

    signature = getattr(module, "_z", None)
    legacy_texts = [t for t in _texts(legacy_path) if t != signature]
    assert legacy_texts == _texts(studio_path)
