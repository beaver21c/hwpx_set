"""서식 스킬(skillpack) — 채팅창에 올리는 zip이 조건을 지키고, 설치 없이 도는가."""

from __future__ import annotations

import io
import json
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from hwpx_studio.cli import main
from hwpx_studio.profile import load_profile
from hwpx_studio.skillpack import build_skill, pack_skill, sample_text, skill_fields

ROOT = Path(__file__).resolve().parents[1]
PRESETS = ["kihasa-research", "policy-default", "gov-3level", "narrative"]


def _description(skill_md: str) -> str:
    front = skill_md.split("---", 2)[1]
    body = front.split("description:", 1)[1].strip()
    return " ".join(body.lstrip(">-").split())


def _unpack(tmp_path: Path, data: bytes) -> Path:
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        z.extractall(str(tmp_path))
    (root,) = [p for p in tmp_path.iterdir() if p.is_dir()]
    return root


@pytest.mark.parametrize("preset", PRESETS)
def test_skill_zip_meets_upload_rules(preset):
    """claude.ai: 맨 위 폴더 하나 = 스킬 이름, 설명 200자 이하, 이름 소문자·하이픈."""
    profile = load_profile(preset)
    fields = skill_fields(profile, "아주 긴 이름의 ○○기관 연구보고서 표준 서식 2026년 개정판",
                          "my-crown")
    files = build_skill(profile, fields["name"], skill_id="my-crown")
    with zipfile.ZipFile(io.BytesIO(pack_skill(files, fields["slug"]))) as z:
        roots = {n.split("/", 1)[0] for n in z.namelist()}
        skill_md = z.read(f"{fields['slug']}/SKILL.md").decode("utf-8")
    assert roots == {"my-crown"}
    assert re.search(r"^name: my-crown$", skill_md, re.M)
    assert len(_description(skill_md)) <= 200
    assert "{{" not in skill_md, "채우지 않은 자리표가 남았다"


def test_skill_carries_everything_it_needs():
    files = build_skill(load_profile("kihasa-research"), "크라운판")
    for need in ("SKILL.md", "README.md", "profile.json", "template.hwpx", "예시.md",
                 "scripts/hwpx_build.py"):
        assert need in files, f"{need}가 빠지면 채팅창에서 못 쓴다"
    assert json.loads(files["profile.json"])["page"]["width_mm"] == 166


@pytest.mark.parametrize("preset", PRESETS)
def test_unpacked_skill_builds_with_the_standard_library_only(tmp_path, preset):
    """채팅창처럼 설치 없는 파이썬(-S: site-packages 없음)으로 예시 원고를 문서로 만든다."""
    profile = load_profile(preset)
    fields = skill_fields(profile, "")
    root = _unpack(tmp_path, pack_skill(build_skill(profile), fields["slug"]))
    done = subprocess.run(
        [sys.executable, "-S", "scripts/hwpx_build.py", "예시.md", "-o", "결과.hwpx"],
        cwd=root, capture_output=True, text=True, timeout=120)
    assert done.returncode == 0, done.stdout + done.stderr
    with zipfile.ZipFile(str(root / "결과.hwpx")) as z:
        section = z.read("Contents/section0.xml").decode("utf-8")
    assert "추진 체계" in section                # 도식 제목
    assert "처리 건수" in section                # 표
    assert "<hp:footNote" in section             # 각주


def test_crown_skill_output_is_crown_sized(tmp_path):
    profile = load_profile("kihasa-research")
    root = _unpack(tmp_path, pack_skill(build_skill(profile), "crown"))
    subprocess.run([sys.executable, "-S", "scripts/hwpx_build.py", "예시.md", "-o", "r.hwpx"],
                   cwd=root, check=True, capture_output=True, timeout=120)
    with zipfile.ZipFile(str(root / "r.hwpx")) as z:
        section = z.read("Contents/section0.xml").decode("utf-8")
    page = re.search(r"<hp:pagePr[^>]*>", section).group()
    assert 'width="47056"' in page and 'height="68316"' in page     # 166×241mm


def test_cli_skill_command(tmp_path):
    out = tmp_path / "crown.zip"
    assert main(["skill", "--pack", str(out), "--id", "hwpx-crown-report"]) == 0
    with zipfile.ZipFile(str(out)) as z:
        assert "hwpx-crown-report/SKILL.md" in z.namelist()


def test_sample_uses_this_profiles_markers():
    text = sample_text(load_profile("kihasa-research"))
    assert "표) 연도별 실적" in text and "그림) 추진 체계" in text
    assert "#### 가. 단계의 예시 문장이다." in text


# ──────────────────────────────────────────────────────────────
# 브라우저(skillpack.js)가 같은 파일을 만드는가
# ──────────────────────────────────────────────────────────────
JS = """
import fs from 'fs';
import { buildSkill } from './docs/js/skillpack.js';
const cases = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const out = {};
for (const [key, c] of Object.entries(cases)) {
  const { files, fields } = buildSkill(c.profile, c.name, new Uint8Array([1, 2, 3]), c.id);
  const texts = {};
  for (const [path, data] of files) {
    if (path !== 'template.hwpx') texts[path] = new TextDecoder().decode(data);
  }
  out[key] = { fields, texts };
}
console.log(JSON.stringify(out));
"""


@pytest.mark.skipif(shutil.which("node") is None, reason="node 없음")
def test_browser_builds_the_same_skill(tmp_path):
    cases = {}
    for preset in PRESETS:
        cases[preset] = {"profile": load_profile(preset), "name": "", "id": ""}
    cases["named"] = {"profile": load_profile("kihasa-research"),
                      "name": "우리 기관 보고서", "id": "our-report"}
    source = tmp_path / "cases.json"
    source.write_text(json.dumps(cases, ensure_ascii=False), encoding="utf-8")
    script = tmp_path / "run.mjs"
    script.write_text(JS.replace("./docs/", (ROOT / "docs").as_uri() + "/"), encoding="utf-8")
    done = subprocess.run(["node", str(script), str(source)], cwd=ROOT,
                          capture_output=True, text=True, timeout=120)
    assert done.returncode == 0, done.stderr
    js = json.loads(done.stdout)

    for key, case in cases.items():
        fields = skill_fields(case["profile"], case["name"], case["id"])
        files = build_skill(case["profile"], case["name"], template=b"\x01\x02\x03",
                            skill_id=case["id"])
        assert js[key]["fields"] == fields, key
        for path, data in files.items():
            if path == "template.hwpx":
                continue
            if path == "profile.json":
                assert json.loads(js[key]["texts"][path]) == json.loads(data), key
            else:
                assert js[key]["texts"][path] == data.decode("utf-8"), f"{key}: {path}"
