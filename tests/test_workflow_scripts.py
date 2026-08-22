"""GitHub Actions에서 도는 스크립트 검사.

워크플로에서만 실행되는 코드라 눈에 잘 띄지 않는다. 이슈 폼 본문 해석은
신뢰할 수 없는 입력을 다루므로 특히 고정해 둔다.
"""

import importlib.util
import os
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / ".github" / "scripts"


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ISSUE_BODY = """### 본문 (마커 텍스트)

```text
# 시험 보고서
## 개요
□ 첫 주제
○ 첫 항목
```

### 서식 프로파일

gov-3level

### 결과 파일 이름

_No response_

### 도식 렌더 방식

image

### 옵션

- [x] 본문 검사 경고도 오류로 취급(strict)
- [ ] HTML 근사 미리보기도 만들기
"""


@pytest.fixture
def issue_script():
    return load("issue_to_input")


def test_sections_and_code_fence(issue_script):
    sections = issue_script.parse_sections(ISSUE_BODY)
    body = issue_script.strip_code_fence(sections["본문 (마커 텍스트)"])
    assert body.startswith("# 시험 보고서")
    assert "```" not in body
    assert sections["결과 파일 이름"] == ""        # _No response_ → 빈 값
    assert sections["서식 프로파일"] == "gov-3level"


def test_issue_form_writes_input_and_outputs(issue_script, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ISSUE_BODY", ISSUE_BODY)
    monkeypatch.setenv("GITHUB_OUTPUT", str(tmp_path / "out.txt"))
    assert issue_script.main() == 0

    outputs = dict(
        line.split("=", 1)
        for line in (tmp_path / "out.txt").read_text(encoding="utf-8").splitlines()
    )
    assert outputs["ok"] == "true"
    assert outputs["profile"] == "gov-3level"
    assert outputs["output_name"] == "보고서.hwpx"   # 미입력 시 기본값
    assert outputs["diagram_render"] == "image"
    assert outputs["strict"] == "true"
    assert outputs["preview"] == "false"
    assert (tmp_path / "issue_input.md").read_text(encoding="utf-8").startswith("# 시험")


def test_empty_body_is_rejected(issue_script, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ISSUE_BODY", "### 본문 (마커 텍스트)\n\n_No response_")
    monkeypatch.setenv("GITHUB_OUTPUT", str(tmp_path / "out.txt"))
    assert issue_script.main() == 1
    assert "ok=false" in (tmp_path / "out.txt").read_text(encoding="utf-8")


def test_unknown_profile_falls_back(issue_script, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ISSUE_BODY", "### 본문 (마커 텍스트)\n\n□ 하나\n\n"
                                     "### 서식 프로파일\n\n../../etc/passwd")
    monkeypatch.setenv("GITHUB_OUTPUT", str(tmp_path / "out.txt"))
    assert issue_script.main() == 0
    text = (tmp_path / "out.txt").read_text(encoding="utf-8")
    assert "profile=policy-default" in text


def test_output_name_cannot_escape_directory(issue_script, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ISSUE_BODY", "### 본문 (마커 텍스트)\n\n□ 하나\n\n"
                                     "### 결과 파일 이름\n\n../../탈출.hwpx")
    monkeypatch.setenv("GITHUB_OUTPUT", str(tmp_path / "out.txt"))
    assert issue_script.main() == 0
    assert "output_name=탈출.hwpx" in (tmp_path / "out.txt").read_text(encoding="utf-8")


def test_build_script_runs_and_blocks_on_strict(tmp_path, monkeypatch, repo_root):
    build = load("run_build")
    monkeypatch.chdir(repo_root)
    monkeypatch.setenv("INPUT_PATH", "examples/input_outline.md")
    monkeypatch.setenv("PROFILE", "policy-default")
    monkeypatch.setenv("OUTPUT_NAME", "결과")
    monkeypatch.setenv("OUT_DIR", str(tmp_path / "out"))
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    monkeypatch.setenv("STRICT", "false")
    monkeypatch.setenv("PREVIEW", "false")
    assert build.main() == 0
    assert (tmp_path / "out" / "결과.hwpx").exists()    # 확장자 자동 보정

    monkeypatch.setenv("INPUT_PATH", "examples/input_diagram.md")
    monkeypatch.setenv("STRICT", "true")
    assert build.main() == 1                            # 경고 → 중단


def test_build_script_reports_missing_input(tmp_path, monkeypatch):
    build = load("run_build")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("INPUT_PATH", "없는파일.md")
    monkeypatch.setenv("OUT_DIR", str(tmp_path / "out"))
    assert build.main() == 2


def test_extract_script(tmp_path, monkeypatch, repo_root, policy):
    from hwpx_studio.engine import build_document

    doc = tmp_path / "src.hwpx"
    build_document(policy, [("title", "장"), (1, "주제"), (2, "항목")], str(doc))

    extract = load("run_extract")
    monkeypatch.setenv("SOURCE_PATH", str(doc))
    monkeypatch.setenv("OUT_DIR", str(tmp_path / "out"))
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    assert extract.main() == 0
    assert (tmp_path / "out" / "src.profile.json").exists()
    assert (tmp_path / "out" / "src.report.md").exists()


def test_extract_script_rejects_binary_hwp(tmp_path, monkeypatch):
    extract = load("run_extract")
    path = tmp_path / "old.hwp"
    path.write_bytes(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 32)
    monkeypatch.setenv("SOURCE_PATH", str(path))
    monkeypatch.setenv("OUT_DIR", str(tmp_path / "out"))
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    assert extract.main() == 1
