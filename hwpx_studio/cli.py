"""hwpx-studio 명령줄 도구.

    hwpx-studio init     [--from policy-default] profile.json
    hwpx-studio extract  ref.hwpx -o profile.json [--report report.md]
    hwpx-studio build    input.md -p profile.json -o out.hwpx [--strict] [--preview]
    hwpx-studio lint     input.md -p profile.json [--strict]
    hwpx-studio preview  out.hwpx -o preview.html
    hwpx-studio diagram  "대표 > 기획부, 운영부" -o org.hwpx
    hwpx-studio capture  조직도.svg --hwpx 조직도.hwpx
    hwpx-studio export-skill profile.json -o ./my-skill [--standalone]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from .profile import (
    DEFAULT_PROFILE,
    list_builtin_profiles,
    load_profile,
    merge_profile,
    resolve_profile_path,
    save_profile,
    validate_profile,
)


def _echo(msg: str) -> None:
    print(msg)


def _load(profile_arg: Optional[str]) -> Dict[str, Any]:
    return load_profile(profile_arg or "policy-default")


# ──────────────────────────────────────────────────────────────
# init
# ──────────────────────────────────────────────────────────────
def run_init(out_path: str, base: str = "policy-default", levels: Optional[int] = None,
             mode: Optional[str] = None, font_bold: Optional[str] = None,
             font_light: Optional[str] = None) -> int:
    try:
        profile = load_profile(base)
    except FileNotFoundError:
        _echo(f"기본 프로파일을 찾을 수 없음: {base} "
              f"(사용 가능: {', '.join(list_builtin_profiles())})")
        return 1

    if mode:
        profile["mode"] = mode
    if font_bold:
        profile["fonts"]["bold"] = font_bold
    if font_light:
        profile["fonts"]["light"] = font_light
        profile["fonts"]["fallback"] = font_light
    if levels:
        profile["levels"] = profile["levels"][:max(1, levels)]
        keys = {lv["key"] for lv in profile["levels"]}
        if profile["table"].get("anchor_level") not in keys:
            profile["table"]["anchor_level"] = None
        profile["rules"]["min_children"] = {
            k: v for k, v in (profile["rules"].get("min_children") or {}).items()
            if k in keys
        }

    errors = validate_profile(profile)
    if errors:
        _echo("프로파일 검증 실패:\n  " + "\n  ".join(errors))
        return 1
    save_profile(profile, out_path)
    _echo(f"생성: {out_path} (레벨 {len(profile['levels'])}개, mode={profile['mode']})")
    return 0


# ──────────────────────────────────────────────────────────────
# extract
# ──────────────────────────────────────────────────────────────
def run_extract(source: str, out_path: Optional[str], report_path: Optional[str],
                name: str = "추출 프로파일", show_report: bool = True) -> int:
    from .extractor import extract_profile, write_outputs

    result = extract_profile(source, name=name)
    if show_report and not report_path:
        _echo(result.report)
    write_outputs(result, out_path, report_path)
    if out_path:
        _echo(f"생성: {out_path} (레벨 {len(result.profile.get('levels', []))}개)")
    if report_path:
        _echo(f"생성: {report_path}")
    if not out_path and not report_path:
        _echo(json.dumps(result.profile, ensure_ascii=False, indent=2))
    _echo("※ 추정 결과다. 리포트의 '접두 후보'와 레벨 순서를 확인한 뒤 사용할 것")
    return 0


# ──────────────────────────────────────────────────────────────
# lint / build
# ──────────────────────────────────────────────────────────────
def _parse_input(input_path: str, profile: Dict[str, Any]):
    from .parser import parse_file

    return parse_file(input_path, profile)


def run_lint(input_path: str, profile_arg: Optional[str], strict: bool = False) -> int:
    from .lint import format_issues, has_blocking, lint_items

    profile = _load(profile_arg)
    parsed = _parse_input(input_path, profile)
    issues = lint_items(parsed.items, profile, parsed.line_of, parsed.warnings)
    _echo(format_issues(issues))
    return 1 if has_blocking(issues, strict) else 0


def run_build(input_path: str, profile_arg: Optional[str], out_path: str,
              strict: bool = False, preview_path: Optional[str] = None,
              lint: bool = True) -> int:
    from .engine import build_document
    from .lint import format_issues, has_blocking, lint_items

    profile = _load(profile_arg)
    parsed = _parse_input(input_path, profile)

    if lint:
        issues = lint_items(parsed.items, profile, parsed.line_of, parsed.warnings)
        if issues:
            _echo(format_issues(issues))
        if has_blocking(issues, strict):
            _echo("중단: 위 사항을 고친 뒤 다시 실행하세요 (--no-lint로 건너뛸 수 있음)")
            return 1

    result = build_document(profile, parsed.items, out_path)
    for warn in result.warnings:
        _echo(f"[경고] {warn}")
    _echo(f"생성: {out_path} ({len(result.data):,} bytes)")

    if preview_path:
        from .preview import render_preview

        _, warns = render_preview(out_path, preview_path)
        for warn in warns:
            _echo(f"[미리보기 경고] {warn}")
        _echo(f"생성: {preview_path}")
    return 0


# ──────────────────────────────────────────────────────────────
# preview / diagram / export-skill
# ──────────────────────────────────────────────────────────────
def run_preview(source: str, out_path: str) -> int:
    from .preview import DISCLAIMER, render_preview

    _, warns = render_preview(source, out_path)
    for warn in warns:
        _echo(f"[경고] {warn}")
    _echo(f"생성: {out_path}\n※ {DISCLAIMER}")
    return 0


def _diagram_spec_from_arg(text: str, dtype: str, title: str):
    """`대표 > 기획부, 운영부` 축약 표기 또는 :::diagram 블록 본문을 spec으로."""
    from .diagram import DiagramSpec, parse_text as parse_diagram_text

    if text.strip().startswith(":::") or "\n" in text:
        return parse_diagram_text(text)
    if dtype == "flow":
        return DiagramSpec(type="flow", title=title, lines=[text])
    lines: List[str] = []
    for depth, part in enumerate(text.split(">")):
        names = [n.strip() for n in part.split(",") if n.strip()]
        for name in names:
            lines.append("  " * depth + name)
    return DiagramSpec(type=dtype, title=title, lines=lines)


def run_diagram(text: str, out_path: str, profile_arg: Optional[str],
                dtype: str = "org", title: str = "", render: Optional[str] = None) -> int:
    from .engine import build_document

    profile = _load(profile_arg)
    spec = _diagram_spec_from_arg(text, dtype, title)
    if render:
        spec.options["render"] = render
    result = build_document(profile, [{"type": "diagram", "spec": spec.to_dict()}], out_path)
    for warn in result.warnings:
        _echo(f"[경고] {warn}")
    _echo(f"생성: {out_path}")
    return 0


def run_capture(source: str, out_path: Optional[str], kind: str, title: str,
                 hwpx_path: Optional[str], profile_arg: Optional[str]) -> int:
    """남의 도식(Mermaid·SVG·HTML)을 읽어 `:::diagram` 블록으로 옮긴다."""
    import sys

    from .capture import capture, capture_text

    if source == "-":
        result = capture_text(sys.stdin.read(), kind, title)
    else:
        result = capture(source, kind, title)

    for warn in result.warnings:
        _echo(f"[경고] {warn}")
    if not result.spec.lines:
        _echo("도식을 읽지 못했다. --kind로 형식을 지정하거나 원본을 확인할 것")
        return 2

    text = result.to_text()
    if result.spec.type == "flow":
        from .diagram import _ARROW_SPLIT

        boxes = sum(len([p for p in _ARROW_SPLIT.split(ln) if p.strip()])
                    for ln in result.spec.lines)
    else:
        boxes = sum(1 for ln in result.spec.lines if ln.strip())
    _echo(f"읽음: {result.source} · 상자 {boxes}개 · 유형 {result.spec.type}")

    if out_path:
        with open(out_path, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
        _echo(f"생성: {out_path}")
    else:
        _echo("")
        _echo(text)

    if hwpx_path:
        from .engine import build_document

        profile = _load(profile_arg)
        built = build_document(profile, [{"type": "diagram", "spec": result.spec.to_dict()}],
                               hwpx_path)
        for warn in built.warnings:
            _echo(f"[경고] {warn}")
        _echo(f"생성: {hwpx_path}")
    return 0


def run_export_skill(profile_arg: str, out_dir: str, slug: str = "hwpx-report",
                     standalone: bool = False) -> int:
    from .export_skill import export_skill

    profile = _load(profile_arg)
    created = export_skill(profile, out_dir, slug=slug, standalone=standalone)
    for path in created:
        _echo(f"생성: {path}")
    return 0


def run_formkit(source: str, out: Optional[str], name: str,
                pack: Optional[str], report_only: bool) -> int:
    """양식 hwpx를 해부해 그 양식 전용 꾸러미를 만든다."""
    from .export_form import build_bundle, pack_bundle, write_bundle

    files, result = build_bundle(source, name=name)
    _echo(result.report)
    if report_only:
        return 0
    if not out and not pack:
        _echo("만들 곳을 지정할 것: -o 폴더 또는 --pack 파일.skill")
        return 2

    root = result.form["name"]
    if out:
        path = write_bundle(files, Path(out))
        _echo(f"꾸러미 저장 → {path} ({len(files)}개 파일)")
    if pack:
        data = pack_bundle(files, root)
        Path(pack).write_bytes(data)
        _echo(f"꾸러미 묶음 저장 → {pack} ({len(data):,}바이트)")
    if result.notes:
        _echo("살펴볼 것: " + " / ".join(result.notes))
    return 0


def run_readback(source: str, out: Optional[str], form: Optional[str],
                 report: Optional[str]) -> int:
    """서식 없는 hwpx를 마커 텍스트로 되돌린다(꾸러미의 read_hwpx.py와 같은 코드)."""
    import importlib.util

    asset = Path(__file__).resolve().parent / "assets" / "read_hwpx.py"
    spec = importlib.util.spec_from_file_location("hwpx_studio._read_hwpx", asset)
    reader = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = reader
    spec.loader.exec_module(reader)

    blocks = reader.read_blocks(Path(source))
    if not blocks:
        _echo("읽을 내용이 없음")
        return 2
    notes = reader.classify(blocks)
    markers, form_name = reader.load_markers(Path(form) if form else None)
    text = reader.to_marker_text(blocks, markers)
    if out:
        Path(out).write_text(text, encoding="utf-8")
        _echo(f"마커 텍스트 저장 → {out} (양식: {form_name})")
    else:
        _echo(text)
    rendered = reader.render_report(blocks, markers, notes)
    if report:
        Path(report).write_text(rendered, encoding="utf-8")
        _echo(f"추정 근거 저장 → {report}")
    else:
        _echo(rendered)
    return 0


# ──────────────────────────────────────────────────────────────
# 진입점
# ──────────────────────────────────────────────────────────────
def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="hwpx-studio",
        description="서식 프로파일로 한국어 보고서 hwpx를 만들고, 기존 hwpx의 서식을 읽는다",
    )
    sub = ap.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="프로파일 JSON 만들기")
    p_init.add_argument("out", help="저장할 프로파일 경로")
    p_init.add_argument("--from", dest="base", default="policy-default",
                        help=f"기준 프로파일 ({', '.join(list_builtin_profiles()) or '내장'})")
    p_init.add_argument("--levels", type=int, help="레벨 수를 앞에서부터 N개로 자름")
    p_init.add_argument("--mode", choices=["outline", "narrative"])
    p_init.add_argument("--font-bold")
    p_init.add_argument("--font-light")

    p_ext = sub.add_parser("extract", help="hwpx에서 서식 읽어 프로파일 만들기")
    p_ext.add_argument("source", help="기준이 될 .hwpx")
    p_ext.add_argument("-o", "--out", help="저장할 프로파일 경로")
    p_ext.add_argument("--report", help="근거 리포트(markdown) 저장 경로")
    p_ext.add_argument("--name", default="추출 프로파일")

    p_build = sub.add_parser("build", help="마커 텍스트 → hwpx")
    p_build.add_argument("input")
    p_build.add_argument("-p", "--profile")
    p_build.add_argument("-o", "--out", default="report.hwpx")
    p_build.add_argument("--strict", action="store_true", help="경고도 오류로 취급")
    p_build.add_argument("--no-lint", action="store_true")
    p_build.add_argument("--preview", help="HTML 미리보기 저장 경로")

    p_lint = sub.add_parser("lint", help="본문 규칙 검사")
    p_lint.add_argument("input")
    p_lint.add_argument("-p", "--profile")
    p_lint.add_argument("--strict", action="store_true")

    p_prev = sub.add_parser("preview", help="hwpx → HTML 근사 미리보기")
    p_prev.add_argument("source")
    p_prev.add_argument("-o", "--out", default="preview.html")

    p_dia = sub.add_parser("diagram", help="도식만 단독 생성")
    p_dia.add_argument("text", help='"대표 > 기획부, 운영부" 또는 :::diagram 블록')
    p_dia.add_argument("-o", "--out", default="diagram.hwpx")
    p_dia.add_argument("-p", "--profile")
    p_dia.add_argument("-t", "--type", dest="dtype", default="org",
                       choices=["org", "flow", "matrix"])
    p_dia.add_argument("--title", default="")
    p_dia.add_argument("--render", choices=["table", "image"])

    p_cap = sub.add_parser("capture", help="남의 도식(Mermaid·SVG·HTML) → 도식 블록")
    p_cap.add_argument("source", help="파일 경로, 또는 -(표준입력)")
    p_cap.add_argument("-o", "--out", help="도식 블록을 저장할 텍스트 파일(없으면 화면 출력)")
    p_cap.add_argument("--kind", default="auto",
                       choices=["auto", "mermaid", "svg", "html"])
    p_cap.add_argument("--title", default="")
    p_cap.add_argument("--hwpx", help="읽은 도식을 곧바로 hwpx로도 생성")
    p_cap.add_argument("-p", "--profile")

    p_form = sub.add_parser(
        "formkit", help="양식 hwpx → 그 양식 전용 꾸러미(빌더·스킬·codex 지시문)")
    p_form.add_argument("source", help="양식이 될 .hwpx")
    p_form.add_argument("-o", "--out", help="꾸러미를 풀어 놓을 폴더")
    p_form.add_argument("--name", default="", help="양식 이름(기본: 파일 이름)")
    p_form.add_argument("--pack", metavar="PATH",
                        help="꾸러미를 .skill 한 파일로 묶어 저장")
    p_form.add_argument("--report-only", action="store_true",
                        help="해부 결과만 보고 만들지 않음")

    p_read = sub.add_parser(
        "readback", help="서식 없는 hwpx → 마커 텍스트(양식에 맞춰 다시 만들 준비)")
    p_read.add_argument("source", help="읽어 들일 .hwpx")
    p_read.add_argument("-o", "--out", help="저장할 마커 텍스트")
    p_read.add_argument("--form", help="대상 양식의 form.json(마커를 맞춰 준다)")
    p_read.add_argument("--report", help="추정 근거를 저장할 경로")

    p_exp = sub.add_parser("export-skill", help="프로파일 → 스킬 폴더")
    p_exp.add_argument("profile")
    p_exp.add_argument("-o", "--out", default="./my-skill")
    p_exp.add_argument("--slug", default="hwpx-report")
    p_exp.add_argument("--standalone", action="store_true",
                       help="hwpx_studio 패키지를 스킬 폴더에 함께 넣음")
    return ap


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    cmd = args.command
    try:
        if cmd == "init":
            return run_init(args.out, args.base, args.levels, args.mode,
                            args.font_bold, args.font_light)
        if cmd == "extract":
            return run_extract(args.source, args.out, args.report, args.name)
        if cmd == "build":
            return run_build(args.input, args.profile, args.out, args.strict,
                             args.preview, lint=not args.no_lint)
        if cmd == "lint":
            return run_lint(args.input, args.profile, args.strict)
        if cmd == "preview":
            return run_preview(args.source, args.out)
        if cmd == "diagram":
            return run_diagram(args.text, args.out, args.profile, args.dtype,
                               args.title, args.render)
        if cmd == "capture":
            return run_capture(args.source, args.out, args.kind, args.title,
                               args.hwpx, args.profile)
        if cmd == "formkit":
            return run_formkit(args.source, args.out, args.name, args.pack,
                               args.report_only)
        if cmd == "readback":
            return run_readback(args.source, args.out, args.form, args.report)
        if cmd == "export-skill":
            return run_export_skill(args.profile, args.out, args.slug, args.standalone)
    except FileNotFoundError as exc:
        _echo(f"파일을 찾을 수 없음: {exc}")
        return 2
    except ValueError as exc:
        _echo(f"오류: {exc}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
