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
    ("AUTO_CHAPTER", re.compile(r"^제\s?\d{1,2}\s?장\s")),
    ("AUTO_SECTION", re.compile(r"^제\s?\d{1,2}\s?절\s")),
    ("AUTO_ROMAN", re.compile(rf"^[{ROMAN_CHARS}]+[.)]\s")),
    ("AUTO_NUM", re.compile(r"^\d{1,2}\.\s")),
    ("AUTO_PAREN", re.compile(r"^\d{1,2}\)\s")),
    ("AUTO_ALPHA", re.compile(r"^[A-Z][.)]\s")),
    ("AUTO_CIRCLED", re.compile(rf"^[{CIRCLED_CHARS}]\s?")),
    ("AUTO_HANGUL", re.compile(r"^[가나다라마바사아자차카타파하][.)]\s")),
]
#: 선행 비문자 기호 1~2자 + 공백 (□ ○ - · ※ ▪ – 등)
_SYMBOL_PREFIX = re.compile(r"^([^\w\s]{1,2})\s")
#: 글꼴 이름만으로 굵은 글꼴을 판정하는 규칙
_BOLD_NAME_RE = re.compile(r"(?i)bold|black|heavy|헤드라인|굵은")
#: 이 비율 이상이 표 안에서만 나오면 '표 전용 스타일'로 보고 레벨에서 제외
TABLE_ONLY_RATIO = 0.8
#: 1행이면서 셀이 이 수 이하인 표는 데이터 표가 아니라 제목 상자로 본다
LAYOUT_TABLE_MAX_CELLS = 3
#: 글자 수가 이 이하인 문단은 번호·쪽번호로 본다
SHORT_TEXT_LEN = 2
#: 짧은 텍스트가 이 비율 이상인 클러스터는 레벨에서 제외
SHORT_TEXT_RATIO = 0.6


@dataclass
class Cluster:
    key: Tuple[Any, ...]
    style_id: Optional[int] = None
    para_pr_id: Optional[int] = None
    char_pr_id: Optional[int] = None
    style_name: str = ""
    count: int = 0
    in_table_count: int = 0
    short_count: int = 0
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
#: OLE 복합 문서 서명 — 한글 5.0 바이너리(.hwp)
_HWP_BINARY_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"


def _check_format(head: bytes, label: str) -> None:
    if head.startswith(_HWP_BINARY_MAGIC):
        raise ValueError(
            f"{label}은(는) 한글 바이너리 형식(.hwp)이다. 이 도구는 .hwpx만 읽는다. "
            "한글에서 [다른 이름으로 저장] → 파일 형식 'HWPX 문서'로 저장한 뒤 다시 실행할 것"
        )
    if not head.startswith(b"PK"):
        raise ValueError(f"{label}을(를) hwpx로 열 수 없다(zip 형식이 아님)")


def _read_parts(source: Any) -> Dict[str, str]:
    if isinstance(source, (bytes, bytearray)):
        _check_format(bytes(source[:8]), "입력 데이터")
        zf = zipfile.ZipFile(BytesIO(bytes(source)))
    else:
        with open(str(source), "rb") as fh:
            _check_format(fh.read(8), str(source))
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


def _paragraph_records(section_xml: str) -> List[Dict[str, Any]]:
    """문단 기록 목록. 표 안 문단은 in_table=True, row=행번호를 갖는다."""
    root = _et(section_xml)
    records: List[Dict[str, Any]] = []

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
            "in_table": in_table,
        }
        records.append(rec)

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
                rows = child.findall(f"{{{NS['hp']}}}tr")
                cells = len(child.findall(f".//{{{NS['hp']}}}tc"))
                # 1행짜리 표는 대개 제목 상자(레이아웃)다 → 본문 문단으로 취급
                is_data = len(rows) > 1 or cells > LAYOUT_TABLE_MAX_CELLS
                for tr_i, tr in enumerate(rows):
                    walk(tr, is_data, tr_i if is_data else None)
            else:
                walk(child, in_table, row)

    walk(root, False, None)
    return records


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
def _font_roles(clusters: List[Cluster]) -> Tuple[str, str]:
    """(bold 역할 글꼴, light 역할 글꼴).

    굵기를 `bold` 속성이 아니라 **글꼴 이름**(예: 'KoPub돋움체 Bold' / 'Light')으로
    구분하는 문서가 많다. bold 속성 → 이름 규칙 → 최대 글자 크기 순으로 판정한다.
    """
    weight: Counter = Counter()
    for c in clusters:
        if c.font_face:
            weight[c.font_face] += max(1, c.count)
    if not weight:
        return "맑은 고딕", "맑은 고딕"

    bold_weight = Counter()
    for c in clusters:
        if c.bold and c.font_face:
            bold_weight[c.font_face] += max(1, c.count)
    bold_face = bold_weight.most_common(1)[0][0] if bold_weight else ""

    if not bold_face:
        named = Counter({face: n for face, n in weight.items()
                         if _BOLD_NAME_RE.search(face)})
        bold_face = named.most_common(1)[0][0] if named else ""

    if not bold_face:
        biggest = max(clusters, key=lambda c: (c.size_pt, c.count))
        bold_face = biggest.font_face or weight.most_common(1)[0][0]

    rest = Counter({face: n for face, n in weight.items() if face != bold_face})
    light_face = rest.most_common(1)[0][0] if rest else bold_face
    return bold_face, light_face


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

    records: List[Dict[str, Any]] = []
    section_names = sorted(n for n in parts if re.match(r"Contents/section\d+\.xml", n))
    for sec_name in section_names:
        records += _paragraph_records(parts[sec_name])

    notes: List[str] = []
    use_style = sum(1 for r in records if r["style"] != 0) >= max(3, len(records) * 0.3)
    notes.append("클러스터 기준: styleIDRef" if use_style
                 else "클러스터 기준: (paraPrIDRef, charPrIDRef) — styleIDRef가 대부분 0")

    def cluster_key(rec: Dict[str, Any]) -> Tuple[Any, ...]:
        return (rec["style"],) if use_style else (rec["para"], rec["char"])

    # 표 안 문단도 레벨 후보에 포함한다(제목이 제목 상자=표 안에 있는 문서가 흔하다).
    grouped: Dict[Tuple[Any, ...], Cluster] = {}
    for rec in records:
        if not rec["text"]:
            continue
        key = cluster_key(rec)
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
        if rec["in_table"]:
            cluster.in_table_count += 1
        if len(rec["text"].strip()) <= SHORT_TEXT_LEN:
            cluster.short_count += 1
        if len(cluster.samples) < 3:
            cluster.samples.append(rec["text"])
        prefix = guess_prefix(rec["text"])
        if prefix:
            cluster.prefixes[prefix] += 1

    for cluster in grouped.values():
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

    # 표 셀 전용 스타일은 레벨에서 제외한다
    cell_recs = [r for r in records if r["in_table"] and r["text"]]
    table_styles, table_keys, table_notes = _table_styles(
        cell_recs, chars, paras, faces, cluster_key, grouped)
    notes += table_notes

    def is_numbering_noise(c: Cluster) -> bool:
        return bool(c.count) and c.short_count / c.count >= SHORT_TEXT_RATIO

    clusters, dropped = [], []
    for key, c in grouped.items():
        if c.count < min_count or key in table_keys:
            continue
        (dropped if is_numbering_noise(c) else clusters).append(c)
    if dropped:
        notes.append(
            "번호·쪽번호로 보이는 클러스터를 레벨에서 제외: "
            + ", ".join(f"{c.style_name or c.key}({c.count}회)" for c in dropped))

    def sort_key(c: Cluster) -> Tuple[Any, ...]:
        prefix = c.prefixes.most_common(1)[0][0] if c.prefixes else ""
        is_title = prefix.startswith("AUTO_")
        title_rank = {"AUTO_ROMAN": 0, "AUTO_ALPHA": 1, "AUTO_HANGUL": 2,
                      "AUTO_NUM": 3, "AUTO_CIRCLED": 4}.get(prefix, 9)
        return (0 if is_title else 1, title_rank if is_title else 0,
                c.left_pt, -c.size_pt)

    clusters.sort(key=sort_key)

    font_bold, font_light = _font_roles(clusters)

    levels: List[Dict[str, Any]] = []
    title_seen = 0
    symbol_seen = False
    auto_marked: List[str] = []
    for i, cluster in enumerate(clusters):
        prefix = cluster.prefixes.most_common(1)[0][0] if cluster.prefixes else ""
        if prefix.startswith("AUTO_"):
            key = "title" if title_seen == 0 else ("title2" if title_seen == 1
                                                   else f"T{title_seen + 1}")
            marker = "#" * (title_seen + 1)
            title_seen += 1
        elif not prefix and not symbol_seen and cluster.left_pt == 0:
            # 접두 기호가 없는 최상위 레벨(번호가 별도 셀에 있는 제목 등)
            # → 제목 마커(#, ##)를 이어서 배정한다
            key = "title" if title_seen == 0 else ("title2" if title_seen == 1
                                                   else f"T{title_seen + 1}")
            marker = "#" * (title_seen + 1)
            title_seen += 1
            auto_marked.append(f"{key}({cluster.style_name or '이름없음'})")
        else:
            symbol_seen = symbol_seen or bool(prefix.strip())
            key = f"L{i - title_seen + 1}"
            marker = prefix.strip()
        levels.append({
            "key": key,
            "name": cluster.style_name or key,
            "marker": marker,
            "prefix": prefix,
            "size_pt": cluster.size_pt,
            "bold": cluster.bold,
            "font": "bold" if cluster.font_face == font_bold else "light",
            "color": cluster.color,
            "left_pt": cluster.left_pt,
            "indent_pt": cluster.indent_pt,
            "spacing_below_pt": cluster.spacing_below_pt,
            "line_spacing": cluster.line_spacing,
            "align": cluster.align,
        })

    if auto_marked:
        notes.append(
            "접두 기호가 없어 제목 마커를 자동 배정한 레벨: " + ", ".join(auto_marked)
            + " — 원본에서 번호가 별도 셀·필드에 있는 경우다. 생성 시에는 번호가 "
            "붙지 않으니, 자동 번호가 필요하면 prefix를 AUTO_NUM 등으로 바꿀 것")

    no_marker = [lv["key"] for lv in levels if not lv["marker"]]
    if no_marker:
        notes.append(
            f"마커가 비어 있는 레벨: {', '.join(no_marker)} "
            "— 마커 텍스트에서 이 레벨을 쓰려면 marker를 직접 지정해야 한다")

    only_in_table = [lv["key"] for lv, c in zip(levels, clusters)
                     if c.in_table_count == c.count]
    if only_in_table:
        notes.append(
            f"표 안에서만 등장한 레벨: {', '.join(only_in_table)} "
            "— 제목 상자(표)에 든 제목일 수 있다. 표 전용 서식이면 levels에서 지울 것")

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

    # hh:heading은 header.xml의 paraPr 안에 있다(section이 아니다)
    if _has_auto_numbering(header_xml):
        notes.append("한글 번호매기기·글머리표(hh:heading)를 쓰는 양식이다. "
                     "프로파일 방식은 이 기능을 옮기지 못한다 → 서식을 그대로 지키려면 "
                     "`hwpx-studio formkit`으로 양식 보존 꾸러미를 만들 것")

    result_profile = merge_profile(profile)
    report = build_report(clusters, result_profile, notes,
                          sum(1 for r in records if r["text"]))
    return ExtractResult(profile=profile, report=report, clusters=clusters, notes=notes)


def _has_auto_numbering(header_xml: str) -> bool:
    """한글이 기호·번호를 자동으로 붙이는 양식인가. 정의는 header.xml에 있다."""
    return bool(re.search(r'<hh:heading[^>]*type="(NUMBER|BULLET)"', header_xml))


def _table_styles(cell_recs, chars, paras, faces, cluster_key, grouped
                  ) -> Tuple[Dict[str, Any], set, List[str]]:
    """표 셀 스타일과, 레벨에서 제외할 클러스터 key 집합을 돌려준다.

    표 셀 대표 스타일이라도 표 밖에서도 자주 쓰이면(본문과 같은 스타일) 제외하지
    않는다 — 실제 레벨을 잃는 쪽이 더 나쁘다.
    """
    if not cell_recs:
        return {}, set(), ["표가 없어 표 스타일은 기본값 사용"]

    def cell_style(recs) -> Dict[str, Any]:
        char_id = Counter(r["char"] for r in recs).most_common(1)[0][0]
        para_id = Counter(r["para"] for r in recs).most_common(1)[0][0]
        cp, pp = chars.get(char_id, {}), paras.get(para_id, {})
        return {
            "size_pt": cp.get("size_pt", 11),
            "bold": bool(cp.get("bold", False)),
            "font": "light",
            "color": cp.get("color", "#000000"),
            "line_spacing": pp.get("line_spacing", 120),
            "align": pp.get("align", "CENTER"),
            "left_pt": pp.get("left_pt", 0),
            "indent_pt": pp.get("indent_pt", 0),
        }

    head = [r for r in cell_recs if r["row"] == 0]
    rest = [r for r in cell_recs if r["row"] not in (0, None)]
    out: Dict[str, Any] = {}
    keys: set = set()

    for label, recs, name, eng in (("top", head, "표(위)", "Table(Top)"),
                                   ("mid", rest, "표(중간)", "Table(Mid)")):
        if not recs:
            continue
        out[label] = dict(cell_style(recs), name=name, eng_name=eng)
        rep = Counter(cluster_key(r) for r in recs).most_common(1)[0][0]
        cluster = grouped.get(rep)
        if cluster and cluster.count and \
                cluster.in_table_count / cluster.count >= TABLE_ONLY_RATIO:
            keys.add(rep)
    return out, keys, []


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
    lines.append("| key | 스타일명 | 빈도 | 표안 | 크기 | 굵기 | 글꼴 | 왼쪽여백 | "
                 "내어쓰기 | 줄간격 | 접두 후보 | 예시 |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
    levels = profile.get("levels", [])
    for level, cluster in zip(levels, clusters):
        cands = ", ".join(f"{p!r}×{n}" for p, n in cluster.prefixes.most_common(3)) or "-"
        sample = (cluster.samples[0][:24] + "…") if cluster.samples else ""
        lines.append(
            f"| {level['key']} | {cluster.style_name or '-'} | {cluster.count} | "
            f"{cluster.in_table_count} | {cluster.size_pt}pt | "
            f"{'B' if cluster.bold else '-'} | {level['font']} | {cluster.left_pt}pt | "
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
