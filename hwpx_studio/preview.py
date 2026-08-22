"""HTML 근사 미리보기(python-hwpx layout_preview 래퍼).

근사값이다. 글꼴 실측·줄바꿈·도식 연결선(한 변 테두리)은 재현되지 않으므로
최종 확인은 한글(또는 한글 뷰어)에서 해야 한다.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, List, Optional, Tuple

DISCLAIMER = (
    "근사 미리보기입니다. 글꼴·줄바꿈·도식 연결선은 한글(뷰어)에서 확인하세요."
)


def render_preview(source: Any, out_path: Optional[str] = None,
                   mode: str = "pages") -> Tuple[str, List[str]]:
    """hwpx(경로 또는 바이트) → HTML 문자열. (html, 경고목록)"""
    from hwpx.tools.layout_preview import render_layout_preview

    preview = render_layout_preview(source, mode=mode, title="hwpx-studio 미리보기")
    html = preview.html
    banner = (
        '<div style="padding:8px 12px;margin:8px;border:1px solid #d0d0d0;'
        'background:#fffbe6;font-family:sans-serif;font-size:13px;">'
        f"⚠ {DISCLAIMER}</div>"
    )
    if "<body" in html:
        idx = html.index("<body")
        end = html.index(">", idx) + 1
        html = html[:end] + banner + html[end:]
    else:
        html = banner + html

    warnings = list(getattr(preview, "warnings", []) or [])
    if out_path:
        Path(out_path).write_text(html, encoding="utf-8")
    return html, warnings
