"""서식 프로파일(JSON) 스키마 · 기본값 병합 · 검증.

프로파일은 문서의 '서식'만 담는다. 본문은 마커 텍스트(parser.py), 변환은
엔진(engine.py)이 맡는다. 부분 JSON을 허용하며, 빠진 값은 기본값과 병합된다.
"""

from __future__ import annotations

import json
import os
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List, Optional

SCHEMA_ID = "hwpx-studio.profile.v1"

#: 레벨 1개에 적용되는 기본값. profile["levels"][i]의 빠진 항목을 채운다.
LEVEL_DEFAULTS: Dict[str, Any] = {
    "key": "",
    "name": "",
    "marker": "",
    "prefix": "",
    "size_pt": 12,
    "bold": False,
    "font": "light",
    "color": "#000000",
    "left_pt": 0,
    "indent_pt": 0,
    "spacing_below_pt": 0,
    "line_spacing": 160,
    "align": "JUSTIFY",
}

#: 표 셀 스타일 기본값
_TABLE_CELL_DEFAULTS: Dict[str, Any] = {
    "size_pt": 11,
    "bold": False,
    "font": "light",
    "color": "#000000",
    "left_pt": 0,
    "indent_pt": 0,
    "prefix": "",
    "spacing_below_pt": 0,
    "line_spacing": 120,
    "align": "CENTER",
}

DEFAULT_PROFILE: Dict[str, Any] = {
    "schema": SCHEMA_ID,
    "name": "기본",
    "mode": "outline",  # outline(개조식) | narrative(서술식)
    "fonts": {"bold": "맑은 고딕", "light": "맑은 고딕", "fallback": "맑은 고딕"},
    "page": {
        "size": "A4",
        "margin_mm": {
            "left": 20, "right": 20, "top": 10, "bottom": 10,
            "header": 10, "footer": 10,
        },
    },
    "header_footer": {"header_text": "", "page_number": False},
    "levels": [],
    "body": {
        "name": "본문",
        "size_pt": 12,
        "font": "light",
        "color": "#000000",
        "bold": False,
        "left_pt": 0,
        "indent_pt": 0,
        "spacing_below_pt": 0,
        "line_spacing": 160,
        "align": "JUSTIFY",
        "first_line_indent_pt": 0,
    },
    "table": {
        "border_color": "#999999",
        "header_bg": "#4472C4",
        "width_mm": 162.5,
        "cell_margin_mm": 0.3,
        "treat_as_char": True,
        "anchor_level": None,   # 표를 감싸는 문단에 적용할 레벨 key (None이면 마지막 본문 레벨)
        "top": dict(_TABLE_CELL_DEFAULTS, name="표(위)", eng_name="Table(Top)",
                    bold=True, font="bold", color="#FFFFFF"),
        "mid": dict(_TABLE_CELL_DEFAULTS, name="표(중간)", eng_name="Table(Mid)"),
        "left": dict(_TABLE_CELL_DEFAULTS, name="표(왼쪽)", eng_name="Table(Left)",
                     align="LEFT", indent_pt=12, prefix="· "),
    },
    "image": {"default_width_mm": 120, "treat_as_char": True},
    "diagram": {
        "render": "table",           # table | image
        "box_fill": "#DCE6F1",
        "box_border": "#1F3864",
        "box_color": "#000000",
        "root_fill": "#1F3864",
        "root_color": "#FFFFFF",
        "line_color": "#1F3864",
        "line_width_mm": 0.3,
        "font_size_pt": 11,
        "col_width_mm": 28,
        "col_gap_mm": 6,
        "grid_resolution": 6,   # 상자 1개가 차지하는 열 수(짝수). 클수록 연결선 위치가 정밀
        "row_height_mm": 9,
        "row_gap_mm": 7,
        "max_width_mm": 160,
        "image_backend": "matplotlib",
    },
    "rules": {
        "min_children": {},
        "period_policy": "single_sentence_no_period",
    },
    # 문서 끝에 삽입할 서명 문단(선택). 공개 도구 기본값은 비활성.
    "signature": {"text": "", "size_pt": 5, "color": "#FFFFFF"},
}

_VALID_ALIGN = {"JUSTIFY", "LEFT", "RIGHT", "CENTER", "DISTRIBUTE", "DIVISION"}
_VALID_FONT_KEYS = {"bold", "light", "fallback"}


# ──────────────────────────────────────────────────────────────
# 병합 · 적재
# ──────────────────────────────────────────────────────────────
def _deep_merge(base: Any, override: Any) -> Any:
    """dict는 키 단위로 재귀 병합, 그 외는 override로 교체."""
    if isinstance(base, dict) and isinstance(override, dict):
        out = deepcopy(base)
        for k, v in override.items():
            out[k] = _deep_merge(base.get(k), v) if k in base else deepcopy(v)
        return out
    return deepcopy(override)


def merge_profile(user: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """부분 프로파일을 기본값과 병합한 완전 프로파일을 돌려준다."""
    user = user or {}
    merged = _deep_merge(DEFAULT_PROFILE, {k: v for k, v in user.items() if k != "levels"})

    levels: List[Dict[str, Any]] = []
    for i, lv in enumerate(user.get("levels") or DEFAULT_PROFILE["levels"]):
        item = _deep_merge(LEVEL_DEFAULTS, lv)
        if not item["key"]:
            item["key"] = f"L{i + 1}"
        if not item["name"]:
            item["name"] = item["key"]
        if not item["marker"]:
            # marker 미지정 시 prefix에서 유추(자동 번호 접두어는 제외)
            pfx = str(item["prefix"])
            item["marker"] = "" if pfx.startswith("AUTO_") else pfx.strip()
        levels.append(item)
    merged["levels"] = levels

    for key in ("top", "mid", "left"):
        merged["table"][key] = _deep_merge(_TABLE_CELL_DEFAULTS, merged["table"].get(key) or {})
    return merged


def load_profile(source: Any) -> Dict[str, Any]:
    """경로·파일객체·dict·JSON 문자열 중 무엇이든 받아 완전 프로파일로."""
    if isinstance(source, dict):
        data = source
    elif hasattr(source, "read"):
        data = json.load(source)
    else:
        text = str(source)
        if text.lstrip().startswith("{"):
            data = json.loads(text)
        else:
            path = resolve_profile_path(text)
            data = json.loads(Path(path).read_text(encoding="utf-8"))
    return merge_profile(data)


def builtin_profiles_dir() -> Path:
    """동봉 프로파일 폴더. 설치본·저장소 양쪽에서 동작."""
    here = Path(__file__).resolve().parent
    for cand in (here / "profiles", here.parent / "profiles"):
        if cand.is_dir():
            return cand
    return here.parent / "profiles"


def resolve_profile_path(name: str) -> str:
    """'policy-default' 같은 이름 또는 실제 경로를 파일 경로로 변환."""
    if os.path.exists(name):
        return name
    stem = name[:-5] if name.endswith(".json") else name
    cand = builtin_profiles_dir() / f"{stem}.json"
    if cand.exists():
        return str(cand)
    raise FileNotFoundError(f"프로파일을 찾을 수 없음: {name}")


def list_builtin_profiles() -> List[str]:
    d = builtin_profiles_dir()
    return sorted(p.stem for p in d.glob("*.json")) if d.is_dir() else []


def save_profile(profile: Dict[str, Any], path: str) -> None:
    Path(path).write_text(
        json.dumps(profile, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


# ──────────────────────────────────────────────────────────────
# 검증
# ──────────────────────────────────────────────────────────────
def validate_profile(profile: Dict[str, Any]) -> List[str]:
    """치명적 오류 목록을 돌려준다(빈 리스트 = 통과)."""
    errors: List[str] = []
    schema = profile.get("schema")
    if schema and schema != SCHEMA_ID:
        errors.append(f"schema 값이 다름: {schema} (기대: {SCHEMA_ID})")
    if profile.get("mode") not in ("outline", "narrative"):
        errors.append(f"mode는 outline|narrative 중 하나여야 함: {profile.get('mode')!r}")

    levels = profile.get("levels") or []
    if profile.get("mode") == "outline" and not levels:
        errors.append("outline 모드인데 levels가 비어 있음")

    seen_keys, seen_markers = set(), {}
    for i, lv in enumerate(levels):
        where = f"levels[{i}]({lv.get('key', '?')})"
        key = lv.get("key")
        if not key:
            errors.append(f"{where}: key 없음")
        elif key in seen_keys:
            errors.append(f"{where}: key 중복")
        seen_keys.add(key)

        marker = lv.get("marker") or ""
        if marker:
            if marker in seen_markers:
                errors.append(f"{where}: marker {marker!r}가 {seen_markers[marker]}와 중복")
            seen_markers[marker] = key
        try:
            size = float(lv.get("size_pt", 0))
            if size <= 0:
                errors.append(f"{where}: size_pt는 0보다 커야 함")
        except (TypeError, ValueError):
            errors.append(f"{where}: size_pt가 숫자가 아님")
        if lv.get("font") not in _VALID_FONT_KEYS:
            errors.append(f"{where}: font는 {sorted(_VALID_FONT_KEYS)} 중 하나여야 함")
        if lv.get("align") not in _VALID_ALIGN:
            errors.append(f"{where}: align 값이 올바르지 않음: {lv.get('align')!r}")
        for field in ("color",):
            val = lv.get(field)
            if val and not _is_hex_color(val):
                errors.append(f"{where}: {field}는 #RRGGBB 형식이어야 함: {val!r}")

    tbl = profile.get("table") or {}
    for field in ("border_color", "header_bg"):
        if tbl.get(field) and not _is_hex_color(tbl[field]):
            errors.append(f"table.{field}는 #RRGGBB 형식이어야 함: {tbl[field]!r}")
    anchor = tbl.get("anchor_level")
    if anchor and anchor not in seen_keys:
        errors.append(f"table.anchor_level={anchor!r}에 해당하는 레벨이 없음")

    dia = profile.get("diagram") or {}
    if dia.get("render") not in ("table", "image"):
        errors.append(f"diagram.render는 table|image 중 하나여야 함: {dia.get('render')!r}")

    for key, need in (profile.get("rules", {}).get("min_children") or {}).items():
        if key not in seen_keys:
            errors.append(f"rules.min_children의 {key!r}에 해당하는 레벨이 없음")
        if not isinstance(need, int) or need < 0:
            errors.append(f"rules.min_children[{key}]는 0 이상 정수여야 함")
    return errors


def _is_hex_color(value: Any) -> bool:
    if not isinstance(value, str) or not value.startswith("#") or len(value) != 7:
        return False
    try:
        int(value[1:], 16)
    except ValueError:
        return False
    return True


# ──────────────────────────────────────────────────────────────
# 조회 헬퍼
# ──────────────────────────────────────────────────────────────
def level_by_key(profile: Dict[str, Any], key: str) -> Optional[Dict[str, Any]]:
    for lv in profile.get("levels", []):
        if lv["key"] == key:
            return lv
    return None


def level_index(profile: Dict[str, Any], key: str) -> int:
    for i, lv in enumerate(profile.get("levels", [])):
        if lv["key"] == key:
            return i
    return -1


def marker_map(profile: Dict[str, Any]) -> Dict[str, str]:
    """마커 문자열 → 레벨 key. 긴 마커가 먼저 매칭되도록 정렬해 쓴다."""
    out: Dict[str, str] = {}
    for lv in profile.get("levels", []):
        if lv.get("marker"):
            out[lv["marker"]] = lv["key"]
    return out


def body_levels(profile: Dict[str, Any]) -> List[Dict[str, Any]]:
    """제목(자동 번호) 레벨을 제외한 본문 레벨."""
    return [lv for lv in profile.get("levels", [])
            if not str(lv.get("prefix", "")).startswith("AUTO_")]
