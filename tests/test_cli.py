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


def test_export_skill_standalone_bundles_package(tmp_path):
    target = tmp_path / "skill"
    assert main(["export-skill", "policy-default", "-o", str(target),
                 "--standalone"]) == 0
    assert (target / "scripts" / "hwpx_studio" / "engine.py").exists()
    assert not list((target / "scripts" / "hwpx_studio").glob("**/__pycache__"))


def test_missing_file_is_reported(tmp_path, capsys):
    assert main(["build", str(tmp_path / "nope.md"), "-o", str(tmp_path / "x.hwpx")]) == 2
