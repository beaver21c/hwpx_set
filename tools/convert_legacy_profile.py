#!/usr/bin/env python3
"""기존 hwpx_generator.py(v6)의 설정값을 프로파일 JSON으로 변환한다.

M0의 완료 기준(수기 변환 금지)을 만족시키기 위한 스크립트.

    python tools/convert_legacy_profile.py path/to/hwpx_generator.py \
        -o hwpx_studio/profiles/policy-default.json --contents examples/input_outline.md
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hwpx_studio.profile import merge_profile, validate_profile  # noqa: E402

#: 레거시 STYLE_* 이름 → (프로파일 레벨 key, 입력 마커)
LEVEL_SPECS = [
    ("STYLE_TITLE", "title", "#"),
    ("STYLE_TITLE_NUM", "title2", "##"),
    ("STYLE_LEVEL1", "L1", None),
    ("STYLE_LEVEL2", "L2", None),
    ("STYLE_LEVEL3", "L3", None),
    ("STYLE_LEVEL4", "L4", None),
    ("STYLE_LEVEL5", "L5", None),
]


def load_legacy(path: Path):
    spec = importlib.util.spec_from_file_location("legacy_hwpx_generator", path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"모듈을 읽을 수 없음: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def level_from_style(cfg: dict, key: str, marker: str | None) -> dict:
    prefix = cfg.get("prefix", "")
    out = {
        "key": key,
        "name": cfg.get("name", key),
        "marker": marker if marker is not None else str(prefix).strip(),
        "prefix": prefix,
        "size_pt": cfg.get("size_pt", 12),
        "bold": bool(cfg.get("bold", False)),
        "font": cfg.get("font", "light"),
        "color": cfg.get("color", "#000000"),
        "left_pt": cfg.get("left_pt", 0),
        "indent_pt": cfg.get("indent_pt", 0),
        "spacing_below_pt": cfg.get("spacing_below_pt", 0),
        "line_spacing": cfg.get("line_spacing", 160),
        "align": cfg.get("align", "JUSTIFY"),
    }
    return out


def cell_from_style(cfg: dict) -> dict:
    return {
        "name": cfg.get("name", ""),
        "eng_name": cfg.get("eng_name", cfg.get("name", "")),
        "size_pt": cfg.get("size_pt", 11),
        "bold": bool(cfg.get("bold", False)),
        "font": cfg.get("font", "light"),
        "color": cfg.get("color", "#000000"),
        "left_pt": cfg.get("left_pt", 0),
        "indent_pt": cfg.get("indent_pt", 0),
        "prefix": cfg.get("prefix", ""),
        "spacing_below_pt": cfg.get("spacing_below_pt", 0),
        "line_spacing": cfg.get("line_spacing", 120),
        "align": cfg.get("align", "CENTER"),
    }


def build_profile(m, name: str) -> dict:
    levels = [level_from_style(getattr(m, attr), key, marker)
              for attr, key, marker in LEVEL_SPECS if hasattr(m, attr)]
    body_ls = getattr(m, "STYLE_BODY", {}).get("line_spacing", 160)
    tbl = dict(getattr(m, "TABLE_CONFIG", {}))
    img = dict(getattr(m, "IMAGE_CONFIG", {}))

    profile = {
        "schema": "hwpx-studio.profile.v1",
        "name": name,
        "mode": "outline",
        "fonts": {
            "bold": getattr(m, "FONT_BOLD", "맑은 고딕"),
            "light": getattr(m, "FONT_LIGHT", "맑은 고딕"),
            "fallback": getattr(m, "FONT_LIGHT", "맑은 고딕"),
        },
        "page": {"size": "A4", "margin_mm": dict(getattr(m, "PAGE_MARGIN", {}))},
        "levels": levels,
        "body": {"size_pt": 12, "font": "light", "line_spacing": body_ls,
                 "first_line_indent_pt": 0},
        "table": {
            "border_color": tbl.get("border_color", "#999999"),
            "header_bg": tbl.get("header_bg", "#4472C4"),
            "width_mm": tbl.get("width_mm", 162.5),
            "cell_margin_mm": tbl.get("cell_margin_mm", 0.3),
            "treat_as_char": tbl.get("treat_as_char", True),
            "anchor_level": "L3",   # 레거시 엔진은 표/그림 외곽 문단을 '하이픈'으로 고정
            "top": cell_from_style(getattr(m, "STYLE_TABLE_TOP", {})),
            "mid": cell_from_style(getattr(m, "STYLE_TABLE_MID", {})),
            "left": cell_from_style(getattr(m, "STYLE_TABLE_LEFT", {})),
        },
        "image": {
            "default_width_mm": img.get("default_width_mm", 120),
            "treat_as_char": img.get("treat_as_char", True),
        },
        "rules": {
            "min_children": {"title2": 2, "L1": 2, "L2": 2},
            "period_policy": "single_sentence_no_period",
        },
    }
    return profile


def contents_to_markers(m, profile: dict) -> str:
    """레거시 REPORT_CONTENTS → 마커 텍스트(패리티 테스트 입력)."""
    by_key = {lv["key"]: lv for lv in profile["levels"]}
    order = [lv["key"] for lv in profile["levels"]]
    lines: list[str] = []
    for level, content in getattr(m, "REPORT_CONTENTS", []):
        if level == 0:
            lines.append("")
        elif level == "table":
            rows, cols, data = content
            lines.append("")
            for r in range(rows):
                cells = [str(data[r * cols + c]) if r * cols + c < len(data) else ""
                         for c in range(cols)]
                lines.append("| " + " | ".join(cells) + " |")
                if r == 0:
                    lines.append("|" + "---|" * cols)
            lines.append("")
        elif level == "image":
            lines.append(f"![]({content})")
        else:
            key = level if isinstance(level, str) else f"L{level}"
            lv = by_key.get(key)
            if lv is None:
                lines.append(str(content))
                continue
            marker = lv["marker"] or order.index(key) * "  "
            lines.append(f"{marker} {content}".strip())
    # 연속 빈 줄 정리
    cleaned: list[str] = []
    for line in lines:
        if line == "" and cleaned and cleaned[-1] == "":
            continue
        cleaned.append(line)
    return "\n".join(cleaned).strip() + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description="hwpx_generator.py → 프로파일 JSON")
    ap.add_argument("legacy", help="기존 hwpx_generator.py 경로")
    ap.add_argument("-o", "--out", default="hwpx_studio/profiles/policy-default.json")
    ap.add_argument("--name", default="정책보고서 기본")
    ap.add_argument("--contents", help="REPORT_CONTENTS를 마커 텍스트로 함께 저장할 경로")
    args = ap.parse_args()

    module = load_legacy(Path(args.legacy))
    profile = build_profile(module, args.name)

    errors = validate_profile(merge_profile(profile))
    if errors:
        print("프로파일 검증 실패:", *errors, sep="\n  ")
        return 1

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(profile, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"생성: {out}  (레벨 {len(profile['levels'])}개)")

    if args.contents:
        cpath = Path(args.contents)
        cpath.parent.mkdir(parents=True, exist_ok=True)
        cpath.write_text(contents_to_markers(module, profile), encoding="utf-8")
        print(f"생성: {cpath}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
