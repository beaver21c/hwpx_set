"""본문 규칙 검사(계층 균형·기호 중복·온점·각주 번호 자리·블록 앞뒤 빈 줄)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence

from .profile import merge_profile

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
#: 본문 중간에 레벨 기호가 '단독 토큰'으로 나타나는 경우만 잡는다
def _stray_marker(text: str, markers: Sequence[str]) -> Optional[str]:
    for marker in markers:
        if not marker or marker in ("-", "#"):     # 하이픈·샵은 오탐이 잦아 제외
            continue
        if re.search(rf"(?:^|\s){re.escape(marker)}(?=\s)", text):
            return marker
    return None


@dataclass
class Issue:
    severity: str      # "error" | "warn"
    line: int
    code: str
    message: str

    def format(self) -> str:
        mark = "오류" if self.severity == "error" else "경고"
        return f"{self.line:>4}행 [{mark}:{self.code}] {self.message}"


def lint_items(items: Sequence[Dict[str, Any]], profile: Dict[str, Any],
               line_of: Optional[Sequence[int]] = None,
               parser_warnings: Sequence[str] = ()) -> List[Issue]:
    profile = merge_profile(profile)
    lines = list(line_of) if line_of else list(range(1, len(items) + 1))
    order = [lv["key"] for lv in profile["levels"]]
    depth_of = {key: i for i, key in enumerate(order)}
    markers = sorted({lv["marker"] for lv in profile["levels"] if lv.get("marker")})
    auto_keys = {lv["key"] for lv in profile["levels"]
                 if str(lv.get("prefix", "")).startswith("AUTO_")}
    rules = profile.get("rules", {})
    min_children = rules.get("min_children") or {}
    head_patterns = {k: v for k, v in (rules.get("head_pattern") or {}).items() if v}
    policy = rules.get("period_policy", "single_sentence_no_period")
    position = rules.get("footnote_position", "before_period")

    issues: List[Issue] = []
    note_no = 0
    for text in parser_warnings:
        m = re.match(r"(\d+)행: (.*)", text)
        if m:
            issues.append(Issue("warn", int(m.group(1)), "parser", m.group(2)))
        else:
            issues.append(Issue("warn", 0, "parser", text))

    # 문단만 추린 목록(깊이 포함)
    paras = [(i, item) for i, item in enumerate(items) if item.get("type") == "para"]

    for pos, (idx, item) in enumerate(paras):
        key = item.get("key", "body")
        line = lines[idx]
        text = str(item.get("text", ""))
        depth = depth_of.get(key)

        if key != "body" and depth is None:
            issues.append(Issue("error", line, "level", f"프로파일에 없는 레벨: {key}"))
            continue
        if not text.strip():
            issues.append(Issue("warn", line, "empty", "내용이 빈 문단"))

        # 본문에 레벨 기호를 다시 쓴 경우
        stray = _stray_marker(text, markers)
        if stray:
            issues.append(Issue(
                "warn", line, "symbol",
                f"본문에 레벨 기호 {stray!r}가 들어 있음 → 마커와 혼동 가능"))

        # 머릿글 규칙(네모의 【】, 원의 () 처럼 레벨마다 정해 둔 앞머리)
        pattern = head_patterns.get(key)
        if pattern and not re.match(pattern, text):
            issues.append(Issue(
                "warn", line, "head",
                f"{key}에 머릿글이 없음(규칙 {pattern}): {text[:20]}"))

        # 온점 규칙(제목 레벨은 제외)
        if key not in auto_keys:
            issues += _period_issues(text, line, policy)

        # 각주 번호 자리
        for note in item.get("notes") or []:
            note_no += 1
            issues += _footnote_issues(note, note_no, line, key in auto_keys, position)

        # 계층 균형
        need = min_children.get(key)
        if need:
            found = _count_children(paras, pos, depth, depth_of)
            if found < need:
                issues.append(Issue(
                    "warn", line, "balance",
                    f"{key} 아래 하위 항목이 {found}개 (권장 {need}개 이상): "
                    f"{text[:20]}"))

        # 레벨 점프(부모 없이 두 단계 이상 깊어짐)
        if pos > 0 and depth is not None:
            prev_key = paras[pos - 1][1].get("key", "body")
            prev_depth = depth_of.get(prev_key)
            if prev_depth is not None and depth - prev_depth > 1:
                issues.append(Issue(
                    "warn", line, "jump",
                    f"{prev_key} 다음에 {key}가 나옴 → 중간 레벨 생략"))

    issues += _block_spacing_issues(items, lines)
    issues.sort(key=lambda x: (x.line, x.code))
    return issues


def _count_children(paras, pos: int, depth: Optional[int], depth_of) -> int:
    if depth is None:
        return 0
    count = 0
    for _, item in [p for p in paras[pos + 1:]]:
        child_depth = depth_of.get(item.get("key", "body"))
        if child_depth is None:
            continue
        if child_depth <= depth:
            break
        if child_depth == depth + 1:
            count += 1
    return count


_SENTENCE_END = ".。!?"


def _footnote_issues(note: Dict[str, Any], number: int, line: int,
                     in_heading: bool, position: str) -> List[Issue]:
    """각주 번호를 놓은 자리를 본다. 본문 규칙이지 서식 문제가 아니다."""
    out: List[Issue] = []
    label = str(note.get("label", ""))
    before = str(note.get("before", ""))
    after = str(note.get("after", ""))
    where = f"각주 {number}"

    if in_heading:
        out.append(Issue("warn", line, "footnote",
                         f"{where}: 제목에 각주를 닮 → 본문 문단으로 옮길 것"))
    if not before:
        out.append(Issue("warn", line, "footnote",
                         f"{where}: 문단 맨 앞에 번호가 옴 → 근거가 되는 말 뒤에 붙일 것"))
    elif before.isspace():
        out.append(Issue("warn", line, "footnote",
                         f"{where}: 번호 앞에 빈칸이 있음 → 앞말에 붙여 쓸 것"))
    if position == "before_period" and before and before in _SENTENCE_END:
        out.append(Issue("warn", line, "footnote",
                         f"{where}: 마침표 뒤에 번호가 옴 → 마침표 앞에 붙일 것"))
    elif position == "after_period" and after and after in _SENTENCE_END:
        out.append(Issue("warn", line, "footnote",
                         f"{where}: 마침표 앞에 번호가 옴 → 마침표 뒤에 붙일 것"))
    if label.isdigit() and int(label) != number:
        out.append(Issue("warn", line, "footnote",
                         f"[^{label}]로 적었지만 문서 순서로는 {number}번째 각주 "
                         f"→ 번호는 한글이 매기므로 라벨과 다를 수 있음"))
    return out


def _period_issues(text: str, line: int, policy: str) -> List[Issue]:
    stripped = text.strip()
    if not stripped or policy in ("off", None):
        return []
    sentences = [s for s in _SENTENCE_SPLIT.split(stripped) if s]
    ends_with_period = stripped.endswith(".")
    out: List[Issue] = []
    if policy == "single_sentence_no_period":
        if len(sentences) == 1 and ends_with_period:
            out.append(Issue("warn", line, "period", "단문인데 온점이 붙음"))
        elif len(sentences) > 1 and not ends_with_period:
            out.append(Issue("warn", line, "period", "두 문장 이상인데 끝 온점이 없음"))
    elif policy == "always_period" and not ends_with_period:
        out.append(Issue("warn", line, "period", "온점으로 끝나야 함"))
    elif policy == "never_period" and ends_with_period:
        out.append(Issue("warn", line, "period", "온점을 쓰지 않는 규칙"))
    return out


def _block_spacing_issues(items: Sequence[Dict[str, Any]], lines: Sequence[int]) -> List[Issue]:
    out: List[Issue] = []
    for i, item in enumerate(items):
        kind = item.get("type")
        if kind not in ("table", "diagram"):
            continue
        label = "표" if kind == "table" else "도식"
        before = items[i - 1].get("type") if i > 0 else "blank"
        after = items[i + 1].get("type") if i + 1 < len(items) else "blank"
        if before != "blank":
            out.append(Issue("warn", lines[i], "spacing", f"{label} 앞에 빈 줄이 없음"))
        if after != "blank":
            out.append(Issue("warn", lines[i], "spacing", f"{label} 뒤에 빈 줄이 없음"))
        if kind == "diagram" and not (item.get("spec") or {}).get("lines"):
            out.append(Issue("error", lines[i], "diagram", "도식 블록 내용이 비어 있음"))
    return out


def format_issues(issues: Sequence[Issue]) -> str:
    if not issues:
        return "검사 통과 — 지적 사항 없음"
    body = "\n".join(issue.format() for issue in issues)
    errors = sum(1 for i in issues if i.severity == "error")
    warns = len(issues) - errors
    return f"{body}\n\n오류 {errors}건 / 경고 {warns}건"


def has_blocking(issues: Sequence[Issue], strict: bool = False) -> bool:
    if strict:
        return bool(issues)
    return any(i.severity == "error" for i in issues)
