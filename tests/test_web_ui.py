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
