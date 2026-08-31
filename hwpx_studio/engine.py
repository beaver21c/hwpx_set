"""프로파일 구동형 hwpx 생성 엔진.

기존 hwpx_generator.py v6의 동작 원리(템플릿 header.xml 정규식 패치 →
python-hwpx로 문단·표 추가 → section0.xml 후처리)를 유지하되,

* 모든 설정값을 전역이 아닌 ``profile`` 인자로 받고,
* charPr/paraPr/style/borderFill ID를 템플릿의 itemCnt에서 읽어 동적 할당하며,
* 레벨 개수·순서를 가변으로 처리한다.
"""

from __future__ import annotations

import os
import random
import re
import struct
import warnings
import zipfile
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

warnings.filterwarnings("ignore")

from hwpx.document import HwpxDocument  # noqa: E402
from hwpx.templates import blank_document_bytes  # noqa: E402

from . import diagram as diagram_mod  # noqa: E402
from .profile import level_by_key, merge_profile, validate_profile  # noqa: E402
from .units import mm, pt  # noqa: E402
from .xmlgen import border_fill, char_pr, para_pr, style  # noqa: E402

ROMAN = ["Ⅰ", "Ⅱ", "Ⅲ", "Ⅳ", "Ⅴ", "Ⅵ", "Ⅶ", "Ⅷ", "Ⅸ", "Ⅹ",
         "Ⅺ", "Ⅻ", "XIII", "XIV", "XV", "XVI", "XVII", "XVIII", "XIX", "XX"]
HANGUL = list("가나다라마바사아자차카타파하")
CIRCLED = list("①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮")

FONT_ID_BOLD = 0
FONT_ID_LIGHT = 1


def _font_id(font_key: str) -> int:
    return FONT_ID_BOLD if font_key == "bold" else FONT_ID_LIGHT


# ──────────────────────────────────────────────────────────────
# 콘텐츠 정규화
# ──────────────────────────────────────────────────────────────
def normalize_contents(items: Sequence[Any], profile: Dict[str, Any]) -> List[Dict[str, Any]]:
    """레거시 튜플·dict 혼재 입력을 내부 표준 dict 항목으로 변환."""
    keys = [lv["key"] for lv in profile.get("levels", [])]
    out: List[Dict[str, Any]] = []
    for item in items:
        if isinstance(item, dict):
            out.append(dict(item))
            continue
        if not isinstance(item, (tuple, list)):
            out.append({"type": "para", "key": "body", "text": str(item)})
            continue

        head, rest = item[0], item[1:]
        payload = rest[0] if len(rest) == 1 else rest
        if head == 0 or head == "blank":
            out.append({"type": "blank"})
        elif head == "table":
            rows, cols, data = payload
            out.append({"type": "table", "rows": rows, "cols": cols, "data": list(data)})
        elif head == "image":
            out.append({"type": "image", "path": payload})
        elif head == "diagram":
            out.append({"type": "diagram", "spec": payload})
        elif head == "para":
            out.append({"type": "para", "key": rest[0], "text": rest[1]})
        elif isinstance(head, int):
            key = f"L{head}"
            out.append({"type": "para", "key": key if key in keys else "body",
                        "text": str(payload)})
        else:
            key = str(head)
            out.append({"type": "para", "key": key if key in keys else "body",
                        "text": str(payload)})
    return out


# ──────────────────────────────────────────────────────────────
# ID 계획
# ──────────────────────────────────────────────────────────────
@dataclass
class IdMap:
    """레벨 key → (styleID, charPrID, paraPrID) 및 부속 ID 모음."""

    styles: Dict[str, int] = field(default_factory=dict)
    chars: Dict[str, int] = field(default_factory=dict)
    paras: Dict[str, int] = field(default_factory=dict)
    border_base: int = 3
    border_header: int = 4
    signature_char: Optional[int] = None

    def style_to_para(self) -> Dict[int, int]:
        return {self.styles[k]: self.paras[k] for k in self.styles if k in self.paras}

    def refs(self, key: str) -> Tuple[int, int, int]:
        """key에 대한 (styleIDRef, charPrIDRef, paraPrIDRef)."""
        if key not in self.styles:
            key = "body"
        return self.styles[key], self.chars[key], self.paras[key]


def _next_id(xml: str, item_tag: str, default: int = 0) -> int:
    ids = [int(v) for v in re.findall(rf'<{item_tag} id="(\d+)"', xml)]
    return max(ids) + 1 if ids else default


def plan_ids(header_xml: str, profile: Dict[str, Any],
             extra_keys: Optional[Sequence[str]] = None) -> IdMap:
    """템플릿 header.xml을 읽어 충돌하지 않는 ID를 순차 할당한다.

    ``extra_keys``는 도식의 노드별 글자색처럼 본문을 보고서야 알 수 있는
    추가 서식(`dia:#RRGGBB`)이다.
    """
    char_id = _next_id(header_xml, "hh:charPr")
    para_id = _next_id(header_xml, "hh:paraPr")
    bf_id = _next_id(header_xml, "hh:borderFill", 1)

    ids = IdMap()
    keys = [lv["key"] for lv in profile["levels"]]
    keys += ["table_top", "table_mid", "table_left", "body", "diagram", "diagram_root"]
    keys += ["footnote"]
    keys += list(extra_keys or [])

    for key in keys:
        ids.chars[key] = char_id
        char_id += 1
        ids.paras[key] = para_id
        para_id += 1

    if (profile.get("signature") or {}).get("text"):
        ids.signature_char = char_id
        char_id += 1

    ids.border_base = bf_id
    ids.border_header = bf_id + 1

    # styleID 0은 템플릿의 '바탕글'을 유지, 1번부터 커스텀 스타일
    sid = 1
    for lv in profile["levels"]:
        ids.styles[lv["key"]] = sid
        sid += 1
    for key in ("table_top", "table_mid", "table_left", "body", "footnote"):
        ids.styles[key] = sid
        sid += 1
    # 도식 셀은 별도 스타일 없이 표(중간) 스타일을 쓴다
    ids.styles["diagram"] = ids.styles["table_mid"]
    ids.styles["diagram_root"] = ids.styles["table_mid"]
    for key in (extra_keys or []):
        ids.styles[key] = ids.styles["table_mid"]
    return ids


# ──────────────────────────────────────────────────────────────
# 템플릿 패치
# ──────────────────────────────────────────────────────────────
def _diagram_text_cfg(profile: Dict[str, Any], color: str) -> Dict[str, Any]:
    dia = profile["diagram"]
    return {"name": f"도식({color})", "size_pt": dia["font_size_pt"], "bold": True,
            "font": "bold", "color": color, "left_pt": 0, "indent_pt": 0,
            "spacing_below_pt": 0, "line_spacing": 130, "align": "CENTER"}


def _intent(cfg: Dict[str, Any]) -> int:
    """`hc:intent` 값. 음수는 내어쓰기, 양수는 첫 줄 들여쓰기.

    `indent_pt`는 내어쓰기 폭(양수로 적고 음수로 나간다), `first_line_indent_pt`는
    첫 줄 들여쓰기다. 둘 다 있으면 내어쓰기가 이긴다 — 한글에서도 한 값이라
    동시에 줄 수 없다.
    """
    hanging = cfg.get("indent_pt") or 0
    if hanging:
        return -pt(hanging)
    return pt(cfg.get("first_line_indent_pt", 0) or 0)


def _style_cfgs(profile: Dict[str, Any],
                extra_keys: Optional[Sequence[str]] = None) -> List[Tuple[str, Dict[str, Any]]]:
    """(key, 스타일 설정) 목록. header 주입 순서와 동일."""
    tbl = profile["table"]
    dia = profile["diagram"]
    out: List[Tuple[str, Dict[str, Any]]] = [(lv["key"], lv) for lv in profile["levels"]]
    out.append(("table_top", tbl["top"]))
    out.append(("table_mid", tbl["mid"]))
    out.append(("table_left", tbl["left"]))
    out.append(("body", profile["body"]))
    out.append(("diagram", {
        "name": "도식", "size_pt": dia["font_size_pt"], "bold": True, "font": "bold",
        "color": dia.get("box_color", "#000000"), "left_pt": 0, "indent_pt": 0,
        "spacing_below_pt": 0, "line_spacing": 130, "align": "CENTER",
    }))
    out.append(("diagram_root", {
        "name": "도식(강조)", "size_pt": dia["font_size_pt"], "bold": True, "font": "bold",
        "color": dia.get("root_color", "#FFFFFF"), "left_pt": 0, "indent_pt": 0,
        "spacing_below_pt": 0, "line_spacing": 130, "align": "CENTER",
    }))
    out.append(("footnote", profile["footnote"]))
    for key in (extra_keys or []):
        out.append((key, _diagram_text_cfg(profile, key.split(":", 1)[-1])))
    return out


def patch_template_bytes(profile: Dict[str, Any], ids: IdMap,
                         extra_keys: Optional[Sequence[str]] = None) -> bytes:
    original = blank_document_bytes()
    buf_in, buf_out = BytesIO(original), BytesIO()
    with zipfile.ZipFile(buf_in, "r") as zi, \
            zipfile.ZipFile(buf_out, "w", zipfile.ZIP_DEFLATED) as zo:
        for item in zi.infolist():
            data = zi.read(item.filename)
            if item.filename == "Contents/header.xml":
                data = patch_header(data.decode("utf-8"), profile, ids,
                                    extra_keys).encode("utf-8")
            elif item.filename == "Contents/section0.xml":
                data = _patch_section_margins(data.decode("utf-8"), profile).encode("utf-8")
            zo.writestr(
                item, data,
                compress_type=zipfile.ZIP_STORED if item.filename == "mimetype"
                else zipfile.ZIP_DEFLATED,
            )
    return buf_out.getvalue()


#: 이름으로 부를 수 있는 용지. (가로 mm, 세로 mm)
PAPER_SIZES = {
    "A4": (210.0, 297.0), "B5": (182.0, 257.0), "A5": (148.0, 210.0),
    "A3": (297.0, 420.0), "B4": (257.0, 364.0), "Letter": (215.9, 279.4),
    # 국내 보고서에서 쓰는 판형
    "크라운": (166.0, 241.0), "크라운판": (166.0, 241.0), "crown": (166.0, 241.0),
    "신국판": (152.0, 225.0), "국판": (148.0, 210.0), "4x6배판": (188.0, 257.0),
}


def paper_mm(page: Dict[str, Any]) -> Optional[Tuple[float, float]]:
    """프로파일의 용지 설정 → (가로 mm, 세로 mm). 알 수 없으면 None.

    `width_mm`·`height_mm`를 직접 적으면 그것이 이긴다. 아니면 `size` 이름을 찾는다.
    """
    if page.get("width_mm") and page.get("height_mm"):
        return float(page["width_mm"]), float(page["height_mm"])
    name = str(page.get("size", "") or "").strip()
    for key, size in PAPER_SIZES.items():
        if key.lower() == name.lower():
            return size
    return None


def _patch_section_margins(xml: str, profile: Dict[str, Any]) -> str:
    page = profile["page"]
    m = page["margin_mm"]
    new_margin = (
        f'<hp:margin header="{mm(m["header"])}" footer="{mm(m["footer"])}" '
        f'gutter="0" left="{mm(m["left"])}" right="{mm(m["right"])}" '
        f'top="{mm(m["top"])}" bottom="{mm(m["bottom"])}"/>'
    )
    xml = re.sub(r'<hp:margin header="[^"]*"[^/]*/>', new_margin, xml)

    size = paper_mm(page)
    if size is not None:
        width, height = size
        xml = re.sub(r'(<hp:pagePr[^>]*?)width="\d+" height="\d+"',
                     rf'\g<1>width="{mm(width)}" height="{mm(height)}"', xml, count=1)
    return xml


def patch_header(x: str, profile: Dict[str, Any], ids: IdMap,
                 extra_keys: Optional[Sequence[str]] = None) -> str:
    fonts = profile["fonts"]

    # (A) 폰트 교체: font id=0 → bold, id=1 → light (모든 lang 그룹에 적용)
    x = re.sub(r'(<hh:font id="0" face=")([^"]+)(")', rf"\g<1>{fonts['bold']}\3", x)
    x = re.sub(r'(<hh:font id="1" face=")([^"]+)(")', rf"\g<1>{fonts['light']}\3", x)

    # (B) 바탕글(paraPr id=0) 줄간격을 body 설정에 맞춤
    x = _update_para_pr_line_spacing(x, 0, int(profile["body"].get("line_spacing", 160)))

    cfgs = _style_cfgs(profile, extra_keys)

    # (C) charProperties 주입
    new_chars = "".join(
        char_pr(
            ids.chars[key],
            cfg.get("size_pt", 12),
            bool(cfg.get("bold", False)),
            color=cfg.get("color", "#000000") or "#000000",
            font_id=_font_id(cfg.get("font", "light")),
            letter_spacing=int(cfg.get("letter_spacing", 0) or 0),
        )
        for key, cfg in cfgs
    )
    if ids.signature_char is not None:
        sig = profile["signature"]
        new_chars += char_pr(ids.signature_char, sig.get("size_pt", 5), False,
                             color=sig.get("color", "#FFFFFF"), font_id=FONT_ID_LIGHT)
    x = x.replace("</hh:charProperties>", f"{new_chars}</hh:charProperties>", 1)
    x = _bump_item_cnt(x, "charProperties", "hh:charPr", x)

    # (D) paraProperties 주입
    new_paras = "".join(
        para_pr(
            ids.paras[key],
            left=pt(cfg.get("left_pt", 0)),
            indent=_intent(cfg),
            align=cfg.get("align", "JUSTIFY"),
            spacing_below=pt(cfg.get("spacing_below_pt", 0)),
            line_spacing=int(cfg.get("line_spacing", 180)),
            spacing_above=pt(cfg.get("spacing_above_pt", 0)),
        )
        for key, cfg in cfgs
    )
    x = x.replace("</hh:paraProperties>", f"{new_paras}</hh:paraProperties>", 1)
    x = _bump_item_cnt(x, "paraProperties", "hh:paraPr", x)

    # (E) borderFills: 표 테두리 + 표 헤더(배경색)
    tbl = profile["table"]
    new_bf = (border_fill(ids.border_base, tbl["border_color"])
              + border_fill(ids.border_header, tbl["border_color"], tbl["header_bg"]))
    x = x.replace("</hh:borderFills>", f"{new_bf}</hh:borderFills>", 1)
    x = _bump_item_cnt(x, "borderFills", "hh:borderFill", x)

    # (F) styles 전체 교체(바탕글 + 프로파일 스타일)
    style_items: List[Tuple[str, Dict[str, Any], int]] = []
    for key, cfg in cfgs:
        if key in ("diagram", "diagram_root") or key.startswith("dia:"):
            continue
        style_items.append((key, cfg, ids.styles[key]))
    max_sid = max(sid for _, _, sid in style_items) if style_items else 0

    bg_style = (
        '<hh:style id="0" type="PARA" name="바탕글" engName="Normal" '
        'paraPrIDRef="0" charPrIDRef="0" nextStyleIDRef="0" '
        'langID="1042" lockForm="0"/>'
    )
    custom = ""
    for key, cfg, sid in style_items:
        nxt = sid + 1 if sid < max_sid else sid
        name = cfg.get("name") or key
        eng = cfg.get("eng_name") or _ascii_name(key)
        custom += style(sid, name, eng, ids.paras[key], ids.chars[key], nxt)
    block = f'<hh:styles itemCnt="{len(style_items) + 1}">{bg_style}{custom}</hh:styles>'
    x = re.sub(r"<hh:styles\b.*?</hh:styles>", block, x, count=1, flags=re.DOTALL)
    return x


def _ascii_name(key: str) -> str:
    return {"table_top": "Table(Top)", "table_mid": "Table(Mid)",
            "table_left": "Table(Left)", "body": "Body"}.get(key, key)


def _bump_item_cnt(x: str, container: str, item_tag: str, source: str) -> str:
    """컨테이너 블록 안의 실제 item 수를 세어 itemCnt를 갱신."""
    m = re.search(rf"<hh:{container}\b.*?</hh:{container}>", source, flags=re.DOTALL)
    if not m:
        return x
    count = len(re.findall(rf"<{item_tag} id=\"", m.group()))
    return re.sub(rf'(<hh:{container}\s+itemCnt=")\d+(")', rf"\g<1>{count}\2", x, count=1)


def _update_para_pr_line_spacing(xml: str, para_id: int, ls_val: int) -> str:
    def replacer(m: "re.Match[str]") -> str:
        return re.sub(r'(<hh:lineSpacing[^>]*value=")\d+(")', rf"\g<1>{ls_val}\2", m.group())

    return re.sub(rf'(<hh:paraPr id="{para_id}".*?</hh:paraPr>)', replacer, xml, flags=re.DOTALL)


# ──────────────────────────────────────────────────────────────
# 자동 번호 접두어
# ──────────────────────────────────────────────────────────────
def _auto_prefix(kind: str, n: int, chapter: int = 0) -> str:
    if kind == "AUTO_ROMAN":
        return f"{ROMAN[n]}. " if n < len(ROMAN) else f"{n + 1}. "
    if kind == "AUTO_NUM":
        return f"{n + 1}. "
    if kind == "AUTO_ALPHA":
        return f"{chr(ord('A') + n)}. " if n < 26 else f"{n + 1}. "
    if kind == "AUTO_HANGUL":
        return f"{HANGUL[n]}. " if n < len(HANGUL) else f"{n + 1}. "
    if kind == "AUTO_CIRCLED":
        return f"{CIRCLED[n]} " if n < len(CIRCLED) else f"{n + 1}) "
    if kind == "AUTO_CHAPTER":          # 제1장 — 연구보고서 장 제목
        return f"제{n + 1}장 "
    if kind == "AUTO_SECTION":          # 제1절 — 연구보고서 절 제목
        return f"제{n + 1}절 "
    if kind == "AUTO_PAREN":            # 1) — 숫자에 닫는 괄호
        return f"{n + 1}) "
    if kind == "AUTO_TABLE":            # 〈표 1-1〉 — 장 번호를 따라간다
        return f"〈표 {chapter}-{n + 1}〉 "
    if kind == "AUTO_FIGURE":           # 〔그림 1-1〕
        return f"〔그림 {chapter}-{n + 1}〕 "
    return ""


class _Numbering:
    """AUTO_* 접두어 카운터. 상위 레벨이 증가하면 하위 카운터를 초기화한다."""

    def __init__(self, profile: Dict[str, Any]) -> None:
        self.order = [lv["key"] for lv in profile["levels"]]
        self.counters: Dict[str, int] = {k: 0 for k in self.order}
        #: 표·그림 번호가 따라가는 장 번호(〈표 1-1〉의 앞자리)
        self.chapter_keys = {lv["key"] for lv in profile["levels"]
                             if lv.get("prefix") == "AUTO_CHAPTER"}
        self.chapter = 0

    def next_prefix(self, key: str, kind: str) -> str:
        idx = self.order.index(key) if key in self.order else len(self.order)
        value = self.counters.get(key, 0)
        if key in self.chapter_keys:
            self.chapter = value + 1
        text = _auto_prefix(kind, value, self.chapter)
        self.counters[key] = value + 1
        for deeper in self.order[idx + 1:]:
            self.counters[deeper] = 0
        return text


# ──────────────────────────────────────────────────────────────
# 문서 생성
# ──────────────────────────────────────────────────────────────
@dataclass
class BuildResult:
    data: bytes
    warnings: List[str] = field(default_factory=list)
    path: Optional[str] = None


def build_document(
    profile: Dict[str, Any],
    contents: Sequence[Any],
    out_path: Optional[str] = None,
) -> BuildResult:
    """프로파일 + 콘텐츠 → hwpx 바이트(및 선택적 파일 저장)."""
    profile = merge_profile(profile)
    errors = validate_profile(profile)
    if errors:
        raise ValueError("프로파일 오류:\n  " + "\n  ".join(errors))

    items = normalize_contents(contents, profile)
    warns: List[str] = []

    header_xml = _template_header_xml()
    extra_keys = _diagram_text_keys(items, profile, warns)
    ids = plan_ids(header_xml, profile, extra_keys)
    patched = patch_template_bytes(profile, ids, extra_keys)

    doc = HwpxDocument.open(BytesIO(patched))
    sec = doc.sections[0]
    numbering = _Numbering(profile)
    table_plans: List[Dict[str, Any]] = []
    pending_images: List[Dict[str, Any]] = []

    for item in items:
        kind = item.get("type")
        if kind == "blank":
            doc.add_paragraph("", section=sec)
        elif kind == "table":
            _add_content_table(doc, sec, item, profile, table_plans)
        elif kind == "image":
            _add_image(doc, sec, item["path"], profile, pending_images, warns)
        elif kind == "diagram":
            _add_diagram(doc, sec, item["spec"], profile, ids,
                         table_plans, pending_images, warns)
        else:
            _add_paragraph(doc, sec, item, profile, ids, numbering)

    sig = profile.get("signature") or {}
    if sig.get("text") and ids.signature_char is not None:
        doc.add_paragraph(sig["text"], section=sec, char_pr_id_ref=ids.signature_char)

    data = doc.to_bytes()
    if pending_images:
        data = _finalize_with_images(data, pending_images, profile)
    data = _postprocess(data, profile, ids, table_plans)

    if out_path:
        parent = os.path.dirname(os.path.abspath(out_path))
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(out_path, "wb") as fh:
            fh.write(data)
    return BuildResult(data=data, warnings=warns, path=out_path)


def _diagram_text_keys(items: Sequence[Dict[str, Any]], profile: Dict[str, Any],
                       warns: List[str]) -> List[str]:
    """본문의 도식들이 쓰는 글자색을 모아 charPr key 목록으로 만든다."""
    keys: List[str] = []
    for item in items:
        if item.get("type") != "diagram":
            continue
        try:
            colors = diagram_mod.collect_text_colors(item["spec"], profile)
        except Exception:                       # 격자 계산 실패는 생성 단계에서 다룬다
            continue
        for color in colors:
            key = diagram_mod.text_style_key(color)
            if key not in keys:
                keys.append(key)
    return keys


def _template_header_xml() -> str:
    with zipfile.ZipFile(BytesIO(blank_document_bytes())) as zf:
        return zf.read("Contents/header.xml").decode("utf-8")


def _add_paragraph(doc, sec, item, profile, ids: IdMap, numbering: _Numbering) -> None:
    key = item.get("key", "body")
    lv = level_by_key(profile, key)
    text = str(item.get("text", ""))
    shift = 0
    if lv is not None:
        prefix = str(lv.get("prefix", ""))
        if prefix.startswith("AUTO_"):
            prefix = numbering.next_prefix(key, prefix)
        text = f"{prefix}{text}"
        shift = len(prefix)
    elif key == "body" and profile["body"].get("first_line_indent_pt"):
        pass  # 첫 줄 들여쓰기는 paraPr에서 처리
    sid, cid, pid = ids.refs(key if (lv is not None or key in ids.styles) else "body")

    notes = item.get("notes") or []
    if not notes:
        doc.add_paragraph(text, section=sec, style_id_ref=sid,
                          char_pr_id_ref=cid, para_pr_id_ref=pid)
        return
    _add_paragraph_with_notes(doc, sec, text, notes, shift, (sid, cid, pid), ids)


def _add_paragraph_with_notes(doc, sec, text: str, notes: Sequence[Dict[str, Any]],
                              shift: int, refs: Tuple[int, int, int], ids: IdMap) -> None:
    """각주가 달린 문단. 번호가 놓일 자리에서 run을 끊어 각주를 붙인다.

    한글은 각주를 '문단 안 어느 run 뒤'에 매다는 방식이라, 번호 자리를 지키려면
    앞 토막을 먼저 넣고 각주를 붙인 뒤 나머지를 새 run으로 이어야 한다.
    번호 자체는 한글이 문서 순서대로 매기므로 여기서 정하지 않는다.
    """
    sid, cid, pid = refs
    marks = sorted(min(max(int(n.get("offset", 0)) + shift, 0), len(text)) for n in notes)
    order = sorted(range(len(notes)),
                   key=lambda i: min(max(int(notes[i].get("offset", 0)) + shift, 0), len(text)))

    para = doc.add_paragraph(text[:marks[0]], section=sec, style_id_ref=sid,
                             char_pr_id_ref=cid, para_pr_id_ref=pid)
    for pos, idx in enumerate(order):
        para.add_footnote(str(notes[idx].get("text", "")),
                          char_pr_id_ref=ids.chars["footnote"])
        end = marks[pos + 1] if pos + 1 < len(marks) else len(text)
        chunk = text[marks[pos]:end]
        if chunk:
            para.add_run(chunk, char_pr_id_ref=cid)


def _add_content_table(doc, sec, item, profile, table_plans) -> None:
    rows, cols = int(item["rows"]), int(item["cols"])
    data = item.get("data") or []
    width = mm(profile["table"]["width_mm"]) if profile["table"]["width_mm"] > 0 else None
    tbl = doc.add_table(rows, cols, section=sec, width=width)
    for r in range(rows):
        for c in range(cols):
            idx = r * cols + c
            if idx < len(data):
                tbl.set_cell_text(r, c, str(data[idx]))
    table_plans.append({"kind": "content", "header": bool(item.get("header", True))})


def _add_diagram(doc, sec, spec, profile, ids, table_plans, pending_images, warns) -> None:
    spec = diagram_mod.ensure_spec(spec)
    render = spec.options.get("render") or profile["diagram"]["render"]

    if render == "table":
        grid = diagram_mod.build_grid(spec, profile)
        warns.extend(grid.warnings)
        if grid.fallback_to_image:
            render = "image"
        else:
            diagram_mod.emit_grid(doc, sec, grid, profile, ids, table_plans)
            return

    png = diagram_mod.render_png(spec, profile, warnings=warns)
    if png is None:
        warns.append(f"도식 '{spec.title or spec.type}': 이미지 백엔드를 쓸 수 없어 표로 생성")
        grid = diagram_mod.build_grid(spec, profile, force=True)
        warns.extend(grid.warnings)
        diagram_mod.emit_grid(doc, sec, grid, profile, ids, table_plans)
        return
    _add_image(doc, sec, png, profile, pending_images, warns)


# ──────────────────────────────────────────────────────────────
# 그림 삽입
# ──────────────────────────────────────────────────────────────
def _add_image(doc, sec, image_path, profile, pending_images, warns) -> None:
    path = Path(image_path)
    if not path.exists():
        warns.append(f"이미지 파일 없음: {image_path}")
        doc.add_paragraph(f"[이미지 누락: {image_path}]", section=sec)
        return

    ext = path.suffix.lower()
    media_types = {".png": "image/png", ".jpg": "image/jpg", ".jpeg": "image/jpg",
                   ".gif": "image/gif", ".bmp": "image/bmp",
                   ".tif": "image/tiff", ".tiff": "image/tiff"}
    data = path.read_bytes()
    w_px, h_px = _detect_image_size(data, ext)

    target_w = mm(profile["image"]["default_width_mm"])
    target_h = round(target_w * h_px / w_px) if w_px and h_px else round(target_w * 0.75)

    idx = len(pending_images)
    img_id = f"image{idx + 1}"
    pending_images.append({
        "id": img_id, "filename": f"{img_id}{ext}", "data": data,
        "media_type": media_types.get(ext, "image/png"),
        "width": target_w, "height": target_h,
    })
    doc.add_paragraph(f"__IMAGE_PLACEHOLDER_{idx}__", section=sec)


def _detect_image_size(data: bytes, ext: str) -> Tuple[int, int]:
    try:
        if ext == ".png" and data[:8] == b"\x89PNG\r\n\x1a\n":
            return (struct.unpack(">I", data[16:20])[0],
                    struct.unpack(">I", data[20:24])[0])
        if ext in (".jpg", ".jpeg"):
            i = 2
            while i < len(data) - 1:
                if data[i] != 0xFF:
                    break
                marker = data[i + 1]
                if marker in (0xC0, 0xC1, 0xC2):
                    h = struct.unpack(">H", data[i + 5:i + 7])[0]
                    w = struct.unpack(">H", data[i + 7:i + 9])[0]
                    return w, h
                i += 2 + struct.unpack(">H", data[i + 2:i + 4])[0]
    except Exception:
        pass
    return 0, 0


def _finalize_with_images(doc_bytes: bytes, images, profile) -> bytes:
    buf_in, buf_out = BytesIO(doc_bytes), BytesIO()
    with zipfile.ZipFile(buf_in, "r") as zi, \
            zipfile.ZipFile(buf_out, "w", zipfile.ZIP_DEFLATED) as zo:
        for item in zi.infolist():
            data = zi.read(item.filename)
            if item.filename == "Contents/section0.xml":
                data = _replace_image_placeholders(
                    data.decode("utf-8"), images, profile).encode("utf-8")
            elif item.filename == "Contents/content.hpf":
                data = _add_bindata_to_hpf(data.decode("utf-8"), images).encode("utf-8")
            zo.writestr(item, data,
                        compress_type=zipfile.ZIP_STORED if item.filename == "mimetype"
                        else zipfile.ZIP_DEFLATED)
        for img in images:
            zo.writestr(f'BinData/{img["filename"]}', img["data"])
    return buf_out.getvalue()


def _replace_image_placeholders(xml: str, images, profile) -> str:
    if not images:
        return xml
    if "xmlns:hc=" not in xml:
        xml = re.sub(r"(<hs:sec\b[^>]*?)(\s*>)",
                     r'\1 xmlns:hc="http://www.hancom.co.kr/hwpml/2011/core"\2',
                     xml, count=1)
    tac = "1" if profile["image"]["treat_as_char"] else "0"
    for idx, img in enumerate(images):
        w, h, img_id = img["width"], img["height"], img["id"]
        pic = (
            f'<hp:pic id="{random.randint(100000000, 999999999)}" zOrder="0" '
            f'numberingType="PICTURE" textWrap="TOP_AND_BOTTOM" textFlow="BOTH_SIDES" '
            f'lock="0" dropcapstyle="None" href="" groupLevel="0" '
            f'instid="{random.randint(10000000, 99999999)}" reverse="0">'
            f'<hp:offset x="0" y="0"/>'
            f'<hp:orgSz width="{w}" height="{h}"/>'
            f'<hp:curSz width="{w}" height="{h}"/>'
            f'<hp:flip horizontal="0" vertical="0"/>'
            f'<hp:rotationInfo angle="0" centerX="0" centerY="0" rotateimage="1"/>'
            f"<hp:renderingInfo>"
            f'<hc:transMatrix e1="1" e2="0" e3="0" e4="0" e5="1" e6="0"/>'
            f'<hc:scaMatrix e1="1" e2="0" e3="0" e4="0" e5="1" e6="0"/>'
            f'<hc:rotMatrix e1="1" e2="0" e3="0" e4="0" e5="1" e6="0"/>'
            f"</hp:renderingInfo>"
            f'<hp:imgRect><hc:pt0 x="0" y="0"/><hc:pt1 x="{w}" y="0"/>'
            f'<hc:pt2 x="{w}" y="{h}"/><hc:pt3 x="0" y="{h}"/></hp:imgRect>'
            f'<hp:imgClip left="0" right="0" top="0" bottom="0"/>'
            f'<hp:inMargin left="0" right="0" top="0" bottom="0"/>'
            f'<hc:img binaryItemIDRef="{img_id}" bright="0" contrast="0" '
            f'effect="REAL_PIC" alpha="0"/>'
            f"<hp:effects/>"
            f'<hp:sz width="{w}" widthRelTo="ABSOLUTE" height="{h}" '
            f'heightRelTo="ABSOLUTE" protect="0"/>'
            f'<hp:pos treatAsChar="{tac}" affectLSpacing="0" flowWithText="1" '
            f'allowOverlap="1" holdAnchorAndSO="0" vertRelTo="PARA" '
            f'horzRelTo="COLUMN" vertAlign="TOP" horzAlign="LEFT" '
            f'vertOffset="0" horzOffset="0"/>'
            f'<hp:outMargin left="0" right="0" top="0" bottom="0"/>'
            f"</hp:pic>"
        )
        xml = xml.replace(f"<hp:t>__IMAGE_PLACEHOLDER_{idx}__</hp:t>", pic)
    return xml


def _add_bindata_to_hpf(xml: str, images) -> str:
    items = "".join(
        f'<opf:item id="{img["id"]}" href="BinData/{img["filename"]}" '
        f'media-type="{img["media_type"]}" isEmbeded="1"/>'
        for img in images
    )
    return xml.replace("</opf:manifest>", f"{items}</opf:manifest>")


# ──────────────────────────────────────────────────────────────
# section0.xml 후처리
# ──────────────────────────────────────────────────────────────
def _postprocess(data: bytes, profile, ids: IdMap, table_plans) -> bytes:
    buf_in, buf_out = BytesIO(data), BytesIO()
    with zipfile.ZipFile(buf_in, "r") as zi, \
            zipfile.ZipFile(buf_out, "w", zipfile.ZIP_DEFLATED) as zo:
        for item in zi.infolist():
            payload = zi.read(item.filename)
            if item.filename.startswith("Contents/section") and item.filename.endswith(".xml"):
                payload = patch_section_xml(
                    payload.decode("utf-8"), profile, ids, table_plans).encode("utf-8")
            zo.writestr(item, payload,
                        compress_type=zipfile.ZIP_STORED if item.filename == "mimetype"
                        else zipfile.ZIP_DEFLATED)
    return buf_out.getvalue()


def patch_section_xml(xml: str, profile, ids: IdMap, table_plans) -> str:
    xml = _patch_block_paragraphs(xml, profile, ids)
    xml = _patch_tables(xml, profile, ids, table_plans)
    xml = _patch_images(xml, profile)
    xml = _patch_paragraph_para_refs(xml, ids)
    return xml


def _anchor_refs(profile, ids: IdMap) -> Tuple[int, int, int]:
    """표·그림을 감싸는 외곽 문단에 쓸 (styleID, charPrID, paraPrID)."""
    key = profile["table"].get("anchor_level")
    if not key:
        body_keys = [lv["key"] for lv in profile["levels"]
                     if not str(lv.get("prefix", "")).startswith("AUTO_")]
        key = body_keys[-1] if body_keys else "body"
    return ids.refs(key)


def _patch_block_paragraphs(xml: str, profile, ids: IdMap) -> str:
    """표·그림을 담은 최상위 <hp:p>의 문단 속성을 anchor 레벨로 맞춘다."""
    sid, cid, pid = _anchor_refs(profile, ids)
    masks: List[str] = []

    def save(m):
        masks.append(m.group())
        return f"__SUBLIST_MASK_{len(masks) - 1}__"

    tmp = re.sub(r"<hp:subList\b.*?</hp:subList>", save, xml, flags=re.DOTALL)

    def patch_p(pm):
        p = pm.group()
        if "<hp:tbl" not in p and "<hp:pic" not in p:
            return p
        p = re.sub(r'(<hp:p\b[^>]*?paraPrIDRef=")\d+(")', rf"\g<1>{pid}\2", p, count=1)
        p = re.sub(r'(<hp:p\b[^>]*?styleIDRef=")\d+(")', rf"\g<1>{sid}\2", p, count=1)

        def patch_run(rm):
            r = rm.group()
            if "<hp:tbl" in r or "<hp:pic" in r:
                r = re.sub(r'(charPrIDRef=")\d+(")', rf"\g<1>{cid}\2", r, count=1)
            return r

        return re.sub(r"<hp:run\b.*?</hp:run>", patch_run, p, flags=re.DOTALL)

    tmp = re.sub(r"<hp:p\b.*?</hp:p>", patch_p, tmp, flags=re.DOTALL)
    for i, saved in enumerate(masks):
        tmp = tmp.replace(f"__SUBLIST_MASK_{i}__", saved, 1)
    return tmp


def _patch_paragraph_para_refs(xml: str, ids: IdMap) -> str:
    """styleIDRef에 맞춰 paraPrIDRef를 보정(누락 대비 안전망)."""
    mapping = ids.style_to_para()

    def patch_open(m):
        tag = m.group()
        sid_m = re.search(r'styleIDRef="(\d+)"', tag)
        if not sid_m:
            return tag
        pid = mapping.get(int(sid_m.group(1)))
        if pid is None or 'paraPrIDRef="' not in tag:
            return tag
        if re.search(r'paraPrIDRef="0"', tag):
            return re.sub(r'(paraPrIDRef=")\d+(")', rf"\g<1>{pid}\2", tag, count=1)
        return tag

    return re.sub(r"<hp:p\b[^>]*>", patch_open, xml)


def _patch_tables(xml: str, profile, ids: IdMap, table_plans) -> str:
    cfg = profile["table"]
    counter = {"i": 0}

    def patch_table(m):
        t = m.group()
        idx = counter["i"]
        counter["i"] += 1
        plan = table_plans[idx] if idx < len(table_plans) else {"kind": "content"}
        if plan.get("kind") == "diagram":
            return _patch_diagram_table(t, plan, profile, ids)
        return _patch_content_table(t, cfg, ids, plan)

    return re.sub(r"<hp:tbl.*?</hp:tbl>", patch_table, xml, flags=re.DOTALL)


def _cell_margin_xml(margin_mm: float) -> str:
    v = mm(margin_mm)
    return f'<hp:cellMargin left="{v}" right="{v}" top="{v}" bottom="{v}"/>'


def _apply_cell_margin(cell_xml: str, margin_xml: str) -> str:
    c = re.sub(r'(hasMargin=")\d+(")', r"\g<1>1\2", cell_xml)
    if re.search(r"<hp:cellMargin\b", c):
        return re.sub(r"<hp:cellMargin\b[^/]*/>", margin_xml, c)
    return c.replace("</hp:tc>", f"{margin_xml}</hp:tc>")


def _patch_content_table(t: str, cfg, ids: IdMap, plan) -> str:
    t = re.sub(r'(<hp:tbl[^>]*borderFillIDRef=")\d+(")', rf"\g<1>{ids.border_base}\2", t)
    tac = "1" if cfg["treat_as_char"] else "0"
    t = re.sub(r'(treatAsChar=")\d+(")', rf"\g<1>{tac}\2", t)
    if cfg["width_mm"] > 0:
        t = re.sub(r'(<hp:sz width=")\d+(")', rf"\g<1>{mm(cfg['width_mm'])}\2", t)
    t = re.sub(r'(<hp:tc[^>]*borderFillIDRef=")\d+(")', rf"\g<1>{ids.border_base}\2", t)

    margin_xml = _cell_margin_xml(cfg.get("cell_margin_mm", 0))
    t = re.sub(r"<hp:tc\b[^>]*>.*?</hp:tc>",
               lambda m: _apply_cell_margin(m.group(), margin_xml), t, flags=re.DOTALL)

    mid_s, mid_c, mid_p = ids.styles["table_mid"], ids.chars["table_mid"], ids.paras["table_mid"]

    def patch_sl(sm):
        s = sm.group()
        s = re.sub(r'(<hp:p[^>]*paraPrIDRef=")\d+(")', rf"\g<1>{mid_p}\2", s)
        s = re.sub(r'(<hp:p[^>]*styleIDRef=")\d+(")', rf"\g<1>{mid_s}\2", s)
        s = re.sub(r'(<hp:run[^>]*charPrIDRef=")\d+(")', rf"\g<1>{mid_c}\2", s)
        return s

    t = re.sub(r"<hp:subList.*?</hp:subList>", patch_sl, t, flags=re.DOTALL)

    if plan.get("header", True):
        top_s, top_c, top_p = (ids.styles["table_top"], ids.chars["table_top"],
                               ids.paras["table_top"])

        def patch_hdr(cm):
            c = cm.group()
            if 'rowAddr="0"' not in c:
                return c
            c = re.sub(rf'(<hp:tc[^>]*borderFillIDRef="){ids.border_base}(")',
                       rf"\g<1>{ids.border_header}\2", c)
            c = re.sub(r'(<hp:p[^>]*styleIDRef=")\d+(")', rf"\g<1>{top_s}\2", c)
            c = re.sub(r'(<hp:p[^>]*paraPrIDRef=")\d+(")', rf"\g<1>{top_p}\2", c)
            c = re.sub(r'(<hp:run[^>]*charPrIDRef=")\d+(")', rf"\g<1>{top_c}\2", c)
            return c

        t = re.sub(r"<hp:tc.*?</hp:tc>", patch_hdr, t, flags=re.DOTALL)
    return t


def _patch_diagram_table(t: str, plan, profile, ids: IdMap) -> str:
    """도식 표: 셀 테두리(borderFill)는 유지하고 크기·여백·글자 속성만 조정."""
    cfg = profile["table"]
    tac = "1" if cfg["treat_as_char"] else "0"
    t = re.sub(r'(treatAsChar=")\d+(")', rf"\g<1>{tac}\2", t)
    blank = plan.get("blank_border_fill")
    if blank:                       # 표 바깥 테두리 제거(기본값은 검은 실선 사각형)
        t = re.sub(r'(<hp:tbl\b[^>]*borderFillIDRef=")\d+(")', rf"\g<1>{blank}\2",
                   t, count=1)
    t = re.sub(r'(<hp:sz width=")\d+(")', rf"\g<1>{plan['width']}\2", t, count=1)
    t = re.sub(r'(<hp:sz [^>]*height=")\d+(")', rf"\g<1>{plan['height']}\2", t, count=1)

    margin_xml = _cell_margin_xml(0.2)
    cells = plan["cells"]

    def patch_cell(m):
        c = m.group()
        addr = re.search(r'<hp:cellAddr colAddr="(\d+)" rowAddr="(\d+)"/>', c)
        if not addr:
            return c
        col, row = int(addr.group(1)), int(addr.group(2))
        info = cells.get((row, col))
        c = _apply_cell_margin(c, margin_xml)
        if info:
            c = re.sub(r'(<hp:cellSz width=")\d+(")', rf"\g<1>{info['width']}\2", c, count=1)
            c = re.sub(r'(<hp:cellSz [^>]*height=")\d+(")', rf"\g<1>{info['height']}\2",
                       c, count=1)
            char_key = info.get("char", "diagram")
            cid, pid = ids.chars[char_key], ids.paras[char_key]
            sid = ids.styles.get(char_key, ids.styles["table_mid"])
            c = re.sub(r'(<hp:p[^>]*paraPrIDRef=")\d+(")', rf"\g<1>{pid}\2", c)
            c = re.sub(r'(<hp:p[^>]*styleIDRef=")\d+(")', rf"\g<1>{sid}\2", c)
            c = re.sub(r'(<hp:run[^>]*charPrIDRef=")\d+(")', rf"\g<1>{cid}\2", c)
        return c

    return re.sub(r"<hp:tc\b[^>]*>.*?</hp:tc>", patch_cell, t, flags=re.DOTALL)


def _patch_images(xml: str, profile) -> str:
    tac = "1" if profile["image"]["treat_as_char"] else "0"
    width = mm(profile["image"]["default_width_mm"])

    def patch_pic(m):
        p = m.group()
        p = re.sub(r'(treatAsChar=")\d+(")', rf"\g<1>{tac}\2", p)
        sz = re.search(r'<hp:sz width="(\d+)"[^>]*height="(\d+)"', p)
        if sz:
            w0, h0 = int(sz.group(1)), int(sz.group(2))
            if w0 > 0:
                new_h = round(width * h0 / w0)
                p = re.sub(r'(<hp:sz width=")\d+("[^>]*height=")\d+(")',
                           rf"\g<1>{width}\g<2>{new_h}\3", p)
        return p

    return re.sub(r"<hp:pic.*?</hp:pic>", patch_pic, xml, flags=re.DOTALL)
