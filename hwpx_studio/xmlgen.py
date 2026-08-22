"""header.xml에 주입할 XML 조각 생성기.

정규식으로 템플릿 header.xml을 패치하는 방식(기존 생성기 v6)을 유지하되,
ID를 인자로 받아 동적 할당이 가능하도록 분리했다.
"""

from __future__ import annotations

from typing import Optional

from .units import pt


def char_pr(
    id_val: int,
    size_pt: float,
    bold: bool = False,
    color: str = "#000000",
    font_id: int = 0,
    border_fill_id: int = 2,
) -> str:
    b = ' bold="1"' if bold else ""
    fid = str(font_id)
    return (
        f'<hh:charPr id="{id_val}" height="{pt(size_pt)}" textColor="{color}" '
        f'shadeColor="none" useFontSpace="0" useKerning="0" symMark="NONE" '
        f'borderFillIDRef="{border_fill_id}"{b}>'
        f'<hh:fontRef hangul="{fid}" latin="{fid}" hanja="{fid}" japanese="{fid}" '
        f'other="{fid}" symbol="{fid}" user="{fid}"/>'
        f'<hh:ratio hangul="100" latin="100" hanja="100" japanese="100" other="100" symbol="100" user="100"/>'
        f'<hh:spacing hangul="0" latin="0" hanja="0" japanese="0" other="0" symbol="0" user="0"/>'
        f'<hh:relSz hangul="100" latin="100" hanja="100" japanese="100" other="100" symbol="100" user="100"/>'
        f'<hh:offset hangul="0" latin="0" hanja="0" japanese="0" other="0" symbol="0" user="0"/>'
        f'<hh:underline type="NONE" shape="SOLID" color="#000000"/>'
        f'<hh:strikeout shape="NONE" color="#000000"/>'
        f'<hh:outline type="NONE"/>'
        f'<hh:shadow type="NONE" color="#C0C0C0" offsetX="10" offsetY="10"/>'
        f"</hh:charPr>"
    )


def para_pr(
    id_val: int,
    left: int = 0,
    indent: int = 0,
    align: str = "JUSTIFY",
    spacing_below: int = 0,
    line_spacing: int = 180,
    border_fill_id: int = 2,
) -> str:
    body = (
        f"<hh:margin>"
        f'<hc:intent value="{indent}" unit="HWPUNIT"/>'
        f'<hc:left value="{left}" unit="HWPUNIT"/>'
        f'<hc:right value="0" unit="HWPUNIT"/>'
        f'<hc:prev value="0" unit="HWPUNIT"/>'
        f'<hc:next value="{spacing_below}" unit="HWPUNIT"/>'
        f"</hh:margin>"
        f'<hh:lineSpacing type="PERCENT" value="{line_spacing}" unit="HWPUNIT"/>'
    )
    return (
        f'<hh:paraPr id="{id_val}" tabPrIDRef="0" condense="0" fontLineHeight="0" '
        f'snapToGrid="1" suppressLineNumbers="0" checked="0" textDir="LTR">'
        f'<hh:align horizontal="{align}" vertical="BASELINE"/>'
        f'<hh:heading type="NONE" idRef="0" level="0"/>'
        f'<hh:breakSetting breakLatinWord="KEEP_WORD" breakNonLatinWord="KEEP_WORD" '
        f'widowOrphan="0" keepWithNext="0" keepLines="0" pageBreakBefore="0" lineWrap="BREAK"/>'
        f'<hh:autoSpacing eAsianEng="0" eAsianNum="0"/>'
        f'<hp:switch><hp:case hp:required-namespace="http://www.hancom.co.kr/hwpml/2016/HwpUnitChar">'
        f"{body}</hp:case><hp:default>{body}</hp:default></hp:switch>"
        f'<hh:border borderFillIDRef="{border_fill_id}" offsetLeft="0" offsetRight="0" '
        f'offsetTop="0" offsetBottom="0" connect="0" ignoreMargin="0"/>'
        f"</hh:paraPr>"
    )


def border_fill(
    id_val: int,
    border_color: str,
    bg_color: Optional[str] = None,
    width: str = "0.12 mm",
) -> str:
    fill = ""
    if bg_color:
        fill = (
            f"<hc:fillBrush><hc:winBrush faceColor=\"{bg_color}\" "
            f'hatchColor="#999999" alpha="0"/></hc:fillBrush>'
        )
    return (
        f'<hh:borderFill id="{id_val}" threeD="0" shadow="0" centerLine="NONE" '
        f'breakCellSeparateLine="0">'
        f'<hh:slash type="NONE" Crooked="0" isCounter="0"/>'
        f'<hh:backSlash type="NONE" Crooked="0" isCounter="0"/>'
        f'<hh:leftBorder type="SOLID" width="{width}" color="{border_color}"/>'
        f'<hh:rightBorder type="SOLID" width="{width}" color="{border_color}"/>'
        f'<hh:topBorder type="SOLID" width="{width}" color="{border_color}"/>'
        f'<hh:bottomBorder type="SOLID" width="{width}" color="{border_color}"/>'
        f'<hh:diagonal type="NONE" width="{width}" color="{border_color}"/>'
        f"{fill}</hh:borderFill>"
    )


def style(
    id_val: int,
    name: str,
    eng_name: str,
    para_pr_id: int,
    char_pr_id: int,
    next_style_id: int,
) -> str:
    return (
        f'<hh:style id="{id_val}" type="PARA" name="{name}" engName="{eng_name}" '
        f'paraPrIDRef="{para_pr_id}" charPrIDRef="{char_pr_id}" '
        f'nextStyleIDRef="{next_style_id}" langID="1042" lockForm="0"/>'
    )
