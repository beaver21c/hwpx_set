import json
from pathlib import Path

from hwpx_studio.cli import main


def test_build_from_example(tmp_path, repo_root, capsys):
    out = tmp_path / "out.hwpx"
    code = main(["build", str(repo_root / "examples" / "input_outline.md"),
                 "-p", "policy-default", "-o", str(out)])
    assert code == 0 and out.exists()
    assert "생성" in capsys.readouterr().out


def test_lint_strict_returns_error(tmp_path, capsys):
    src = tmp_path / "in.md"
    src.write_text("## 절\n□ 하나\n○ 유일\n", encoding="utf-8")
    assert main(["lint", str(src), "-p", "policy-default"]) == 0
    assert main(["lint", str(src), "-p", "policy-default", "--strict"]) == 1


def test_build_strict_stops_before_writing(tmp_path):
    src = tmp_path / "in.md"
    src.write_text("## 절\n□ 하나\n○ 유일\n", encoding="utf-8")
    out = tmp_path / "out.hwpx"
    assert main(["build", str(src), "-p", "policy-default", "-o", str(out),
                 "--strict"]) == 1
    assert not out.exists()


def test_init_and_extract_roundtrip(tmp_path, repo_root):
    profile_path = tmp_path / "p.json"
    assert main(["init", str(profile_path), "--from", "policy-default"]) == 0

    src = tmp_path / "in.md"
    src.write_text("# 장\n## 절\n□ 하나\n○ 둘\n", encoding="utf-8")
    doc = tmp_path / "doc.hwpx"
    assert main(["build", str(src), "-p", str(profile_path), "-o", str(doc),
                 "--no-lint"]) == 0

    out_profile = tmp_path / "extracted.json"
    report = tmp_path / "report.md"
    assert main(["extract", str(doc), "-o", str(out_profile),
                 "--report", str(report)]) == 0
    data = json.loads(out_profile.read_text(encoding="utf-8"))
    assert [lv["key"] for lv in data["levels"]][:2] == ["title", "title2"]
    assert "서식 추출 리포트" in report.read_text(encoding="utf-8")


def test_preview_writes_html(tmp_path, repo_root):
    src = tmp_path / "in.md"
    src.write_text("# 장\n□ 하나\n", encoding="utf-8")
    doc = tmp_path / "doc.hwpx"
    main(["build", str(src), "-p", "policy-default", "-o", str(doc), "--no-lint"])
    html = tmp_path / "preview.html"
    assert main(["preview", str(doc), "-o", str(html)]) == 0
    assert "근사 미리보기" in html.read_text(encoding="utf-8")


def test_diagram_shorthand(tmp_path):
    out = tmp_path / "org.hwpx"
    assert main(["diagram", "대표 > 기획부, 운영부", "-o", str(out)]) == 0
    assert out.exists()


def test_export_skill(tmp_path):
    target = tmp_path / "skill"
    assert main(["export-skill", "policy-default", "-o", str(target)]) == 0
    skill_md = (target / "SKILL.md").read_text(encoding="utf-8")
    assert "마커 규칙" in skill_md and "□" in skill_md
    assert (target / "scripts" / "build.py").exists()
    prompt = (target / "prompt.txt").read_text(encoding="utf-8")
    assert ":::diagram" in prompt and len(prompt) > 100


def test_export_skill_covers_every_diagram_type(tmp_path):
    """스킬을 쓰는 에이전트가 도식 네 가지를 다 알 수 있어야 한다."""
    target = tmp_path / "skill"
    assert main(["export-skill", "policy-default", "-o", str(target)]) == 0
    skill_md = (target / "SKILL.md").read_text(encoding="utf-8")

    for kind in ("type=org", "type=flow", "type=matrix", "type=strategy"):
        assert kind in skill_md, f"{kind} 설명이 없음"
    assert "{fill=#C00000 color=#FFFFFF}" in skill_md          # 색 지정 예시
    assert "layout=side" in skill_md                            # 상자가 많을 때
    assert "border=none" in skill_md and "link=dash" in skill_md
    assert "에이전트가 직접 그림을 보고" in skill_md            # 그림뿐일 때의 절차

    front = skill_md.split("---")[1]
    for word in ("조직도", "체계도", "절차도"):
        assert word in front, f"description에 '{word}'가 없어 도식 요청에 안 걸린다"


def test_export_skill_bundles_a_capture_script(tmp_path):
    target = tmp_path / "skill"
    assert main(["export-skill", "policy-default", "-o", str(target)]) == 0
    script = (target / "scripts" / "capture.py").read_text(encoding="utf-8")
    assert "run_capture" in script and "profile.json" in script


def test_exported_skill_scripts_actually_run(tmp_path):
    """동봉본만으로 도식 가져오기 → 문서 생성이 돌아야 한다."""
    import subprocess
    import sys

    target = tmp_path / "skill"
    assert main(["export-skill", "policy-default", "-o", str(target),
                 "--standalone"]) == 0

    source = tmp_path / "org.mmd"
    source.write_text("flowchart TD\n A[본부] --> B[가팀]\n A --> C[나팀]\n",
                      encoding="utf-8")
    block, doc = tmp_path / "block.txt", tmp_path / "org.hwpx"
    run = subprocess.run(
        [sys.executable, str(target / "scripts" / "capture.py"), str(source),
         "-o", str(block), "--hwpx", str(doc)],
        capture_output=True, text=True, cwd=str(target))
    assert run.returncode == 0, run.stderr
    assert ":::diagram" in block.read_text(encoding="utf-8")
    assert doc.exists()

    body = tmp_path / "input.md"
    body.write_text(block.read_text(encoding="utf-8"), encoding="utf-8")
    out = tmp_path / "report.hwpx"
    run = subprocess.run(
        [sys.executable, str(target / "scripts" / "build.py"), str(body),
         "-o", str(out)], capture_output=True, text=True, cwd=str(target))
    assert run.returncode == 0, run.stderr
    assert out.exists()


def test_export_skill_standalone_bundles_package(tmp_path):
    target = tmp_path / "skill"
    assert main(["export-skill", "policy-default", "-o", str(target),
                 "--standalone"]) == 0
    assert (target / "scripts" / "hwpx_studio" / "engine.py").exists()
    assert not list((target / "scripts" / "hwpx_studio").glob("**/__pycache__"))


def test_missing_file_is_reported(tmp_path, capsys):
    assert main(["build", str(tmp_path / "nope.md"), "-o", str(tmp_path / "x.hwpx")]) == 2


def test_exported_build_script_supports_preview_and_strict(tmp_path):
    """SKILL.md가 안내하는 옵션을 동봉 스크립트가 실제로 받아야 한다."""
    import subprocess
    import sys

    target = tmp_path / "skill"
    assert main(["export-skill", "policy-default", "-o", str(target),
                 "--standalone"]) == 0

    body = tmp_path / "input.md"
    body.write_text("# 시험\n## 개요\n□ 첫 주제\n○ 첫 항목\n- 가\n- 나\n"
                    "○ 둘째 항목\n- 다\n- 라\n□ 둘째 주제\n○ 셋째 항목\n- 마\n- 바\n"
                    "○ 넷째 항목\n- 사\n- 아\n", encoding="utf-8")
    out, preview = tmp_path / "r.hwpx", tmp_path / "r.html"
    run = subprocess.run(
        [sys.executable, str(target / "scripts" / "build.py"), str(body),
         "-o", str(out), "--preview", str(preview)],
        capture_output=True, text=True, cwd=str(target))
    assert run.returncode == 0, run.stderr
    assert out.exists() and preview.exists()


def test_skill_build_script_assembles_the_house_skill(tmp_path):
    """skills/build.py: 내보낸 뼈대 + 손으로 쓴 문서 + 집필 규칙."""
    import json
    import subprocess
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    run = subprocess.run(
        [sys.executable, str(root / "skills" / "build.py"), "-o", str(tmp_path)],
        capture_output=True, text=True)
    assert run.returncode == 0, run.stderr

    skill = tmp_path / "hwpx-report-studio"
    for name in ("SKILL.md", "profile.json", "설치.md", "prompt.txt"):
        assert (skill / name).exists(), f"{name} 없음"
    for name in ("level-system.md", "hierarchy-rules.md", "examples.md", "diagram.md"):
        assert (skill / "reference" / name).exists(), f"reference/{name} 없음"
    assert (skill / "scripts" / "hwpx_studio" / "engine.py").exists()

    profile = json.loads((skill / "profile.json").read_text(encoding="utf-8"))
    assert profile["rules"]["head_pattern"]["L1"]          # 머릿글 규칙이 실려 있다
    assert profile["rules"]["min_children"] == {"title2": 2, "L1": 2, "L2": 2}

    skill_md = (skill / "SKILL.md").read_text(encoding="utf-8")
    assert "표준 작업 절차" in skill_md and "계층 균형" in skill_md   # 기존 스킬에서 옮겨온 것
    assert "type=strategy" in skill_md                               # 새로 생긴 것
