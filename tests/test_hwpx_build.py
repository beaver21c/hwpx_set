"""표준 라이브러리판 hwpx_build.py 검사.

JS 엔진(docs/js/hwpx-studio.js)과 zip 안의 모든 파일이 바이트까지 같은지 본다.
"""

import ast
import base64
import importlib.util
import io
import json
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "hwpx_studio" / "assets" / "hwpx_build.py"
PROFILES = sorted((ROOT / "hwpx_studio" / "profiles").glob("*.json"))
INPUTS = sorted((ROOT / "examples").glob("*.md")) + sorted((ROOT / "tests" / "fixtures").glob("*.md"))

#: 여러 사례를 node 한 번에 돌린다. 입력: {template, cases:[{profile,input,out}]}
NODE_RUNNER = """
const m = await import(process.argv[1]);
const { readFile, writeFile } = await import('node:fs/promises');
let raw = '';
for await (const chunk of process.stdin) raw += chunk;
const job = JSON.parse(raw);
const tpl = await readFile(job.template);
const out = [];
for (const c of job.cases) {
  try {
    const profile = JSON.parse(await readFile(c.profile, 'utf8'));
    const text = await readFile(c.input, 'utf8');
    const r = await m.buildFromText(tpl, profile, text);
    await writeFile(c.out, r.bytes);
    out.push({ ok: true, issues: r.issues, warnings: r.warnings });
  } catch (e) {
    out.push({ ok: false, error: String(e && e.stack || e) });
  }
}
process.stdout.write(JSON.stringify(out));
"""


def load_module():
    spec = importlib.util.spec_from_file_location("hwpx_build", MODULE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def template_bytes():
    text = (ROOT / "docs" / "assets.js").read_text(encoding="utf-8")
    return base64.b64decode(re.search(r'HWPX_TEMPLATE_B64 = "([^"]*)"', text).group(1))


def entries(data):
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        return [(info.filename, info.compress_type, zf.read(info)) for info in zf.infolist()]


def test_stdlib_only():
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0, "상대 import 금지"
            names.add(node.module.split(".")[0])
    outside = {n for n in names if n not in sys.stdlib_module_names and n != "__future__"}
    assert not outside, outside


@pytest.fixture(scope="module")
def js_results(tmp_path_factory):
    if shutil.which("node") is None:
        pytest.skip("node가 없음")
    tmp = tmp_path_factory.mktemp("js")
    tpl = tmp / "template.hwpx"
    tpl.write_bytes(template_bytes())
    cases = []
    for inp in INPUTS:
        for prof in PROFILES:
            out = tmp / f"{inp.stem}__{prof.stem}.hwpx"
            cases.append({"profile": str(prof), "input": str(inp), "out": str(out)})
    proc = subprocess.run(
        ["node", "--input-type=module", "-e", NODE_RUNNER,
         str(ROOT / "docs" / "js" / "hwpx-studio.js")],
        input=json.dumps({"template": str(tpl), "cases": cases}),
        capture_output=True, text=True, encoding="utf-8", check=True)
    return list(zip(cases, json.loads(proc.stdout)))


def test_matches_js_engine(js_results):
    mod = load_module()
    tpl = template_bytes()
    compared = 0
    failures = []
    for case, js in js_results:
        label = f"{Path(case['input']).name} × {Path(case['profile']).stem}"
        profile = json.loads(Path(case["profile"]).read_text(encoding="utf-8"))
        text = Path(case["input"]).read_bytes().decode("utf-8", "replace")
        if not js["ok"]:
            # JS가 던지는 조합은 파이썬판도 던져야 한다
            with pytest.raises(Exception):
                mod.build_from_text(tpl, profile, text)
            continue
        py = mod.build_from_text(tpl, profile, text)
        js_entries = entries(Path(case["out"]).read_bytes())
        py_entries = entries(py["bytes"])
        if [e[:2] for e in js_entries] != [e[:2] for e in py_entries]:
            failures.append(f"{label}: 항목 목록 다름")
        for (name, _, a), (_, _, b) in zip(js_entries, py_entries):
            if a != b:
                failures.append(f"{label}: {name} 다름")
        js_issues = mod.from_js(mod.to_js(js["issues"]))
        if js_issues != py["issues"]:
            failures.append(f"{label}: 검사 결과 다름")
        if mod.from_js(mod.to_js(js["warnings"])) != py["warnings"]:
            failures.append(f"{label}: 경고 다름")
        compared += 1
    assert not failures, "\n".join(failures)
    assert compared == len(js_results)


def test_cli_end_to_end(tmp_path):
    tpl = tmp_path / "template.hwpx"
    tpl.write_bytes(template_bytes())
    out = tmp_path / "결과.hwpx"
    proc = subprocess.run(
        [sys.executable, str(MODULE), str(ROOT / "examples" / "input_research.md"),
         "-o", str(out), "--profile", str(ROOT / "hwpx_studio" / "profiles" / "kihasa-research.json"),
         "--template", str(tpl)],
        capture_output=True, text=True, encoding="utf-8")
    assert proc.returncode == 0, proc.stderr
    assert "생성:" in proc.stdout and "오류 0건" in proc.stdout
    with zipfile.ZipFile(out) as zf:
        names = zf.namelist()
        assert names[0] == "mimetype"
        assert zf.getinfo("mimetype").compress_type == zipfile.ZIP_STORED
        section = zf.read("Contents/section0.xml").decode("utf-8")
    first = next(line for line in (ROOT / "examples" / "input_research.md")
                 .read_text(encoding="utf-8").splitlines() if line.startswith("# "))
    assert first[2:].strip() in section


def test_cli_check_only_and_strict(tmp_path):
    tpl = tmp_path / "template.hwpx"
    tpl.write_bytes(template_bytes())
    prof = tmp_path / "profile.json"
    prof.write_text(json.dumps({"levels": [{"key": "a", "marker": "□"}]}), encoding="utf-8")
    src = tmp_path / "in.md"
    src.write_text("□ 제목\n", encoding="utf-8")
    common = [sys.executable, str(MODULE), str(src), "--profile", str(prof), "--template", str(tpl)]
    proc = subprocess.run(common + ["--check-only"], capture_output=True, text=True, encoding="utf-8")
    assert proc.returncode == 0 and "오류 0건" in proc.stdout
    assert not (tmp_path / "in.hwpx").exists()
    proc = subprocess.run(common + ["--strict"], capture_output=True, text=True, encoding="utf-8")
    assert proc.returncode == 0 and (tmp_path / "in.hwpx").exists()


def test_js_quirks():
    mod = load_module()
    assert mod.js_round(2.5) == 3 and mod.js_round(-2.5) == -2 and mod.js_round(0.49999999999999994) == 0
    assert mod.to_fixed(2.5, 0) == "3" and mod.to_fixed(1.005, 2) == "1.00"
    assert mod.js_str(0.00001) == "0.00001" and mod.js_str(1e21) == "1e+21" and mod.js_str(160.0) == "160"
    assert mod.js_replace("ab", re.compile("(a)"), "$11") == "a1b"
    assert len(mod.to_js("😀")) == 2
