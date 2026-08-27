#!/usr/bin/env python3
"""브라우저 엔진(JS)과 파이썬 엔진의 산출물을 대조한다.

같은 입력·프로파일로 두 엔진이 만든 hwpx의 **스타일 속성과 본문 텍스트**가
같은지 본다(ID 번호는 달라도 된다). CI에서 돌린다.

    python tools/compare_js_python.py
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hwpx.templates import blank_document_bytes  # noqa: E402

from hwpx_studio.engine import build_document  # noqa: E402
from hwpx_studio.parser import parse_file  # noqa: E402
from hwpx_studio.profile import load_profile  # noqa: E402

#: 도식 수집 대조 대상(파일, 형식, 제목)
CAPTURE_CASES = [
    ("examples/capture/org.mmd", "auto", "위원회 구성"),
    ("examples/capture/process.mmd", "auto", "처리 절차"),
    ("examples/capture/org.svg", "auto", "위원회 구성"),
    ("tests/fixtures/capture_rows.svg", "auto", ""),
]

#: (입력, 프로파일). 이미지 렌더 도식(render=image)은 파이썬 전용이라 제외한다.
CASES = [
    ("examples/input_outline.md", "policy-default"),
    ("tests/fixtures/diagram_table_only.md", "policy-default"),
    ("tests/fixtures/diagram_styled.md", "policy-default"),
    ("tests/fixtures/diagram_side.md", "policy-default"),
    ("tests/fixtures/diagram_strategy.md", "policy-default"),
    ("tests/fixtures/footnote.md", "policy-default"),
    ("examples/input_research.md", "kihasa-research"),
    ("examples/input_narrative.md", "narrative"),
]


def style_attributes(path: Path) -> dict:
    """스타일명 → 서식 속성(글꼴·크기·굵기·색·정렬·줄간격·여백)."""
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


def texts(path: Path) -> list:
    with zipfile.ZipFile(str(path)) as zf:
        section = zf.read("Contents/section0.xml").decode("utf-8")
    return re.findall(r"<hp:t>(.*?)</hp:t>", section)


def table_shapes(path: Path) -> list:
    """(행, 열, 셀 수) 목록 — 표·도식 구조 비교용."""
    with zipfile.ZipFile(str(path)) as zf:
        section = zf.read("Contents/section0.xml").decode("utf-8")
    out = []
    for tbl in re.findall(r"<hp:tbl.*?</hp:tbl>", section, re.S):
        head = re.search(r'rowCnt="(\d+)" colCnt="(\d+)"', tbl)
        spans = re.findall(r'<hp:cellSpan colSpan="(\d+)"', tbl)
        out.append((head.group(1), head.group(2), len(spans),
                    sorted(set(spans), key=int)))
    return out


def cell_designs(path: Path) -> list:
    """도식 표의 셀 디자인(채움색·테두리 변/색/선종류) 목록 — 색 재현 비교용."""
    with zipfile.ZipFile(str(path)) as zf:
        header = zf.read("Contents/header.xml").decode("utf-8")
        section = zf.read("Contents/section0.xml").decode("utf-8")

    designs = {}
    for m in re.finditer(r'<hh:borderFill id="(\d+)"(.*?)</hh:borderFill>', header, re.S):
        fill = re.search(r'faceColor="(#?\w+)"', m.group(2))
        edges = tuple(
            (name, typ.upper(), color.upper())
            for name, typ, color in re.findall(
                r'<hh:(left|right|top|bottom)Border type="(\w+)" width="[^"]*" color="(#\w+)"',
                m.group(2))
            if typ.upper() != "NONE")
        face = (fill.group(1).upper() if fill and fill.group(1) != "none" else None)
        designs[m.group(1)] = (face, edges)

    out = []
    for tbl in re.findall(r"<hp:tbl.*?</hp:tbl>", section, re.S):
        used = [designs.get(i) for i in re.findall(r'borderFillIDRef="(\d+)"', tbl)]
        out.append(sorted({d for d in used if d and (d[0] or d[1])},
                          key=lambda d: (d[0] or "", d[1])))
    return out


def footnotes(path: Path) -> list:
    """(번호, 매김표 문자, 각주 본문) 목록 — 각주 재현 비교용."""
    with zipfile.ZipFile(str(path)) as zf:
        section = zf.read("Contents/section0.xml").decode("utf-8")
    out = []
    for note in re.findall(r"<hp:footNote .*?</hp:footNote>", section, re.S):
        head = re.search(r'number="(\d+)" suffixChar="(\d+)"', note)
        body = re.search(r"<hp:t>(.*?)</hp:t>", note, re.S)
        num = re.search(r'<hp:autoNum num="(\d+)" numType="(\w+)"', note)
        out.append((head.group(1), head.group(2), num.groups() if num else None,
                    body.group(1) if body else ""))
    return out


def build_with_js(template: Path, profile_path: Path, input_path: Path, out: Path) -> None:
    script = f"""
    const m = await import({json.dumps(str(ROOT / 'docs' / 'js' / 'hwpx-studio.js'))});
    const {{ readFile, writeFile }} = await import('node:fs/promises');
    const tpl = await readFile({json.dumps(str(template))});
    const profile = JSON.parse(await readFile({json.dumps(str(profile_path))}, 'utf8'));
    const text = await readFile({json.dumps(str(input_path))}, 'utf8');
    const r = await m.buildFromText(tpl, profile, text);
    await writeFile({json.dumps(str(out))}, r.bytes);
    """
    subprocess.run(["node", "--input-type=module", "-e", script], check=True)


def capture_with_js(path: Path, kind: str, title: str) -> str:
    script = f"""
    const m = await import({json.dumps(str(ROOT / 'docs' / 'js' / 'capture.js'))});
    const {{ readFile }} = await import('node:fs/promises');
    const text = await readFile({json.dumps(str(path))}, 'utf8');
    const r = m.captureText(text, {json.dumps(kind)}, {json.dumps(title)});
    process.stdout.write(m.specToText(r.spec) + "\\n---\\n" + r.warnings.join("\\n"));
    """
    out = subprocess.run(["node", "--input-type=module", "-e", script],
                         check=True, capture_output=True, text=True)
    return out.stdout


def form_with_js(path: Path, name: str, bullets: str = "auto") -> dict:
    script = f"""
    const m = await import({json.dumps(str(ROOT / 'docs' / 'js' / 'formkit.js'))});
    const z = await import({json.dumps(str(ROOT / 'docs' / 'js' / 'zip.js'))});
    const {{ readFile }} = await import('node:fs/promises');
    const data = await readFile({json.dumps(str(path))});
    const parts = await z.unzip(
      data.buffer.slice(data.byteOffset, data.byteOffset + data.byteLength));
    const dec = new TextDecoder();
    const text = {{}};
    for (const [n, b] of parts) {{
      if (n.startsWith('Contents/') && n.endsWith('.xml')) text[n] = dec.decode(b);
    }}
    const r = m.analyzeParts(text, {json.dumps(name)}, {json.dumps(bullets)});
    process.stdout.write(JSON.stringify(r.form));
    """
    out = subprocess.run(["node", "--input-type=module", "-e", script],
                         check=True, capture_output=True, text=True)
    return json.loads(out.stdout)


def same_value(left, right, path: str, diffs: list) -> None:
    """숫자는 값으로 비교한다(JSON에서 18.0과 18은 같은 값이다)."""
    if isinstance(left, bool) or isinstance(right, bool):
        if left != right:
            diffs.append(f"{path}: {left!r} ≠ {right!r}")
        return
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        if abs(left - right) > 1e-9:
            diffs.append(f"{path}: {left} ≠ {right}")
        return
    if isinstance(left, dict) and isinstance(right, dict):
        for key in sorted(set(left) | set(right)):
            if key not in left or key not in right:
                diffs.append(f"{path}/{key}: 한쪽에만 있음")
            else:
                same_value(left[key], right[key], f"{path}/{key}", diffs)
        return
    if isinstance(left, list) and isinstance(right, list):
        if len(left) != len(right):
            diffs.append(f"{path}: 길이 {len(left)} ≠ {len(right)}")
            return
        for i, (a, b) in enumerate(zip(left, right)):
            same_value(a, b, f"{path}[{i}]", diffs)
        return
    if left != right:
        diffs.append(f"{path}: {left!r} ≠ {right!r}")


def compare_forms(failures: list, tmp_path: Path) -> None:
    """양식 해부도 두 엔진이 같은 form.json을 내야 한다."""
    sys.path.insert(0, str(ROOT / "tests"))
    from formfixtures import (                              # noqa: PLC0415
        auto_bullet_form, chapter_form, plain_form, table_note_form)

    from hwpx_studio.formkit import analyze                 # noqa: PLC0415

    for label, maker in (("기호가 텍스트에 든 양식", plain_form),
                         ("한글이 기호를 붙이는 양식", auto_bullet_form),
                         ("표 주가 있는 양식", table_note_form),
                         ("장 표지·표 번호가 있는 양식", chapter_form)):
        path = tmp_path / f"form_{len(label)}.hwpx"
        path.write_bytes(maker())
        # 글머리표 담당을 고르는 세 갈래 모두에서 같아야 한다
        for bullets in ("auto", "hangul", "text"):
            py_form = analyze(str(path), label, bullets=bullets).form
            js_form = form_with_js(path, label, bullets)
            diffs: list = []
            same_value(py_form, js_form, "form", diffs)
            if diffs:
                failures.append(f"formkit {label} (--bullets {bullets}): 결과 불일치\n    "
                                + "\n    ".join(diffs[:12]))
            else:
                print(f"  ✔ formkit {label} · 기호 {bullets}: "
                      f"레벨 {len(py_form['levels'])}개 일치")


def readback_with_js(path: Path, form_path: Path) -> str:
    script = f"""
    const m = await import({json.dumps(str(ROOT / 'docs' / 'js' / 'readback.js'))});
    const {{ readFile }} = await import('node:fs/promises');
    const data = await readFile({json.dumps(str(path))});
    const form = JSON.parse(await readFile({json.dumps(str(form_path))}, 'utf8'));
    const r = await m.readBack(
      data.buffer.slice(data.byteOffset, data.byteOffset + data.byteLength), form);
    process.stdout.write(r.text + "\\n---\\n" + r.report);
    """
    out = subprocess.run(["node", "--input-type=module", "-e", script],
                         check=True, capture_output=True, text=True)
    return out.stdout


def compare_readback(failures: list, tmp_path: Path) -> None:
    """되돌리기도 두 엔진이 같은 마커 텍스트를 내야 한다."""
    import importlib.util                                    # noqa: PLC0415

    sys.path.insert(0, str(ROOT / "tests"))
    from formfixtures import plain_form                      # noqa: PLC0415

    from hwpx_studio.export_form import build_bundle         # noqa: PLC0415

    asset = ROOT / "hwpx_studio" / "assets" / "read_hwpx.py"
    spec = importlib.util.spec_from_file_location("_read_hwpx_parity", asset)
    reader = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = reader
    spec.loader.exec_module(reader)

    files, result = build_bundle(plain_form(), name="대조양식")
    form_path = tmp_path / "form.json"
    form_path.write_bytes(files["form.json"])

    for rel in ("tests/fixtures/footnote.md", "examples/input_outline.md"):
        profile_path = ROOT / "hwpx_studio" / "profiles" / "policy-default.json"
        profile = load_profile(str(profile_path))
        parsed = parse_file(str(ROOT / rel), profile)
        source = tmp_path / f"read_{Path(rel).stem}.hwpx"
        build_document(profile, parsed.items, str(source))

        blocks = reader.read_blocks(source)
        notes = reader.classify(blocks)
        markers, _name = reader.load_markers(form_path)
        py_text = (reader.to_marker_text(blocks, markers) + "\n---\n"
                   + reader.render_report(blocks, markers, notes))
        js_text = readback_with_js(source, form_path)
        if py_text.strip() != js_text.strip():
            failures.append(f"readback {rel}: 결과 불일치\n"
                            f"    --- py ---\n{py_text}\n    --- js ---\n{js_text}")
        else:
            print(f"  ✔ readback {rel}: 문단 {len(blocks)}개 일치")
    void = result
    del void


def compare_capture(failures: list) -> int:
    """도식 수집도 두 엔진이 같은 블록을 내야 한다."""
    from hwpx_studio.capture import capture as py_capture, spec_to_text

    for rel, kind, title in CAPTURE_CASES:
        path = ROOT / rel
        result = py_capture(str(path), kind, title)
        py_text = spec_to_text(result.spec) + "\n---\n" + "\n".join(result.warnings)
        js_text = capture_with_js(path, kind, title)
        if py_text.strip() != js_text.strip():
            failures.append(f"capture {rel}: 결과 불일치\n"
                            f"    --- py ---\n{py_text}\n    --- js ---\n{js_text}")
        else:
            print(f"  ✔ capture {rel}: 상자 {len(result.spec.lines)}줄 일치")
    return 0


def main() -> int:
    failures = []
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        template = tmp_path / "template.hwpx"
        template.write_bytes(blank_document_bytes())

        for rel_input, profile_name in CASES:
            input_path = ROOT / rel_input
            profile_path = ROOT / "hwpx_studio" / "profiles" / f"{profile_name}.json"
            profile = load_profile(str(profile_path))

            py_out = tmp_path / f"py_{Path(rel_input).stem}.hwpx"
            parsed = parse_file(str(input_path), profile)
            build_document(profile, parsed.items, str(py_out))

            js_out = tmp_path / f"js_{Path(rel_input).stem}.hwpx"
            build_with_js(template, profile_path, input_path, js_out)

            label = f"{rel_input} ({profile_name})"
            py_styles, js_styles = style_attributes(py_out), style_attributes(js_out)
            for name, attrs in py_styles.items():
                if name not in js_styles:
                    failures.append(f"{label}: JS에 '{name}' 스타일 없음")
                elif js_styles[name] != attrs:
                    failures.append(f"{label}: '{name}' 서식 불일치\n"
                                    f"    py={attrs}\n    js={js_styles[name]}")

            py_texts = texts(py_out)
            js_texts = [t for t in texts(js_out) if t]
            py_texts = [t for t in py_texts if t]
            if py_texts != js_texts:
                only_py = [t for t in py_texts if t not in js_texts][:3]
                only_js = [t for t in js_texts if t not in py_texts][:3]
                failures.append(f"{label}: 본문 텍스트 불일치 "
                                f"(py {len(py_texts)}개 / js {len(js_texts)}개)\n"
                                f"    py에만={only_py}\n    js에만={only_js}")

            py_designs, js_designs = cell_designs(py_out), cell_designs(js_out)
            if py_designs != js_designs:
                failures.append(f"{label}: 셀 디자인(색·테두리) 불일치\n"
                                f"    py={py_designs}\n    js={js_designs}")

            py_notes, js_notes = footnotes(py_out), footnotes(js_out)
            if py_notes != js_notes:
                failures.append(f"{label}: 각주 불일치\n"
                                f"    py={py_notes}\n    js={js_notes}")

            py_tables, js_tables = table_shapes(py_out), table_shapes(js_out)
            if py_tables != js_tables:
                failures.append(f"{label}: 표·도식 구조 불일치\n"
                                f"    py={py_tables}\n    js={js_tables}")

            if not failures:
                print(f"  ✔ {label}: 스타일 {len(py_styles)}개 · 텍스트 {len(py_texts)}개 · "
                      f"표 {len(py_tables)}개 · 각주 {len(py_notes)}개 · 셀 디자인 "
                      f"{sum(len(d) for d in py_designs)}종 일치")

        compare_capture(failures)
        compare_forms(failures, tmp_path)
        compare_readback(failures, tmp_path)

    if failures:
        print("\n브라우저 엔진과 파이썬 엔진의 산출물이 다릅니다:\n")
        for item in failures:
            print(f"  ✘ {item}")
        return 1
    print("\n두 엔진의 산출물이 일치합니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
