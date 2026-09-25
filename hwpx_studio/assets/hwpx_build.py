#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""마커 텍스트 → 한글 문서(.hwpx). 표준 라이브러리만 쓴다.

브라우저 엔진 `docs/js/hwpx-studio.js`(와 그 안에서 쓰는 `docs/js/zip.js`)를
함수 하나하나 그대로 옮긴 것이다. 스킬 안(채팅 코드 샌드박스, pip 없음)에서
돌도록 python-hwpx·lxml 같은 외부 라이브러리를 하나도 쓰지 않는다.

    python hwpx_build.py 원고.md -o 결과.hwpx
    python hwpx_build.py 원고.md -o 결과.hwpx --profile profile.json --template template.hwpx
    python hwpx_build.py 원고.md --check-only      # 검사만
    python hwpx_build.py 원고.md -o 결과.hwpx --strict   # 오류가 있으면 만들지 않음

`--profile`·`--template`을 주지 않으면 이 파일이 있는 폴더, 그다음 그 위 폴더에서
`profile.json`·`template.hwpx`를 찾는다(스킬 배치: `<skill>/scripts/hwpx_build.py`).

코드에서는 `build_from_text(template_bytes, profile, text)`를 부른다.

JS와 같은 결과를 내려고 JS의 동작을 흉내 낸 곳이 있다.
  - 문자열은 UTF-16 단위로 다룬다(길이·자르기·정렬). 들어올 때 쪼개고 나갈 때 붙인다.
  - `\\s`·`trim()`은 JS의 공백 집합, `.`은 줄바꿈 네 가지를 뺀 문자다.
  - `Math.round`는 0.5를 올리고, `toFixed`는 정확한 이진값을 반올림한다.
  - 숫자를 글자로 바꿀 때는 JS의 `String(number)` 규칙을 따른다.
  - `String.prototype.replace`의 `$1`·`$&` 치환 규칙을 그대로 따른다.

`tests/test_hwpx_build.py`가 JS 엔진과 zip 안의 모든 파일이 바이트까지 같은지
대조한다. JS를 고치면 여기도 같이 고친다.
"""

from __future__ import annotations

import argparse
import copy
import io
import json
import math
import re
import struct
import sys
import zipfile
import zlib
from decimal import ROUND_HALF_UP, Decimal, localcontext
from pathlib import Path

# ──────────────────────────────────────────────────────────────
# JS 흉내
# ──────────────────────────────────────────────────────────────
#: JS의 `\s`·`trim()`이 보는 공백
WS_CHARS = ('\t\n\x0b\x0c\r \xa0 '
            + ''.join(chr(c) for c in range(0x2000, 0x200B))
            + '    　﻿')
S = '[' + re.escape(WS_CHARS) + ']'
NS = '[^' + re.escape(WS_CHARS) + ']'
#: JS의 `.`(줄바꿈 네 가지를 뺀 문자)
DOT = '[^\n\r  ]'


class JsError(Exception):
    """JS 엔진이 던지는 자리에서 같이 던진다."""


def js_trim(s):
    return s.strip(WS_CHARS)


def js_rtrim(s):
    return s.rstrip(WS_CHARS)


def to_js(value):
    """파이썬 값 → JS 문자열 규칙(UTF-16 단위). 한 글자짜리 확장 문자를 대리쌍 둘로 쪼갠다."""
    if isinstance(value, str):
        if not any(ord(c) > 0xFFFF for c in value):
            return value
        out = []
        for c in value:
            o = ord(c)
            if o > 0xFFFF:
                o -= 0x10000
                out.append(chr(0xD800 + (o >> 10)))
                out.append(chr(0xDC00 + (o & 0x3FF)))
            else:
                out.append(c)
        return ''.join(out)
    if isinstance(value, dict):
        return {to_js(k): to_js(v) for k, v in value.items()}
    if isinstance(value, list):
        return [to_js(v) for v in value]
    return value


def from_js(value):
    """JS 문자열 → 파이썬 문자열. 대리쌍을 붙이고 외톨이는 U+FFFD(TextEncoder와 같음)."""
    if isinstance(value, str):
        if not any(0xD800 <= ord(c) <= 0xDFFF for c in value):
            return value
        return value.encode('utf-16-le', 'surrogatepass').decode('utf-16-le', 'replace')
    if isinstance(value, dict):
        return {from_js(k): from_js(v) for k, v in value.items()}
    if isinstance(value, list):
        return [from_js(v) for v in value]
    return value


def js_truthy(v):
    if v is None or v is False:
        return False
    if v is True:
        return True
    if isinstance(v, (int, float)):
        return not (v == 0 or v != v)
    if isinstance(v, str):
        return v != ''
    return True


def _or(*values):
    """JS의 `a || b || c`."""
    for v in values[:-1]:
        if js_truthy(v):
            return v
    return values[-1]


def _nn(v, default):
    """JS의 `v ?? default`."""
    return default if v is None else v


def _norm_num(x):
    """정수 값인 실수는 int로(연산 결과는 같고 range·키로 쓰기 편하다)."""
    if isinstance(x, float) and x == x and x not in (math.inf, -math.inf) \
            and x.is_integer() and abs(x) < 2 ** 53:
        return int(x)
    return x


_NUM_LITERAL = re.compile(r'[+-]?(?:[0-9]+\.?[0-9]*|\.[0-9]+)(?:[eE][+-]?[0-9]+)?\Z')


def js_number(v):
    """JS의 `Number(v)`."""
    if v is None:
        return 0
    if isinstance(v, bool):
        return 1 if v else 0
    if isinstance(v, (int, float)):
        return _norm_num(v)
    if isinstance(v, str):
        s = js_trim(v)
        if s == '':
            return 0
        low = s[:2].lower()
        for prefix, base in (('0x', 16), ('0o', 8), ('0b', 2)):
            if low == prefix:
                try:
                    return _norm_num(float(int(s[2:], base))) if s[2:].isascii() else math.nan
                except ValueError:
                    return math.nan
        if s in ('Infinity', '+Infinity'):
            return math.inf
        if s == '-Infinity':
            return -math.inf
        if _NUM_LITERAL.match(s):
            return _norm_num(float(s))
        return math.nan
    if isinstance(v, list):
        return js_number(js_str(v))
    return math.nan


def _num_str(x):
    """JS의 Number::toString."""
    if x != x:
        return 'NaN'
    if x in (math.inf, -math.inf):
        return 'Infinity' if x > 0 else '-Infinity'
    if x == 0:
        return '0'
    if x < 0:
        return '-' + _num_str(-x)
    if isinstance(x, int):
        x = float(x) if x >= 2 ** 53 else x
        if isinstance(x, int):
            return str(x) if x < 10 ** 21 else _num_str(float(x))
    tup = Decimal(repr(x)).as_tuple()
    digits = ''.join(map(str, tup.digits)).rstrip('0') or '0'
    lead = len(''.join(map(str, tup.digits))) - len(''.join(map(str, tup.digits)).lstrip('0'))
    digits = digits[lead:] if lead else digits
    k = len(digits)
    n = tup.exponent + len(tup.digits) - lead
    if k <= n <= 21:
        return digits + '0' * (n - k)
    if 0 < n <= 21:
        return digits[:n] + '.' + digits[n:]
    if -6 < n <= 0:
        return '0.' + '0' * (-n) + digits
    e = n - 1
    sign = '+' if e >= 0 else '-'
    if k == 1:
        return f'{digits}e{sign}{abs(e)}'
    return f'{digits[0]}.{digits[1:]}e{sign}{abs(e)}'


def js_str(v):
    """JS의 `String(v)`·템플릿 문자열 보간."""
    if v is None:
        return 'null'
    if v is True:
        return 'true'
    if v is False:
        return 'false'
    if isinstance(v, (int, float)):
        return _num_str(v)
    if isinstance(v, str):
        return v
    if isinstance(v, list):
        return ','.join('' if x is None else js_str(x) for x in v)
    return '[object Object]'


def js_round(x):
    """JS의 `Math.round` — 0.5는 +무한 쪽으로."""
    if isinstance(x, int):
        return x
    if x != x or x in (math.inf, -math.inf):
        return x
    f = math.floor(x)
    return f + 1 if x - f >= 0.5 else f


def js_floor(x):
    if isinstance(x, int):
        return x
    if x != x or x in (math.inf, -math.inf):
        return x
    return math.floor(x)


def js_max(*values):
    if not values:
        return -math.inf
    if any(v != v for v in values):
        return math.nan
    return max(values)


def js_min(*values):
    if not values:
        return math.inf
    if any(v != v for v in values):
        return math.nan
    return min(values)


def js_mod(a, b):
    """JS의 `%` — 부호가 나뉘는 수를 따른다."""
    if isinstance(a, int) and isinstance(b, int) and b:
        r = abs(a) % abs(b)
        return -r if a < 0 else r
    return _norm_num(math.fmod(a, b)) if b else math.nan


def js_sum(values):
    """`reduce((a, b) => a + b, 0)` — 앞에서부터 차례로 더한다(보정 합 아님)."""
    total = 0
    for v in values:
        total = total + v
    return total


def to_fixed(x, digits):
    """JS의 `Number.prototype.toFixed`."""
    if x != x:
        return 'NaN'
    if abs(x) >= 1e21:
        return js_str(x)
    with localcontext() as ctx:
        ctx.prec = 200
        q = Decimal(abs(x)).quantize(Decimal(1).scaleb(-digits), rounding=ROUND_HALF_UP)
    return ('-' if x < 0 else '') + format(q, 'f')


def utf16_key(s):
    """JS 기본 정렬 순서(UTF-16 단위). 이 모듈의 문자열은 이미 UTF-16 단위다."""
    return s


def _expand(template, groups, matched, pos, subject):
    """JS 치환 문자열의 `$$`·`$&`·`` $` ``·`$'`·`$n`·`$nn`."""
    out = []
    i = 0
    n = len(template)
    m = len(groups)
    while i < n:
        c = template[i]
        if c == '$' and i + 1 < n:
            d = template[i + 1]
            if d == '$':
                out.append('$')
                i += 2
                continue
            if d == '&':
                out.append(matched)
                i += 2
                continue
            if d == '`':
                out.append(subject[:pos])
                i += 2
                continue
            if d == "'":
                out.append(subject[pos + len(matched):])
                i += 2
                continue
            if '0' <= d <= '9':
                if i + 2 < n and '0' <= template[i + 2] <= '9':
                    nn = int(template[i + 1:i + 3])
                    if 1 <= nn <= m:
                        out.append(groups[nn - 1] or '')
                        i += 3
                        continue
                nn = int(d)
                if 1 <= nn <= m:
                    out.append(groups[nn - 1] or '')
                    i += 2
                    continue
        out.append(c)
        i += 1
    return ''.join(out)


def js_replace(subject, pattern, replacement, global_=False):
    """JS의 `String.prototype.replace`. pattern은 문자열이나 컴파일한 정규식."""
    if isinstance(pattern, str):
        pos = subject.find(pattern)
        if pos < 0:
            return subject
        rep = (replacement(pattern) if callable(replacement)
               else _expand(replacement, [], pattern, pos, subject))
        return subject[:pos] + rep + subject[pos + len(pattern):]
    out = []
    last = 0
    for m in pattern.finditer(subject):
        out.append(subject[last:m.start()])
        if callable(replacement):
            out.append(replacement(m.group(0), *m.groups()))
        else:
            out.append(_expand(replacement, list(m.groups()), m.group(0), m.start(), subject))
        last = m.end()
        if not global_:
            break
    out.append(subject[last:])
    return ''.join(out)


# ──────────────────────────────────────────────────────────────
# 최소 ZIP 읽기·쓰기 (zip.js 이식)
# ──────────────────────────────────────────────────────────────
#: 일반 목적 비트 11. 켜지 않으면 한글 파일 이름이 CP437로 읽혀 깨진다.
UTF8_NAMES = 0x0800


def unzip(data):
    """ZIP 바이트 → {파일명: bytes}. 중앙 디렉터리 순서를 보존한다."""
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise JsError('zip 형식이 아닙니다') from exc
    files = {}
    with zf:
        for info in zf.infolist():
            name = info.filename
            if not info.flag_bits & UTF8_NAMES:
                name = name.encode('cp437').decode('utf-8', 'replace')
            files[name] = zf.read(info)
    return files


def zip_bytes(files, stored=('mimetype',)):
    """{파일명: bytes|str} → ZIP 바이트. `stored`에 든 이름은 압축하지 않는다."""
    locals_ = []
    central = []
    offset = 0
    for name, content in files.items():
        data = content.encode('utf-8') if isinstance(content, str) else content
        name_bytes = name.encode('utf-8')
        use_store = name in stored
        if use_store:
            body = data
        else:
            comp = zlib.compressobj(zlib.Z_DEFAULT_COMPRESSION, zlib.DEFLATED, -15)
            body = comp.compress(data) + comp.flush()
        method = 0 if use_store else 8
        crc = zlib.crc32(data) & 0xFFFFFFFF
        local = struct.pack('<IHHHHHIIIHH', 0x04034B50, 20, UTF8_NAMES, method, 0, 0x21,
                            crc, len(body), len(data), len(name_bytes), 0) + name_bytes
        dir_ = struct.pack('<IHHHHHHIIIHHHHHII', 0x02014B50, 20, 20, UTF8_NAMES, method, 0, 0x21,
                           crc, len(body), len(data), len(name_bytes), 0, 0, 0, 0, 0,
                           offset) + name_bytes
        locals_.extend([local, body])
        central.append(dir_)
        offset += len(local) + len(body)
    central_size = sum(len(p) for p in central)
    end = struct.pack('<IHHHHIIH', 0x06054B50, 0, 0, len(central), len(central),
                      central_size, offset, 0)
    return b''.join(locals_ + central + [end])


# ──────────────────────────────────────────────────────────────
# 프로파일
# ──────────────────────────────────────────────────────────────
PT = 100
MM = 283.47


def mm(v):
    return js_round(js_number(v) * MM)


def pt(v):
    return js_round(js_number(v) * PT)


ROMAN = ['Ⅰ', 'Ⅱ', 'Ⅲ', 'Ⅳ', 'Ⅴ', 'Ⅵ', 'Ⅶ', 'Ⅷ', 'Ⅸ', 'Ⅹ', 'Ⅺ', 'Ⅻ']
HANGUL = list('가나다라마바사아자차카타파하')
CIRCLED = list('①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮')

LEVEL_DEFAULTS = {
    'key': '', 'name': '', 'marker': '', 'prefix': '', 'size_pt': 12, 'bold': False,
    'font': 'light', 'color': '#000000', 'left_pt': 0, 'indent_pt': 0, 'spacing_below_pt': 0,
    'line_spacing': 160, 'align': 'JUSTIFY',
}

TABLE_CELL_DEFAULTS = {
    'size_pt': 11, 'bold': False, 'font': 'light', 'color': '#000000', 'left_pt': 0,
    'indent_pt': 0, 'prefix': '', 'spacing_below_pt': 0, 'line_spacing': 120, 'align': 'CENTER',
}

DEFAULT_PROFILE = {
    'schema': 'hwpx-studio.profile.v1',
    'name': '기본',
    'mode': 'outline',
    'fonts': {'bold': '맑은 고딕', 'light': '맑은 고딕', 'fallback': '맑은 고딕'},
    'page': {'size': 'A4', 'margin_mm': {'left': 20, 'right': 20, 'top': 10, 'bottom': 10,
                                          'header': 10, 'footer': 10}},
    'levels': [],
    'body': {
        'name': '본문', 'size_pt': 12, 'font': 'light', 'color': '#000000', 'bold': False,
        'left_pt': 0, 'indent_pt': 0, 'spacing_below_pt': 0, 'line_spacing': 160,
        'align': 'JUSTIFY', 'first_line_indent_pt': 0, 'spacing_above_pt': 0, 'letter_spacing': 0,
    },
    'table': {
        'border_color': '#999999', 'header_bg': '#4472C4', 'width_mm': 162.5,
        'cell_margin_mm': 0.3, 'treat_as_char': True, 'anchor_level': None,
        'top': {**TABLE_CELL_DEFAULTS, 'name': '표(위)', 'eng_name': 'Table(Top)', 'bold': True,
                'font': 'bold', 'color': '#FFFFFF'},
        'mid': {**TABLE_CELL_DEFAULTS, 'name': '표(중간)', 'eng_name': 'Table(Mid)'},
        'left': {**TABLE_CELL_DEFAULTS, 'name': '표(왼쪽)', 'eng_name': 'Table(Left)',
                 'align': 'LEFT', 'indent_pt': 12, 'prefix': '· '},
    },
    'image': {'default_width_mm': 120, 'treat_as_char': True},
    'footnote': {
        'name': '각주', 'eng_name': 'Footnote', 'size_pt': 8, 'bold': False, 'font': 'light',
        'color': '#808080', 'left_pt': 0, 'indent_pt': 0, 'spacing_below_pt': 0,
        'line_spacing': 130, 'align': 'JUSTIFY',
    },
    'diagram': {
        'render': 'table', 'box_fill': '#DCE6F1', 'box_border': '#1F3864',
        'box_color': '#000000', 'root_fill': '#1F3864', 'root_color': '#FFFFFF',
        'line_color': '#1F3864', 'line_width_mm': 0.3, 'font_size_pt': 11, 'col_width_mm': 28,
        'col_gap_mm': 6, 'grid_resolution': 6, 'row_height_mm': 9, 'row_gap_mm': 7,
        'max_width_mm': 160,
    },
    'rules': {
        'min_children': {}, 'period_policy': 'single_sentence_no_period',
        'footnote_position': 'before_period',
    },
    # 표·그림 번호 모양. {장}은 장 번호, {번호}는 그 장 안의 순번. 장이 없으면 `{장}-`를 뺀다
    'captions': {'table': '〈표 {장}-{번호}〉', 'figure': '〔그림 {장}-{번호}〕'},
}


def is_plain_object(v):
    return isinstance(v, dict)


def deep_merge(base, override):
    if is_plain_object(base) and is_plain_object(override):
        out = dict(base)
        for k, v in override.items():
            out[k] = deep_merge(base[k], v) if k in base else copy.deepcopy(v)
        return out
    return copy.deepcopy(override)


def merge_profile(user=None):
    """사용자 프로파일에 기본값을 채운다. 레벨마다 key·name·marker도 채운다."""
    user = {} if user is None else user
    rest = dict(user)
    rest.pop('levels', None)
    merged = deep_merge(copy.deepcopy(DEFAULT_PROFILE), rest)
    levels = []
    for i, lv in enumerate(_or(user.get('levels'), [])):
        item = deep_merge(LEVEL_DEFAULTS, lv)
        if not js_truthy(item.get('key')):
            item['key'] = f'L{i + 1}'
        if not js_truthy(item.get('name')):
            item['name'] = item['key']
        if not js_truthy(item.get('marker')):
            prefix = js_str(item.get('prefix'))
            item['marker'] = '' if prefix.startswith('AUTO_') else js_trim(prefix)
        levels.append(item)
    merged['levels'] = levels
    for key in ('top', 'mid', 'left'):
        merged['table'][key] = deep_merge(TABLE_CELL_DEFAULTS, _or(merged['table'].get(key), {}))
    return merged


def body_levels(profile):
    return [lv for lv in profile['levels'] if not js_str(_or(lv.get('prefix'), '')).startswith('AUTO_')]


# ──────────────────────────────────────────────────────────────
# 마커 텍스트 파서
# ──────────────────────────────────────────────────────────────
IMAGE_RE = re.compile(r'^!\[[^\]]*\]\(([^)]+)\)' + S + r'*\Z')
TABLE_SEP_RE = re.compile(r'^\|(?:' + S + r'|[:|-])+\|\Z')
FENCE_RE = re.compile(r'^:::' + S + r'*(?:diagram)?' + S + r'*(' + DOT + r'*)\Z')
FOOTNOTE_REF_RE = re.compile(r'\[\^((?:(?!' + S + r')[^\]])+)\]')
FOOTNOTE_DEF_RE = re.compile(r'^\[\^((?:(?!' + S + r')[^\]])+)\]:' + S + r'*(' + DOT + r'*)\Z')


def parse_text(text, profile):
    """마커 텍스트 → 항목 목록. (items, line_of, warnings)"""
    markers = sorted(([lv['marker'], lv['key']] for lv in profile['levels']
                      if js_truthy(lv.get('marker'))), key=lambda p: -len(p[0]))
    fallback = [lv['key'] for lv in body_levels(profile)]
    # 마커가 없는 레벨 — 마커 없는 줄이 갈 제자리(예: 크라운판의 바탕글)
    home = next((lv for lv in body_levels(profile) if not js_truthy(lv.get('marker'))), {})
    plain_home = _or(home.get('key'), None)
    narrative = profile.get('mode') == 'narrative'

    items = []
    line_of = []
    warnings = []
    notes = {}          # 라벨 → {text, line, used}

    def push(item, line):
        items.append(item)
        line_of.append(line)

    lines = re.sub(r'\r\n?', '\n', text).split('\n')
    i = 0
    while i < len(lines):
        raw = js_rtrim(lines[i])
        lineno = i + 1
        stripped = js_trim(raw)

        if not stripped:
            push({'type': 'blank'}, lineno)
            i += 1
            continue

        definition = FOOTNOTE_DEF_RE.match(stripped)
        if definition:
            label = definition.group(1)
            body_text = js_trim(definition.group(2))
            if label in notes:
                warnings.append(f'{lineno}행: 각주 [^{label}]의 내용이 두 번 적힘 → 뒤엣것을 씀')
            if not body_text:
                warnings.append(f'{lineno}행: 각주 [^{label}]의 내용이 비어 있음')
            notes[label] = {'text': body_text, 'line': lineno, 'used': 0}
            next_blank = i + 1 >= len(lines) or not js_trim(lines[i + 1])
            if next_blank and items and items[-1]['type'] == 'blank':
                items.pop()
                line_of.pop()
            i += 1
            continue

        fence = FENCE_RE.match(stripped) if stripped.startswith(':::') else None
        if fence:
            header = js_trim(fence.group(1))
            body = []
            i += 1
            while i < len(lines) and not js_trim(lines[i]).startswith(':::'):
                body.append(js_rtrim(lines[i]))
                i += 1
            i += 1
            spec = parse_diagram_block(header, body)
            if not spec['lines']:
                warnings.append(f'{lineno}행: 내용이 빈 도식 블록')
            push({'type': 'diagram', 'spec': spec}, lineno)
            continue

        if IMAGE_RE.match(stripped):
            warnings.append(f'{lineno}행: 웹 버전은 그림 삽입을 지원하지 않습니다(무시됨)')
            i += 1
            continue

        if stripped.startswith('|') and stripped.endswith('|'):
            rows = []
            start = lineno
            while i < len(lines):
                cur = js_trim(lines[i])
                if not (cur.startswith('|') and cur.endswith('|')):
                    break
                if not TABLE_SEP_RE.match(cur):
                    rows.append([js_trim(c) for c in cur[1:-1].split('|')])
                i += 1
            if rows:
                cols = max(len(r) for r in rows)
                data = []
                for row in rows:
                    for c in range(cols):
                        data.append(row[c] if c < len(row) else '')
                push({'type': 'table', 'rows': len(rows), 'cols': cols, 'data': data}, start)
            continue

        matched = match_marker(stripped, markers)
        if matched['warn']:
            warnings.append(f"{lineno}행: {matched['warn']}")
        if matched['key'] is not None:
            push({'type': 'para', 'key': matched['key'], 'text': matched['text']}, lineno)
            i += 1
            continue

        if narrative or not fallback:
            push({'type': 'para', 'key': 'body', 'text': stripped}, lineno)
        elif js_truthy(plain_home):
            push({'type': 'para', 'key': plain_home, 'text': stripped}, lineno)
        else:
            expanded = raw.replace('\t', '  ')
            indent = len(expanded) - len(expanded.lstrip(' '))
            depth = min(indent // 2, len(fallback) - 1)
            warnings.append(f'{lineno}행: 마커 없는 줄 → 들여쓰기 {indent}칸으로 '
                            f'{js_str(fallback[depth])} 레벨 적용')
            push({'type': 'para', 'key': fallback[depth], 'text': stripped}, lineno)
        i += 1
    resolve_footnotes(items, line_of, warnings, notes)
    return {'items': items, 'lineOf': line_of, 'warnings': warnings}


def resolve_footnotes(items, line_of, warnings, notes):
    """본문의 `[^라벨]` 자리표를 각주 내용과 잇는다."""
    def has_ref(s):
        return FOOTNOTE_REF_RE.search(js_str(s)) is not None

    for idx, item in enumerate(items):
        line = line_of[idx] if idx < len(line_of) else idx + 1
        if item['type'] == 'table':
            if any(has_ref(s) for s in _or(item.get('data'), [])):
                warnings.append(f'{line}행: 표 안에는 각주를 달 수 없음 → 표 아래 문단에 달 것')
            continue
        if item['type'] == 'diagram':
            spec = item.get('spec') or {}
            if any(has_ref(s) for s in _or(spec.get('lines'), [])):
                warnings.append(f'{line}행: 도식 상자 안에는 각주를 달 수 없음 → 도식 아래 문단에 달 것')
            continue
        if item['type'] != 'para':
            continue
        text = js_str(_or(item.get('text'), ''))
        if '[^' not in text:
            continue
        split = split_notes(text, notes, warnings, line)
        item['text'] = split['text']
        if split['found']:
            item['notes'] = split['found']

    for label, note in notes.items():
        if not note['used']:
            warnings.append(f"{note['line']}행: 각주 [^{label}]을 본문에서 부르지 않음 → 만들지 않음")


def split_notes(text, notes, warnings, line):
    out = []
    found = []
    pos = 0
    for m in FOOTNOTE_REF_RE.finditer(text):
        out.append(text[pos:m.start()])
        pos = m.end()
        label = m.group(1)
        note = notes.get(label)
        if note is None:
            warnings.append(f'{line}행: 각주 [^{label}]의 내용을 찾지 못함 '
                            f'(`[^{label}]: 내용` 줄이 없음) → 본문에 그대로 남김')
            out.append(m.group(0))
        else:
            note['used'] += 1
            if note['used'] > 1:
                warnings.append(f'{line}행: 각주 [^{label}]을 두 번 이상 부름 → '
                                '한글에는 같은 각주를 다시 못 쓰므로 따로 만들어짐')
            before = ''.join(out)
            found.append({
                'label': label, 'text': note['text'], 'offset': len(before),
                'before': before[-1:], 'after': text[pos:pos + 1],
            })
    out.append(text[pos:])
    return {'text': ''.join(out), 'found': found}


def match_marker(text, markers):
    for marker, key in markers:
        if text.startswith(f'{marker} ') or text == marker:
            rest = js_trim(text[len(marker):])
            warn = None
            while rest.startswith(f'{marker} ') or rest == marker:
                rest = js_trim(rest[len(marker):])
                warn = f"마커 '{marker}'가 중복 입력됨 → 1회만 인식"
            return {'key': key, 'text': rest, 'warn': warn}
    return {'key': None, 'text': text, 'warn': None}


# ──────────────────────────────────────────────────────────────
# 본문 검사
# ──────────────────────────────────────────────────────────────
SENTENCE_SPLIT = re.compile(r'(?<=[.!?])' + S + '+')
_PARSER_WARN = re.compile(r'^([0-9]+)행: (' + DOT + r'*)\Z')


def lint_items(items, profile, line_of=(), parser_warnings=()):
    """문단·표·도식을 검사해 문제 목록을 낸다."""
    order = [lv['key'] for lv in profile['levels']]
    depth_of = {k: i for i, k in enumerate(order)}
    markers = sorted({lv.get('marker'): None for lv in profile['levels']
                      if js_truthy(lv.get('marker'))}, key=utf16_key)
    auto_keys = {lv['key'] for lv in profile['levels']
                 if js_str(lv.get('prefix')).startswith('AUTO_')}
    rules = profile.get('rules') or {}
    min_children = _or(rules.get('min_children'), {})
    policy = _or(rules.get('period_policy'), 'single_sentence_no_period')
    position = _or(rules.get('footnote_position'), 'before_period')
    issues = []
    note_no = 0

    for text in parser_warnings:
        m = _PARSER_WARN.match(text)
        issues.append({'severity': 'warn', 'line': js_number(m.group(1)) if m else 0,
                       'code': 'parser', 'message': m.group(2) if m else text})

    paras = [(item, idx) for idx, item in enumerate(items) if item['type'] == 'para']

    for pos, (item, idx) in enumerate(paras):
        key = _or(item.get('key'), 'body')
        line = line_of[idx] if idx < len(line_of) else idx + 1
        text = js_str(_or(item.get('text'), ''))
        depth = depth_of.get(key)

        if key != 'body' and depth is None:
            issues.append({'severity': 'error', 'line': line, 'code': 'level',
                           'message': f'프로파일에 없는 레벨: {js_str(key)}'})
            continue
        if not js_trim(text):
            issues.append({'severity': 'warn', 'line': line, 'code': 'empty',
                           'message': '내용이 빈 문단'})

        stray = next((marker for marker in markers
                      if marker and marker != '-' and marker != '#'
                      and re.search('(^|' + S + ')' + re.escape(marker) + '(?=' + S + ')', text)),
                     None)
        if stray is not None:
            issues.append({'severity': 'warn', 'line': line, 'code': 'symbol',
                           'message': f"본문에 레벨 기호 '{stray}'가 들어 있음 → 마커와 혼동 가능"})

        if key not in auto_keys:
            issues.extend(period_issues(text, line, policy))

        for note in _or(item.get('notes'), []):
            note_no += 1
            issues.extend(footnote_issues(note, note_no, line, key in auto_keys, position))

        need = min_children.get(key) if isinstance(min_children, dict) else None
        if js_truthy(need) and depth is not None:
            count = 0
            for later, _ in paras[pos + 1:]:
                child_depth = depth_of.get(_or(later.get('key'), 'body'))
                if child_depth is None:
                    continue
                if child_depth <= depth:
                    break
                if child_depth == depth + 1:
                    count += 1
            if count < js_number(need):
                issues.append({'severity': 'warn', 'line': line, 'code': 'balance',
                               'message': f'{js_str(key)} 아래 하위 항목이 {count}개 '
                                          f'(권장 {js_str(need)}개 이상): {text[:20]}'})

        if pos > 0 and depth is not None:
            prev = paras[pos - 1][0]
            prev_depth = depth_of.get(_or(prev.get('key'), 'body'))
            if prev_depth is not None and depth - prev_depth > 1:
                issues.append({'severity': 'warn', 'line': line, 'code': 'jump',
                               'message': f"{js_str(prev.get('key'))} 다음에 {js_str(key)}가 나옴 "
                                          '→ 중간 레벨 생략'})

    for i, item in enumerate(items):
        if item['type'] not in ('table', 'diagram'):
            continue
        label = '표' if item['type'] == 'table' else '도식'
        line = line_of[i] if i < len(line_of) else i + 1
        before = items[i - 1]['type'] if i > 0 else 'blank'
        after = items[i + 1]['type'] if i + 1 < len(items) else 'blank'
        if before != 'blank':
            issues.append({'severity': 'warn', 'line': line, 'code': 'spacing',
                           'message': f'{label} 앞에 빈 줄이 없음'})
        if after != 'blank':
            issues.append({'severity': 'warn', 'line': line, 'code': 'spacing',
                           'message': f'{label} 뒤에 빈 줄이 없음'})

    issues.sort(key=lambda it: (it['line'], it['code']))
    return issues


SENTENCE_END = '.。!?'


def footnote_issues(note, number, line, in_heading, position):
    """각주 번호를 놓은 자리 검사."""
    out = []
    label = js_str(_nn(note.get('label'), ''))
    before = js_str(_nn(note.get('before'), ''))
    after = js_str(_nn(note.get('after'), ''))
    where = f'각주 {number}'

    def warn(message):
        out.append({'severity': 'warn', 'line': line, 'code': 'footnote', 'message': message})

    if in_heading:
        warn(f'{where}: 제목에 각주를 닮 → 본문 문단으로 옮길 것')
    if not before:
        warn(f'{where}: 문단 맨 앞에 번호가 옴 → 근거가 되는 말 뒤에 붙일 것')
    elif not js_trim(before):
        warn(f'{where}: 번호 앞에 빈칸이 있음 → 앞말에 붙여 쓸 것')
    if position == 'before_period' and before and before in SENTENCE_END:
        warn(f'{where}: 마침표 뒤에 번호가 옴 → 마침표 앞에 붙일 것')
    elif position == 'after_period' and after and after in SENTENCE_END:
        warn(f'{where}: 마침표 앞에 번호가 옴 → 마침표 뒤에 붙일 것')
    if re.match(r'[0-9]+\Z', label) and js_number(label) != number:
        warn(f'[^{label}]로 적었지만 문서 순서로는 {number}번째 각주 → '
             '번호는 한글이 매기므로 라벨과 다를 수 있음')
    return out


def period_issues(text, line, policy):
    stripped = js_trim(text)
    if not stripped or policy == 'off':
        return []
    sentences = [s for s in SENTENCE_SPLIT.split(stripped) if s]
    ends_with_period = stripped.endswith('.')
    out = []
    if policy == 'single_sentence_no_period':
        if len(sentences) == 1 and ends_with_period:
            out.append({'severity': 'warn', 'line': line, 'code': 'period', 'message': '단문인데 온점이 붙음'})
        elif len(sentences) > 1 and not ends_with_period:
            out.append({'severity': 'warn', 'line': line, 'code': 'period',
                        'message': '두 문장 이상인데 끝 온점이 없음'})
    elif policy == 'always_period' and not ends_with_period:
        out.append({'severity': 'warn', 'line': line, 'code': 'period', 'message': '온점으로 끝나야 함'})
    elif policy == 'never_period' and ends_with_period:
        out.append({'severity': 'warn', 'line': line, 'code': 'period', 'message': '온점을 쓰지 않는 규칙'})
    return out


# ──────────────────────────────────────────────────────────────
# 도식
# ──────────────────────────────────────────────────────────────
ARROW_SPLIT = re.compile(S + r'*(?:→|->|=>|▶|>)' + S + '*')
MIN_BOX_WIDTH_MM = 12
#: DB 구성도 상자 폭. 필드 이름에 `(PK)`가 붙어 기본 상자보다 넓다
DB_BOX_WIDTH_MM = 45
DB_KEY_MARKS = {'*': 'PK', '+': 'FK'}
DB_ENTITY = re.compile(r'^\[(' + DOT + r'+?)\]' + S + r'*(\{' + DOT + r'*\})?\Z')

LINE_TYPES = {
    'solid': 'SOLID', 'dash': 'DASH', 'dot': 'DOT',
    'dashdot': 'DASH_DOT', 'dashdotdot': 'DASH_DOT_DOT', 'longdash': 'LONG_DASH',
}
BLOCK_COLOR_OPTIONS = ['box_fill', 'box_border', 'box_color', 'root_fill', 'root_color', 'line_color']
TOKEN_RE = re.compile('(?:' + NS.replace('[^', '[^"\'') + '+|"[^"]*"|\'[^\']*\')+')
QUOTE_EDGE = re.compile('^["\']|["\']\\Z')


def normalize_color(value):
    if not js_truthy(value):
        return None
    v = re.sub('^#', '', js_trim(js_str(value)))
    if re.match(r'[0-9a-fA-F]{3}\Z', v):
        v = ''.join(c + c for c in v)
    return f'#{v.upper()}' if re.match(r'[0-9a-fA-F]{6}\Z', v) else None


def normalize_line_type(value):
    if not js_truthy(value):
        return None
    v = re.sub('[-_]', '', js_trim(js_str(value)).lower())
    if v in ('점선', '파선'):
        v = 'dash'
    elif v == '실선':
        v = 'solid'
    return LINE_TYPES.get(v)


_ATTRS_RE = re.compile(S + r'*\{([^{}]*)\}' + S + r'*\Z')


def split_attrs(text):
    """`기획부 {fill=#DCE6F1 color=#000}` → (텍스트, 속성)"""
    m = _ATTRS_RE.search(text)
    if not m:
        return js_trim(text), {}
    attrs = {}
    for token in TOKEN_RE.findall(m.group(1).replace(',', ' ')):
        eq = token.find('=')
        if eq > 0:
            attrs[js_trim(token[:eq]).lower()] = QUOTE_EDGE.sub('', js_trim(token[eq + 1:]))
    return js_trim(text[:m.start()]), attrs


def node_style(attrs):
    style = {}
    for key in ('fill', 'color', 'border', 'link_color'):
        raw = js_trim(js_str(_or(attrs.get(key), ''))).lower()
        if key == 'border' and raw in ('none', '없음'):
            style['border'] = 'none'
            continue
        color = normalize_color(attrs.get(key))
        if color:
            style[key] = color
    raw_link = js_trim(js_str(_or(attrs.get('link'), ''))).lower()
    if raw_link in ('none', '없음'):
        style['link'] = 'none'
    else:
        link = normalize_line_type(attrs.get('link'))
        if link:
            style['link'] = link
    return style


def _opt(spec, key):
    options = spec.get('options')
    return options.get(key) if isinstance(options, dict) else None


def effective_diagram(spec, profile):
    """블록 헤더 옵션으로 프로파일의 diagram 설정을 덮어쓴 사본"""
    dia = dict(profile['diagram'])
    for key in BLOCK_COLOR_OPTIONS:
        color = normalize_color(_opt(spec, key))
        if color:
            dia[key] = color
    line_type = normalize_line_type(_opt(spec, 'line_style'))
    if line_type:
        dia['line_type'] = line_type
    return dia


def parse_diagram_block(header, lines):
    options = {}
    for token in TOKEN_RE.findall(header):
        eq = token.find('=')
        if eq > 0:
            options[js_trim(token[:eq])] = QUOTE_EDGE.sub('', js_trim(token[eq + 1:]))
    type_ = _or(options.get('type'), 'org')
    options.pop('type', None)
    if type_ not in ('org', 'flow', 'matrix', 'strategy', 'db'):
        type_ = 'org'
    title = _or(options.get('title'), '')
    options.pop('title', None)
    body = [js_rtrim(line) for line in lines]
    while body and not js_trim(body[0]):
        body.pop(0)
    while body and not js_trim(body[-1]):
        body.pop()
    return {'type': type_, 'title': title, 'options': options, 'lines': body}


def parse_tree(lines):
    entries = []
    for raw in lines:
        if not js_trim(raw):
            continue
        expanded = raw.replace('\t', '  ')
        stripped = expanded.lstrip(' ')
        indent = len(expanded) - len(stripped)
        text, attrs = split_attrs(re.sub('^[-*•]' + S + '+', '', js_trim(stripped), count=1))
        if text:
            entries.append((indent, text, node_style(attrs)))
    roots = []
    stack = []
    for indent, text, style in entries:
        node = {'text': text, 'depth': 0, 'children': [], 'center': 0, 'row': 0, 'style': style}
        while stack and stack[-1][0] >= indent:
            stack.pop()
        if stack:
            parent = stack[-1][1]
            node['depth'] = parent['depth'] + 1
            parent['children'].append(node)
        else:
            roots.append(node)
        stack.append((indent, node))
    return roots


def leaf_count(node):
    return sum(leaf_count(c) for c in node['children']) if node['children'] else 1


def max_depth(nodes):
    d = 0
    for n in nodes:
        d = max(d, n['depth'] + 1, max_depth(n['children']))
    return d


def walk(nodes):
    for node in nodes:
        yield node
        yield from walk(node['children'])


BOX_BORDERS = ['left', 'right', 'top', 'bottom']


def _cell(row, col, text, borders, fill, char, col_span, row_span,
          text_color=None, border_color=None, border_type=None):
    return {'row': row, 'col': col, 'text': text, 'borders': borders, 'fill': fill,
            'char': char, 'colSpan': col_span, 'rowSpan': row_span, 'textColor': text_color,
            'borderColor': border_color, 'borderType': border_type}


def _empty_grid(dia):
    return {'rows': 1, 'cols': 1, 'colWidths': [dia['col_width_mm']],
            'rowHeights': [dia['row_height_mm']], 'cells': [],
            'warnings': ['도식 내용이 비어 있음'], 'fallbackToImage': False}


def build_grid(spec, profile, force=False):
    effective = {**profile, 'diagram': effective_diagram(spec, profile)}
    layout = js_str(_or(_opt(spec, 'layout'), '')).lower()
    if spec['type'] == 'flow':
        grid = grid_flow(spec, effective)
    elif spec['type'] == 'matrix':
        grid = grid_matrix(spec, effective)
    elif spec['type'] == 'strategy':
        grid = grid_strategy(spec, effective)
    elif spec['type'] == 'db':
        grid = grid_db(spec, effective)
    elif layout.startswith('side'):
        grid = grid_org_side(spec, effective)
    else:
        grid = grid_org(spec, effective)
        if grid['fallbackToImage'] and not layout:
            side = grid_org_side(spec, effective)
            side['warnings'] = [w for w in grid['warnings'] if '이미지로 폴백' not in w]
            side['warnings'].append('가로로 늘어놓기에는 상자가 많아 세로 목록형으로 배치했다'
                                    '(가로를 원하면 width를 늘리거나 layout=wide)')
            grid = side
    grid['title'] = _or(spec.get('title'), '')
    grid['diagram'] = effective['diagram']
    line_type = effective['diagram'].get('line_type')
    if js_truthy(line_type):
        for cell in grid['cells']:
            if not js_truthy(cell['text']) and not js_truthy(cell['fill']) \
                    and not js_truthy(cell['borderType']):
                cell['borderType'] = line_type
    max_w = js_number(_or(_opt(spec, 'width'), effective['diagram'].get('max_width_mm')))
    if force:
        grid['fallbackToImage'] = False
    if total_width(grid) > max_w + 0.01 and not force:
        grid['warnings'].append(f'도식 폭 {to_fixed(total_width(grid), 0)}mm > 최대 {js_str(max_w)}mm')
    return grid


def total_width(grid):
    return js_sum(grid['colWidths'])


def total_height(grid):
    return js_sum(grid['rowHeights'])


def fit_box_width(slots, profile, max_w):
    box_w = js_number(profile['diagram'].get('col_width_mm'))
    gap = js_number(profile['diagram'].get('col_gap_mm'))
    if slots <= 0 or slots * box_w + (slots - 1) * gap <= max_w:
        return box_w, gap
    gap = js_max(2, gap * 0.5)
    box_w = (max_w - (slots - 1) * gap) / slots
    return box_w, gap


def _box_cols(dia):
    box_cols = js_number(_or(dia.get('grid_resolution'), 6))
    return js_max(2, _norm_num(box_cols + js_mod(box_cols, 2)))


def _fill_array(n, value):
    if not isinstance(n, int) or n < 0:
        raise JsError('Invalid array length')
    return [value] * n


def grid_org(spec, profile):
    dia = profile['diagram']
    warnings = []
    roots = parse_tree(spec['lines'])
    if not roots:
        return _empty_grid(dia)

    box_cols = _box_cols(dia)
    half = _norm_num(box_cols / 2)

    leaves = sum(leaf_count(r) for r in roots)
    depth = max_depth(roots)
    max_w = js_number(_or(_opt(spec, 'width'), dia.get('max_width_mm')))
    box_w, gap = fit_box_width(leaves, profile, max_w)

    unit = box_w / box_cols
    gap_cols = js_max(2, 2 * js_max(1, js_round(gap / (2 * unit))))
    stride = box_cols + gap_cols
    cols = stride * leaves - gap_cols

    if cols * unit > max_w:
        unit = max_w / cols
        box_w = unit * box_cols
    too_narrow = box_w < MIN_BOX_WIDTH_MM
    if too_narrow:
        warnings.append(f'같은 단계 상자가 {leaves}개여서 폭이 {to_fixed(box_w, 1)}mm까지 좁아짐')
    elif abs(box_w - js_number(dia.get('col_width_mm'))) > 0.5:
        warnings.append(f'도식 상자 폭을 {to_fixed(box_w, 1)}mm로 자동 축소')

    slot = 0

    def assign(node):
        nonlocal slot
        if not node['children']:
            center = stride * slot + half - 1
            slot += 1
        else:
            centers = [assign(c) for c in node['children']]
            center = js_floor((centers[0] + centers[-1]) / 2)
        node['center'] = center
        return center

    for r in roots:
        assign(r)

    rows = 3 * depth - 2 if depth else 1
    row_heights = []
    for d in range(depth):
        row_heights.append(js_number(dia.get('row_height_mm')))
        if d < depth - 1:
            row_heights.extend([js_number(dia.get('row_gap_mm')) / 2,
                                js_number(dia.get('row_gap_mm')) / 2])

    cells = []
    for node in walk(roots):
        node['row'] = 3 * node['depth']
        start = js_max(0, js_min(node['center'] - (half - 1), cols - box_cols))
        cells.append(_cell(
            node['row'], start, node['text'], list(BOX_BORDERS),
            _or(node['style'].get('fill'), dia['root_fill'] if node['depth'] == 0 else dia['box_fill']),
            'diagram_root' if node['depth'] == 0 else 'diagram', box_cols, 1,
            _or(node['style'].get('color'), None), _or(node['style'].get('border'), None), None))
    for node in walk(roots):
        if not node['children']:
            continue
        row_a = 3 * node['depth'] + 1
        row_b = row_a + 1
        by_center = {}
        for c in node['children']:
            by_center[c['center']] = c
        centers = sorted(by_center)
        add_border(cells, row_a, node['center'], 'right')
        for col in range(centers[0] + 1, centers[-1] + 1):
            child = by_center.get(col)
            add_border(cells, row_b, col, 'top',
                       child['style'].get('link_color') if child else None,
                       child['style'].get('link') if child else None)
        for col in centers:
            child = by_center.get(col)
            add_border(cells, row_b, col, 'right',
                       child['style'].get('link_color') if child else None,
                       child['style'].get('link') if child else None)

    return {'rows': rows, 'cols': cols, 'colWidths': _fill_array(cols, unit),
            'rowHeights': row_heights, 'cells': cells, 'warnings': warnings,
            'fallbackToImage': too_narrow}


_BAND_SEP = re.compile(r'^\|(?:' + S + r'|[:|-])+\|?\Z')


def parse_bands(lines):
    """`라벨 | 칸 | 칸` 줄들을 단으로 묶는다."""
    bands = []
    for raw in lines:
        line = js_trim(raw)
        if not line:
            continue
        if _BAND_SEP.match(line):
            continue
        parts = [js_trim(p) for p in line.split('|')]
        while len(parts) > 1 and not parts[-1]:
            parts.pop()
        head = parts[0]
        cells = parts[1:]
        if not cells:
            head = ''
            cells = [parts[0]]
        row = [(text, node_style(attrs)) for text, attrs in (split_attrs(c) for c in cells) if text]
        if not row:
            continue
        if head:
            label, attrs = split_attrs(head)
            bands.append({'label': label, 'labelStyle': node_style(attrs), 'rows': [row]})
        elif bands:
            bands[-1]['rows'].append(row)
        else:
            bands.append({'label': '', 'labelStyle': {}, 'rows': [row]})
    return bands


def grid_strategy(spec, profile):
    """전략체계도."""
    dia = profile['diagram']
    warnings = []
    bands = parse_bands(spec['lines'])
    if not bands:
        return _empty_grid(dia)

    n_cols = js_max(*[len(r) for b in bands for r in b['rows']], 1)
    has_label = any(b['label'] for b in bands)

    box_cols = _box_cols(dia)
    half = _norm_num(box_cols / 2)

    max_w = js_number(_or(_opt(spec, 'width'), dia.get('max_width_mm')))
    label_w = js_number(_or(_opt(spec, 'label_width'), 22)) if has_label else 0
    box_w, gap = fit_box_width(n_cols, profile, max_w - label_w)
    unit = box_w / box_cols
    gap_cols = js_max(2, 2 * js_max(1, js_round(gap / (2 * unit))))
    stride = box_cols + gap_cols
    content_cols = stride * n_cols - gap_cols
    if content_cols * unit > max_w - label_w:
        unit = (max_w - label_w) / content_cols
        box_w = unit * box_cols
    if box_w < MIN_BOX_WIDTH_MM:
        warnings.append(f'한 단에 칸이 {n_cols}개여서 폭이 {to_fixed(box_w, 1)}mm까지 좁아짐')

    offset = 1 if has_label else 0
    col_widths = ([label_w] if has_label else []) + _fill_array(content_cols, unit)

    def centre(index, span=1):
        first = offset + stride * index + half - 1
        last = offset + stride * (index + span - 1) + half - 1
        return js_floor((first + last) / 2)

    row_h = js_number(dia.get('row_height_mm'))
    row_gap = js_number(dia.get('row_gap_mm'))
    inner_gap = js_max(1, row_gap / 3)

    cells = []
    row_heights = []
    band_rows = []

    for b, band in enumerate(bands):
        if b:
            if band['labelStyle'].get('link') == 'none':
                row_heights.append(inner_gap)
            else:
                row_heights.extend([row_gap / 2, row_gap / 2])
        rows_here = []
        for r, row in enumerate(band['rows']):
            if r:
                row_heights.append(inner_gap)
            rows_here.append(len(row_heights))
            row_heights.append(row_h)
        band_rows.append(rows_here)

        for r, row in enumerate(band['rows']):
            each = js_max(1, n_cols // len(row))
            for i, (text, style) in enumerate(row):
                start = offset + stride * (i * each)
                width = box_cols + stride * (each - 1)
                plain = style.get('border') == 'none'
                cells.append(_cell(
                    rows_here[r], start, text, [] if plain else list(BOX_BORDERS),
                    _or(style.get('fill'), None if plain else dia['box_fill']),
                    'diagram', js_min(width, len(col_widths) - start), 1,
                    _or(style.get('color'), None),
                    None if plain else _or(style.get('border'), None), None))

        if has_label and band['label']:
            style = band['labelStyle']
            plain = style.get('border') == 'none'
            cells.append(_cell(
                rows_here[0], 0, band['label'], [] if plain else list(BOX_BORDERS),
                _or(style.get('fill'), dia['root_fill']), 'diagram_root',
                1, rows_here[-1] - rows_here[0] + 1,
                _or(style.get('color'), None),
                None if plain else _or(style.get('border'), None), None))

    for b in range(1, len(bands)):
        upper = bands[b - 1]
        lower = bands[b]
        if lower['labelStyle'].get('link') == 'none':
            continue
        row_b = band_rows[b][0] - 1
        row_a = row_b - 1
        line_type = lower['labelStyle'].get('link')
        line_type = None if (not line_type or line_type == 'none') else line_type
        colour = _or(lower['labelStyle'].get('link_color'), None)

        top_row = upper['rows'][-1]
        bottom_row = lower['rows'][0]
        each_t = js_max(1, n_cols // len(top_row))
        each_b = js_max(1, n_cols // len(bottom_row))
        tops = [centre(i * each_t, each_t) for i in range(len(top_row))]
        bottoms = [centre(i * each_b, each_b) for i in range(len(bottom_row))]

        for col in tops:
            add_border(cells, row_a, col, 'right', colour, line_type)
        same = tops == bottoms
        if not same:
            spread = sorted(dict.fromkeys(tops + bottoms))
            for col in range(spread[0] + 1, spread[-1] + 1):
                add_border(cells, row_b, col, 'top', colour, line_type)
        for col in bottoms:
            add_border(cells, row_b, col, 'right', colour, line_type)

    return {'rows': len(row_heights), 'cols': len(col_widths), 'colWidths': col_widths,
            'rowHeights': row_heights, 'cells': cells, 'warnings': warnings,
            'fallbackToImage': False}


def grid_org_side(spec, profile):
    """세로 목록형 계층도. 상자를 한 줄에 하나씩 쌓고 단계마다 오른쪽으로 들여쓴다."""
    dia = profile['diagram']
    warnings = []
    roots = parse_tree(spec['lines'])
    if not roots:
        return _empty_grid(dia)

    nodes = list(walk(roots))
    depth = max_depth(roots)
    max_w = js_number(_or(_opt(spec, 'width'), dia.get('max_width_mm')))

    step = js_max(4, js_number(dia.get('col_gap_mm')))
    spine_w = step / 2
    box_w = js_number(dia.get('col_width_mm')) * 2
    if step * (depth - 1) + box_w > max_w:
        box_w = js_max(MIN_BOX_WIDTH_MM, max_w - step * (depth - 1))
        warnings.append(f'세로 목록형: 상자 폭을 {to_fixed(box_w, 1)}mm로 맞춤')
    col_widths = []
    for _ in range(depth - 1):
        col_widths.extend([spine_w, spine_w])
    col_widths.append(box_w)
    last_col = len(col_widths) - 1

    row_h = js_number(dia.get('row_height_mm')) / 2
    gap_h = js_max(1, js_number(dia.get('row_gap_mm')) / 3)
    cells = []
    row_heights = []
    row_of = {}

    for i, node in enumerate(nodes):
        if i:
            row_heights.append(gap_h)
        top = len(row_heights)
        row_of[id(node)] = top
        row_heights.extend([row_h, row_h])
        col = min(2 * node['depth'], last_col)
        cells.append(_cell(
            top, col, node['text'], list(BOX_BORDERS),
            _or(node['style'].get('fill'), dia['root_fill'] if node['depth'] == 0 else dia['box_fill']),
            'diagram_root' if node['depth'] == 0 else 'diagram', last_col - col + 1, 2,
            _or(node['style'].get('color'), None), _or(node['style'].get('border'), None), None))

    for node in nodes:
        if not node['children']:
            continue
        spine = min(2 * node['depth'], last_col)
        if spine >= last_col:
            continue
        last = node['children'][-1]
        for row in range(row_of[id(node)] + 2, row_of[id(last)] + 1):
            add_border(cells, row, spine, 'right')
        for child in node['children']:
            add_border(cells, row_of[id(child)] + 1, spine + 1, 'top',
                       child['style'].get('link_color'), child['style'].get('link'))

    return {'rows': len(row_heights), 'cols': len(col_widths), 'colWidths': col_widths,
            'rowHeights': row_heights, 'cells': cells, 'warnings': warnings,
            'fallbackToImage': False}


def add_border(cells, row, col, edge, color=None, line_type=None):
    found = next((c for c in cells if c['row'] == row and c['col'] == col), None)
    if found is not None:
        if edge not in found['borders']:
            found['borders'] = sorted(dict.fromkeys(found['borders'] + [edge]), key=utf16_key)
        found['borderColor'] = _or(color, found['borderColor'], None)
        found['borderType'] = _or(line_type, found['borderType'], None)
        return
    cells.append(_cell(row, col, '', [edge], None, 'diagram', 1, 1,
                       None, _or(color, None), _or(line_type, None)))


def grid_flow(spec, profile):
    dia = profile['diagram']
    warnings = []
    steps = []
    for line in spec['lines']:
        if not js_trim(line):
            continue
        for part in ARROW_SPLIT.split(js_trim(line)):
            if not js_trim(part):
                continue
            text, attrs = split_attrs(js_trim(part))
            if text:
                steps.append((text, node_style(attrs)))
    if not steps:
        return _empty_grid(dia)
    direction = js_str(_or(_opt(spec, 'direction'), 'right')).lower()
    row_h = js_number(dia.get('row_height_mm'))
    max_w = js_number(_or(_opt(spec, 'width'), dia.get('max_width_mm')))
    cells = []

    if direction.startswith('d'):
        rows = 2 * len(steps) - 1
        box_w = js_min(js_number(dia.get('col_width_mm')) * 2, max_w)
        row_heights = []
        for i, (text, style) in enumerate(steps):
            cells.append(_cell(2 * i, 0, text, list(BOX_BORDERS),
                               _or(style.get('fill'), dia['box_fill']), 'diagram', 1, 1,
                               _or(style.get('color'), None), _or(style.get('border'), None), None))
            if i < len(steps) - 1:
                cells.append(_cell(2 * i + 1, 0, '▼', [], None, 'diagram', 1, 1))
        for i in range(rows):
            row_heights.append(row_h if i % 2 == 0 else js_number(dia.get('row_gap_mm')))
        return {'rows': rows, 'cols': 1, 'colWidths': [box_w], 'rowHeights': row_heights,
                'cells': cells, 'warnings': warnings, 'fallbackToImage': False}

    n = len(steps)
    arrow_w = js_max(4, js_number(dia.get('col_gap_mm')))
    box_w = js_number(dia.get('col_width_mm'))
    if n * box_w + (n - 1) * arrow_w > max_w:
        box_w = js_max(MIN_BOX_WIDTH_MM, (max_w - (n - 1) * arrow_w) / n)
        warnings.append(f'절차도 상자 폭을 {to_fixed(box_w, 1)}mm로 자동 축소')
    col_widths = []
    for i, (text, style) in enumerate(steps):
        cells.append(_cell(0, 2 * i, text, list(BOX_BORDERS),
                           _or(style.get('fill'), dia['box_fill']), 'diagram', 1, 1,
                           _or(style.get('color'), None), _or(style.get('border'), None), None))
        col_widths.append(box_w)
        if i < n - 1:
            cells.append(_cell(0, 2 * i + 1, '→', [], None, 'diagram', 1, 1))
            col_widths.append(arrow_w)
    return {'rows': 1, 'cols': 2 * n - 1, 'colWidths': col_widths, 'rowHeights': [row_h],
            'cells': cells, 'warnings': warnings, 'fallbackToImage': False}


def parse_db(lines):
    """DB 구성도 본문 → (테이블, 관계, 경고)."""
    tables = []
    links = []
    warnings = []
    for raw in lines:
        line = js_trim(raw)
        if not line:
            continue
        if ARROW_SPLIT.search(line):
            parts = [p for p in (js_trim(s) for s in ARROW_SPLIT.split(line)) if p]
            for i in range(len(parts) - 1):
                links.append((parts[i], parts[i + 1]))
            continue
        m = DB_ENTITY.match(line)
        if m:
            name, attrs = split_attrs(js_trim(f"{m.group(1)} {m.group(2) or ''}"))
            tables.append({'name': name, 'style': node_style(attrs), 'fields': []})
            continue
        if not tables:
            warnings.append(f'테이블([이름]) 앞에 적힌 줄은 건너뛴다: {line}')
            continue
        text, attrs = split_attrs(line)
        key = DB_KEY_MARKS.get(text[:1], '')
        if key:
            text = js_trim(text[1:])
        tables[-1]['fields'].append({'text': text, 'key': key, 'style': node_style(attrs)})
    return {'tables': tables, 'links': links, 'warnings': warnings}


def grid_db(spec, profile):
    """DB 구성도."""
    dia = profile['diagram']
    parsed = parse_db(spec['lines'])
    tables, links, warnings = parsed['tables'], parsed['links'], parsed['warnings']
    if not tables:
        return _empty_grid(dia)

    n = len(tables)
    depth = max(len(t['fields']) for t in tables)
    rows = 1 + depth
    max_w = js_number(_or(_opt(spec, 'width'), dia.get('max_width_mm')))
    arrow_w = js_max(4, js_number(dia.get('col_gap_mm')))
    box_w = js_min(DB_BOX_WIDTH_MM, (max_w - (n - 1) * arrow_w) / n)
    if box_w < MIN_BOX_WIDTH_MM:
        box_w = MIN_BOX_WIDTH_MM
        warnings.append(f'테이블이 {n}개라 폭이 모자란다. width를 늘리거나 나눠 그리라')

    row_h = js_number(dia.get('row_height_mm'))
    cells = []
    col_widths = []

    def cell(row, col, text, **extra):
        out = _cell(row, col, text, [], None, 'diagram', 1, 1)
        out.update(extra)
        return out

    for i, table in enumerate(tables):
        col = 2 * i
        style = table['style']
        cells.append(cell(0, col, table['name'], borders=list(BOX_BORDERS),
                          fill=_or(style.get('fill'), dia['root_fill']),
                          textColor=_or(style.get('color'), dia['root_color']),
                          borderColor=_or(style.get('border'), None)))
        for idx, fld in enumerate(table['fields']):
            fstyle = fld['style']
            cells.append(cell(idx + 1, col,
                              f"{fld['text']} ({fld['key']})" if fld['key'] else fld['text'],
                              borders=list(BOX_BORDERS),
                              fill=_or(fstyle.get('fill'), dia['box_fill'] if fld['key'] else None),
                              textColor=_or(fstyle.get('color'), None),
                              borderColor=_or(fstyle.get('border'), None)))
        col_widths.append(box_w)
        if i < n - 1:
            col_widths.append(arrow_w)

    index = {}
    for i, t in enumerate(tables):
        index[t['name']] = i
    for a, b in links:
        if a not in index or b not in index:
            warnings.append(f'관계 `{a} → {b}`에 없는 테이블 이름이 있다')
            continue
        left = index[a]
        right = index[b]
        if abs(left - right) != 1:
            warnings.append(f'관계 `{a} → {b}`는 두 테이블이 붙어 있지 않아 화살표를 못 그렸다'
                            ' (테이블 순서를 바꾸면 그려진다)')
            continue
        cells.append(cell(0, 2 * min(left, right) + 1, '→' if left < right else '←'))

    return {'rows': rows, 'cols': 2 * n - 1, 'colWidths': col_widths,
            'rowHeights': _fill_array(rows, row_h), 'cells': cells, 'warnings': warnings,
            'fallbackToImage': False}


_MATRIX_SEP = re.compile(r'^\|(?:' + S + r'|[:|-])+\|\Z')


def grid_matrix(spec, profile):
    dia = profile['diagram']
    table = []
    for line in spec['lines']:
        s = js_trim(line)
        if not s.startswith('|'):
            continue
        if _MATRIX_SEP.match(s):
            continue
        table.append([split_attrs(js_trim(p)) for p in s[1:-1].split('|')])
    if not table:
        return _empty_grid(dia)
    cols = max(len(r) for r in table)
    max_w = js_number(_or(_opt(spec, 'width'), dia.get('max_width_mm')))
    col_w = js_min(js_number(dia.get('col_width_mm')), max_w / cols)
    cells = []
    for r, row in enumerate(table):
        for c in range(cols):
            text, attrs = row[c] if c < len(row) else ('', {})
            style = node_style(attrs)
            is_head = r == 0 or c == 0
            cells.append(_cell(
                r, c, text, list(BOX_BORDERS),
                _or(style.get('fill'), dia['root_fill'] if (r == 0 and c == 0 and not text)
                    else (dia['box_fill'] if is_head else None)),
                'diagram', 1, 1, _or(style.get('color'), None), _or(style.get('border'), None),
                None))
    return {'rows': len(table), 'cols': cols, 'colWidths': _fill_array(cols, col_w),
            'rowHeights': _fill_array(len(table), js_number(dia.get('row_height_mm'))),
            'cells': cells, 'warnings': [], 'fallbackToImage': False}


# ──────────────────────────────────────────────────────────────
# XML 조각
# ──────────────────────────────────────────────────────────────
def escape_xml(s):
    return js_str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def font_id(key):
    return 0 if key == 'bold' else 1


def intent_of(cfg):
    """`hc:intent` 값. 음수는 내어쓰기, 양수는 첫 줄 들여쓰기. 둘 다 있으면 내어쓰기가 이긴다."""
    hanging = _or(cfg.get('indent_pt'), 0)
    return -pt(hanging) if js_truthy(hanging) else pt(_or(cfg.get('first_line_indent_pt'), 0))


def _n(v):
    """숫자 보간(`${n}`). -0은 0으로 찍힌다."""
    return js_str(v)


def char_pr_xml(id_, size_pt, bold, color='#000000', font=0, border_fill_id=2, letter_spacing=0):
    """글자모양 하나. letter_spacing은 자간 — 음수가 좁히는 쪽이다."""
    b = ' bold="1"' if bold else ''
    f = js_str(font)
    ls = _or(js_number(letter_spacing), 0)
    ls = _n(ls)
    return (f'<hh:charPr id="{_n(id_)}" height="{_n(pt(size_pt))}" textColor="{js_str(color)}" shadeColor="none"'
            f' useFontSpace="0" useKerning="0" symMark="NONE" borderFillIDRef="{_n(border_fill_id)}"{b}>'
            f'<hh:fontRef hangul="{f}" latin="{f}" hanja="{f}" japanese="{f}" other="{f}" symbol="{f}" user="{f}"/>'
            '<hh:ratio hangul="100" latin="100" hanja="100" japanese="100" other="100" symbol="100" user="100"/>'
            f'<hh:spacing hangul="{ls}" latin="{ls}" hanja="{ls}" japanese="{ls}" other="{ls}" symbol="{ls}" user="{ls}"/>'
            '<hh:relSz hangul="100" latin="100" hanja="100" japanese="100" other="100" symbol="100" user="100"/>'
            '<hh:offset hangul="0" latin="0" hanja="0" japanese="0" other="0" symbol="0" user="0"/>'
            '<hh:underline type="NONE" shape="SOLID" color="#000000"/>'
            '<hh:strikeout shape="NONE" color="#000000"/><hh:outline type="NONE"/>'
            '<hh:shadow type="NONE" color="#C0C0C0" offsetX="10" offsetY="10"/></hh:charPr>')


def para_pr_xml(id_, left=0, indent=0, align='JUSTIFY', spacing_below=0, line_spacing=180,
                spacing_above=0):
    """문단모양 하나. indent가 음수면 내어쓰기, 양수면 첫 줄 들여쓰기다."""
    body = ('<hh:margin>'
            f'<hc:intent value="{_n(indent)}" unit="HWPUNIT"/>'
            f'<hc:left value="{_n(left)}" unit="HWPUNIT"/>'
            f'<hc:right value="0" unit="HWPUNIT"/><hc:prev value="{_n(spacing_above)}" unit="HWPUNIT"/>'
            f'<hc:next value="{_n(spacing_below)}" unit="HWPUNIT"/></hh:margin>'
            f'<hh:lineSpacing type="PERCENT" value="{_n(line_spacing)}" unit="HWPUNIT"/>')
    return (f'<hh:paraPr id="{_n(id_)}" tabPrIDRef="0" condense="0" fontLineHeight="0" snapToGrid="1"'
            ' suppressLineNumbers="0" checked="0" textDir="LTR">'
            f'<hh:align horizontal="{js_str(align)}" vertical="BASELINE"/>'
            '<hh:heading type="NONE" idRef="0" level="0"/>'
            '<hh:breakSetting breakLatinWord="KEEP_WORD" breakNonLatinWord="KEEP_WORD" widowOrphan="0"'
            ' keepWithNext="0" keepLines="0" pageBreakBefore="0" lineWrap="BREAK"/>'
            '<hh:autoSpacing eAsianEng="0" eAsianNum="0"/>'
            '<hp:switch><hp:case hp:required-namespace="http://www.hancom.co.kr/hwpml/2016/HwpUnitChar">'
            f'{body}</hp:case><hp:default>{body}</hp:default></hp:switch>'
            '<hh:border borderFillIDRef="2" offsetLeft="0" offsetRight="0" offsetTop="0" offsetBottom="0"'
            ' connect="0" ignoreMargin="0"/></hh:paraPr>')


def border_fill_xml(id_, borders=BOX_BORDERS, color='#000000', fill=None, width='0.12 mm',
                    type_='SOLID'):
    color = js_str(color)

    def edge(name):
        if name in borders:
            return f'<hh:{name}Border type="{js_str(type_)}" width="{width}" color="{color}"/>'
        return f'<hh:{name}Border type="NONE" width="{width}" color="{color}"/>'

    brush = (f'<hc:fillBrush><hc:winBrush faceColor="{js_str(fill)}" hatchColor="#999999" alpha="0"/></hc:fillBrush>'
             if js_truthy(fill) else '')
    return (f'<hh:borderFill id="{_n(id_)}" threeD="0" shadow="0" centerLine="NONE" breakCellSeparateLine="0">'
            '<hh:slash type="NONE" Crooked="0" isCounter="0"/><hh:backSlash type="NONE" Crooked="0" isCounter="0"/>'
            + edge('left') + edge('right') + edge('top') + edge('bottom')
            + f'<hh:diagonal type="NONE" width="{width}" color="{color}"/>{brush}</hh:borderFill>')


def style_xml(id_, name, eng, para_pr, char_pr, next_):
    return (f'<hh:style id="{_n(id_)}" type="PARA" name="{escape_xml(name)}" engName="{escape_xml(eng)}"'
            f' paraPrIDRef="{_n(para_pr)}" charPrIDRef="{_n(char_pr)}" nextStyleIDRef="{_n(next_)}"'
            ' langID="1042" lockForm="0"/>')


# ──────────────────────────────────────────────────────────────
# 엔진
# ──────────────────────────────────────────────────────────────
def next_id(xml, tag, fallback=0):
    ids = [js_number(m) for m in re.findall(f'<{re.escape(tag)} id="([0-9]+)"', xml)]
    return js_max(*ids) + 1 if ids else fallback


def diagram_text_cfg(profile, color):
    return {
        'name': f'도식({color})', 'size_pt': profile['diagram'].get('font_size_pt'), 'bold': True,
        'font': 'bold', 'color': color, 'left_pt': 0, 'indent_pt': 0, 'spacing_below_pt': 0,
        'line_spacing': 130, 'align': 'CENTER',
    }


def style_configs(profile, text_keys=()):
    dia = profile['diagram']
    out = [(lv['key'], lv) for lv in profile['levels']]
    out.extend([('table_top', profile['table']['top']), ('table_mid', profile['table']['mid']),
                ('table_left', profile['table']['left']), ('body', profile['body'])])
    out.append(('diagram', {
        'name': '도식', 'size_pt': dia.get('font_size_pt'), 'bold': True, 'font': 'bold',
        'color': dia.get('box_color'), 'left_pt': 0, 'indent_pt': 0, 'spacing_below_pt': 0,
        'line_spacing': 130, 'align': 'CENTER',
    }))
    out.append(('diagram_root', {
        'name': '도식(강조)', 'size_pt': dia.get('font_size_pt'), 'bold': True, 'font': 'bold',
        'color': dia.get('root_color'), 'left_pt': 0, 'indent_pt': 0, 'spacing_below_pt': 0,
        'line_spacing': 130, 'align': 'CENTER',
    }))
    out.append(('footnote', profile['footnote']))
    for key in text_keys:
        out.append((key, diagram_text_cfg(profile, key[4:])))
    return out


def plan_ids(header_xml, profile, diagram_fills, text_keys=()):
    char_id = next_id(header_xml, 'hh:charPr')
    para_id = next_id(header_xml, 'hh:paraPr')
    bf_id = next_id(header_xml, 'hh:borderFill', 1)

    ids = {'styles': {}, 'chars': {}, 'paras': {}, 'borderBase': bf_id,
           'borderHeader': bf_id + 1, 'diagramFills': {}}
    keys = ([lv['key'] for lv in profile['levels']]
            + ['table_top', 'table_mid', 'table_left', 'body', 'diagram', 'diagram_root',
               'footnote'] + list(text_keys))
    for key in keys:
        ids['chars'][key] = char_id
        char_id += 1
        ids['paras'][key] = para_id
        para_id += 1
    sid = 1
    for lv in profile['levels']:
        ids['styles'][lv['key']] = sid
        sid += 1
    for key in ('table_top', 'table_mid', 'table_left', 'body', 'footnote'):
        ids['styles'][key] = sid
        sid += 1
    ids['styles']['diagram'] = ids['styles']['table_mid']
    ids['styles']['diagram_root'] = ids['styles']['table_mid']
    for key in text_keys:
        ids['styles'][key] = ids['styles']['table_mid']

    fill_id = bf_id + 2
    for key in diagram_fills:
        ids['diagramFills'][key] = fill_id
        fill_id += 1
    return ids


def refs(ids, key):
    k = key if key in ids['styles'] else 'body'
    return {'style': ids['styles'].get(k), 'char': ids['chars'].get(k), 'para': ids['paras'].get(k)}


_FONT0 = re.compile(r'(<hh:font id="0" face=")([^"]+)(")')
_FONT1 = re.compile(r'(<hh:font id="1" face=")([^"]+)(")')
_PARA0 = re.compile(r'<hh:paraPr id="0"[\s\S]*?</hh:paraPr>')
_LINE_SPACING = re.compile(r'(<hh:lineSpacing[^>]*value=")[0-9]+(")')
_WORD_END = '(?![A-Za-z0-9_])'
_STYLES = re.compile(r'<hh:styles' + _WORD_END + r'[\s\S]*?</hh:styles>')


def patch_header(xml, profile, ids, diagram_fills, text_keys=()):
    x = xml
    x = js_replace(x, _FONT0, f"$1{js_str(profile['fonts']['bold'])}$3", global_=True)
    x = js_replace(x, _FONT1, f"$1{js_str(profile['fonts']['light'])}$3", global_=True)

    x = js_replace(x, _PARA0, lambda block: js_replace(
        block, _LINE_SPACING, f"$1{_n(js_number(profile['body'].get('line_spacing')))}$2"))

    cfgs = style_configs(profile, text_keys)
    chars = ''.join(char_pr_xml(
        ids['chars'][key], _nn(cfg.get('size_pt'), 12), js_truthy(cfg.get('bold')),
        _or(cfg.get('color'), '#000000'), font_id(_or(cfg.get('font'), 'light')), 2,
        js_number(_or(cfg.get('letter_spacing'), 0)),
    ) for key, cfg in cfgs)
    x = js_replace(x, '</hh:charProperties>', f'{chars}</hh:charProperties>')

    paras = ''.join(para_pr_xml(
        ids['paras'][key],
        left=pt(_or(cfg.get('left_pt'), 0)),
        indent=intent_of(cfg),
        align=_or(cfg.get('align'), 'JUSTIFY'),
        spacing_below=pt(_or(cfg.get('spacing_below_pt'), 0)),
        line_spacing=js_number(_nn(cfg.get('line_spacing'), 180)),
        spacing_above=pt(_or(cfg.get('spacing_above_pt'), 0)),
    ) for key, cfg in cfgs)
    x = js_replace(x, '</hh:paraProperties>', f'{paras}</hh:paraProperties>')

    fills = (border_fill_xml(ids['borderBase'], color=profile['table'].get('border_color'))
             + border_fill_xml(ids['borderHeader'], color=profile['table'].get('border_color'),
                               fill=profile['table'].get('header_bg')))
    dia = profile['diagram']
    for key, id_ in ids['diagramFills'].items():
        parts = key.split('|')
        parts += [''] * (4 - len(parts))
        border_part, fill_part, color_part, type_part = parts[0], parts[1], parts[2], parts[3]
        borders = border_part.split(',') if border_part else []
        fills += border_fill_xml(
            id_, borders=borders,
            color=color_part or (dia.get('box_border') if fill_part else dia.get('line_color')),
            fill=fill_part or None,
            width=f"{_n(js_number(dia.get('line_width_mm')))} mm",
            type_=type_part or 'SOLID')
    x = js_replace(x, '</hh:borderFills>', f'{fills}</hh:borderFills>')

    for container, item in (('charProperties', 'hh:charPr'), ('paraProperties', 'hh:paraPr'),
                            ('borderFills', 'hh:borderFill')):
        block = re.search(f'<hh:{container}{_WORD_END}[\\s\\S]*?</hh:{container}>', x)
        if block:
            count = block.group(0).count(f'<{item} id="')
            x = js_replace(x, re.compile(f'(<hh:{container}{S}+itemCnt=")[0-9]+(")'),
                           f'$1{count}$2')

    style_items = [(key, cfg) for key, cfg in cfgs
                   if key != 'diagram' and key != 'diagram_root' and not key.startswith('dia:')]
    max_sid = js_max(*[ids['styles'][key] for key, _ in style_items])
    bg = ('<hh:style id="0" type="PARA" name="바탕글" engName="Normal" paraPrIDRef="0"'
          ' charPrIDRef="0" nextStyleIDRef="0" langID="1042" lockForm="0"/>')
    custom = ''.join(
        style_xml(ids['styles'][key], _or(cfg.get('name'), key), _or(cfg.get('eng_name'), key),
                  ids['paras'][key], ids['chars'][key],
                  ids['styles'][key] + 1 if ids['styles'][key] < max_sid else ids['styles'][key])
        for key, cfg in style_items)
    x = js_replace(x, _STYLES, f'<hh:styles itemCnt="{len(style_items) + 1}">{bg}{custom}</hh:styles>')
    return x


def caption_prefix(fmt, chapter, n):
    """캡션 번호. 장 번호가 없으면(0) `{장}`과 뒤따르는 구분 기호를 뺀다."""
    fmt = js_str(fmt)
    if not chapter:
        fmt = re.sub(r'\{장\}[-.·]?', '', fmt)
    return fmt.replace('{장}', js_str(chapter)).replace('{번호}', js_str(n + 1)) + ' '


def auto_prefix(kind, n, chapter=0, captions=None):
    captions = captions if isinstance(captions, dict) else DEFAULT_PROFILE['captions']
    if kind == 'AUTO_ROMAN':
        return f'{ROMAN[n]}. ' if n < len(ROMAN) else f'{n + 1}. '
    if kind == 'AUTO_NUM':
        return f'{n + 1}. '
    if kind == 'AUTO_ALPHA':
        return f'{chr(65 + n)}. ' if n < 26 else f'{n + 1}. '
    if kind == 'AUTO_HANGUL':
        return f'{HANGUL[n]}. ' if n < len(HANGUL) else f'{n + 1}. '
    if kind == 'AUTO_CIRCLED':
        return f'{CIRCLED[n]} ' if n < len(CIRCLED) else f'{n + 1}) '
    if kind == 'AUTO_CHAPTER':
        return f'제{n + 1}장 '       # 연구보고서 장 제목
    if kind == 'AUTO_SECTION':
        return f'제{n + 1}절 '       # 연구보고서 절 제목
    if kind == 'AUTO_PAREN':
        return f'{n + 1}) '          # 숫자에 닫는 괄호
    if kind == 'AUTO_TABLE':                  # 장 번호를 따라간다
        return caption_prefix(captions.get('table') or DEFAULT_PROFILE['captions']['table'], chapter, n)
    if kind == 'AUTO_FIGURE':
        return caption_prefix(captions.get('figure') or DEFAULT_PROFILE['captions']['figure'], chapter, n)
    return ''


def make_numbering(profile):
    order = [lv['key'] for lv in profile['levels']]
    counters = {k: 0 for k in order}
    # 표·그림 번호가 따라가는 장 번호(〈표 1-1〉의 앞자리)
    chapter_keys = {lv['key'] for lv in profile['levels'] if lv.get('prefix') == 'AUTO_CHAPTER'}
    state = {'chapter': 0}

    def numbering(key, kind):
        idx = order.index(key) if key in order else -1
        value = _or(counters.get(key), 0)
        if key in chapter_keys:
            state['chapter'] = value + 1
        text = auto_prefix(kind, value, state['chapter'], profile.get('captions'))
        counters[key] = value + 1
        for deeper in order[idx + 1:]:
            counters[deeper] = 0
        return text

    return numbering


CELL_HEAD = 'name="" header="0" hasMargin="1" protect="0" editable="0" dirty="1"'
SUBLIST_HEAD = ('id="" textDirection="HORIZONTAL" lineWrap="BREAK" vertAlign="CENTER"'
                ' linkListIDRef="0" linkListNextIDRef="0" textWidth="0" textHeight="0"'
                ' hasTextRef="0" hasNumRef="0"')


_SUBLIST_TOP = SUBLIST_HEAD.replace('vertAlign="CENTER"', 'vertAlign="TOP"', 1)


def make_id_gen():
    state = {'n': 1000000}

    def gen():
        state['n'] += 1
        return state['n']

    return gen


def para_xml(next_id_fn, r, text, runs=None):
    inner = runs if runs is not None else f'<hp:run charPrIDRef="{_n(r["char"])}">{text_xml(text)}</hp:run>'
    return (f'<hp:p id="{next_id_fn()}" paraPrIDRef="{_n(r["para"])}" styleIDRef="{_n(r["style"])}" pageBreak="0"'
            f' columnBreak="0" merged="0">{inner}</hp:p>')


def text_xml(text):
    return f'<hp:t>{escape_xml(text)}</hp:t>' if js_truthy(text) else '<hp:t/>'


def foot_note_xml(next_id_fn, number, note_refs, text):
    """각주 하나. 번호는 한글이 문서 순서대로 매기므로 여기서 넘겨받는다."""
    return ('<hp:ctrl>'
            f'<hp:footNote number="{number}" suffixChar="41" instid="{next_id_fn()}">'
            f'<hp:subList {_SUBLIST_TOP}>'
            f'<hp:p paraPrIDRef="{_n(note_refs["para"])}" styleIDRef="{_n(note_refs["style"])}" pageBreak="0"'
            ' columnBreak="0" merged="0" id="0">'
            f'<hp:run charPrIDRef="{_n(note_refs["char"])}"><hp:ctrl>'
            f'<hp:autoNum num="{number}" numType="FOOTNOTE">'
            '<hp:autoNumFormat type="DIGIT" userChar="" prefixChar="" suffixChar=")" supscript="0"/>'
            f'</hp:autoNum></hp:ctrl>{text_xml(text)}</hp:run></hp:p>'
            '</hp:subList></hp:footNote></hp:ctrl>')


def note_runs_xml(next_id_fn, char, note_refs, text, notes, shift, first_number):
    """각주가 달린 문단의 run 묶음. 번호 자리에서 run을 끊어 각주를 매단다.
    뒤따르는 글이 없으면 run을 새로 열지 않고 앞 run에 각주를 하나 더 단다."""
    def at(note):
        return js_min(js_max(js_number(_or(note.get('offset'), 0)) + shift, 0), len(text))

    marks = sorted(at(n) for n in notes)
    order = [i for _, i in sorted(((at(n), i) for i, n in enumerate(notes)), key=lambda p: p[0])]

    runs = [{'text': text[:marks[0]], 'ctrls': []}]
    for pos, idx in enumerate(order):
        runs[-1]['ctrls'].append(foot_note_xml(next_id_fn, first_number + pos, note_refs,
                                               js_str(_or(notes[idx].get('text'), ''))))
        end = marks[pos + 1] if pos + 1 < len(marks) else len(text)
        chunk = text[marks[pos]:end]
        if chunk:
            runs.append({'text': chunk, 'ctrls': []})
    return ''.join(f'<hp:run charPrIDRef="{_n(char)}">{text_xml(r["text"])}{"".join(r["ctrls"])}</hp:run>'
                   for r in runs)


def cell_xml(next_id_fn, row, col, width, height, border_fill, style, text, margin,
             col_span=1, row_span=1):
    inner = para_xml(next_id_fn, style, text)
    return (f'<hp:tc {CELL_HEAD} borderFillIDRef="{_n(border_fill)}">'
            f'<hp:subList {SUBLIST_HEAD}>{inner}</hp:subList>'
            f'<hp:cellAddr colAddr="{_n(col)}" rowAddr="{_n(row)}"/>'
            f'<hp:cellSpan colSpan="{_n(col_span)}" rowSpan="{_n(row_span)}"/>'
            f'<hp:cellSz width="{_n(width)}" height="{_n(height)}"/>'
            f'<hp:cellMargin left="{_n(margin)}" right="{_n(margin)}" top="{_n(margin)}" bottom="{_n(margin)}"/></hp:tc>')


def table_wrapper(next_id_fn, anchor, inner, rows, cols, width, height, border_fill, treat_as_char):
    return (f'<hp:p id="{next_id_fn()}" paraPrIDRef="{_n(anchor["para"])}" styleIDRef="{_n(anchor["style"])}"'
            f' pageBreak="0" columnBreak="0" merged="0"><hp:run charPrIDRef="{_n(anchor["char"])}">'
            f'<hp:tbl id="{next_id_fn()}" zOrder="0" numberingType="TABLE" textWrap="TOP_AND_BOTTOM"'
            ' textFlow="BOTH_SIDES" lock="0" dropcapstyle="None" pageBreak="CELL" repeatHeader="0"'
            f' rowCnt="{_n(rows)}" colCnt="{_n(cols)}" cellSpacing="0" borderFillIDRef="{_n(border_fill)}" noAdjust="0">'
            f'<hp:sz width="{_n(width)}" widthRelTo="ABSOLUTE" height="{_n(height)}" heightRelTo="ABSOLUTE" protect="0"/>'
            f'<hp:pos treatAsChar="{1 if js_truthy(treat_as_char) else 0}" affectLSpacing="0" flowWithText="1" allowOverlap="0"'
            ' holdAnchorAndSO="0" vertRelTo="PARA" horzRelTo="COLUMN" vertAlign="TOP" horzAlign="LEFT"'
            ' vertOffset="0" horzOffset="0"/>'
            '<hp:outMargin left="0" right="0" top="0" bottom="0"/>'
            '<hp:inMargin left="510" right="510" top="141" bottom="141"/>'
            f'{inner}</hp:tbl></hp:run></hp:p>')


def fill_key(cell, dia):
    color = _or(cell['borderColor'], dia.get('box_border') if js_truthy(cell['fill']) else dia.get('line_color'))
    type_ = _or(cell['borderType'], dia.get('line_type'), 'SOLID')
    return (f"{','.join(sorted(cell['borders'], key=utf16_key))}|{js_str(_or(cell['fill'], ''))}"
            f'|{js_str(color)}|{js_str(type_)}')


def text_colors(grid):
    return list(dict.fromkeys(c['textColor'] for c in grid['cells'] if js_truthy(c['textColor'])))


def collect_diagram_fills(items, profile):
    keys = {}
    text_keys = {}
    grids = {}
    warnings = []
    for index, item in enumerate(items):
        if item['type'] != 'diagram':
            continue
        render = _or(_opt(item['spec'], 'render'), profile['diagram'].get('render'))
        if render == 'image':
            warnings.append(f"도식 '{js_str(_or(item['spec'].get('title'), item['spec']['type']))}': "
                            '웹 버전은 이미지 렌더를 '
                            '지원하지 않아 표로 만듭니다(파이썬판에서는 PNG로 그려집니다)')
        grid = build_grid(item['spec'], profile, True)
        warnings.extend(grid['warnings'])
        grids[index] = grid
        keys['||' + js_str(profile['diagram'].get('line_color')) + '|SOLID'] = None     # 투명 셀
        for cell in grid['cells']:
            keys[fill_key(cell, grid.get('diagram') or profile['diagram'])] = None
        for color in text_colors(grid):
            text_keys[f'dia:{js_str(color)}'] = None
    return {'keys': list(keys), 'textKeys': list(text_keys), 'grids': grids, 'warnings': warnings}


def content_table_xml(next_id_fn, item, profile, ids):
    cfg = profile['table']
    cols = item['cols']
    width = mm(cfg.get('width_mm')) if js_number(cfg.get('width_mm')) > 0 else mm(162.5)
    col_width = js_floor(width / cols)
    row_height = 3600
    margin = mm(_or(cfg.get('cell_margin_mm'), 0))
    top = refs(ids, 'table_top')
    mid = refs(ids, 'table_mid')

    rows_xml = []
    for r in range(item['rows']):
        cells = []
        for c in range(cols):
            is_header = r == 0 and item.get('header') is not False
            idx = r * cols + c
            cells.append(cell_xml(
                next_id_fn, row=r, col=c, width=col_width, height=row_height,
                border_fill=ids['borderHeader'] if is_header else ids['borderBase'],
                style=top if is_header else mid,
                text=_nn(item['data'][idx] if idx < len(item['data']) else None, ''),
                margin=margin))
        rows_xml.append(f"<hp:tr>{''.join(cells)}</hp:tr>")
    return table_wrapper(next_id_fn, anchor_refs(profile, ids), ''.join(rows_xml),
                         rows=item['rows'], cols=cols, width=width,
                         height=row_height * item['rows'], border_fill=ids['borderBase'],
                         treat_as_char=cfg.get('treat_as_char'))


def diagram_table_xml(next_id_fn, grid, profile, ids):
    width = mm(js_sum(grid['colWidths']))
    height = mm(js_sum(grid['rowHeights']))
    margin = mm(0.2)
    dia = grid.get('diagram') or profile['diagram']
    blank = ids['diagramFills'].get('||' + js_str(profile['diagram'].get('line_color')) + '|SOLID')
    by_pos = {}
    for cell in grid['cells']:
        by_pos[(cell['row'], cell['col'])] = cell
    covered = set()
    for cell in grid['cells']:
        for c in range(cell['col'], cell['col'] + cell['colSpan']):
            for r in range(cell['row'], cell['row'] + cell['rowSpan']):
                if r != cell['row'] or c != cell['col']:
                    covered.add((r, c))

    rows_xml = []
    for r in range(grid['rows']):
        cells = []
        for c in range(grid['cols']):
            if (r, c) in covered:
                continue
            cell = by_pos.get((r, c))
            col_span = cell['colSpan'] if cell else 1
            row_span = cell['rowSpan'] if cell else 1
            cell_width = mm(js_sum(grid['colWidths'][c:c + col_span]))
            cell_height = mm(js_sum(grid['rowHeights'][r:r + row_span]))
            if cell and js_truthy(cell['textColor']) and f"dia:{js_str(cell['textColor'])}" in ids['styles']:
                style_key = f"dia:{js_str(cell['textColor'])}"
            else:
                style_key = _or(cell['char'] if cell else None, 'diagram')
            cells.append(cell_xml(
                next_id_fn, row=r, col=c, col_span=col_span, row_span=row_span,
                width=cell_width, height=cell_height,
                border_fill=ids['diagramFills'].get(fill_key(cell, dia)) if cell else blank,
                style=refs(ids, style_key),
                text=_or(cell['text'] if cell else None, ''),
                margin=margin))
        rows_xml.append(f"<hp:tr>{''.join(cells)}</hp:tr>")

    xml = table_wrapper(next_id_fn, anchor_refs(profile, ids), ''.join(rows_xml),
                        rows=grid['rows'], cols=grid['cols'], width=width, height=height,
                        border_fill=blank, treat_as_char=profile['table'].get('treat_as_char'))
    if js_truthy(grid.get('title')):
        xml += para_xml(next_id_fn, refs(ids, 'table_mid'), grid['title'])
    return xml


def anchor_refs(profile, ids):
    key = profile['table'].get('anchor_level')
    if not js_truthy(key):
        body = body_levels(profile)
        key = body[-1]['key'] if body else 'body'
    return refs(ids, key)


#: 이름으로 부를 수 있는 용지. [가로 mm, 세로 mm]
PAPER_SIZES = {
    'A4': [210.0, 297.0], 'B5': [182.0, 257.0], 'A5': [148.0, 210.0],
    'A3': [297.0, 420.0], 'B4': [257.0, 364.0], 'Letter': [215.9, 279.4],
    '크라운': [166.0, 241.0], '크라운판': [166.0, 241.0], 'crown': [166.0, 241.0],
    '신국판': [152.0, 225.0], '국판': [148.0, 210.0], '4x6배판': [188.0, 257.0],
}


def paper_mm(page):
    """프로파일의 용지 → [가로 mm, 세로 mm]. `width_mm`·`height_mm`가 이름보다 이긴다"""
    if js_truthy(page.get('width_mm')) and js_truthy(page.get('height_mm')):
        return [js_number(page['width_mm']), js_number(page['height_mm'])]
    name = js_trim(js_str(_or(page.get('size'), ''))).lower()
    hit = next((v for k, v in PAPER_SIZES.items() if k.lower() == name), None)
    return hit


_SECTION_MARGIN = re.compile(r'<hp:margin header="[^"]*"[^/]*/>')
_PAGE_SIZE = re.compile(r'(<hp:pagePr[^>]*?)width="[0-9]+" height="[0-9]+"')


def build_section(template_section, profile, ids, items, grids):
    margin = profile['page']['margin_mm']
    end = template_section.find('</hp:p>')
    head = template_section[:end + len('</hp:p>')] if end >= 0 else template_section[:len('</hp:p>') - 1]
    head = js_replace(head, _SECTION_MARGIN,
                      f'<hp:margin header="{_n(mm(margin.get("header")))}" footer="{_n(mm(margin.get("footer")))}" gutter="0"'
                      f' left="{_n(mm(margin.get("left")))}" right="{_n(mm(margin.get("right")))}" top="{_n(mm(margin.get("top")))}"'
                      f' bottom="{_n(mm(margin.get("bottom")))}"/>')
    paper = paper_mm(profile['page'])
    if paper:
        head = js_replace(head, _PAGE_SIZE,
                          f'$1width="{_n(mm(paper[0]))}" height="{_n(mm(paper[1]))}"')

    next_id_fn = make_id_gen()
    numbering = make_numbering(profile)
    level_by_key = {lv['key']: lv for lv in profile['levels']}
    body = []
    note_number = 1              # 각주 번호는 문서 전체에서 이어진다

    for index, item in enumerate(items):
        if item['type'] == 'blank':
            body.append(para_xml(next_id_fn, refs(ids, 'body'), ''))
        elif item['type'] == 'table':
            body.append(content_table_xml(next_id_fn, item, profile, ids))
        elif item['type'] == 'diagram':
            grid = grids.get(index)
            if grid:
                body.append(diagram_table_xml(next_id_fn, grid, profile, ids))
        else:
            key = _or(item.get('key'), 'body')
            level = level_by_key.get(key)
            text = js_str(_nn(item.get('text'), ''))
            shift = 0
            if level is not None:
                prefix = js_str(_or(level.get('prefix'), ''))
                resolved = numbering(key, prefix) if prefix.startswith('AUTO_') else prefix
                text = resolved + text
                shift = len(resolved)
            notes = _or(item.get('notes'), [])
            if notes:
                runs = note_runs_xml(next_id_fn, refs(ids, key)['char'], refs(ids, 'footnote'),
                                     text, notes, shift, note_number)
                note_number += len(notes)
                body.append(para_xml(next_id_fn, refs(ids, key), text, runs))
            else:
                body.append(para_xml(next_id_fn, refs(ids, key), text))

    return f"{head}{''.join(body)}</hs:sec>"


def _decode(data):
    """TextDecoder와 같이: 잘못된 바이트는 U+FFFD, 맨 앞 BOM은 뗀다."""
    text = data.decode('utf-8', 'replace')
    return to_js(text[1:] if text.startswith('﻿') else text)


def _encode(text):
    """TextEncoder와 같이: 외톨이 대리 문자는 U+FFFD."""
    return from_js(text).encode('utf-8')


def build_document(template_bytes, user_profile, items):
    """템플릿 hwpx 바이트 + 프로파일 + 항목 → {'bytes', 'warnings'}."""
    profile = merge_profile(user_profile)
    files = unzip(template_bytes)
    if 'Contents/header.xml' not in files or 'Contents/section0.xml' not in files:
        raise JsError('템플릿에 Contents/header.xml·section0.xml이 없습니다')

    header_xml = _decode(files['Contents/header.xml'])
    section_xml = _decode(files['Contents/section0.xml'])

    collected = collect_diagram_fills(items, profile)
    keys, text_keys = collected['keys'], collected['textKeys']
    ids = plan_ids(header_xml, profile, keys, text_keys)

    files['Contents/header.xml'] = _encode(patch_header(header_xml, profile, ids, keys, text_keys))
    files['Contents/section0.xml'] = _encode(build_section(section_xml, profile, ids, items,
                                                           collected['grids']))
    return {'bytes': zip_bytes(files), 'warnings': collected['warnings']}


def build_from_text(template_bytes: bytes, profile: dict, text: str) -> dict:
    """마커 텍스트 한 번에 처리: 파싱 → 검사 → 생성.

    반환: {'bytes', 'warnings', 'issues', 'items', 'profile'}
    """
    merged = merge_profile(to_js(profile))
    parsed = parse_text(to_js(text), merged)
    issues = lint_items(parsed['items'], merged, parsed['lineOf'], parsed['warnings'])
    built = build_document(template_bytes, merged, parsed['items'])
    return {'bytes': built['bytes'], 'warnings': from_js(built['warnings']),
            'issues': from_js(issues), 'items': from_js(parsed['items']),
            'profile': from_js(merged)}


# ──────────────────────────────────────────────────────────────
# 명령행
# ──────────────────────────────────────────────────────────────
def _find_default(name):
    here = Path(__file__).resolve().parent
    for folder in (here, here.parent):
        if (folder / name).is_file():
            return folder / name
    return None


def format_issue(issue):
    kind = '오류' if issue['severity'] == 'error' else '경고'
    return f"  {issue['line']}행 [{kind}:{issue['code']}] {issue['message']}"


def main(argv=None):
    ap = argparse.ArgumentParser(description='마커 텍스트 → 한글 문서(.hwpx). 표준 라이브러리만 쓴다.')
    ap.add_argument('input', help='마커 텍스트 원고(.md/.txt)')
    ap.add_argument('-o', '--output', help='만들 .hwpx 경로(기본: 원고 이름.hwpx)')
    ap.add_argument('--profile', help='서식 프로파일 JSON(기본: profile.json)')
    ap.add_argument('--template', help='템플릿 .hwpx(기본: template.hwpx)')
    ap.add_argument('--check-only', action='store_true', help='검사만 하고 만들지 않는다')
    ap.add_argument('--strict', action='store_true', help='오류가 하나라도 있으면 만들지 않는다')
    args = ap.parse_args(argv)

    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding='utf-8')
        except (AttributeError, ValueError):
            pass

    profile_path = Path(args.profile) if args.profile else _find_default('profile.json')
    template_path = Path(args.template) if args.template else _find_default('template.hwpx')
    if profile_path is None or not profile_path.is_file():
        print('프로파일을 찾지 못함: --profile로 지정할 것', file=sys.stderr)
        return 2
    if template_path is None or not template_path.is_file():
        print('템플릿을 찾지 못함: --template로 지정할 것', file=sys.stderr)
        return 2

    input_path = Path(args.input)
    text = input_path.read_bytes().decode('utf-8', 'replace')
    profile = json.loads(profile_path.read_text(encoding='utf-8'))
    template = template_path.read_bytes()

    if args.check_only:
        merged = merge_profile(to_js(profile))
        parsed = parse_text(to_js(text), merged)
        issues = from_js(lint_items(parsed['items'], merged, parsed['lineOf'], parsed['warnings']))
        warnings = []
    else:
        result = build_from_text(template, profile, text)
        issues, warnings = result['issues'], result['warnings']

    for issue in issues:
        print(format_issue(issue))
    for warning in warnings:
        print(f'  [도식] {warning}')
    errors = sum(1 for i in issues if i['severity'] == 'error')
    print(f'오류 {errors}건 / 경고 {len(issues) - errors}건')

    if args.check_only:
        return 1 if errors else 0
    if args.strict and errors:
        print('--strict: 오류가 있어 만들지 않음', file=sys.stderr)
        return 1

    output = Path(args.output) if args.output else input_path.with_suffix('.hwpx')
    output.write_bytes(result['bytes'])
    print(f"생성: {output} ({len(result['bytes'])} bytes)")
    return 0


if __name__ == '__main__':
    sys.exit(main())
