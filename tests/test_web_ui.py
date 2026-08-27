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


def open_page(browser, url, lane="write"):
    """페이지를 열고 서비스 갈래를 고른다.

    화면이 갈래로 나뉘어 있어 다른 갈래의 요소는 숨어 있다. 시험마다 어느 갈래를
    보는지 분명히 해 둔다(갈래는 localStorage에 남으므로 시험끼리 새면 안 된다).
    """
    page = browser.new_page(viewport={"width": 420, "height": 900})
    problems = []
    page.on("pageerror", lambda e: problems.append(str(e)))
    page.on("console", lambda m: problems.append(m.text) if m.type == "error" else None)
    page.goto(url, wait_until="networkidle")
    go(page, lane)
    return page, problems


def go(page, lane):
    page.click(f'[data-lane="{lane}"]')
    page.wait_for_selector(f'[data-panel="{lane}"]', state="visible")


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
    page.click('[data-sample="research"]')
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
    page, problems = open_page(browser, server, "diagram")
    page.click('[data-capture-sample="mermaid"]')
    page.fill("#capture-title", "위원회 구성")
    page.click("#capture-run")
    page.wait_for_timeout(200)
    assert "상자 6개" in page.inner_text("#capture-status")

    go(page, "write")
    body = page.input_value("#body-text")
    assert ':::diagram type=org title="위원회 구성"' in body
    assert "○○위원회 {fill=#C00000 color=#FFFFFF}" in body
    assert "  기획분과 {fill=#2E75B6 color=#FFFFFF}" in body
    assert "link=dash" in body                       # 점선 화살표가 옮겨진다
    assert "도식" in page.inner_text("#stat")        # 본문 통계에 반영
    assert problems == []


def test_capture_of_svg_and_then_build(browser, server, tmp_path):
    import zipfile

    page, problems = open_page(browser, server, "diagram")
    page.click('[data-capture-sample="svg"]')
    page.click("#capture-run")
    page.wait_for_timeout(200)

    go(page, "write")
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


def test_diagram_downloads_a_hwpx_on_its_own(browser, server, tmp_path):
    """② 갈래에서 도식만으로 바로 한글파일이 나온다(본문을 거치지 않는다)."""
    import zipfile

    page, problems = open_page(browser, server, "diagram")
    page.click('[data-diagram-sample="db"]')
    page.wait_for_timeout(200)
    page.fill("#capture-filename", "DB구성")

    with page.expect_download() as download:
        page.click("#capture-download")
    saved = tmp_path / "db.hwpx"
    download.value.save_as(str(saved))

    assert download.value.suggested_filename == "DB구성.hwpx"    # 확장자 자동 보정
    with zipfile.ZipFile(str(saved)) as zf:
        assert zf.testzip() is None
        section = zf.read("Contents/section0.xml").decode("utf-8")
    for word in ("회원", "신청ID (PK)", "회원ID (FK)", "지원사업 DB 구성"):
        assert word in section
    assert "저장됨" in page.inner_text("#capture-status")

    go(page, "write")
    assert page.input_value("#body-text").strip() == ""          # 본문은 건드리지 않는다
    assert problems == []


def test_diagram_samples_draw_their_own_preview(browser, server):
    """작성 예시 다섯 가지가 각각 결과 격자까지 그린다."""
    page, problems = open_page(browser, server, "diagram")
    page.wait_for_selector("#diagram-samples .sample")
    assert page.locator("#diagram-samples .sample").count() == 5
    assert page.locator("#diagram-samples table.gridview").count() == 5

    db = page.locator("#diagram-samples .sample", has_text="DB 구성").first
    assert "신청ID (PK)" in db.inner_text()          # 열쇠 표시가 미리보기에 나온다
    assert "→" in db.inner_text()                    # 관계 화살표도
    assert problems == []


def test_diagram_preview_follows_what_is_typed(browser, server):
    page, problems = open_page(browser, server, "diagram")
    page.fill("#capture-text", ":::diagram type=flow\n접수 → 심의 → 통보\n:::")
    page.click("#capture-preview")
    page.wait_for_selector("#capture-view table.gridview")
    view = page.inner_text("#capture-view")
    for word in ("접수", "심의", "통보", "→"):
        assert word in view
    assert problems == []


def test_diagram_download_reports_what_it_cannot_draw(browser, server):
    """그리지 못한 관계는 조용히 넘어가지 않는다."""
    page, _ = open_page(browser, server, "diagram")
    page.fill("#capture-text",
              ":::diagram type=db\n[가]\n  값\n[나]\n  값\n[다]\n  값\n가 → 다\n:::")
    page.click("#capture-preview")
    page.wait_for_timeout(200)
    assert "붙어 있지 않아" in page.inner_text("#capture-status")


def test_capture_reports_unreadable_input(browser, server):
    page, _ = open_page(browser, server, "diagram")
    page.fill("#capture-text", "이건 그냥 문장이다")
    page.click("#capture-run")
    page.wait_for_timeout(200)
    status = page.inner_text("#capture-status")
    assert "못" in status or "찾지" in status
    go(page, "write")
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
    go(page, "diagram")
    page.wait_for_selector("#diagram-samples table.gridview")   # 예시 미리보기도 그려진다
    page.click('[data-capture-sample="mermaid"]')
    page.click("#capture-run")
    page.wait_for_timeout(200)
    go(page, "write")
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


# ──────────────────────────────────────────────────────────────
# ① 양식으로 도구 만들기 · ③ 서식 없는 문서를 양식에 맞추기
# ──────────────────────────────────────────────────────────────
def _fixture_form(tmp_path, kind="auto"):
    """시험용 양식 파일을 만들어 둔다."""
    import sys

    sys.path.insert(0, str(ROOT / "tests"))
    from formfixtures import auto_bullet_form, plain_form   # noqa: PLC0415

    path = tmp_path / f"{kind}.hwpx"
    path.write_bytes(auto_bullet_form() if kind == "auto" else plain_form())
    return path


def test_form_upload_makes_a_bundle(browser, server, tmp_path):
    """양식을 올리면 해부 결과를 보여 주고 꾸러미를 내려받게 한다."""
    import zipfile

    page, problems = open_page(browser, server, "form")
    page.set_input_files("#form-file", str(_fixture_form(tmp_path)))
    page.fill("#form-name", "시험양식")
    page.click("#form-run")
    page.wait_for_selector("#form-result", state="visible")

    report = page.inner_text("#form-report")
    assert "찾아낸 레벨" in report
    assert "한글이 자동으로" in report, "자동 글머리표를 찾았다고 말해야 한다"
    assert "레벨" in page.inner_text("#form-status")

    with page.expect_download() as download:
        page.click("#form-download")
    saved = tmp_path / "bundle.zip"
    download.value.save_as(str(saved))
    with zipfile.ZipFile(str(saved)) as zf:
        names = [n.split("/", 1)[1] for n in zf.namelist()]
        assert "build_form.py" in names
        assert "template.hwpx" in names
        assert "form.json" in names
        assert "SKILL.md" in names
    assert problems == []


def test_browser_bundle_actually_builds_a_document(browser, server, tmp_path):
    """브라우저가 만든 꾸러미를 풀어 그 안의 빌더를 실제로 돌린다."""
    import subprocess
    import sys
    import zipfile

    page, _ = open_page(browser, server, "form")
    page.set_input_files("#form-file", str(_fixture_form(tmp_path)))
    page.fill("#form-name", "돌려보기")
    page.click("#form-run")
    page.wait_for_selector("#form-result", state="visible")
    with page.expect_download() as download:
        page.click("#form-download")
    saved = tmp_path / "bundle.zip"
    download.value.save_as(str(saved))

    out = tmp_path / "풀린곳"
    with zipfile.ZipFile(str(saved)) as zf:
        zf.extractall(str(out))
    bundle = out / "돌려보기"
    done = subprocess.run(
        [sys.executable, "build_form.py", "예시.md", "-o", "결과.hwpx"],
        cwd=bundle, capture_output=True, text=True, timeout=120)
    assert done.returncode == 0, done.stdout + done.stderr

    with zipfile.ZipFile(str(bundle / "template.hwpx")) as a, \
            zipfile.ZipFile(str(bundle / "결과.hwpx")) as b:
        assert a.read("Contents/header.xml") == b.read("Contents/header.xml"), \
            "양식의 서식 정의가 한 바이트도 바뀌면 안 된다"


def test_skill_download_uses_the_skill_extension(browser, server, tmp_path):
    page, _ = open_page(browser, server, "form")
    page.set_input_files("#form-file", str(_fixture_form(tmp_path, "plain")))
    page.fill("#form-name", "스킬시험")
    page.click("#form-run")
    page.wait_for_selector("#form-result", state="visible")
    with page.expect_download() as download:
        page.click("#form-download-skill")
    assert download.value.suggested_filename == "스킬시험.skill"


def test_binary_hwp_is_refused_with_guidance(browser, server, tmp_path):
    page, _ = open_page(browser, server, "form")
    bad = tmp_path / "옛문서.hwpx"
    bad.write_bytes(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"0" * 64)
    page.set_input_files("#form-file", str(bad))
    page.click("#form-run")
    page.wait_for_timeout(400)
    status = page.inner_text("#form-status")
    assert "HWPX" in status, status
    assert page.locator("#form-result").is_hidden()


def test_convert_reads_a_plain_document_back(browser, server, tmp_path):
    """서식 없는 문서를 마커 원고로 되돌리고 근거를 보여 준다."""
    import sys

    sys.path.insert(0, str(ROOT / "tests"))
    from formfixtures import plain_form, without_symbols     # noqa: PLC0415

    plain = tmp_path / "내용만.hwpx"
    plain.write_bytes(plain_form())

    page, problems = open_page(browser, server, "convert")
    page.set_input_files("#convert-file", str(plain))
    page.set_input_files("#convert-form", str(_fixture_form(tmp_path)))
    page.click("#convert-run")
    page.wait_for_selector("#convert-result", state="visible")

    text = page.input_value("#convert-text")
    assert "□ 추진 배경 및 목적" in text
    assert "| 구분 | 2024년 | 2025년 |" in text
    assert "기호 □" in page.inner_text("#convert-report")   # 백틱은 <code>로 그려진다

    with page.expect_download() as download:
        page.click("#convert-bundle")
    assert download.value.suggested_filename.endswith(".zip")
    assert problems == []
    assert without_symbols is not None


def test_convert_hands_the_draft_to_the_writing_lane(browser, server, tmp_path):
    page, _ = open_page(browser, server, "convert")
    plain = tmp_path / "내용만2.hwpx"
    plain.write_bytes(_fixture_form(tmp_path, "plain").read_bytes())
    page.set_input_files("#convert-file", str(plain))
    page.click("#convert-run")
    page.wait_for_selector("#convert-result", state="visible")
    page.click("#convert-copy")
    page.wait_for_selector('[data-panel="write"]', state="visible")
    assert "추진 배경 및 목적" in page.input_value("#body-text")


def test_every_lane_opens(browser, server):
    page, problems = open_page(browser, server, "form")
    for lane in ("form", "diagram", "convert", "write"):
        go(page, lane)
        assert page.locator(f'[data-panel="{lane}"]').is_visible()
    assert problems == []


def test_bullet_source_can_be_chosen_in_the_page(browser, server, tmp_path):
    """글머리표를 누가 붙일지 고르면 곧바로 다시 해부하고, 어긋나면 말한다."""
    page, problems = open_page(browser, server, "form")
    page.set_input_files("#form-file", str(_fixture_form(tmp_path)))
    page.fill("#form-name", "고르기")
    page.click("#form-run")
    page.wait_for_selector("#form-result", state="visible")
    assert "한글이 자동으로" in page.inner_text("#form-report")

    page.select_option("#form-bullets", "text")
    page.wait_for_timeout(600)
    report = page.inner_text("#form-report")
    assert "두 번 찍힌다" in report, report[:300]
    assert "어긋나는" in page.inner_text("#form-status")

    page.select_option("#form-bullets", "auto")
    page.wait_for_timeout(600)
    assert "두 번 찍힌다" not in page.inner_text("#form-report")
    assert problems == []
