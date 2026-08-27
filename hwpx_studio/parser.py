"""마커 텍스트 → 콘텐츠 항목 목록.

    # 장 제목            → title
    ## 절 제목           → title2
    □ / ○ / - / · / ※   → 프로파일 levels[].marker
    (빈 줄)              → 블록 구분
    | 구분 | 값 |        → 표(연속 파이프 행, 첫 행 헤더, |---| 행 무시)
    ![](그림.png)        → 그림
    :::diagram … :::     → 도식
    본문 안 [^1]         → 각주 번호가 들어갈 자리
    [^1]: 출처           → 각주 내용(문서 어디에 써도 된다)
    마커 없는 줄         → narrative: 본문 문단 / outline: 들여쓰기 깊이로 폴백

마커는 **"마커 + 공백"** 조합만 인식한다(`-3%` 같은 표현 보호).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from . import diagram as diagram_mod
from .profile import body_levels, merge_profile

_IMAGE_RE = re.compile(r"^!\[[^\]]*\]\(([^)]+)\)\s*$")
_TABLE_SEP_RE = re.compile(r"^\|[\s:|-]+\|$")
_FENCE_RE = re.compile(r"^:::\s*(?:diagram)?\s*(.*)$")
#: 본문 안 각주 번호 자리표(`앞말[^1]`)
FOOTNOTE_REF_RE = re.compile(r"\[\^([^\]\s]+)\]")
#: 각주 내용을 적는 줄(`[^1]: 통계청, …`)
FOOTNOTE_DEF_RE = re.compile(r"^\[\^([^\]\s]+)\]:\s*(.*)$")


@dataclass
class ParseResult:
    items: List[Dict[str, Any]] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    line_of: List[int] = field(default_factory=list)   # items[i]가 온 줄 번호(1-base)


def _marker_table(profile: Dict[str, Any]) -> List[Tuple[str, str]]:
    """(마커, 레벨 key) 목록. 긴 마커 우선."""
    pairs = [(lv["marker"], lv["key"]) for lv in profile["levels"] if lv.get("marker")]
    pairs.sort(key=lambda kv: -len(kv[0]))
    return pairs


def parse_text(text: str, profile: Dict[str, Any]) -> ParseResult:
    profile = merge_profile(profile)
    markers = _marker_table(profile)
    fallback = [lv["key"] for lv in body_levels(profile)]
    #: 마커가 없는 레벨 — 마커 없는 줄이 갈 제자리가 프로파일에 있는가
    plain_home = any(not lv.get("marker") for lv in body_levels(profile))
    narrative = profile.get("mode") == "narrative"

    result = ParseResult()
    notes: Dict[str, Dict[str, Any]] = {}      # 라벨 → {"text", "line", "used"}
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    i = 0
    while i < len(lines):
        raw = lines[i].rstrip()
        lineno = i + 1
        stripped = raw.strip()

        if not stripped:
            _append(result, {"type": "blank"}, lineno)
            i += 1
            continue

        # ── 각주 내용 줄 ──
        definition = FOOTNOTE_DEF_RE.match(stripped)
        if definition:
            label, body_text = definition.group(1), definition.group(2).strip()
            if label in notes:
                result.warnings.append(
                    f"{lineno}행: 각주 [^{label}]의 내용이 두 번 적힘 → 뒤엣것을 씀")
            if not body_text:
                result.warnings.append(f"{lineno}행: 각주 [^{label}]의 내용이 비어 있음")
            notes[label] = {"text": body_text, "line": lineno, "used": 0}
            # 각주 내용 줄 앞뒤가 모두 빈 줄이면 빈 문단이 겹치므로 하나만 남긴다
            next_blank = i + 1 >= len(lines) or not lines[i + 1].strip()
            if next_blank and result.items and result.items[-1].get("type") == "blank":
                result.items.pop()
                result.line_of.pop()
            i += 1
            continue

        # ── 도식 블록 ──
        fence = _FENCE_RE.match(stripped)
        if fence and stripped.startswith(":::"):
            header = fence.group(1).strip()
            body: List[str] = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith(":::"):
                body.append(lines[i].rstrip())
                i += 1
            i += 1  # 닫는 :::
            spec = diagram_mod.parse_block(header, body)
            if not spec.lines:
                result.warnings.append(f"{lineno}행: 내용이 빈 도식 블록")
            _append(result, {"type": "diagram", "spec": spec.to_dict()}, lineno)
            continue

        # ── 그림 ──
        img = _IMAGE_RE.match(stripped)
        if img:
            _append(result, {"type": "image", "path": img.group(1).strip()}, lineno)
            i += 1
            continue

        # ── 표(연속 파이프 행) ──
        if stripped.startswith("|") and stripped.endswith("|"):
            rows: List[List[str]] = []
            start = lineno
            while i < len(lines):
                cur = lines[i].strip()
                if not (cur.startswith("|") and cur.endswith("|")):
                    break
                if not _TABLE_SEP_RE.match(cur):
                    rows.append([c.strip() for c in cur.strip("|").split("|")])
                i += 1
            if rows:
                cols = max(len(r) for r in rows)
                data: List[str] = []
                for row in rows:
                    data += [row[c] if c < len(row) else "" for c in range(cols)]
                _append(result, {"type": "table", "rows": len(rows), "cols": cols,
                                 "data": data}, start)
            continue

        # ── 마커 문단 ──
        key, body_text, warn = _match_marker(stripped, markers)
        if warn:
            result.warnings.append(f"{lineno}행: {warn}")
        if key is not None:
            _append(result, {"type": "para", "key": key, "text": body_text}, lineno)
            i += 1
            continue

        # ── 마커 없는 줄 ──
        if narrative or not fallback:
            _append(result, {"type": "para", "key": "body", "text": stripped}, lineno)
        else:
            expanded = raw.replace("\t", "  ")
            indent = len(expanded) - len(expanded.lstrip(" "))
            depth = min(indent // 2, len(fallback) - 1)
            # 프로파일에 마커 없는 레벨이 있으면 그 레벨이 본문의 제자리다.
            # 도구가 추측한 것이 아니므로 알리지 않는다.
            if not plain_home:
                result.warnings.append(
                    f"{lineno}행: 마커 없는 줄 → 들여쓰기 {indent}칸으로 "
                    f"{fallback[depth]} 레벨 적용")
            _append(result, {"type": "para", "key": fallback[depth], "text": stripped},
                    lineno)
        i += 1

    _resolve_footnotes(result, notes)
    return result


def _resolve_footnotes(result: ParseResult, notes: Dict[str, Dict[str, Any]]) -> None:
    """본문의 `[^라벨]` 자리표를 각주 내용과 이어 붙인다.

    내용을 찾지 못한 자리표는 **본문에 그대로 남긴다**. 조용히 지우면 각주가
    빠진 사실이 산출물에서 보이지 않기 때문이다.
    """
    for item, line in zip(result.items, result.line_of):
        kind = item.get("type")
        if kind == "table":
            if any(FOOTNOTE_REF_RE.search(str(cell)) for cell in item.get("data") or []):
                result.warnings.append(
                    f"{line}행: 표 안에는 각주를 달 수 없음 → 표 아래 문단에 달 것")
            continue
        if kind == "diagram":
            if any(FOOTNOTE_REF_RE.search(str(ln)) for ln in (item.get("spec") or {}).get("lines") or []):
                result.warnings.append(
                    f"{line}행: 도식 상자 안에는 각주를 달 수 없음 → 도식 아래 문단에 달 것")
            continue
        if kind != "para":
            continue

        text = str(item.get("text", ""))
        if "[^" not in text:
            continue
        item["text"], found = _split_notes(text, notes, result.warnings, line)
        if found:
            item["notes"] = found

    for label, note in notes.items():
        if not note["used"]:
            result.warnings.append(
                f"{note['line']}행: 각주 [^{label}]을 본문에서 부르지 않음 → 만들지 않음")


def _split_notes(text: str, notes: Dict[str, Dict[str, Any]],
                 warnings: List[str], line: int) -> Tuple[str, List[Dict[str, Any]]]:
    """`[^라벨]`을 떼어 내고 (본문, 각주 목록)으로 나눈다.

    각주에는 번호가 놓일 자리(``offset``)와 그 앞뒤 글자를 함께 담는다.
    번호 위치 검사(lint)가 이 값을 본다.
    """
    out: List[str] = []
    found: List[Dict[str, Any]] = []
    pos = 0
    for m in FOOTNOTE_REF_RE.finditer(text):
        out.append(text[pos:m.start()])
        pos = m.end()
        label = m.group(1)
        note = notes.get(label)
        if note is None:
            warnings.append(f"{line}행: 각주 [^{label}]의 내용을 찾지 못함 "
                            f"(`[^{label}]: 내용` 줄이 없음) → 본문에 그대로 남김")
            out.append(m.group())
            continue
        note["used"] += 1
        if note["used"] > 1:
            warnings.append(f"{line}행: 각주 [^{label}]을 두 번 이상 부름 "
                            f"→ 한글에는 같은 각주를 다시 못 쓰므로 따로 만들어짐")
        before = "".join(out)
        found.append({"label": label, "text": note["text"], "offset": len(before),
                      "before": before[-1:], "after": text[m.end():m.end() + 1]})
    out.append(text[pos:])
    return "".join(out), found


def _append(result: ParseResult, item: Dict[str, Any], lineno: int) -> None:
    result.items.append(item)
    result.line_of.append(lineno)


def _match_marker(text: str, markers: Sequence[Tuple[str, str]]
                  ) -> Tuple[Optional[str], str, Optional[str]]:
    """'마커 + 공백'만 인식. 같은 마커가 반복되면 1회만 인식하고 경고."""
    for marker, key in markers:
        if text.startswith(marker + " ") or text == marker:
            rest = text[len(marker):].strip()
            warn = None
            while rest.startswith(marker + " ") or rest == marker:
                rest = rest[len(marker):].strip()
                warn = f"마커 {marker!r}가 중복 입력됨 → 1회만 인식"
            return key, rest, warn
    return None, text, None


def parse_file(path: str, profile: Dict[str, Any]) -> ParseResult:
    from pathlib import Path

    return parse_text(Path(path).read_text(encoding="utf-8"), profile)
