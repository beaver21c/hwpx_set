"""도식(조직도·체계도·절차도) 생성.

입력은 텍스트 블록이다.

    :::diagram type=org title="조직 체계"
    대표
      기획부
        기획팀
      운영부
    :::

기본 렌더는 표(`render=table`)다. 격자 셀의 한 변 테두리로 연결선을 그리며,
연결선은 상자 칸의 **가운데**(상자를 2개 열에 걸쳐 병합한 경계)에 놓인다.
폭이 `diagram.max_width_mm`를 넘으면 상자 폭을 줄이고, 그래도 넘치면
이미지 렌더로 폴백한다.
"""

from __future__ import annotations

import re
import shlex
import tempfile
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .units import mm

ARROW_RIGHT = "→"
ARROW_DOWN = "▼"
_ARROW_SPLIT = re.compile(r"\s*(?:→|->|=>|▶|>)\s*")

VALID_TYPES = ("org", "flow", "matrix", "strategy", "db")

#: 상자·연결선에 쓸 수 있는 선 종류(OWPML LineType). 짧은 이름 → OWPML 값
LINE_TYPES = {
    "solid": "SOLID", "dash": "DASH", "dot": "DOT",
    "dashdot": "DASH_DOT", "dashdotdot": "DASH_DOT_DOT", "longdash": "LONG_DASH",
}

#: 노드 뒤 `{...}`로 줄 수 있는 속성
NODE_ATTRS = ("fill", "color", "border", "link", "link_color")

_ATTR_BLOCK = re.compile(r"\s*\{([^{}]*)\}\s*$")


def normalize_color(value: Optional[str]) -> Optional[str]:
    """`#abc` `abc` `#AABBCC` → `#AABBCC`. 알 수 없으면 None."""
    if not value:
        return None
    v = value.strip().lstrip("#")
    if len(v) == 3 and all(c in "0123456789abcdefABCDEF" for c in v):
        v = "".join(c * 2 for c in v)
    if len(v) == 6 and all(c in "0123456789abcdefABCDEF" for c in v):
        return "#" + v.upper()
    return None


def normalize_line_type(value: Optional[str]) -> Optional[str]:
    """`dash` `DASH` `점선` → `DASH`. 알 수 없으면 None."""
    if not value:
        return None
    v = value.strip().lower().replace("-", "").replace("_", "")
    if v in ("점선", "파선"):
        v = "dash"
    elif v in ("실선",):
        v = "solid"
    return LINE_TYPES.get(v)


def split_attrs(text: str) -> Tuple[str, Dict[str, str]]:
    """`기획부 {fill=#DCE6F1 color=#000}` → ("기획부", {...}).

    쉼표·공백 어느 쪽으로 구분해도 되고, 값에 따옴표를 써도 된다.
    """
    m = _ATTR_BLOCK.search(text)
    if not m:
        return text.strip(), {}
    body = m.group(1).replace(",", " ")
    attrs: Dict[str, str] = {}
    try:
        tokens = shlex.split(body)
    except ValueError:
        tokens = body.split()
    for token in tokens:
        if "=" not in token:
            continue
        key, _, value = token.partition("=")
        attrs[key.strip().lower()] = value.strip().strip('"').strip("'")
    return text[:m.start()].strip(), attrs


def node_style(attrs: Dict[str, str]) -> Dict[str, Any]:
    """노드 속성 문자열 dict → 정규화된 스타일 dict(빈 값은 넣지 않는다).

    `border=none`은 "테두리를 그리지 말라"는 뜻이라 색과 구분해 남긴다.
    `link=none`도 마찬가지로 "이 단 위로는 연결선을 긋지 말라"는 뜻이다.
    """
    style: Dict[str, Any] = {}
    for key in ("fill", "color", "border", "link_color"):
        raw = (attrs.get(key) or "").strip().lower()
        if key == "border" and raw in ("none", "없음"):
            style["border"] = "none"
            continue
        color = normalize_color(attrs.get(key))
        if color:
            style[key] = color
    raw_link = (attrs.get("link") or "").strip().lower()
    if raw_link in ("none", "없음"):
        style["link"] = "none"
    else:
        line = normalize_line_type(attrs.get("link"))
        if line:
            style["link"] = line
    return style


# ──────────────────────────────────────────────────────────────
# 입력 파싱
# ──────────────────────────────────────────────────────────────
@dataclass
class DiagramSpec:
    type: str = "org"
    title: str = ""
    options: Dict[str, Any] = field(default_factory=dict)
    lines: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {"type": self.type, "title": self.title,
                "options": dict(self.options), "lines": list(self.lines)}


def ensure_spec(spec: Any) -> DiagramSpec:
    if isinstance(spec, DiagramSpec):
        return spec
    if isinstance(spec, dict):
        return DiagramSpec(
            type=spec.get("type", "org"),
            title=spec.get("title", ""),
            options=dict(spec.get("options") or {}),
            lines=list(spec.get("lines") or []),
        )
    raise TypeError(f"도식 spec 형식을 알 수 없음: {type(spec)!r}")


def parse_options(header: str) -> Dict[str, str]:
    """`type=org title="조직 체계" render=image` → dict."""
    out: Dict[str, str] = {}
    try:
        tokens = shlex.split(header)
    except ValueError:
        tokens = header.split()
    for token in tokens:
        if "=" in token:
            key, _, value = token.partition("=")
            out[key.strip()] = value.strip().strip('"').strip("'")
    return out


def parse_block(header: str, lines: Sequence[str]) -> DiagramSpec:
    """`:::diagram` 다음의 헤더 문자열과 블록 본문 줄로 spec을 만든다."""
    opts = parse_options(header)
    dtype = opts.pop("type", "org")
    if dtype not in VALID_TYPES:
        dtype = "org"
    title = opts.pop("title", "")
    body = [ln.rstrip() for ln in lines]
    while body and not body[0].strip():
        body.pop(0)
    while body and not body[-1].strip():
        body.pop()
    return DiagramSpec(type=dtype, title=title, options=opts, lines=body)


def parse_text(text: str) -> DiagramSpec:
    """`:::diagram ...`부터 `:::`까지 통째로 받은 문자열을 spec으로."""
    lines = text.splitlines()
    header = ""
    body: List[str] = []
    for i, line in enumerate(lines):
        if line.strip().startswith(":::"):
            header = line.strip()[3:].strip()
            if header.startswith("diagram"):
                header = header[len("diagram"):].strip()
            body = [ln for ln in lines[i + 1:] if not ln.strip().startswith(":::")]
            break
    else:
        body = lines
    return parse_block(header, body)


# ──────────────────────────────────────────────────────────────
# 트리 파싱(org)
# ──────────────────────────────────────────────────────────────
@dataclass
class Node:
    text: str
    depth: int = 0
    children: List["Node"] = field(default_factory=list)
    center: int = 0
    row: int = 0
    style: Dict[str, Any] = field(default_factory=dict)


def parse_tree(lines: Sequence[str], indent_size: int = 2) -> List[Node]:
    """들여쓰기 트리 → 루트 노드 목록(여러 루트 허용).

    2칸 들여쓰기가 표준이지만, 실제 입력의 들여쓰기 폭이 일정하지 않은 경우를
    대비해 '들여쓰기 값의 등장 순서'로 깊이를 매긴다.
    """
    entries: List[Tuple[int, str, Dict[str, Any]]] = []
    for raw in lines:
        if not raw.strip():
            continue
        expanded = raw.replace("\t", " " * indent_size)
        stripped = expanded.lstrip(" ")
        indent = len(expanded) - len(stripped)
        text = stripped.strip()
        text = re.sub(r"^[-*•]\s+", "", text)  # 마크다운 목록 습관 흡수
        text, attrs = split_attrs(text)
        if text:
            entries.append((indent, text, node_style(attrs)))

    roots: List[Node] = []
    stack: List[Tuple[int, Node]] = []   # (indent, node)
    for indent, text, style in entries:
        node = Node(text=text, style=style)
        while stack and stack[-1][0] >= indent:
            stack.pop()
        if stack:
            parent = stack[-1][1]
            node.depth = parent.depth + 1
            parent.children.append(node)
        else:
            node.depth = 0
            roots.append(node)
        stack.append((indent, node))
    return roots


def _leaves(node: Node) -> int:
    return 1 if not node.children else sum(_leaves(c) for c in node.children)


def _max_depth(nodes: Sequence[Node]) -> int:
    depth = 0
    for n in nodes:
        depth = max(depth, n.depth + 1, _max_depth(n.children))
    return depth


def _walk(nodes: Sequence[Node]):
    for n in nodes:
        yield n
        yield from _walk(n.children)


# ──────────────────────────────────────────────────────────────
# 격자 계획
# ──────────────────────────────────────────────────────────────
@dataclass
class CellPlan:
    row: int
    col: int
    text: str = ""
    borders: Tuple[str, ...] = ()
    fill: Optional[str] = None
    char: str = "diagram"
    col_span: int = 1
    row_span: int = 1
    #: 아래 셋은 프로파일 기본값을 덮어쓰는 값(None이면 프로파일을 따른다)
    text_color: Optional[str] = None
    border_color: Optional[str] = None
    border_type: Optional[str] = None


@dataclass
class GridPlan:
    rows: int
    cols: int
    col_widths_mm: List[float]
    row_heights_mm: List[float]
    cells: List[CellPlan] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    fallback_to_image: bool = False
    title: str = ""
    #: 블록 헤더 옵션까지 반영한 `profile["diagram"]` 사본(렌더가 이것을 쓴다)
    diagram: Dict[str, Any] = field(default_factory=dict)

    @property
    def total_width_mm(self) -> float:
        return sum(self.col_widths_mm)

    @property
    def total_height_mm(self) -> float:
        return sum(self.row_heights_mm)


MIN_BOX_WIDTH_MM = 12.0
#: DB 구성도 상자 폭. 필드 이름에 `(PK)`가 붙어 기본 상자보다 넓다
DB_BOX_WIDTH_MM = 45.0


#: 블록 헤더에서 프로파일 값을 덮어쓸 수 있는 색 항목
BLOCK_COLOR_OPTIONS = ("box_fill", "box_border", "box_color",
                       "root_fill", "root_color", "line_color")


def effective_diagram(spec: DiagramSpec, profile: Dict[str, Any]) -> Dict[str, Any]:
    """블록 헤더 옵션으로 프로파일의 `diagram` 설정을 덮어쓴 사본."""
    dia = dict(profile["diagram"])
    for key in BLOCK_COLOR_OPTIONS:
        color = normalize_color(spec.options.get(key))
        if color:
            dia[key] = color
    line_type = normalize_line_type(spec.options.get("line_style"))
    if line_type:
        dia["line_type"] = line_type
    return dia


def build_grid(spec: DiagramSpec, profile: Dict[str, Any], force: bool = False) -> GridPlan:
    spec = ensure_spec(spec)
    profile = dict(profile, diagram=effective_diagram(spec, profile))
    layout = str(spec.options.get("layout") or "").lower()
    if spec.type == "flow":
        grid = _grid_flow(spec, profile)
    elif spec.type == "matrix":
        grid = _grid_matrix(spec, profile)
    elif spec.type == "strategy":
        grid = _grid_strategy(spec, profile)
    elif spec.type == "db":
        grid = _grid_db(spec, profile)
    elif layout.startswith("side"):
        grid = _grid_org_side(spec, profile)
    else:
        grid = _grid_org(spec, profile)
        if grid.fallback_to_image and not layout:
            # 가로로는 안 들어간다. 이미지로 밀어내기 전에 세로 목록형으로 바꾼다
            side = _grid_org_side(spec, profile)
            side.warnings = [w for w in grid.warnings if "이미지로 폴백" not in w]
            side.warnings.append(
                "가로로 늘어놓기에는 상자가 많아 세로 목록형으로 배치했다"
                "(가로를 원하면 width를 늘리거나 layout=wide)")
            grid = side
    grid.title = spec.title
    grid.diagram = profile["diagram"]

    block_line = profile["diagram"].get("line_type")
    if block_line:
        for cell in grid.cells:
            if not cell.text and not cell.fill and cell.border_type is None:
                cell.border_type = block_line

    max_w = float(spec.options.get("width") or profile["diagram"]["max_width_mm"])
    if force:
        grid.fallback_to_image = False       # 강제 표 렌더(이미지 백엔드 없음 등)
    if grid.total_width_mm > max_w + 0.01 and not force:
        grid.warnings.append(
            f"도식 폭 {grid.total_width_mm:.0f}mm > 최대 {max_w:.0f}mm → 이미지로 폴백"
        )
        grid.fallback_to_image = True
    return grid


def _fit_box_width(n_slots: int, profile: Dict[str, Any], max_w: float,
                   warnings: List[str]) -> Tuple[float, float]:
    """상자 폭·간격을 최대 폭 안에 맞춘다. 반환 (box_w, gap)."""
    dia = profile["diagram"]
    box_w = float(dia["col_width_mm"])
    gap = float(dia["col_gap_mm"])
    total = n_slots * box_w + (n_slots - 1) * gap
    if total <= max_w or n_slots <= 0:
        return box_w, gap
    gap = max(2.0, gap * 0.5)
    box_w = (max_w - (n_slots - 1) * gap) / n_slots
    return box_w, gap


def _grid_org(spec: DiagramSpec, profile: Dict[str, Any]) -> GridPlan:
    """계층형 도식.

    격자는 **균일한 폭의 열**로 만든다. 상자는 짝수 개(`grid_resolution`)의 열을
    병합해 그리므로 병합 구간의 한가운데가 곧 열 경계가 되고, 연결선은 그 경계에
    해당하는 셀의 한 변(오른쪽/위쪽) 테두리로 그린다. 열 폭이 균일하기 때문에
    부모 노드의 중심(자식 중심들의 중간값)이 항상 유효한 열 경계에 떨어진다.
    """
    dia = profile["diagram"]
    warnings: List[str] = []
    roots = parse_tree(spec.lines)
    if not roots:
        return GridPlan(1, 1, [float(dia["col_width_mm"])], [float(dia["row_height_mm"])],
                        warnings=["도식 내용이 비어 있음"])

    box_cols = int(dia.get("grid_resolution", 6) or 6)
    box_cols = max(2, box_cols + (box_cols % 2))        # 짝수 보정
    half = box_cols // 2

    n_leaves = sum(_leaves(r) for r in roots)
    depth = _max_depth(roots)
    max_w = float(spec.options.get("width") or dia["max_width_mm"])
    box_w, gap = _fit_box_width(n_leaves, profile, max_w, warnings)

    unit = box_w / box_cols
    gap_cols = max(2, 2 * max(1, round(gap / (2 * unit))))
    stride = box_cols + gap_cols
    cols = stride * n_leaves - gap_cols

    if cols * unit > max_w:                              # 양자화 뒤 재조정
        unit = max_w / cols
        box_w = unit * box_cols
    too_narrow = box_w < MIN_BOX_WIDTH_MM
    if too_narrow:
        warnings.append(
            f"같은 단계 상자가 {n_leaves}개여서 폭이 {box_w:.1f}mm까지 좁아짐")
    elif abs(box_w - float(dia["col_width_mm"])) > 0.5:
        warnings.append(f"도식 상자 폭을 {box_w:.1f}mm로 자동 축소")

    # 리프 슬롯 배정 → 노드별 중심 열(열 경계) 계산
    slot = {"i": 0}

    def assign(node: Node) -> int:
        if not node.children:
            center = stride * slot["i"] + half - 1
            slot["i"] += 1
        else:
            centers = [assign(c) for c in node.children]
            center = (centers[0] + centers[-1]) // 2
        node.center = center
        return center

    for root in roots:
        assign(root)

    rows = 3 * depth - 2 if depth else 1
    row_h = float(dia["row_height_mm"])
    row_gap = float(dia["row_gap_mm"])
    row_heights: List[float] = []
    for d in range(depth):
        row_heights.append(row_h)
        if d < depth - 1:
            row_heights += [row_gap / 2, row_gap / 2]

    cells: List[CellPlan] = []
    box_borders = ("left", "right", "top", "bottom")
    for node in _walk(roots):
        node.row = 3 * node.depth
        start = max(0, min(node.center - (half - 1), cols - box_cols))
        is_root = node.depth == 0
        cells.append(CellPlan(
            row=node.row, col=start, text=node.text, borders=box_borders,
            fill=node.style.get("fill") or (dia["root_fill"] if is_root else dia["box_fill"]),
            char="diagram_root" if is_root else "diagram",
            col_span=box_cols,
            text_color=node.style.get("color"),
            border_color=node.style.get("border"),
        ))

    # 연결선: 부모 아래 세로선 → 가로 버스 → 자식 위 세로선
    #
    # 자식이 `link=dash` 같은 속성을 가지면 그 자식으로 내려가는 구간(자식 위
    # 세로선 + 바로 앞 버스 칸)에만 적용한다. 한 셀의 여러 변은 같은 선 종류를
    # 공유하므로(hwpx 제약) 구간 단위로 준다.
    for node in _walk(roots):
        if not node.children:
            continue
        row_a = 3 * node.depth + 1
        row_b = row_a + 1
        by_center = {c.center: c for c in node.children}
        centers = sorted(by_center)
        _add_border(cells, row_a, node.center, "right")
        for col in range(centers[0] + 1, centers[-1] + 1):
            child = by_center.get(col)
            _add_border(cells, row_b, col, "top",
                        color=(child.style.get("link_color") if child else None),
                        line_type=(child.style.get("link") if child else None))
        for col in centers:
            child = by_center[col]
            _add_border(cells, row_b, col, "right",
                        color=child.style.get("link_color"),
                        line_type=child.style.get("link"))

    return GridPlan(rows=rows, cols=cols, col_widths_mm=[unit] * cols,
                    row_heights_mm=row_heights, cells=cells, warnings=warnings,
                    fallback_to_image=too_narrow)


@dataclass
class _Band:
    """전략체계도의 한 단(段). 왼쪽 라벨 하나 + 오른쪽 칸 여러 줄."""
    label: str = ""
    label_style: Dict[str, Any] = field(default_factory=dict)
    rows: List[List[Tuple[str, Dict[str, Any]]]] = field(default_factory=list)


def parse_bands(lines: Sequence[str]) -> List[_Band]:
    """`라벨 | 칸 | 칸` 줄들을 단으로 묶는다.

    라벨 자리가 비어 있는 줄(`| 칸 | 칸`)은 **바로 위 단의 다음 줄**이다.
    """
    bands: List[_Band] = []
    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        if re.fullmatch(r"\|[\s:|-]+\|?", line):        # 마크다운 구분선은 버린다
            continue
        parts = [p.strip() for p in line.split("|")]
        while len(parts) > 1 and not parts[-1]:         # 마크다운식 끝 `|`
            parts.pop()
        head, cells = parts[0], parts[1:]
        if not cells:                                   # 구분자 없는 한 칸짜리 줄
            head, cells = "", [parts[0]]
        row = [(text, node_style(attrs))
               for text, attrs in (split_attrs(c) for c in cells) if text]
        if not row:
            continue
        if head:
            label, attrs = split_attrs(head)
            bands.append(_Band(label=label, label_style=node_style(attrs), rows=[row]))
        elif bands:
            bands[-1].rows.append(row)                  # 이어지는 줄
        else:
            bands.append(_Band(rows=[row]))
    return bands


def _grid_strategy(spec: DiagramSpec, profile: Dict[str, Any]) -> GridPlan:
    """전략체계도(미션·비전·핵심가치·전략방향·전략과제 …).

    공공기관 경영전략 체계도에서 흔한 모양이다. 왼쪽에 단 이름, 오른쪽에 그 단의
    칸들이 늘어서고, 단 사이를 연결선이 잇는다.

    열은 org와 같은 요령으로 **균일한 폭의 잔 열**로 쪼갠다(칸 하나 =
    `grid_resolution`개). 그래야 병합 구간의 한가운데가 열 경계가 되어 세로선이
    칸 정중앙에 놓인다. 단 사이에는 절반짜리 행 두 개를 넣어, 가로 버스를 아래
    행의 위쪽 변에 그리면 위에서 내려온 세로선과 정확히 맞물린다.
    """
    dia = profile["diagram"]
    warnings: List[str] = []
    bands = parse_bands(spec.lines)
    if not bands:
        return GridPlan(1, 1, [float(dia["col_width_mm"])], [float(dia["row_height_mm"])],
                        warnings=["도식 내용이 비어 있음"])

    n_cols = max((len(row) for band in bands for row in band.rows), default=1)
    has_label = any(band.label for band in bands)

    box_cols = int(dia.get("grid_resolution", 6) or 6)
    box_cols = max(2, box_cols + (box_cols % 2))
    half = box_cols // 2

    max_w = float(spec.options.get("width") or dia["max_width_mm"])
    label_w = float(spec.options.get("label_width") or 22) if has_label else 0.0
    box_w, gap = _fit_box_width(n_cols, profile, max_w - label_w, warnings)
    unit = box_w / box_cols
    gap_cols = max(2, 2 * max(1, round(gap / (2 * unit))))
    stride = box_cols + gap_cols
    content_cols = stride * n_cols - gap_cols
    if content_cols * unit > max_w - label_w:
        unit = (max_w - label_w) / content_cols
        box_w = unit * box_cols
    if box_w < MIN_BOX_WIDTH_MM:
        warnings.append(f"한 단에 칸이 {n_cols}개여서 폭이 {box_w:.1f}mm까지 좁아짐")

    offset = 1 if has_label else 0
    col_widths = ([label_w] if has_label else []) + [unit] * content_cols

    def centre(index: int, span: int = 1) -> int:
        """`index`번 칸(span개를 병합했다면 그 전체)의 중심 열."""
        first = offset + stride * index + half - 1
        last = offset + stride * (index + span - 1) + half - 1
        return (first + last) // 2

    row_h = float(dia["row_height_mm"])
    row_gap = float(dia["row_gap_mm"])
    inner_gap = max(1.0, row_gap / 3)

    cells: List[CellPlan] = []
    row_heights: List[float] = []
    band_rows: List[List[int]] = []                     # 단마다 자기 칸이 놓인 행 번호

    for b, band in enumerate(bands):
        if b:                                           # 단 사이: 절반짜리 두 행
            no_link = band.label_style.get("link") == "none"
            if no_link:
                row_heights.append(inner_gap)
            else:
                row_heights += [row_gap / 2, row_gap / 2]
        rows_here: List[int] = []
        for r, row in enumerate(band.rows):
            if r:
                row_heights.append(inner_gap)
            rows_here.append(len(row_heights))
            row_heights.append(row_h)
        band_rows.append(rows_here)

        for r, row in enumerate(band.rows):
            each = max(1, n_cols // len(row))            # 칸이 적으면 넓게 편다
            for i, (text, style) in enumerate(row):
                start = offset + stride * (i * each)
                width = box_cols + stride * (each - 1)
                plain = style.get("border") == "none"   # 테두리 없는 글자 칸
                borders = () if plain else ("left", "right", "top", "bottom")
                cells.append(CellPlan(
                    row=rows_here[r], col=start, text=text, borders=borders,
                    fill=style.get("fill") or (None if plain else dia["box_fill"]),
                    col_span=min(width, len(col_widths) - start),
                    text_color=style.get("color"),
                    border_color=(None if style.get("border") == "none"
                                  else style.get("border")),
                ))

        if has_label and band.label:
            first, last = rows_here[0], rows_here[-1]
            style = band.label_style
            cells.append(CellPlan(
                row=first, col=0, text=band.label,
                borders=() if style.get("border") == "none" else
                ("left", "right", "top", "bottom"),
                fill=style.get("fill") or dia["root_fill"],
                char="diagram_root",
                row_span=last - first + 1,
                text_color=style.get("color"),
                border_color=(None if style.get("border") == "none"
                              else style.get("border")),
            ))

    # 단 사이 연결선
    for b in range(1, len(bands)):
        upper, lower = bands[b - 1], bands[b]
        if lower.label_style.get("link") == "none":
            continue
        row_b = band_rows[b][0] - 1                     # 아래 절반 행
        row_a = row_b - 1
        line_type = lower.label_style.get("link")
        line_type = None if line_type in (None, "none") else line_type
        colour = lower.label_style.get("link_color")

        top_row, bottom_row = upper.rows[-1], lower.rows[0]
        each_t = max(1, n_cols // len(top_row))
        each_b = max(1, n_cols // len(bottom_row))
        tops = [centre(i * each_t, each_t) for i in range(len(top_row))]
        bottoms = [centre(i * each_b, each_b) for i in range(len(bottom_row))]

        for col in tops:
            _add_border(cells, row_a, col, "right", colour, line_type)
        if set(tops) != set(bottoms):                   # 갈래가 다를 때만 가로 버스
            spread = sorted(set(tops) | set(bottoms))
            for col in range(spread[0] + 1, spread[-1] + 1):
                _add_border(cells, row_b, col, "top", colour, line_type)
        for col in bottoms:
            _add_border(cells, row_b, col, "right", colour, line_type)

    return GridPlan(rows=len(row_heights), cols=len(col_widths),
                    col_widths_mm=col_widths, row_heights_mm=row_heights,
                    cells=cells, warnings=warnings)


def _grid_org_side(spec: DiagramSpec, profile: Dict[str, Any]) -> GridPlan:
    """세로 목록형 계층도.

    가로로 늘어놓으면 넘치는 조직도(실·국이 여럿인 경우)를 위한 배치다. 상자를
    한 줄에 하나씩 세로로 쌓고, 단계가 내려갈수록 오른쪽으로 들여쓴다. 상자 수가
    늘어도 **폭이 넓어지지 않는다**.

    행·열 모델은 같은 요령이다.

    * 노드마다 **두 행**(위·아래 절반)을 쓰고 상자를 두 행에 걸쳐 병합한다.
      두 행의 경계가 곧 상자의 세로 중심이라, 가로 이음선을 그 경계(아래 절반
      셀의 위쪽 변)에 그리면 상자 한가운데로 들어간다.
    * 단계마다 **두 열**(세로선 자리 + 이음선 자리)을 둔다. 부모의 세로선은 첫
      열의 오른쪽 변이라 부모 상자 안쪽에서 내려오고, 자식 상자는 두 열 뒤에서
      시작하므로 그 사이가 가로 이음선이 된다.
    """
    dia = profile["diagram"]
    warnings: List[str] = []
    roots = parse_tree(spec.lines)
    if not roots:
        return GridPlan(1, 1, [float(dia["col_width_mm"])], [float(dia["row_height_mm"])],
                        warnings=["도식 내용이 비어 있음"])

    nodes = list(_walk(roots))
    depth = _max_depth(roots)
    max_w = float(spec.options.get("width") or dia["max_width_mm"])

    step = max(4.0, float(dia["col_gap_mm"]))          # 한 단계 들여쓰기 폭
    spine_w = stub_w = step / 2
    box_w = float(dia["col_width_mm"]) * 2
    if step * (depth - 1) + box_w > max_w:
        box_w = max(MIN_BOX_WIDTH_MM, max_w - step * (depth - 1))
        warnings.append(f"세로 목록형: 상자 폭을 {box_w:.1f}mm로 맞춤")
    col_widths = [spine_w, stub_w] * (depth - 1) + [box_w]
    last_col = len(col_widths) - 1

    row_h = float(dia["row_height_mm"]) / 2
    gap_h = max(1.0, float(dia["row_gap_mm"]) / 3)
    cells: List[CellPlan] = []
    row_heights: List[float] = []
    row_of: Dict[int, int] = {}                        # id(node) → 위 절반 행

    for i, node in enumerate(nodes):
        if i:                                          # 상자 사이 간격 행
            row_heights.append(gap_h)
        top = len(row_heights)
        row_of[id(node)] = top
        row_heights += [row_h, row_h]
        col = min(2 * node.depth, last_col)
        is_root = node.depth == 0
        cells.append(CellPlan(
            row=top, col=col, text=node.text,
            borders=("left", "right", "top", "bottom"),
            fill=node.style.get("fill") or (dia["root_fill"] if is_root else dia["box_fill"]),
            char="diagram_root" if is_root else "diagram",
            col_span=last_col - col + 1, row_span=2,
            text_color=node.style.get("color"),
            border_color=node.style.get("border"),
        ))

    # 연결선: 부모 상자 안쪽에서 내려오는 세로선 + 자식마다 가로 이음선
    for node in nodes:
        if not node.children:
            continue
        spine = min(2 * node.depth, last_col)
        if spine >= last_col:                          # 더 들여쓸 열이 없다
            continue
        last = node.children[-1]
        for row in range(row_of[id(node)] + 2, row_of[id(last)] + 1):
            _add_border(cells, row, spine, "right")
        for child in node.children:                # 세로선과 자식 상자 사이 한 칸
            _add_border(cells, row_of[id(child)] + 1, spine + 1, "top",
                        color=child.style.get("link_color"),
                        line_type=child.style.get("link"))

    return GridPlan(rows=len(row_heights), cols=len(col_widths),
                    col_widths_mm=col_widths, row_heights_mm=row_heights,
                    cells=cells, warnings=warnings)


def _add_border(cells: List[CellPlan], row: int, col: int, edge: str,
                color: Optional[str] = None, line_type: Optional[str] = None) -> None:
    for cell in cells:
        if cell.row == row and cell.col == col:
            if edge not in cell.borders:
                cell.borders = tuple(sorted(set(cell.borders) | {edge}))
            cell.border_color = color or cell.border_color
            cell.border_type = line_type or cell.border_type
            return
    cells.append(CellPlan(row=row, col=col, borders=(edge,),
                          border_color=color, border_type=line_type))


def _grid_flow(spec: DiagramSpec, profile: Dict[str, Any]) -> GridPlan:
    dia = profile["diagram"]
    warnings: List[str] = []
    steps: List[Tuple[str, Dict[str, Any]]] = []
    for line in spec.lines:
        if not line.strip():
            continue
        for part in _ARROW_SPLIT.split(line.strip()):
            if not part.strip():
                continue
            text, attrs = split_attrs(part.strip())
            if text:
                steps.append((text, node_style(attrs)))
    if not steps:
        return GridPlan(1, 1, [float(dia["col_width_mm"])], [float(dia["row_height_mm"])],
                        warnings=["도식 내용이 비어 있음"])

    direction = (spec.options.get("direction") or "right").lower()
    box_borders = ("left", "right", "top", "bottom")
    row_h = float(dia["row_height_mm"])
    cells: List[CellPlan] = []

    if direction.startswith("d"):  # down
        rows = 2 * len(steps) - 1
        max_w = float(spec.options.get("width") or dia["max_width_mm"])
        box_w = min(float(dia["col_width_mm"]) * 2, max_w)
        for i, (text, style) in enumerate(steps):
            cells.append(CellPlan(row=2 * i, col=0, text=text,
                                  borders=box_borders,
                                  fill=style.get("fill") or dia["box_fill"],
                                  text_color=style.get("color"),
                                  border_color=style.get("border")))
            if i < len(steps) - 1:
                cells.append(CellPlan(row=2 * i + 1, col=0, text=ARROW_DOWN))
        heights = []
        for i in range(rows):
            heights.append(row_h if i % 2 == 0 else float(dia["row_gap_mm"]))
        return GridPlan(rows=rows, cols=1, col_widths_mm=[box_w],
                        row_heights_mm=heights, cells=cells, warnings=warnings)

    n = len(steps)
    cols = 2 * n - 1
    max_w = float(spec.options.get("width") or dia["max_width_mm"])
    arrow_w = max(4.0, float(dia["col_gap_mm"]))
    box_w = float(dia["col_width_mm"])
    if n * box_w + (n - 1) * arrow_w > max_w:
        box_w = max(MIN_BOX_WIDTH_MM, (max_w - (n - 1) * arrow_w) / n)
        warnings.append(f"절차도 상자 폭을 {box_w:.1f}mm로 자동 축소")
    widths: List[float] = []
    for i, (text, style) in enumerate(steps):
        cells.append(CellPlan(row=0, col=2 * i, text=text,
                              borders=box_borders,
                              fill=style.get("fill") or dia["box_fill"],
                              text_color=style.get("color"),
                              border_color=style.get("border")))
        widths.append(box_w)
        if i < n - 1:
            cells.append(CellPlan(row=0, col=2 * i + 1, text=ARROW_RIGHT))
            widths.append(arrow_w)
    return GridPlan(rows=1, cols=cols, col_widths_mm=widths,
                    row_heights_mm=[row_h], cells=cells, warnings=warnings)


#: DB 구성도 — 필드 앞에 붙여 열쇠를 표시하는 글자
DB_KEY_MARKS = {"*": "PK", "+": "FK"}

_DB_ENTITY = re.compile(r"^\[(.+?)\]\s*(\{.*\})?$")


def parse_db(lines: Sequence[str]) -> Tuple[List[Dict[str, Any]], List[Tuple[str, str]], List[str]]:
    """DB 구성도 본문을 (테이블 목록, 관계 목록, 경고)로 나눈다.

    테이블은 `[이름]`으로 열고, 그 아래 들여쓴 줄이 필드다. 화살표가 든 줄은
    관계로 본다. 필드 앞의 `*`는 기본키, `+`는 외래키다.
    """
    tables: List[Dict[str, Any]] = []
    links: List[Tuple[str, str]] = []
    warnings: List[str] = []
    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        if _ARROW_SPLIT.search(line):
            parts = [p.strip() for p in _ARROW_SPLIT.split(line) if p.strip()]
            for a, b in zip(parts, parts[1:]):
                links.append((a, b))
            continue
        m = _DB_ENTITY.match(line)
        if m:
            name, attrs = split_attrs(f"{m.group(1)} {m.group(2) or ''}".strip())
            tables.append({"name": name, "style": node_style(attrs), "fields": []})
            continue
        if not tables:
            warnings.append(f"테이블([이름]) 앞에 적힌 줄은 건너뛴다: {line}")
            continue
        text, attrs = split_attrs(line)
        mark = DB_KEY_MARKS.get(text[:1], "")
        if mark:
            text = text[1:].strip()
        tables[-1]["fields"].append({"text": text, "key": mark,
                                     "style": node_style(attrs)})
    return tables, links, warnings


def _grid_db(spec: DiagramSpec, profile: Dict[str, Any]) -> GridPlan:
    """DB 구성도 — 테이블 상자를 나란히 놓고 사이를 화살표로 잇는다.

    상자 하나가 한 열이다. 맨 윗 칸이 테이블 이름, 그 아래가 필드다. 관계는
    **붙어 있는 두 테이블 사이**에만 화살표로 그린다. 떨어져 있으면 그리지
    못했다고 알린다(순서를 바꾸면 그려진다).
    """
    dia = profile["diagram"]
    tables, links, warnings = parse_db(spec.lines)
    if not tables:
        return GridPlan(1, 1, [float(dia["col_width_mm"])], [float(dia["row_height_mm"])],
                        warnings=["도식 내용이 비어 있음"])

    n = len(tables)
    depth = max(len(t["fields"]) for t in tables)
    rows = 1 + depth
    cols = 2 * n - 1

    max_w = float(spec.options.get("width") or dia["max_width_mm"])
    arrow_w = max(4.0, float(dia["col_gap_mm"]))
    box_w = min(DB_BOX_WIDTH_MM, (max_w - (n - 1) * arrow_w) / n)
    if box_w < MIN_BOX_WIDTH_MM:
        box_w = MIN_BOX_WIDTH_MM
        warnings.append(f"테이블이 {n}개라 폭이 모자란다. width를 늘리거나 나눠 그리라")

    box_borders = ("left", "right", "top", "bottom")
    row_h = float(dia["row_height_mm"])
    cells: List[CellPlan] = []
    widths: List[float] = []

    for i, table in enumerate(tables):
        col = 2 * i
        style = table["style"]
        cells.append(CellPlan(row=0, col=col, text=table["name"], borders=box_borders,
                              fill=style.get("fill") or dia["root_fill"],
                              text_color=style.get("color") or dia["root_color"],
                              border_color=style.get("border")))
        for r, fld in enumerate(table["fields"], start=1):
            fstyle = fld["style"]
            text = f'{fld["text"]} ({fld["key"]})' if fld["key"] else fld["text"]
            cells.append(CellPlan(row=r, col=col, text=text, borders=box_borders,
                                  fill=fstyle.get("fill") or (
                                      dia["box_fill"] if fld["key"] else None),
                                  text_color=fstyle.get("color"),
                                  border_color=fstyle.get("border")))
        widths.append(box_w)
        if i < n - 1:
            widths.append(arrow_w)

    index = {t["name"]: i for i, t in enumerate(tables)}
    for a, b in links:
        if a not in index or b not in index:
            warnings.append(f"관계 `{a} → {b}`에 없는 테이블 이름이 있다")
            continue
        left, right = index[a], index[b]
        if abs(left - right) != 1:
            warnings.append(
                f"관계 `{a} → {b}`는 두 테이블이 붙어 있지 않아 화살표를 못 그렸다"
                " (테이블 순서를 바꾸면 그려진다)")
            continue
        arrow = ARROW_RIGHT if left < right else "←"
        cells.append(CellPlan(row=0, col=2 * min(left, right) + 1, text=arrow))

    return GridPlan(rows=rows, cols=cols, col_widths_mm=widths,
                    row_heights_mm=[row_h] * rows, cells=cells, warnings=warnings)


def _grid_matrix(spec: DiagramSpec, profile: Dict[str, Any]) -> GridPlan:
    dia = profile["diagram"]
    warnings: List[str] = []
    table: List[List[Tuple[str, Dict[str, str]]]] = []
    for line in spec.lines:
        s = line.strip()
        if not s.startswith("|"):
            continue
        if re.fullmatch(r"\|[\s:|-]+\|", s):
            continue
        parts = [split_attrs(p.strip()) for p in s.strip("|").split("|")]
        table.append(parts)
    if not table:
        return GridPlan(1, 1, [float(dia["col_width_mm"])], [float(dia["row_height_mm"])],
                        warnings=["도식 내용이 비어 있음"])

    cols = max(len(r) for r in table)
    rows = len(table)
    max_w = float(spec.options.get("width") or dia["max_width_mm"])
    col_w = min(float(dia["col_width_mm"]), max_w / cols)
    box_borders = ("left", "right", "top", "bottom")

    cells: List[CellPlan] = []
    for r, row in enumerate(table):
        for c in range(cols):
            text, attrs = row[c] if c < len(row) else ("", {})
            style = node_style(attrs)
            is_head = r == 0 or c == 0
            cells.append(CellPlan(
                row=r, col=c, text=text, borders=box_borders,
                fill=style.get("fill") or (
                    dia["root_fill"] if (r == 0 and c == 0 and not text)
                    else (dia["box_fill"] if is_head else None)),
                text_color=style.get("color"),
                border_color=style.get("border"),
            ))
    return GridPlan(rows=rows, cols=cols, col_widths_mm=[col_w] * cols,
                    row_heights_mm=[float(dia["row_height_mm"])] * rows,
                    cells=cells, warnings=warnings)


# ──────────────────────────────────────────────────────────────
# 문서에 표로 삽입
# ──────────────────────────────────────────────────────────────
def emit_grid(doc, sec, grid: GridPlan, profile: Dict[str, Any], ids,
              table_plans: List[Dict[str, Any]]) -> None:
    """GridPlan을 실제 hwpx 표로 만든다(엔진에서 호출)."""
    dia = grid.diagram or profile["diagram"]
    width_hu = mm(grid.total_width_mm)
    tbl = doc.add_table(grid.rows, grid.cols, section=sec, width=width_hu)

    ensure_border_fill = getattr(getattr(doc, "styles", None), "ensure_border_fill",
                                 None) or doc.ensure_border_fill
    blank_bf = ensure_border_fill(active_borders=[])
    line_w = f'{float(dia["line_width_mm"])} mm'
    bf_cache: Dict[Tuple[Any, ...], str] = {}

    def border_fill_for(cell: CellPlan) -> str:
        color = cell.border_color or (
            dia["box_border"] if cell.fill else dia["line_color"])
        line_type = cell.border_type or dia.get("line_type") or "SOLID"
        key = (tuple(cell.borders), cell.fill, color, line_type)
        if key not in bf_cache:
            if not cell.borders and not cell.fill:
                bf_cache[key] = blank_bf
            else:
                bf_cache[key] = ensure_border_fill(
                    border_color=color,
                    border_width=line_w,
                    fill_color=cell.fill,
                    active_borders=list(cell.borders),
                    border_type=line_type,
                )
        return bf_cache[key]

    # 전 셀을 투명으로 초기화한 뒤 계획된 셀만 덮어쓴다
    for r in range(grid.rows):
        for c in range(grid.cols):
            tbl.set_cell_border_fill(r, c, blank_bf)

    plan_cells: Dict[Tuple[int, int], Dict[str, Any]] = {}
    for r in range(grid.rows):
        for c in range(grid.cols):
            plan_cells[(r, c)] = {
                "width": mm(grid.col_widths_mm[c]),
                "height": mm(grid.row_heights_mm[r]),
                "char": "diagram",
            }

    for cell in grid.cells:
        tbl.set_cell_border_fill(cell.row, cell.col, border_fill_for(cell))
        if cell.text:
            tbl.set_cell_text(cell.row, cell.col, cell.text)
        span_w = sum(grid.col_widths_mm[cell.col:cell.col + cell.col_span])
        span_h = sum(grid.row_heights_mm[cell.row:cell.row + cell.row_span])
        plan_cells[(cell.row, cell.col)] = {
            "width": mm(span_w), "height": mm(span_h),
            "char": text_char_key(cell, ids),
        }

    # 상자(2열 병합)는 테두리·글자 설정 뒤에 병합한다
    for cell in grid.cells:
        if cell.col_span > 1 or cell.row_span > 1:
            tbl.merge_cells(cell.row, cell.col,
                            cell.row + cell.row_span - 1, cell.col + cell.col_span - 1)

    table_plans.append({
        "kind": "diagram",
        "cells": plan_cells,
        "width": width_hu,
        "height": mm(grid.total_height_mm),
        # 표 자체의 테두리는 없애야 한다. python-hwpx가 넣는 기본값은 검은 실선
        # 사각형이라, 그대로 두면 도식 전체를 검은 상자가 감싼다.
        "blank_border_fill": blank_bf,
    })

    if grid.title:
        doc.add_paragraph(grid.title, section=sec,
                          style_id_ref=ids.styles["table_mid"],
                          char_pr_id_ref=ids.chars["table_mid"],
                          para_pr_id_ref=ids.paras["table_mid"])


def text_style_key(color: str) -> str:
    """글자색 → 엔진이 charPr을 등록할 때 쓰는 key."""
    return f"dia:{color}"


def text_char_key(cell: CellPlan, ids) -> str:
    """셀에 쓸 charPr key. 색 지정이 있고 등록돼 있으면 그쪽을 쓴다."""
    if cell.text_color:
        key = text_style_key(cell.text_color)
        if key in getattr(ids, "chars", {}):
            return key
    return cell.char


def collect_text_colors(spec: Any, profile: Dict[str, Any]) -> List[str]:
    """도식 spec에서 쓰인 글자색 목록(중복 제거). 엔진이 charPr을 미리 만든다."""
    grid = build_grid(ensure_spec(spec), profile, force=True)
    seen: List[str] = []
    for cell in grid.cells:
        if cell.text_color and cell.text_color not in seen:
            seen.append(cell.text_color)
    return seen


# ──────────────────────────────────────────────────────────────
# 이미지 렌더(폴백)
# ──────────────────────────────────────────────────────────────
#: 이미지 렌더에 쓸 한글 글꼴 후보(설치된 첫 번째를 사용)
KOREAN_FONT_CANDIDATES = [
    "Noto Sans CJK KR", "Noto Sans KR", "NanumGothic", "NanumBarunGothic",
    "Malgun Gothic", "AppleGothic", "UnDotum", "Baekmuk Gulim",
]


def _apply_korean_font(matplotlib, warnings: Optional[List[str]] = None) -> None:
    """설치된 한글 글꼴을 찾아 matplotlib 기본 글꼴로 지정."""
    try:
        from matplotlib import font_manager
        available = {f.name for f in font_manager.fontManager.ttflist}
    except Exception:
        available = set()
    for name in KOREAN_FONT_CANDIDATES:
        if name in available:
            matplotlib.rcParams["font.family"] = name
            matplotlib.rcParams["axes.unicode_minus"] = False
            return
    if warnings is not None:
        warnings.append(
            "이미지 도식: 한글 글꼴을 찾지 못해 글자가 깨질 수 있음 "
            "(예: apt install fonts-nanum 또는 pip install koreanize-matplotlib)"
        )


def render_png(spec: DiagramSpec, profile: Dict[str, Any],
               path: Optional[str] = None,
               warnings: Optional[List[str]] = None) -> Optional[str]:
    """matplotlib으로 PNG를 그린다. 사용 불가하면 None."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.patches import Rectangle
    except Exception:
        return None

    _apply_korean_font(matplotlib, warnings)

    spec = ensure_spec(spec)
    grid = build_grid(spec, profile, force=True)
    dia = grid.diagram or profile["diagram"]

    width_in = max(grid.total_width_mm, 40) / 25.4
    height_in = max(grid.total_height_mm, 20) / 25.4
    fig, ax = plt.subplots(figsize=(width_in, height_in), dpi=200)
    ax.set_xlim(0, grid.total_width_mm)
    ax.set_ylim(0, grid.total_height_mm)
    ax.invert_yaxis()
    ax.axis("off")

    x_edges = [0.0]
    for w in grid.col_widths_mm:
        x_edges.append(x_edges[-1] + w)
    y_edges = [0.0]
    for h in grid.row_heights_mm:
        y_edges.append(y_edges[-1] + h)

    font_pt = float(dia["font_size_pt"])
    for cell in grid.cells:
        x0 = x_edges[cell.col]
        x1 = x_edges[min(cell.col + cell.col_span, len(grid.col_widths_mm))]
        y0 = y_edges[cell.row]
        y1 = y_edges[min(cell.row + cell.row_span, len(grid.row_heights_mm))]
        if cell.fill or set(cell.borders) == {"left", "right", "top", "bottom"}:
            ax.add_patch(Rectangle(
                (x0, y0), x1 - x0, y1 - y0,
                facecolor=cell.fill or "none",
                edgecolor=cell.border_color or dia["box_border"],
                linewidth=0.8, zorder=2))
        else:
            dash = (0, (3, 2)) if (cell.border_type or "").startswith("DASH") else "-"
            line_color = cell.border_color or dia["line_color"]
            for edge in cell.borders:
                if edge == "right":
                    ax.plot([x1, x1], [y0, y1], color=line_color, lw=0.8,
                            linestyle=dash, zorder=1)
                elif edge == "left":
                    ax.plot([x0, x0], [y0, y1], color=line_color, lw=0.8,
                            linestyle=dash, zorder=1)
                elif edge == "top":
                    ax.plot([x0, x1], [y0, y0], color=line_color, lw=0.8,
                            linestyle=dash, zorder=1)
                elif edge == "bottom":
                    ax.plot([x0, x1], [y1, y1], color=line_color, lw=0.8,
                            linestyle=dash, zorder=1)
        if cell.text:
            color = cell.text_color or (
                dia["root_color"] if cell.char == "diagram_root"
                else dia.get("box_color", "#000000"))
            ax.text((x0 + x1) / 2, (y0 + y1) / 2, cell.text, ha="center", va="center",
                    fontsize=font_pt * 0.8, color=color, zorder=3)

    if path is None:
        tmp = tempfile.NamedTemporaryFile(prefix="hwpx_diagram_", suffix=".png", delete=False)
        path = tmp.name
        tmp.close()
    fig.savefig(path, bbox_inches="tight", pad_inches=0.05, transparent=False)
    plt.close(fig)
    return path
