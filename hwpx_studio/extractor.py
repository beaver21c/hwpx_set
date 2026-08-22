"""hwpx → 프로파일 JSON 역생성(서식 읽기).

header.xml의 charPr/paraPr/style과 본문 첫 글자 패턴을 함께 보고 레벨 체계를
추정한다. 추정이므로 **자동 확정하지 않는다**. `extract_report.md`로 근거를
남기고, 사용자가 확인한 뒤 저장하는 것을 전제로 한다.
"""

from __future__ import annotations

import re
import zipfile
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .profile import SCHEMA_ID, merge_profile
from .units import MM, PT

NS = {
    "hh": "http://www.hancom.co.kr/hwpml/2011/head",
    "hp": "http://www.hancom.co.kr/hwpml/2011/paragraph",
    "hc": "http://www.hancom.co.kr/hwpml/2011/core",
    "hs": "http://www.hancom.co.kr/hwpml/2011/section",
}

ROMAN_CHARS = "ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩⅪⅫ"
CIRCLED_CHARS = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮"

_PREFIX_PATTERNS: List[Tuple[str, "re.Pattern[str]"]] = [
    ("AUTO_ROMAN", re.compile(rf"^[{ROMAN_CHARS}]+[.)]\s")),
    ("AUTO_NUM", re.compile(r"^\d{1,2}[.)]\s")),
    ("AUTO_ALPHA", re.compile(r"^[A-Z][.)]\s")),
    ("AUTO_CIRCLED", re.compile(rf"^[{CIRCLED_CHARS}]\s?")),
    ("AUTO_HANGUL", re.compile(r"^[가나다라마바사아자차카타파하][.)]\s")),
]
#: 선행 비문자 기호 1~2자 + 공백 (□ ○ - · ※ ▪ – 등)
_SYMBOL_PREFIX = re.compile(r"^([^\w\s]{1,2})\s")


@dataclass
class Cluster:
    key: Tuple[Any, ...]
    style_id: Optional[int] = None
    para_pr_id: Optional[int] = None
    char_pr_id: Optional[int] = None
    style_name: str = ""
    count: int = 0
    samples: List[str] = field(default_factory=list)
    prefixes: Counter = field(default_factory=Counter)

    # 서식 값
    size_pt: float = 12.0
    bold: bool = False
    color: str = "#000000"
    font_face: str = ""
    left_pt: float = 0.0
    indent_pt: float = 0.0
    spacing_below_pt: float = 0.0
    line_spacing: int = 160
    align: str = "JUSTIFY"


@dataclass
class ExtractResult:
    profile: Dict[str, Any]
    report: str
    clusters: List[Cluster]
    notes: List[str] = field(default_factory=list)


# ──────────────────────────────────────────────────────────────
# XML 읽기
# ──────────────────────────────────────────────────────────────
def _read_parts(source: Any) -> Dict[str, str]:
    if isinstance(source, (bytes, bytearray)):
        zf = zipfile.ZipFile(BytesIO(bytes(source)))
    else:
        zf = zipfile.ZipFile(str(source))
    with zf:
        return {name: zf.read(name).decode("utf-8", "replace")
                for name in zf.namelist()
                if name.endswith(".xml") and (name.startswith("Contents/"))}


def _et(xml: str):
    import xml.etree.ElementTree as ET

    return ET.fromstring(xml)


def _font_faces(head) -> Dict[int, str]:
    """폰트 id → face. 한글 fontface를 우선 사용."""
    faces: Dict[int, str] = {}
    for group in head.iter(f"{{{NS['hh']}}}fontface"):
        lang = group.get("lang", "")
        for font in group.findall(f"{{{NS['hh']}}}font"):
            fid = int(font.get("id", "0"))
            if lang.upper() == "HANGUL" or fid not in faces:
                faces[fid] = font.get("face", "")
    if not faces:
        for font in head.iter(f"{{{NS['hh']}}}font"):
            faces[int(font.get("id", "0"))] = font.get("face", "")
    return faces


def _char_props(head) -> Dict[int, Dict[str, Any]]:
    out: Dict[int, Dict[str, Any]] = {}
    for cp in head.iter(f"{{{NS['hh']}}}charPr"):
        ref = cp.find(f"{{{NS['hh']}}}fontRef")
        out[int(cp.get("id", "0"))] = {
            "size_pt": round(int(cp.get("height", "1000")) / PT, 2),
            "bold": cp.find(f"{{{NS['hh']}}}bold") is not None or cp.get("bold") in ("1", "true"),
            "color": (cp.get("textColor") or "#000000").upper(),
            "font_id": int(ref.get("hangul", "0")) if ref is not None else 0,
        }
    return out


def _para_props(head) -> Dict[int, Dict[str, Any]]:
    out: Dict[int, Dict[str, Any]] = {}
    for pp in head.iter(f"{{{NS['hh']}}}paraPr"):
        # margin/lineSpacing은 hp:switch/hp:case 안에 중첩될 수 있음 → .// 탐색
        margin = pp.find(f".//{{{NS['hh']}}}margin")
        ls = pp.find(f".//{{{NS['hh']}}}lineSpacing")
        align = pp.find(f"{{{NS['hh']}}}align")

        def val(tag: str) -> float:
            if margin is None:
                return 0.0
            node = margin.find(f"{{{NS['hc']}}}{tag}")
            return float(node.get("value", "0")) if node is not None else 0.0

        out[int(pp.get("id", "0"))] = {
            "left_pt": round(val("left") / PT, 2),
            "indent_pt": round(abs(val("intent")) / PT, 2),
            "spacing_below_pt": round(val("next") / PT, 2),
            "line_spacing": int(float(ls.get("value", "160"))) if ls is not None else 160,
            "align": (align.get("horizontal", "JUSTIFY") if align is not None else "JUSTIFY"),
        }
    return out


def _styles(head) -> Dict[int, Dict[str, Any]]:
    out: Dict[int, Dict[str, Any]] = {}
    for st in head.iter(f"{{{NS['hh']}}}style"):
        out[int(st.get("id", "0"))] = {
            "name": st.get("name", ""),
            "eng_name": st.get("engName", ""),
            "para_pr": int(st.get("paraPrIDRef", "0")),
            "char_pr": int(st.get("charPrIDRef", "0")),
        }
    return out


def _paragraph_records(section_xml: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """(본문 문단, 표 셀 문단) 기록을 돌려준다."""
    root = _et(section_xml)
    body: List[Dict[str, Any]] = []
    cells: List[Dict[str, Any]] = []

    def record(p, in_table: bool, row: Optional[int]) -> None:
        runs = p.findall(f"{{{NS['hp']}}}run")
        char_id = None
        texts: List[str] = []
        for run in runs:
            if char_id is None and run.get("charPrIDRef") is not None:
                char_id = int(run.get("charPrIDRef"))
            for t in run.iter(f"{{{NS['hp']}}}t"):
                texts.append("".join(t.itertext()))
        text = "".join(texts).strip()
        rec = {
            "style": int(p.get("styleIDRef", "0")),
            "para": int(p.get("paraPrIDRef", "0")),
            "char": char_id if char_id is not None else 0,
            "text": text[:60],
            "row": row,
        }
        (cells if in_table else body).append(rec)

    def walk(node, in_table: bool, row: Optional[int]) -> None:
        for child in node:
            tag = child.tag.split("}")[-1]
            if tag == "p":
                # 표/그림을 감싸는 외곽 문단은 본문 통계에서 제외
                has_obj = child.find(f".//{{{NS['hp']}}}tbl") is not None or \
                    child.find(f".//{{{NS['hp']}}}pic") is not None
                if not has_obj:
                    record(child, in_table, row)
                walk(child, in_table, row)
            elif tag == "tbl":
                for tr_i, tr in enumerate(child.findall(f"{{{NS['hp']}}}tr")):
                    walk(tr, True, tr_i)
            else:
                walk(child, in_table, row)

    walk(root, False, None)
    return body, cells


# ──────────────────────────────────────────────────────────────
# 접두 기호 추정
# ──────────────────────────────────────────────────────────────
def guess_prefix(text: str) -> Optional[str]:
    """문단 첫 토큰에서 접두 기호를 추정. 없으면 None."""
    if not text:
        return None
    for name, pattern in _PREFIX_PATTERNS:
        if pattern.match(text):
            return name
    m = _SYMBOL_PREFIX.match(text)
    if m:
        return m.group(1) + " "
    return None


# ──────────────────────────────────────────────────────────────
# 추출
# ──────────────────────────────────────────────────────────────
def extract_profile(source: Any, name: str = "추출 프로파일",
                    min_count: int = 1) -> ExtractResult:
    parts = _read_parts(source)
    header_xml = parts.get("Contents/header.xml")
    if header_xml is None:
        raise ValueError("Contents/header.xml이 없음 — hwpx 파일이 맞는지 확인")

    head = _et(header_xml)
    faces = _font_faces(head)
    chars = _char_props(head)
    paras = _para_props(head)
    styles = _styles(head)

    body_recs: List[Dict[str, Any]] = []
    cell_recs: List[Dict[str, Any]] = []
    section_names = sorted(n for n in parts if re.match(r"Contents/section\d+\.xml", n))
    for sec_name in section_names:
        b, c = _paragraph_records(parts[sec_name])
        body_recs += b
        cell_recs += c

    notes: List[str] = []
    use_style = sum(1 for r in body_recs if r["style"] != 0) >= max(3, len(body_recs) * 0.3)
    notes.append("클러스터 기준: styleIDRef" if use_style
                 else "클러스터 기준: (paraPrIDRef, charPrIDRef) — styleIDRef가 대부분 0")

    grouped: Dict[Tuple[Any, ...], Cluster] = {}
    for rec in body_recs:
        if not rec["text"]:
            continue
        key = (rec["style"],) if use_style else (rec["para"], rec["char"])
        cluster = grouped.get(key)
        if cluster is None:
            cluster = Cluster(key=key)
            if use_style:
                cluster.style_id = rec["style"]
                st = styles.get(rec["style"], {})
                cluster.style_name = st.get("name", "")
                cluster.para_pr_id = rec["para"] if rec["para"] else st.get("para_pr", 0)
                cluster.char_pr_id = rec["char"] if rec["char"] else st.get("char_pr", 0)
            else:
                cluster.para_pr_id, cluster.char_pr_id = rec["para"], rec["char"]
            grouped[key] = cluster
        cluster.count += 1
        if len(cluster.samples) < 3:
            cluster.samples.append(rec["text"])
        prefix = guess_prefix(rec["text"])
        if prefix:
            cluster.prefixes[prefix] += 1

    clusters = [c for c in grouped.values() if c.count >= min_count]
    for cluster in clusters:
        cp = chars.get(cluster.char_pr_id or 0, {})
        pp = paras.get(cluster.para_pr_id or 0, {})
        cluster.size_pt = cp.get("size_pt", 12.0)
        cluster.bold = bool(cp.get("bold", False))
        cluster.color = cp.get("color", "#000000")
        cluster.font_face = faces.get(cp.get("font_id", 0), "")
        cluster.left_pt = pp.get("left_pt", 0.0)
        cluster.indent_pt = pp.get("indent_pt", 0.0)
        cluster.spacing_below_pt = pp.get("spacing_below_pt", 0.0)
        cluster.line_spacing = pp.get("line_spacing", 160)
        cluster.align = pp.get("align", "JUSTIFY")

    # 레벨 순서: 자동 번호(제목) 먼저, 그 다음 left_pt 오름차순 → size 내림차순
    def sort_key(c: Cluster) -> Tuple[Any, ...]:
        prefix = c.prefixes.most_common(1)[0][0] if c.prefixes else ""
        is_title = prefix.startswith("AUTO_")
        title_rank = {"AUTO_ROMAN": 0, "AUTO_ALPHA": 1, "AUTO_HANGUL": 2,
                      "AUTO_NUM": 3, "AUTO_CIRCLED": 4}.get(prefix, 9)
        return (0 if is_title else 1, title_rank if is_title else 0,
                c.left_pt, -c.size_pt)

    clusters.sort(key=sort_key)

    bold_faces = {c.font_face for c in clusters if c.bold and c.font_face}
    light_faces = {c.font_face for c in clusters if not c.bold and c.font_face}
    font_bold = sorted(bold_faces)[0] if bold_faces else (
        sorted(light_faces)[0] if light_faces else "맑은 고딕")
    font_light = sorted(light_faces)[0] if light_faces else font_bold

    levels: List[Dict[str, Any]] = []
    title_seen = 0
    for i, cluster in enumerate(clusters):
        prefix = cluster.prefixes.most_common(1)[0][0] if cluster.prefixes else ""
        if prefix.startswith("AUTO_"):
            key = "title" if title_seen == 0 else ("title2" if title_seen == 1
                                                   else f"T{title_seen + 1}")
            marker = "#" * (title_seen + 1) if title_seen < 2 else "#" * (title_seen + 1)
            title_seen += 1
        else:
            key = f"L{i - title_seen + 1}"
            marker = prefix.strip()
        levels.append({
            "key": key,
            "name": cluster.style_name or key,
            "marker": marker,
            "prefix": prefix,
            "size_pt": cluster.size_pt,
            "bold": cluster.bold,
            "font": "bold" if cluster.font_face == font_bold and cluster.bold else "light",
            "color": cluster.color,
            "left_pt": cluster.left_pt,
            "indent_pt": cluster.indent_pt,
            "spacing_below_pt": cluster.spacing_below_pt,
            "line_spacing": cluster.line_spacing,
            "align": cluster.align,
        })

    table_styles, table_notes = _table_styles(cell_recs, chars, paras, faces, font_bold)
    notes += table_notes

    margins = _page_margins(parts, section_names)
    profile: Dict[str, Any] = {
        "schema": SCHEMA_ID,
        "name": name,
        "mode": "outline" if levels else "narrative",
        "fonts": {"bold": font_bold, "light": font_light, "fallback": font_light},
        "page": {"size": "A4", "margin_mm": margins},
        "levels": levels,
    }
    if table_styles:
        profile["table"] = table_styles

    if any(_has_auto_numbering(parts[s]) for s in section_names):
        notes.append("한글 번호매기기/글머리표 기능(hh:heading)이 쓰인 문단이 있음 "
                     "→ 해당 레벨의 prefix는 UNKNOWN_AUTO로 표기")

    result_profile = merge_profile(profile)
    report = build_report(clusters, result_profile, notes, len(body_recs))
    return ExtractResult(profile=profile, report=report, clusters=clusters, notes=notes)


def _has_auto_numbering(section_xml: str) -> bool:
    return bool(re.search(r'<hh:heading[^>]*type="(NUMBER|BULLET)"', section_xml))


def _table_styles(cell_recs, chars, paras, faces, font_bold) -> Tuple[Dict[str, Any], List[str]]:
    if not cell_recs:
        return {}, ["표가 없어 표 스타일은 기본값 사용"]

    def cell_style(recs) -> Dict[str, Any]:
        char_id = Counter(r["char"] for r in recs).most_common(1)[0][0]
        para_id = Counter(r["para"] for r in recs).most_common(1)[0][0]
        cp, pp = chars.get(char_id, {}), paras.get(para_id, {})
        return {
            "size_pt": cp.get("size_pt", 11),
            "bold": bool(cp.get("bold", False)),
            "font": "bold" if faces.get(cp.get("font_id", 0), "") == font_bold
                    and cp.get("bold") else "light",
            "color": cp.get("color", "#000000"),
            "line_spacing": pp.get("line_spacing", 120),
            "align": pp.get("align", "CENTER"),
            "left_pt": pp.get("left_pt", 0),
            "indent_pt": pp.get("indent_pt", 0),
        }

    head = [r for r in cell_recs if r["row"] == 0 and r["text"]]
    rest = [r for r in cell_recs if r["row"] not in (0, None) and r["text"]]
    out: Dict[str, Any] = {}
    if head:
        out["top"] = dict(cell_style(head), name="표(위)", eng_name="Table(Top)")
    if rest:
        out["mid"] = dict(cell_style(rest), name="표(중간)", eng_name="Table(Mid)")
    return out, []


def _page_margins(parts: Dict[str, str], section_names: List[str]) -> Dict[str, float]:
    default = {"left": 20, "right": 20, "top": 10, "bottom": 10, "header": 10, "footer": 10}
    for name in section_names:
        m = re.search(r"<hp:margin\b[^>]*/>", parts[name])
        if not m:
            continue
        tag = m.group()
        out = {}
        for key in default:
            v = re.search(rf'{key}="(\d+)"', tag)
            out[key] = round(int(v.group(1)) / MM, 1) if v else default[key]
        return out
    return default


# ──────────────────────────────────────────────────────────────
# 리포트
# ──────────────────────────────────────────────────────────────
def build_report(clusters: List[Cluster], profile: Dict[str, Any],
                 notes: List[str], total_paragraphs: int) -> str:
    lines: List[str] = []
    lines.append("# 서식 추출 리포트")
    lines.append("")
    lines.append(f"- 본문 문단 수: {total_paragraphs}")
    lines.append(f"- 추정 레벨 수: {len(profile.get('levels', []))}")
    lines.append(f"- 글꼴: bold={profile['fonts']['bold']} / light={profile['fonts']['light']}")
    margin = profile["page"]["margin_mm"]
    lines.append(f"- 여백(mm): 좌{margin['left']} 우{margin['right']} "
                 f"상{margin['top']} 하{margin['bottom']}")
    lines.append("")
    for note in notes:
        lines.append(f"> {note}")
    if notes:
        lines.append("")

    lines.append("## 레벨별 근거")
    lines.append("")
    lines.append("| key | 스타일명 | 빈도 | 크기 | 굵기 | 왼쪽여백 | 내어쓰기 | 줄간격 | "
                 "접두 후보 | 예시 |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|")
    levels = profile.get("levels", [])
    for level, cluster in zip(levels, clusters):
        cands = ", ".join(f"{p!r}×{n}" for p, n in cluster.prefixes.most_common(3)) or "-"
        sample = (cluster.samples[0][:24] + "…") if cluster.samples else ""
        lines.append(
            f"| {level['key']} | {cluster.style_name or '-'} | {cluster.count} | "
            f"{cluster.size_pt}pt | {'B' if cluster.bold else '-'} | {cluster.left_pt}pt | "
            f"{cluster.indent_pt}pt | {cluster.line_spacing}% | {cands} | {sample} |"
        )
    lines.append("")
    lines.append("## 확인 사항")
    lines.append("")
    lines.append("- 접두 기호는 **첫 글자 빈도**로 추정한 값이다. 2위 이하 후보가 있으면 "
                 "위 표의 '접두 후보'를 보고 직접 고칠 것")
    lines.append("- 레벨 순서는 왼쪽 여백 오름차순 → 글자 크기 내림차순으로 정렬했다")
    lines.append("- 이 리포트를 확인한 뒤 프로파일을 저장하는 것을 권장한다 "
                 "(`hwpx-studio extract ... -o profile.json`)")
    return "\n".join(lines) + "\n"


def write_outputs(result: ExtractResult, profile_path: Optional[str],
                  report_path: Optional[str]) -> None:
    import json

    if profile_path:
        Path(profile_path).write_text(
            json.dumps(result.profile, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8")
    if report_path:
        Path(report_path).write_text(result.report, encoding="utf-8")
