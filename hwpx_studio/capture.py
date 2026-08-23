"""도식 수집: 남의 도식을 읽어 `:::diagram` 블록으로 옮긴다.

지금 읽을 수 있는 것은 **구조가 글자로 남아 있는 입력**이다.

* Mermaid (`flowchart TD` / `graph LR` …) — 웹 문서·위키·AI가 가장 흔히 내놓는 형식
* SVG — 웹 페이지·발표자료에서 복사한 벡터 도식
* HTML — 안에 들어 있는 `<svg>`를 꺼내 같은 방식으로 읽는다

색·선 종류는 원본에 적힌 값을 그대로 가져온다(추정이 아니다). 구조는 연결선이
있으면 연결선을, 없으면 상자의 배치(같은 높이 = 같은 단계)를 근거로 세운다.

산출물은 사람이 읽고 고칠 수 있는 텍스트라, 잘못 읽은 곳은 한 줄 고치면 된다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from html import unescape
from typing import Any, Dict, List, Optional, Sequence, Tuple
from xml.etree import ElementTree

from .diagram import DiagramSpec, normalize_color, normalize_line_type

__all__ = ["CaptureResult", "capture", "capture_text", "from_mermaid", "from_svg",
           "from_html", "spec_to_text"]


@dataclass
class CaptureResult:
    spec: DiagramSpec
    source: str = ""                              # mermaid | svg | html
    warnings: List[str] = field(default_factory=list)

    def to_text(self) -> str:
        return spec_to_text(self.spec)


# ──────────────────────────────────────────────────────────────
# 공통 그래프 → 트리
# ──────────────────────────────────────────────────────────────
@dataclass
class CapNode:
    key: str
    text: str
    style: Dict[str, str] = field(default_factory=dict)


@dataclass
class CapEdge:
    src: str
    dst: str
    style: Dict[str, str] = field(default_factory=dict)


def _tree_lines(nodes: Sequence[CapNode], edges: Sequence[CapEdge],
                warnings: List[str]) -> List[str]:
    """노드·간선 → 들여쓰기 트리 줄 목록.

    부모가 여럿인 노드는 첫 번째 간선만 계층으로 쓰고 나머지는 경고로 남긴다
    (표 도식은 한 부모만 그릴 수 있다).
    """
    by_key = {n.key: n for n in nodes}
    order = [n.key for n in nodes]
    children: Dict[str, List[str]] = {k: [] for k in order}
    parent: Dict[str, str] = {}
    edge_style: Dict[str, Dict[str, str]] = {}
    dropped = 0

    for edge in edges:
        if edge.src not in by_key or edge.dst not in by_key:
            continue
        if edge.dst in parent or edge.dst == edge.src:
            dropped += 1
            continue
        parent[edge.dst] = edge.src
        edge_style[edge.dst] = edge.style
        children[edge.src].append(edge.dst)

    if dropped:
        warnings.append(
            f"한 상자에 들어오는 연결선이 여러 개여서 {dropped}개는 계층에서 뺐다"
            "(표 도식은 상자마다 부모 하나만 그린다). 필요하면 손으로 옮길 것")

    rank = {key: i for i, key in enumerate(order)}
    for group in children.values():
        group.sort(key=lambda k: rank[k])          # 원본 순서(SVG는 왼→오른쪽)를 지킨다

    roots = [k for k in order if k not in parent]
    lines: List[str] = []
    seen: set = set()

    def emit(key: str, depth: int) -> None:
        if key in seen:                            # 순환 방지
            return
        seen.add(key)
        node = by_key[key]
        style = dict(node.style)
        style.update(edge_style.get(key, {}))
        lines.append("  " * depth + _node_line(node.text, style))
        for child in children[key]:
            emit(child, depth + 1)

    for root in roots:
        emit(root, 0)
    for key in order:                              # 순환에 갇힌 나머지
        if key not in seen:
            emit(key, 0)
    return lines


_ATTR_ORDER = ("fill", "color", "border", "link", "link_color")


def _node_line(text: str, style: Dict[str, str]) -> str:
    attrs = " ".join(f"{k}={style[k]}" for k in _ATTR_ORDER if style.get(k))
    return f"{text} {{{attrs}}}" if attrs else text


def _is_chain(nodes: Sequence[CapNode], edges: Sequence[CapEdge]) -> bool:
    """간선이 A→B→C 한 줄로만 이어지면 절차도로 본다."""
    if len(nodes) < 2 or len(edges) != len(nodes) - 1:
        return False
    out_deg: Dict[str, int] = {}
    in_deg: Dict[str, int] = {}
    for e in edges:
        out_deg[e.src] = out_deg.get(e.src, 0) + 1
        in_deg[e.dst] = in_deg.get(e.dst, 0) + 1
    return (all(v == 1 for v in out_deg.values())
            and all(v == 1 for v in in_deg.values()))


def _chain_line(nodes: Sequence[CapNode], edges: Sequence[CapEdge]) -> List[str]:
    by_key = {n.key: n for n in nodes}
    nxt = {e.src: e.dst for e in edges}
    start = next(k for k in by_key if k not in {e.dst for e in edges})
    steps: List[str] = []
    key: Optional[str] = start
    while key is not None and key in by_key and len(steps) <= len(by_key):
        node = by_key[key]
        steps.append(_node_line(node.text, node.style))
        key = nxt.get(key)
    return [" → ".join(steps)]


def _make_spec(nodes: Sequence[CapNode], edges: Sequence[CapEdge], title: str,
               warnings: List[str], prefer_flow: bool = False) -> DiagramSpec:
    if not nodes:
        return DiagramSpec(type="org", title=title, lines=[])
    if (prefer_flow or len(nodes) > 2) and _is_chain(nodes, edges):
        return DiagramSpec(type="flow", title=title, lines=_chain_line(nodes, edges))
    return DiagramSpec(type="org", title=title, lines=_tree_lines(nodes, edges, warnings))


# ──────────────────────────────────────────────────────────────
# Mermaid
# ──────────────────────────────────────────────────────────────
#: mermaid 노드 이름. `-`는 화살표와 헷갈리므로 넣지 않는다
_MM_ID = r"[A-Za-z0-9_.]+"
#: `A[라벨]` `A(라벨)` `A{라벨}` `A((라벨))` `A[[라벨]]` …
_MM_NODE = re.compile(rf'({_MM_ID})\s*(\[\[|\[\(|\[|\(\(|\(|\{{\{{|\{{)'
                      r'\s*"?(.*?)"?\s*(\]\]|\)\]|\]|\)\)|\)|\}\}|\})')
#: `A --> B`, `A -.-> B`, `A ==> B`, `A -->|라벨| B`
#: 도착지는 뒤돌아보기로만 확인한다 — `A --> B --> C`처럼 이어 쓴 줄을 다 읽기 위해서다
_MM_EDGE = re.compile(
    rf'({_MM_ID})(?:[\[({{][^\]|)}}]*[\])}}]+)?\s*'
    r'(-\.-+>|-\.-+|-{2,}>|-{2,}|={2,}>|={2,}|--[ox])'
    rf'\s*(?:\|[^|]*\|)?\s*(?=({_MM_ID}))')
_MM_STYLE = re.compile(rf'^\s*style\s+({_MM_ID})\s+(.*)$')
_MM_CLASSDEF = re.compile(rf'^\s*classDef\s+({_MM_ID})\s+(.*)$')
_MM_CLASS = re.compile(rf'^\s*class\s+([A-Za-z0-9_.,]+)\s+({_MM_ID})')
_MM_HEADER = re.compile(r'^\s*(?:flowchart|graph)\s+(TB|TD|BT|RL|LR)?', re.I)
_MM_TITLE = re.compile(r'^\s*title\s*:?\s*(.+)$', re.I)


def _mermaid_style(text: str) -> Dict[str, str]:
    """`fill:#f9f,stroke:#333,stroke-dasharray: 5 5` → 노드 속성."""
    out: Dict[str, str] = {}
    for part in re.split(r"[,;]", text):
        key, _, value = part.partition(":")
        key, value = key.strip().lower(), value.strip()
        if key == "fill":
            color = normalize_color(value)
            if color:
                out["fill"] = color
        elif key == "stroke":
            color = normalize_color(value)
            if color:
                out["border"] = color
        elif key == "color":
            color = normalize_color(value)
            if color:
                out["color"] = color
        elif key == "stroke-dasharray" and value:
            out["link"] = "dash"
    return out


def from_mermaid(text: str, title: str = "") -> CaptureResult:
    """Mermaid flowchart 문법 → 도식 spec."""
    warnings: List[str] = []
    nodes: List[CapNode] = []
    index: Dict[str, CapNode] = {}
    edges: List[CapEdge] = []
    class_styles: Dict[str, Dict[str, str]] = {}
    pending_class: List[Tuple[List[str], str]] = []
    direction = ""

    def touch(key: str, label: Optional[str] = None) -> CapNode:
        node = index.get(key)
        if node is None:
            node = CapNode(key=key, text=label or key)
            index[key] = node
            nodes.append(node)
        elif label:
            node.text = label
        return node

    for raw in text.splitlines():
        line = raw.split("%%", 1)[0].rstrip()      # 주석 제거
        if not line.strip():
            continue

        head = _MM_HEADER.match(line)
        if head and not line.strip().lower().startswith(("graphtd",)):
            direction = (head.group(1) or "").upper()
            rest = line[head.end():].strip()
            if not rest:
                continue
            line = rest

        m = _MM_TITLE.match(line)
        if m and not title:
            title = m.group(1).strip()
            continue

        m = _MM_CLASSDEF.match(line)
        if m:
            class_styles[m.group(1)] = _mermaid_style(m.group(2))
            continue
        m = _MM_CLASS.match(line)
        if m:
            pending_class.append(([k.strip() for k in m.group(1).split(",")], m.group(2)))
            continue
        m = _MM_STYLE.match(line)
        if m:
            touch(m.group(1)).style.update(_mermaid_style(m.group(2)))
            continue

        # `A:::클래스` 표기
        for key, cls in re.findall(r'([A-Za-z0-9_.\-]+):::([A-Za-z0-9_.\-]+)', line):
            pending_class.append(([key], cls))
        line = re.sub(r':::([A-Za-z0-9_.\-]+)', "", line)

        for m in _MM_NODE.finditer(line):
            touch(m.group(1), unescape(m.group(3).strip()) or m.group(1))

        for m in _MM_EDGE.finditer(line):
            src, arrow, dst = m.group(1), m.group(2), m.group(3)
            touch(src)
            touch(dst)
            style: Dict[str, str] = {}
            if "." in arrow:
                style["link"] = "dash"
            edges.append(CapEdge(src=src, dst=dst, style=style))

    for keys, cls in pending_class:
        style = class_styles.get(cls)
        if not style:
            continue
        for key in keys:
            if key in index:
                index[key].style.update(style)

    if not nodes:
        warnings.append("Mermaid에서 상자를 찾지 못했다(flowchart/graph 문법만 읽는다)")

    prefer_flow = direction in ("LR", "RL")
    spec = _make_spec(nodes, edges, title, warnings, prefer_flow=prefer_flow)
    if spec.type == "flow" and direction in ("TB", "TD"):
        spec.options["direction"] = "down"
    return CaptureResult(spec=spec, source="mermaid", warnings=warnings)


# ──────────────────────────────────────────────────────────────
# SVG
# ──────────────────────────────────────────────────────────────
@dataclass
class _Box:
    x: float
    y: float
    w: float
    h: float
    text: str = ""
    style: Dict[str, str] = field(default_factory=dict)

    @property
    def cx(self) -> float:
        return self.x + self.w / 2

    @property
    def cy(self) -> float:
        return self.y + self.h / 2

    def contains(self, px: float, py: float, pad: float = 2.0) -> bool:
        return (self.x - pad <= px <= self.x + self.w + pad
                and self.y - pad <= py <= self.y + self.h + pad)


def _svg_style(elem) -> Dict[str, str]:
    """SVG 요소의 presentation attribute와 style="" 를 합쳐 읽는다."""
    props: Dict[str, str] = {}
    for key in ("fill", "stroke", "stroke-dasharray", "color"):
        value = elem.get(key)
        if value:
            props[key] = value
    for part in re.split(r";", elem.get("style") or ""):
        key, _, value = part.partition(":")
        if key.strip():
            props[key.strip().lower()] = value.strip()
    return props


def _box_style(props: Dict[str, str]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    fill = normalize_color(props.get("fill"))
    if fill and props.get("fill", "").lower() != "none":
        out["fill"] = fill
    border = normalize_color(props.get("stroke"))
    if border:
        out["border"] = border
    return out


def _num(value: Optional[str], default: float = 0.0) -> float:
    try:
        return float(re.sub(r"[^0-9.\-+eE]", "", value or "") or default)
    except ValueError:
        return default


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _path_points(d: str) -> List[Tuple[float, float]]:
    """직선 위주 path의 좌표만 훑는다(곡선은 제어점까지 섞여도 끝점은 맞다)."""
    nums = [float(n) for n in re.findall(r"-?\d+(?:\.\d+)?", d or "")]
    return [(nums[i], nums[i + 1]) for i in range(0, len(nums) - 1, 2)]


def from_svg(text: str, title: str = "") -> CaptureResult:
    """SVG의 사각형·글자·연결선을 읽어 도식 spec으로."""
    warnings: List[str] = []
    try:
        root = ElementTree.fromstring(text)
    except ElementTree.ParseError as exc:
        return CaptureResult(spec=DiagramSpec(type="org", lines=[]), source="svg",
                             warnings=[f"SVG를 읽지 못했다: {exc}"])

    boxes: List[_Box] = []
    texts: List[Tuple[float, float, str, Dict[str, str]]] = []
    edges_raw: List[Tuple[Tuple[float, float], Tuple[float, float], Dict[str, str]]] = []

    for elem in root.iter():
        tag = _local(elem.tag)
        props = _svg_style(elem)
        if tag == "rect":
            boxes.append(_Box(_num(elem.get("x")), _num(elem.get("y")),
                              _num(elem.get("width")), _num(elem.get("height")),
                              style=_box_style(props)))
        elif tag == "text":                       # tspan은 itertext가 함께 훑는다
            content = " ".join("".join(elem.itertext()).split())
            if content:
                texts.append((_num(elem.get("x")), _num(elem.get("y")), content, props))
        elif tag == "line":
            edges_raw.append(((_num(elem.get("x1")), _num(elem.get("y1"))),
                              (_num(elem.get("x2")), _num(elem.get("y2"))), props))
        elif tag in ("path", "polyline"):
            points = (_path_points(elem.get("d") or "") if tag == "path"
                      else _path_points(elem.get("points") or ""))
            if len(points) >= 2:
                edges_raw.append((points[0], points[-1], props))

    boxes = [b for b in boxes if b.w > 1 and b.h > 1]
    if not boxes:
        warnings.append("SVG에서 상자(<rect>)를 찾지 못했다")
        return CaptureResult(spec=DiagramSpec(type="org", title=title, lines=[]),
                             source="svg", warnings=warnings)

    # 배경 사각형(전체를 덮는 것)은 상자가 아니다
    widest = max(b.w * b.h for b in boxes)
    boxes = [b for b in boxes if b.w * b.h < widest or len(boxes) == 1] or boxes

    for x, y, content, props in texts:                      # 글자를 상자에 넣기
        target = next((b for b in boxes if b.contains(x, y)), None)
        if target is None:
            target = min(boxes, key=lambda b: (b.cx - x) ** 2 + (b.cy - y) ** 2)
            if abs(target.cy - y) > target.h:               # 너무 멀면 라벨로 보고 버림
                continue
        target.text = f"{target.text} {content}".strip() if target.text else content
        color = normalize_color(props.get("fill"))
        if color:
            target.style.setdefault("color", color)

    boxes = [b for b in boxes if b.text]
    if not boxes:
        warnings.append("상자 안에서 글자를 찾지 못했다")
        return CaptureResult(spec=DiagramSpec(type="org", title=title, lines=[]),
                             source="svg", warnings=warnings)

    boxes.sort(key=lambda b: (round(b.cy, 1), b.cx))
    nodes = [CapNode(key=str(i), text=b.text, style=dict(b.style))
             for i, b in enumerate(boxes)]

    edges = _svg_edges(boxes, edges_raw)
    if not edges:
        edges = _rows_to_edges(boxes)
        if edges:
            warnings.append("연결선을 찾지 못해 상자의 높이(같은 줄 = 같은 단계)로 "
                            "계층을 세웠다 — 확인할 것")

    spec = _make_spec(nodes, edges, title, warnings)
    return CaptureResult(spec=spec, source="svg", warnings=warnings)


def _svg_edges(boxes: Sequence[_Box],
               raw: Sequence[Tuple[Tuple[float, float], Tuple[float, float],
                                   Dict[str, str]]]) -> List[CapEdge]:
    """선의 양 끝을 가까운 상자에 붙여 간선으로. 위에 있는 쪽이 부모."""
    edges: List[CapEdge] = []
    seen: set = set()
    for (x1, y1), (x2, y2), props in raw:
        a = _nearest_box(boxes, x1, y1)
        b = _nearest_box(boxes, x2, y2)
        if a is None or b is None or a == b:
            continue
        src, dst = (a, b) if boxes[a].cy <= boxes[b].cy else (b, a)
        if (src, dst) in seen:
            continue
        seen.add((src, dst))
        style: Dict[str, str] = {}
        if props.get("stroke-dasharray"):
            style["link"] = "dash"
        color = normalize_color(props.get("stroke"))
        if color:
            style["link_color"] = color
        edges.append(CapEdge(src=str(src), dst=str(dst), style=style))
    return edges


def _nearest_box(boxes: Sequence[_Box], x: float, y: float) -> Optional[int]:
    best, best_d = None, None
    for i, b in enumerate(boxes):
        dx = max(b.x - x, 0, x - (b.x + b.w))
        dy = max(b.y - y, 0, y - (b.y + b.h))
        d = dx * dx + dy * dy
        if best_d is None or d < best_d:
            best, best_d = i, d
    tolerance = max((b.h for b in boxes), default=10) * 1.5
    return best if best_d is not None and best_d <= tolerance ** 2 else None


def _rows_to_edges(boxes: Sequence[_Box]) -> List[CapEdge]:
    """연결선이 없을 때: 같은 높이대를 한 단계로 보고 위 단계에서 가장 가까운 상자에 붙인다."""
    if len(boxes) < 2:
        return []
    tol = max(b.h for b in boxes) * 0.6
    rows: List[List[int]] = []
    for i, b in enumerate(boxes):
        if rows and abs(boxes[rows[-1][0]].cy - b.cy) <= tol:
            rows[-1].append(i)
        else:
            rows.append([i])

    edges: List[CapEdge] = []
    for depth in range(1, len(rows)):
        for i in rows[depth]:
            parent = min(rows[depth - 1], key=lambda j: abs(boxes[j].cx - boxes[i].cx))
            edges.append(CapEdge(src=str(parent), dst=str(i)))
    return edges


# ──────────────────────────────────────────────────────────────
# HTML
# ──────────────────────────────────────────────────────────────
_SVG_IN_HTML = re.compile(r"<svg\b.*?</svg>", re.S | re.I)
_MERMAID_IN_HTML = re.compile(
    r'<(?:pre|div)[^>]*class="[^"]*mermaid[^"]*"[^>]*>(.*?)</(?:pre|div)>', re.S | re.I)
_MERMAID_FENCE = re.compile(r"```\s*mermaid\s*\n(.*?)```", re.S | re.I)


def from_html(text: str, title: str = "") -> CaptureResult:
    """HTML(또는 마크다운) 안에 든 SVG·Mermaid를 찾아 읽는다."""
    m = _MERMAID_FENCE.search(text) or _MERMAID_IN_HTML.search(text)
    if m:
        result = from_mermaid(unescape(m.group(1)), title)
        result.source = "html(mermaid)"
        return result
    m = _SVG_IN_HTML.search(text)
    if m:
        result = from_svg(m.group(0), title)
        result.source = "html(svg)"
        return result
    return CaptureResult(spec=DiagramSpec(type="org", title=title, lines=[]), source="html",
                         warnings=["HTML 안에서 <svg>도 mermaid 블록도 찾지 못했다"])


# ──────────────────────────────────────────────────────────────
# 입력 판별
# ──────────────────────────────────────────────────────────────
def capture_text(text: str, kind: str = "auto", title: str = "") -> CaptureResult:
    """문자열을 읽어 도식 spec으로. `kind`는 auto|mermaid|svg|html."""
    kind = (kind or "auto").lower()
    if kind == "auto":
        head = text.lstrip()[:400].lower()
        if head.startswith(("<!doctype html", "<html")) or "<body" in text[:4000].lower():
            kind = "html"
        elif _MERMAID_FENCE.search(text) or _MERMAID_IN_HTML.search(text):
            kind = "html"
        elif "<svg" in text[:4000].lower():
            kind = "svg"
        else:
            kind = "mermaid"
    if kind == "svg":
        return from_svg(text, title)
    if kind == "html":
        return from_html(text, title)
    return from_mermaid(text, title)


def capture(path: str, kind: str = "auto", title: str = "") -> CaptureResult:
    """파일을 읽어 도식 spec으로. 확장자로도 형식을 짐작한다."""
    with open(path, "r", encoding="utf-8") as fh:
        text = fh.read()
    if kind == "auto":
        lower = path.lower()
        if lower.endswith(".svg"):
            kind = "svg"
        elif lower.endswith((".html", ".htm", ".md", ".markdown")):
            kind = "html"
        elif lower.endswith((".mmd", ".mermaid")):
            kind = "mermaid"
    return capture_text(text, kind, title)


# ──────────────────────────────────────────────────────────────
# 직렬화
# ──────────────────────────────────────────────────────────────
def spec_to_text(spec: DiagramSpec) -> str:
    """spec → 본문에 그대로 붙여 넣을 수 있는 `:::diagram` 블록."""
    header = f"type={spec.type}"
    if spec.title:
        header += f' title="{spec.title}"'
    for key, value in spec.options.items():
        header += f" {key}={value}"
    body = "\n".join(spec.lines)
    return f":::diagram {header}\n{body}\n:::"
