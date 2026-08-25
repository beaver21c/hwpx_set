"""도식 수집(capture) 테스트."""

import re

import pytest

from hwpx_studio.capture import capture, capture_text, spec_to_text
from hwpx_studio.diagram import build_grid, parse_text as parse_diagram
from hwpx_studio.engine import build_document

MERMAID_ORG = """flowchart TD
    A[대표이사] --> B[기획본부]
    A --> C[운영본부]
    A -.-> D[감사실]
    B --> E[기획팀]
    B --> F[예산팀]
    style A fill:#C00000,color:#FFFFFF
    classDef blue fill:#2E75B6,color:#fff
    class B,C blue
"""

SVG_ORG = """<svg xmlns="http://www.w3.org/2000/svg" width="600" height="300">
  <rect x="0" y="0" width="600" height="300" fill="#FFFFFF"/>
  <rect x="230" y="20" width="140" height="40" fill="#C00000" stroke="#000000"/>
  <text x="300" y="45" fill="#FFFFFF">위원회</text>
  <rect x="60" y="140" width="140" height="40" fill="#2E75B6" stroke="#1F3864"/>
  <text x="130" y="165" fill="#FFFFFF">기획분과</text>
  <rect x="400" y="140" width="140" height="40" fill="#FFF2CC" stroke="#BF8F00"/>
  <text x="470" y="165" fill="#000000">자문단</text>
  <line x1="300" y1="60" x2="130" y2="140" stroke="#1F3864"/>
  <path d="M300,60 L470,100 L470,140" stroke="#BF8F00" fill="none" stroke-dasharray="4 3"/>
</svg>"""


def labels(spec):
    return [re.sub(r"\s*\{.*\}$", "", ln).strip() for ln in spec.lines]


def indent_of(spec, name):
    for line in spec.lines:
        if line.strip().startswith(name):
            return len(line) - len(line.lstrip())
    raise AssertionError(f"{name} 없음")


# ──────────────────────────────────────────────────────────────
# Mermaid
# ──────────────────────────────────────────────────────────────
def test_mermaid_builds_the_hierarchy():
    spec = capture_text(MERMAID_ORG).spec
    assert spec.type == "org"
    assert labels(spec) == ["대표이사", "기획본부", "기획팀", "예산팀", "운영본부", "감사실"]
    assert indent_of(spec, "대표이사") == 0
    assert indent_of(spec, "기획본부") == 2
    assert indent_of(spec, "기획팀") == 4


def test_mermaid_carries_style_and_classdef_colors():
    spec = capture_text(MERMAID_ORG).spec
    assert "fill=#C00000" in spec.lines[0] and "color=#FFFFFF" in spec.lines[0]
    blue = [ln for ln in spec.lines if "기획본부" in ln or "운영본부" in ln]
    assert all("fill=#2E75B6" in ln for ln in blue)      # classDef + class 적용


def test_mermaid_dotted_arrow_becomes_a_dashed_link():
    spec = capture_text(MERMAID_ORG).spec
    audit = next(ln for ln in spec.lines if "감사실" in ln)
    assert "link=dash" in audit


def test_mermaid_chain_becomes_a_flow_diagram():
    result = capture_text("graph LR\n  A[접수] --> B[검토] --> C[심의] --> D[통보]")
    assert result.spec.type == "flow"
    assert result.spec.lines == ["접수 → 검토 → 심의 → 통보"]


def test_mermaid_top_down_chain_keeps_the_direction():
    result = capture_text("flowchart TD\n  A[계획] --> B[시행] --> C[평가]")
    assert result.spec.type == "flow"
    assert result.spec.options.get("direction") == "down"


def test_mermaid_extra_incoming_edge_is_reported_not_dropped_silently():
    result = capture_text("flowchart TD\n A[가] --> C[다]\n B[나] --> C\n")
    assert any("연결선이 여러 개" in w for w in result.warnings)
    assert labels(result.spec).count("다") == 1


def test_mermaid_comments_and_quoted_labels():
    result = capture_text('flowchart TD\n %% 주석\n A["따옴표 라벨"] --> B[아래]\n')
    assert labels(result.spec)[0] == "따옴표 라벨"


def test_unreadable_input_reports_instead_of_crashing():
    result = capture_text("이건 도식이 아니라 그냥 문장이다.")
    assert result.spec.lines == [] or result.warnings


# ──────────────────────────────────────────────────────────────
# SVG
# ──────────────────────────────────────────────────────────────
def test_svg_reads_boxes_colors_and_edges():
    result = capture_text(SVG_ORG, title="위원회")
    spec = result.spec
    assert spec.title == "위원회"
    assert labels(spec) == ["위원회", "기획분과", "자문단"]
    assert indent_of(spec, "기획분과") == 2
    assert "fill=#C00000" in spec.lines[0]
    assert "color=#FFFFFF" in spec.lines[0]
    assert "border=#BF8F00" in next(ln for ln in spec.lines if "자문단" in ln)


def test_svg_dasharray_becomes_a_dashed_link():
    spec = capture_text(SVG_ORG).spec
    assert "link=dash" in next(ln for ln in spec.lines if "자문단" in ln)


def test_svg_background_rect_is_not_a_box():
    assert "600" not in " ".join(capture_text(SVG_ORG).spec.lines)
    assert len(capture_text(SVG_ORG).spec.lines) == 3


def test_svg_without_edges_falls_back_to_row_layout():
    svg = """<svg xmlns="http://www.w3.org/2000/svg">
      <rect x="200" y="10" width="100" height="30"/><text x="250" y="25">위</text>
      <rect x="120" y="90" width="100" height="30"/><text x="170" y="105">왼쪽</text>
      <rect x="280" y="90" width="100" height="30"/><text x="330" y="105">오른쪽</text>
    </svg>"""
    result = capture_text(svg)
    assert labels(result.spec) == ["위", "왼쪽", "오른쪽"]
    assert indent_of(result.spec, "왼쪽") == 2
    assert any("높이" in w for w in result.warnings)      # 추정했음을 알린다


def test_broken_svg_is_reported():
    result = capture_text('<svg xmlns="http://www.w3.org/2000/svg"><rect x="1"</svg>')
    assert result.warnings and not result.spec.lines


# ──────────────────────────────────────────────────────────────
# HTML / 자동 판별 / 왕복
# ──────────────────────────────────────────────────────────────
def test_html_with_embedded_svg():
    html = f"<!doctype html><html><body><h1>조직</h1>{SVG_ORG}</body></html>"
    result = capture_text(html)
    assert result.source == "html(svg)"
    assert labels(result.spec)[0] == "위원회"


def test_markdown_mermaid_fence():
    md = f"# 문서\n\n```mermaid\n{MERMAID_ORG}```\n\n본문"
    result = capture_text(md)
    assert result.source == "html(mermaid)"
    assert labels(result.spec)[0] == "대표이사"


def test_file_extension_picks_the_reader(tmp_path):
    path = tmp_path / "a.svg"
    path.write_text(SVG_ORG, encoding="utf-8")
    assert capture(str(path)).source == "svg"


def test_captured_text_round_trips_into_a_diagram(policy):
    """수집 → 텍스트 → 다시 파싱 → 격자까지 그대로 이어져야 한다."""
    result = capture_text(MERMAID_ORG, title="조직")
    spec = parse_diagram(spec_to_text(result.spec))
    assert spec.title == "조직"
    grid = build_grid(spec, policy)
    fills = {c.text: c.fill for c in grid.cells if c.text}
    assert fills["대표이사"] == "#C00000"
    assert fills["기획본부"] == "#2E75B6"
    assert any(c.border_type == "DASH" for c in grid.cells)


def test_captured_diagram_builds_a_document(policy, tmp_path):
    result = capture_text(SVG_ORG, title="위원회")
    out = tmp_path / "cap.hwpx"
    built = build_document(policy, [{"type": "diagram", "spec": result.spec.to_dict()}],
                           str(out))
    assert out.exists() and built.data[:2] == b"PK"


# ──────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────
def test_cli_capture_writes_a_block_and_a_document(tmp_path, capsys):
    from hwpx_studio.cli import main

    src = tmp_path / "d.mmd"
    src.write_text(MERMAID_ORG, encoding="utf-8")
    block, doc = tmp_path / "block.txt", tmp_path / "d.hwpx"
    assert main(["capture", str(src), "-o", str(block), "--hwpx", str(doc),
                 "--title", "조직 체계"]) == 0
    text = block.read_text(encoding="utf-8")
    assert text.startswith(":::diagram type=org title=\"조직 체계\"")
    assert text.rstrip().endswith(":::")
    assert doc.exists()
    assert "상자 6개" in capsys.readouterr().out


def test_cli_capture_reports_failure(tmp_path):
    from hwpx_studio.cli import main

    src = tmp_path / "empty.mmd"
    src.write_text("아무것도 아님", encoding="utf-8")
    assert main(["capture", str(src)]) == 2
