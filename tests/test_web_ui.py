"""브라우저 웹 앱 검사(Playwright).

playwright나 브라우저가 없으면 건너뛴다. CI의 `웹 앱` 잡에서 실제로 돌린다.
"""

from __future__ import annotations

import glob
import http.server
import socketserver
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"

playwright_api = pytest.importorskip("playwright.sync_api",
                                     reason="playwright 미설치")


def find_chromium() -> str | None:
    """설치 위치가 표준이 아닐 수 있어 직접 찾아 본다."""
    for pattern in ("/opt/pw-browsers/chromium-*/chrome-linux/chrome",
                    "/root/.cache/ms-playwright/chromium-*/chrome-linux/chrome"):
        found = sorted(glob.glob(pattern))
        if found:
            return found[-1]
    return None


@pytest.fixture(scope="module")
def server():
    handler = lambda *args, **kw: http.server.SimpleHTTPRequestHandler(  # noqa: E731
        *args, directory=str(DOCS), **kw)
    with socketserver.TCPServer(("127.0.0.1", 0), handler) as httpd:
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        yield f"http://127.0.0.1:{httpd.server_address[1]}/"
        httpd.shutdown()


@pytest.fixture(scope="module")
def browser():
    with playwright_api.sync_playwright() as pw:
        kwargs = {}
        path = find_chromium()
        if path:
            kwargs["executable_path"] = path
        try:
            instance = pw.chromium.launch(**kwargs)
        except Exception as exc:                       # noqa: BLE001
            pytest.skip(f"크로미움을 띄울 수 없음: {exc}")
        yield instance
        instance.close()


def open_page(browser, url):
    page = browser.new_page(viewport={"width": 420, "height": 900})
    problems = []
    page.on("pageerror", lambda e: problems.append(str(e)))
    page.on("console", lambda m: problems.append(m.text) if m.type == "error" else None)
    page.goto(url, wait_until="networkidle")
    return page, problems


def test_page_loads_without_errors(browser, server):
    page, problems = open_page(browser, server)
    assert "hwpx-studio" in page.title()
    assert page.locator("#marker-table tr").count() >= 5     # 마커 치트시트가 채워진다
    assert problems == []


def test_sample_updates_stats(browser, server):
    page, problems = open_page(browser, server)
    page.click('[data-sample="diagram"]')
    page.wait_for_timeout(200)
    stat = page.inner_text("#stat")
    assert "도식" in stat and "문단" in stat
    assert problems == []


def test_build_downloads_valid_hwpx(browser, server, tmp_path):
    import zipfile

    page, problems = open_page(browser, server)
    page.click('[data-sample="outline"]')
    page.fill("#filename", "검사용")
    with page.expect_download() as download:
        page.click("#build")
    saved = tmp_path / "out.hwpx"
    download.value.save_as(str(saved))

    assert download.value.suggested_filename == "검사용.hwpx"   # 확장자 자동 보정
    with zipfile.ZipFile(str(saved)) as zf:
        assert zf.testzip() is None
        assert "Contents/section0.xml" in zf.namelist()
    page.wait_for_timeout(200)
    assert "저장됨" in page.inner_text("#status")
    assert problems == []


def test_extracted_profile_matches_selection(browser, server, tmp_path):
    from hwpx_studio.extractor import extract_profile

    page, _ = open_page(browser, server)
    page.click('[data-sample="diagram"]')
    with page.expect_download() as download:
        page.click("#build")
    saved = tmp_path / "diagram.hwpx"
    download.value.save_as(str(saved))

    result = extract_profile(str(saved))
    keys = [lv["key"] for lv in result.profile["levels"]]
    assert keys[:3] == ["title", "title2", "L1"]


def test_lint_is_reported_in_page(browser, server):
    page, _ = open_page(browser, server)
    page.fill("#body-text", "## 절\n□ 하나\n○ 유일\n")
    page.click("#check")
    page.wait_for_timeout(200)
    assert "경고" in page.inner_text("#status")
    assert page.locator("#issues li").count() >= 1


def test_empty_input_is_rejected(browser, server):
    page, _ = open_page(browser, server)
    page.fill("#body-text", "   ")
    page.click("#build")
    page.wait_for_timeout(200)
    assert "본문을 입력" in page.inner_text("#status")


def test_capture_inserts_a_diagram_block(browser, server):
    """붙여 넣은 Mermaid를 읽어 본문에 도식 블록으로 넣는다."""
    page, problems = open_page(browser, server)
    page.click('[data-capture-sample="mermaid"]')
    page.fill("#capture-title", "위원회 구성")
    page.click("#capture-run")
    page.wait_for_timeout(200)

    body = page.input_value("#body-text")
    assert ':::diagram type=org title="위원회 구성"' in body
    assert "○○위원회 {fill=#C00000 color=#FFFFFF}" in body
    assert "  기획분과 {fill=#2E75B6 color=#FFFFFF}" in body
    assert "link=dash" in body                       # 점선 화살표가 옮겨진다
    assert "상자 6개" in page.inner_text("#capture-status")
    assert "도식" in page.inner_text("#stat")        # 본문 통계에 반영
    assert problems == []


def test_capture_of_svg_and_then_build(browser, server, tmp_path):
    import zipfile

    page, problems = open_page(browser, server)
    page.click('[data-capture-sample="svg"]')
    page.click("#capture-run")
    page.wait_for_timeout(200)
    assert "위원회" in page.input_value("#body-text")

    with page.expect_download() as download:
        page.click("#build")
    saved = tmp_path / "captured.hwpx"
    download.value.save_as(str(saved))
    with zipfile.ZipFile(str(saved)) as zf:
        section = zf.read("Contents/section0.xml").decode("utf-8")
        header = zf.read("Contents/header.xml").decode("utf-8")
    assert "자문단" in section
    assert "#C00000" in header                       # 원본 색이 문서까지 간다
    assert "DASH" in header                          # 점선 연결선도
    assert problems == []


def test_capture_reports_unreadable_input(browser, server):
    page, _ = open_page(browser, server)
    page.fill("#capture-text", "이건 그냥 문장이다")
    page.click("#capture-run")
    page.wait_for_timeout(200)
    status = page.inner_text("#capture-status")
    assert "못" in status or "찾지" in status
    assert ":::diagram" not in page.input_value("#body-text")


def test_standalone_single_file_works(browser, tmp_path):
    """단일 HTML(인터넷 없이 쓰는 버전)도 도식 가져오기가 동작한다."""
    import subprocess
    import sys

    out = tmp_path / "hwpx-studio.html"
    subprocess.run([sys.executable, str(ROOT / "tools" / "build_standalone.py"),
                    "-o", str(out)], check=True, capture_output=True)

    page = browser.new_page()
    problems = []
    page.on("pageerror", lambda e: problems.append(str(e)))
    page.goto(out.as_uri(), wait_until="load")
    page.click('[data-capture-sample="mermaid"]')
    page.click("#capture-run")
    page.wait_for_timeout(200)
    assert ":::diagram" in page.input_value("#body-text")
    assert problems == []


def test_footnote_survives_the_browser_build(browser, server, tmp_path):
    """웹에서 만든 문서에도 각주가 8pt 회색으로 들어가야 한다."""
    import re
    import zipfile

    page, problems = open_page(browser, server)
    page.fill("#body-text",
              "□ 근거가 있는 문장이다[^1]\n○ 두 번째 항목\n\n[^1]: 통계청(2024).\n")
    with page.expect_download() as download:
        page.click("#build")
    saved = tmp_path / "footnote.hwpx"
    download.value.save_as(str(saved))

    with zipfile.ZipFile(str(saved)) as zf:
        section = zf.read("Contents/section0.xml").decode("utf-8")
        header = zf.read("Contents/header.xml").decode("utf-8")
    note = re.search(r"<hp:footNote .*?</hp:footNote>", section, re.S)
    assert note and "통계청(2024)." in note.group()
    assert "[^1]" not in section                      # 자리표는 본문에 남지 않는다
    char_id = re.search(r'<hh:style id="\d+"[^>]*name="각주"[^>]*charPrIDRef="(\d+)"',
                        header).group(1)
    char = re.search(rf'<hh:charPr id="{char_id}".*?</hh:charPr>', header, re.S).group()
    assert 'height="800"' in char and 'textColor="#808080"' in char
    assert problems == []


def test_footnote_position_is_reported_in_page(browser, server):
    page, _ = open_page(browser, server)
    page.fill("#body-text", "□ 문장이다.[^1]\n○ 둘\n\n[^1]: 내용\n")
    page.click("#check")
    page.wait_for_timeout(200)
    assert "마침표 앞에 붙일 것" in page.inner_text("#issues")
