/**
 * hwpx-studio — 브라우저용 엔진.
 *
 * 파이썬 패키지(hwpx_studio)의 파서·도식·엔진을 이식한 것이다. 서버 없이
 * 브라우저에서 마커 텍스트를 한글 문서(.hwpx)로 만든다.
 *
 * 파이썬판과 다른 점: python-hwpx가 만들어 주던 section0.xml을 여기서는 직접
 * 생성한다(파이썬판 출력의 XML 형태를 그대로 따랐다). 그림 삽입은 아직 없다.
 */

import { unzip, zip } from './zip.js';

export const PT = 100;
export const MM = 283.47;

export const mm = (v) => Math.round(Number(v) * MM);
export const pt = (v) => Math.round(Number(v) * PT);

const ROMAN = ['Ⅰ', 'Ⅱ', 'Ⅲ', 'Ⅳ', 'Ⅴ', 'Ⅵ', 'Ⅶ', 'Ⅷ', 'Ⅸ', 'Ⅹ', 'Ⅺ', 'Ⅻ'];
const HANGUL = [...'가나다라마바사아자차카타파하'];
const CIRCLED = [...'①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮'];

const LEVEL_DEFAULTS = {
  key: '', name: '', marker: '', prefix: '', size_pt: 12, bold: false, font: 'light',
  color: '#000000', left_pt: 0, indent_pt: 0, spacing_below_pt: 0,
  line_spacing: 160, align: 'JUSTIFY',
};

const TABLE_CELL_DEFAULTS = {
  size_pt: 11, bold: false, font: 'light', color: '#000000', left_pt: 0, indent_pt: 0,
  prefix: '', spacing_below_pt: 0, line_spacing: 120, align: 'CENTER',
};

export const DEFAULT_PROFILE = {
  schema: 'hwpx-studio.profile.v1',
  name: '기본',
  mode: 'outline',
  fonts: { bold: '맑은 고딕', light: '맑은 고딕', fallback: '맑은 고딕' },
  page: { size: 'A4', margin_mm: { left: 20, right: 20, top: 10, bottom: 10, header: 10, footer: 10 } },
  levels: [],
  body: {
    name: '본문', size_pt: 12, font: 'light', color: '#000000', bold: false,
    left_pt: 0, indent_pt: 0, spacing_below_pt: 0, line_spacing: 160,
    align: 'JUSTIFY', first_line_indent_pt: 0,
  },
  table: {
    border_color: '#999999', header_bg: '#4472C4', width_mm: 162.5, cell_margin_mm: 0.3,
    treat_as_char: true, anchor_level: null,
    top: { ...TABLE_CELL_DEFAULTS, name: '표(위)', eng_name: 'Table(Top)', bold: true, font: 'bold', color: '#FFFFFF' },
    mid: { ...TABLE_CELL_DEFAULTS, name: '표(중간)', eng_name: 'Table(Mid)' },
    left: { ...TABLE_CELL_DEFAULTS, name: '표(왼쪽)', eng_name: 'Table(Left)', align: 'LEFT', indent_pt: 12, prefix: '· ' },
  },
  image: { default_width_mm: 120, treat_as_char: true },
  diagram: {
    render: 'table', box_fill: '#DCE6F1', box_border: '#1F3864', box_color: '#000000',
    root_fill: '#1F3864', root_color: '#FFFFFF', line_color: '#1F3864', line_width_mm: 0.3,
    font_size_pt: 11, col_width_mm: 28, col_gap_mm: 6, grid_resolution: 6,
    row_height_mm: 9, row_gap_mm: 7, max_width_mm: 160,
  },
  rules: { min_children: {}, period_policy: 'single_sentence_no_period' },
};

const isPlainObject = (v) => v !== null && typeof v === 'object' && !Array.isArray(v);

function deepMerge(base, override) {
  if (isPlainObject(base) && isPlainObject(override)) {
    const out = { ...base };
    for (const [k, v] of Object.entries(override)) {
      out[k] = k in base ? deepMerge(base[k], v) : structuredClone(v);
    }
    return out;
  }
  return override === undefined ? structuredClone(base) : structuredClone(override);
}

export function mergeProfile(user = {}) {
  const rest = { ...user };
  delete rest.levels;
  const merged = deepMerge(DEFAULT_PROFILE, rest);
  merged.levels = (user.levels || []).map((lv, i) => {
    const item = deepMerge(LEVEL_DEFAULTS, lv);
    if (!item.key) item.key = `L${i + 1}`;
    if (!item.name) item.name = item.key;
    if (!item.marker) {
      item.marker = String(item.prefix).startsWith('AUTO_') ? '' : String(item.prefix).trim();
    }
    return item;
  });
  for (const key of ['top', 'mid', 'left']) {
    merged.table[key] = deepMerge(TABLE_CELL_DEFAULTS, merged.table[key] || {});
  }
  return merged;
}

export const bodyLevels = (profile) =>
  profile.levels.filter((lv) => !String(lv.prefix || '').startsWith('AUTO_'));

// ──────────────────────────────────────────────────────────────
// 마커 텍스트 파서 (parser.py 이식)
// ──────────────────────────────────────────────────────────────
const IMAGE_RE = /^!\[[^\]]*\]\(([^)]+)\)\s*$/;
const TABLE_SEP_RE = /^\|[\s:|-]+\|$/;
const FENCE_RE = /^:::\s*(?:diagram)?\s*(.*)$/;

export function parseText(text, profile) {
  const markers = profile.levels
    .filter((lv) => lv.marker)
    .map((lv) => [lv.marker, lv.key])
    .sort((a, b) => b[0].length - a[0].length);
  const fallback = bodyLevels(profile).map((lv) => lv.key);
  const narrative = profile.mode === 'narrative';

  const items = [];
  const lineOf = [];
  const warnings = [];
  const push = (item, line) => { items.push(item); lineOf.push(line); };

  const lines = text.replace(/\r\n?/g, '\n').split('\n');
  let i = 0;
  while (i < lines.length) {
    const raw = lines[i].replace(/\s+$/, '');
    const lineno = i + 1;
    const stripped = raw.trim();

    if (!stripped) { push({ type: 'blank' }, lineno); i += 1; continue; }

    const fence = stripped.startsWith(':::') ? FENCE_RE.exec(stripped) : null;
    if (fence) {
      const header = fence[1].trim();
      const body = [];
      i += 1;
      while (i < lines.length && !lines[i].trim().startsWith(':::')) {
        body.push(lines[i].replace(/\s+$/, ''));
        i += 1;
      }
      i += 1;
      const spec = parseDiagramBlock(header, body);
      if (!spec.lines.length) warnings.push(`${lineno}행: 내용이 빈 도식 블록`);
      push({ type: 'diagram', spec }, lineno);
      continue;
    }

    const img = IMAGE_RE.exec(stripped);
    if (img) {
      warnings.push(`${lineno}행: 웹 버전은 그림 삽입을 지원하지 않습니다(무시됨)`);
      i += 1;
      continue;
    }

    if (stripped.startsWith('|') && stripped.endsWith('|')) {
      const rows = [];
      const start = lineno;
      while (i < lines.length) {
        const cur = lines[i].trim();
        if (!(cur.startsWith('|') && cur.endsWith('|'))) break;
        if (!TABLE_SEP_RE.test(cur)) {
          rows.push(cur.slice(1, -1).split('|').map((c) => c.trim()));
        }
        i += 1;
      }
      if (rows.length) {
        const cols = Math.max(...rows.map((r) => r.length));
        const data = [];
        for (const row of rows) {
          for (let c = 0; c < cols; c += 1) data.push(row[c] ?? '');
        }
        push({ type: 'table', rows: rows.length, cols, data }, start);
      }
      continue;
    }

    const matched = matchMarker(stripped, markers);
    if (matched.warn) warnings.push(`${lineno}행: ${matched.warn}`);
    if (matched.key !== null) {
      push({ type: 'para', key: matched.key, text: matched.text }, lineno);
      i += 1;
      continue;
    }

    if (narrative || !fallback.length) {
      push({ type: 'para', key: 'body', text: stripped }, lineno);
    } else {
      const expanded = raw.replace(/\t/g, '  ');
      const indent = expanded.length - expanded.replace(/^ +/, '').length;
      const depth = Math.min(Math.floor(indent / 2), fallback.length - 1);
      warnings.push(`${lineno}행: 마커 없는 줄 → 들여쓰기 ${indent}칸으로 ${fallback[depth]} 레벨 적용`);
      push({ type: 'para', key: fallback[depth], text: stripped }, lineno);
    }
    i += 1;
  }
  return { items, lineOf, warnings };
}

function matchMarker(text, markers) {
  for (const [marker, key] of markers) {
    if (text.startsWith(`${marker} `) || text === marker) {
      let rest = text.slice(marker.length).trim();
      let warn = null;
      while (rest.startsWith(`${marker} `) || rest === marker) {
        rest = rest.slice(marker.length).trim();
        warn = `마커 '${marker}'가 중복 입력됨 → 1회만 인식`;
      }
      return { key, text: rest, warn };
    }
  }
  return { key: null, text, warn: null };
}

// ──────────────────────────────────────────────────────────────
// 본문 검사 (lint.py 이식 — 주요 규칙만)
// ──────────────────────────────────────────────────────────────
const SENTENCE_SPLIT = /(?<=[.!?])\s+/;

export function lintItems(items, profile, lineOf = [], parserWarnings = []) {
  const order = profile.levels.map((lv) => lv.key);
  const depthOf = new Map(order.map((k, i) => [k, i]));
  const markers = [...new Set(profile.levels.map((lv) => lv.marker).filter(Boolean))].sort();
  const autoKeys = new Set(profile.levels.filter((lv) => String(lv.prefix).startsWith('AUTO_')).map((lv) => lv.key));
  const minChildren = profile.rules?.min_children || {};
  const policy = profile.rules?.period_policy || 'single_sentence_no_period';
  const issues = [];

  for (const text of parserWarnings) {
    const m = /^(\d+)행: (.*)$/.exec(text);
    issues.push({ severity: 'warn', line: m ? Number(m[1]) : 0, code: 'parser', message: m ? m[2] : text });
  }

  const paras = items.map((item, idx) => ({ item, idx })).filter(({ item }) => item.type === 'para');

  paras.forEach(({ item, idx }, pos) => {
    const key = item.key || 'body';
    const line = lineOf[idx] ?? idx + 1;
    const text = String(item.text || '');
    const depth = depthOf.get(key);

    if (key !== 'body' && depth === undefined) {
      issues.push({ severity: 'error', line, code: 'level', message: `프로파일에 없는 레벨: ${key}` });
      return;
    }
    if (!text.trim()) {
      issues.push({ severity: 'warn', line, code: 'empty', message: '내용이 빈 문단' });
    }

    const stray = markers.find((marker) =>
      marker && marker !== '-' && marker !== '#'
      && new RegExp(`(^|\\s)${escapeRegExp(marker)}(?=\\s)`).test(text));
    if (stray) {
      issues.push({ severity: 'warn', line, code: 'symbol', message: `본문에 레벨 기호 '${stray}'가 들어 있음 → 마커와 혼동 가능` });
    }

    if (!autoKeys.has(key)) issues.push(...periodIssues(text, line, policy));

    const need = minChildren[key];
    if (need && depth !== undefined) {
      let count = 0;
      for (const later of paras.slice(pos + 1)) {
        const childDepth = depthOf.get(later.item.key || 'body');
        if (childDepth === undefined) continue;
        if (childDepth <= depth) break;
        if (childDepth === depth + 1) count += 1;
      }
      if (count < need) {
        issues.push({ severity: 'warn', line, code: 'balance', message: `${key} 아래 하위 항목이 ${count}개 (권장 ${need}개 이상): ${text.slice(0, 20)}` });
      }
    }

    if (pos > 0 && depth !== undefined) {
      const prevDepth = depthOf.get(paras[pos - 1].item.key || 'body');
      if (prevDepth !== undefined && depth - prevDepth > 1) {
        issues.push({ severity: 'warn', line, code: 'jump', message: `${paras[pos - 1].item.key} 다음에 ${key}가 나옴 → 중간 레벨 생략` });
      }
    }
  });

  items.forEach((item, i) => {
    if (item.type !== 'table' && item.type !== 'diagram') return;
    const label = item.type === 'table' ? '표' : '도식';
    const line = lineOf[i] ?? i + 1;
    const before = i > 0 ? items[i - 1].type : 'blank';
    const after = i + 1 < items.length ? items[i + 1].type : 'blank';
    if (before !== 'blank') issues.push({ severity: 'warn', line, code: 'spacing', message: `${label} 앞에 빈 줄이 없음` });
    if (after !== 'blank') issues.push({ severity: 'warn', line, code: 'spacing', message: `${label} 뒤에 빈 줄이 없음` });
  });

  issues.sort((a, b) => a.line - b.line || a.code.localeCompare(b.code));
  return issues;
}

const escapeRegExp = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

function periodIssues(text, line, policy) {
  const stripped = text.trim();
  if (!stripped || policy === 'off') return [];
  const sentences = stripped.split(SENTENCE_SPLIT).filter(Boolean);
  const endsWithPeriod = stripped.endsWith('.');
  const out = [];
  if (policy === 'single_sentence_no_period') {
    if (sentences.length === 1 && endsWithPeriod) out.push({ severity: 'warn', line, code: 'period', message: '단문인데 온점이 붙음' });
    else if (sentences.length > 1 && !endsWithPeriod) out.push({ severity: 'warn', line, code: 'period', message: '두 문장 이상인데 끝 온점이 없음' });
  } else if (policy === 'always_period' && !endsWithPeriod) {
    out.push({ severity: 'warn', line, code: 'period', message: '온점으로 끝나야 함' });
  } else if (policy === 'never_period' && endsWithPeriod) {
    out.push({ severity: 'warn', line, code: 'period', message: '온점을 쓰지 않는 규칙' });
  }
  return out;
}

// ──────────────────────────────────────────────────────────────
// 도식 (diagram.py 이식)
// ──────────────────────────────────────────────────────────────
const ARROW_SPLIT = /\s*(?:→|->|=>|▶|>)\s*/;
const MIN_BOX_WIDTH_MM = 12;

const LINE_TYPES = {
  solid: 'SOLID', dash: 'DASH', dot: 'DOT',
  dashdot: 'DASH_DOT', dashdotdot: 'DASH_DOT_DOT', longdash: 'LONG_DASH',
};
const BLOCK_COLOR_OPTIONS = ['box_fill', 'box_border', 'box_color', 'root_fill', 'root_color', 'line_color'];

export function normalizeColor(value) {
  if (!value) return null;
  let v = String(value).trim().replace(/^#/, '');
  if (/^[0-9a-fA-F]{3}$/.test(v)) v = v.split('').map((c) => c + c).join('');
  return /^[0-9a-fA-F]{6}$/.test(v) ? `#${v.toUpperCase()}` : null;
}

export function normalizeLineType(value) {
  if (!value) return null;
  let v = String(value).trim().toLowerCase().replace(/[-_]/g, '');
  if (v === '점선' || v === '파선') v = 'dash';
  else if (v === '실선') v = 'solid';
  return LINE_TYPES[v] || null;
}

/** `기획부 {fill=#DCE6F1 color=#000}` → [텍스트, 속성] */
export function splitAttrs(text) {
  const m = /\s*\{([^{}]*)\}\s*$/.exec(text);
  if (!m) return [text.trim(), {}];
  const attrs = {};
  for (const token of (m[1].replace(/,/g, ' ').match(/(?:[^\s"']+|"[^"]*"|'[^']*')+/g) || [])) {
    const eq = token.indexOf('=');
    if (eq > 0) attrs[token.slice(0, eq).trim().toLowerCase()] = token.slice(eq + 1).trim().replace(/^["']|["']$/g, '');
  }
  return [text.slice(0, m.index).trim(), attrs];
}

function nodeStyle(attrs) {
  const style = {};
  for (const key of ['fill', 'color', 'border', 'link_color']) {
    const raw = String(attrs[key] || '').trim().toLowerCase();
    if (key === 'border' && (raw === 'none' || raw === '없음')) { style.border = 'none'; continue; }
    const color = normalizeColor(attrs[key]);
    if (color) style[key] = color;
  }
  const rawLink = String(attrs.link || '').trim().toLowerCase();
  if (rawLink === 'none' || rawLink === '없음') style.link = 'none';
  else {
    const link = normalizeLineType(attrs.link);
    if (link) style.link = link;
  }
  return style;
}

/** 블록 헤더 옵션으로 프로파일의 diagram 설정을 덮어쓴 사본 */
function effectiveDiagram(spec, profile) {
  const dia = { ...profile.diagram };
  for (const key of BLOCK_COLOR_OPTIONS) {
    const color = normalizeColor(spec.options?.[key]);
    if (color) dia[key] = color;
  }
  const lineType = normalizeLineType(spec.options?.line_style);
  if (lineType) dia.line_type = lineType;
  return dia;
}

export function parseDiagramBlock(header, lines) {
  const options = {};
  for (const token of header.match(/(?:[^\s"']+|"[^"]*"|'[^']*')+/g) || []) {
    const eq = token.indexOf('=');
    if (eq > 0) {
      options[token.slice(0, eq).trim()] = token.slice(eq + 1).trim().replace(/^["']|["']$/g, '');
    }
  }
  let type = options.type || 'org';
  delete options.type;
  if (!['org', 'flow', 'matrix', 'strategy'].includes(type)) type = 'org';
  const title = options.title || '';
  delete options.title;
  const body = lines.map((l) => l.replace(/\s+$/, ''));
  while (body.length && !body[0].trim()) body.shift();
  while (body.length && !body[body.length - 1].trim()) body.pop();
  return { type, title, options, lines: body };
}

function parseTree(lines) {
  const entries = [];
  for (const raw of lines) {
    if (!raw.trim()) continue;
    const expanded = raw.replace(/\t/g, '  ');
    const stripped = expanded.replace(/^ +/, '');
    const indent = expanded.length - stripped.length;
    const [text, attrs] = splitAttrs(stripped.trim().replace(/^[-*•]\s+/, ''));
    if (text) entries.push([indent, text, nodeStyle(attrs)]);
  }
  const roots = [];
  const stack = [];
  for (const [indent, text, style] of entries) {
    const node = { text, depth: 0, children: [], center: 0, row: 0, style };
    while (stack.length && stack[stack.length - 1][0] >= indent) stack.pop();
    if (stack.length) {
      const parent = stack[stack.length - 1][1];
      node.depth = parent.depth + 1;
      parent.children.push(node);
    } else {
      roots.push(node);
    }
    stack.push([indent, node]);
  }
  return roots;
}

const leafCount = (node) => (node.children.length ? node.children.reduce((s, c) => s + leafCount(c), 0) : 1);
const maxDepth = (nodes) => nodes.reduce((d, n) => Math.max(d, n.depth + 1, maxDepth(n.children)), 0);
function* walk(nodes) {
  for (const node of nodes) { yield node; yield* walk(node.children); }
}

const BOX_BORDERS = ['left', 'right', 'top', 'bottom'];

export function buildGrid(spec, profile, force = false) {
  const effective = { ...profile, diagram: effectiveDiagram(spec, profile) };
  const layout = String(spec.options?.layout || '').toLowerCase();
  let grid;
  if (spec.type === 'flow') grid = gridFlow(spec, effective);
  else if (spec.type === 'matrix') grid = gridMatrix(spec, effective);
  else if (spec.type === 'strategy') grid = gridStrategy(spec, effective);
  else if (layout.startsWith('side')) grid = gridOrgSide(spec, effective);
  else {
    grid = gridOrg(spec, effective);
    if (grid.fallbackToImage && !layout) {
      const side = gridOrgSide(spec, effective);
      side.warnings = grid.warnings.filter((w) => !w.includes('이미지로 폴백'));
      side.warnings.push('가로로 늘어놓기에는 상자가 많아 세로 목록형으로 배치했다'
        + '(가로를 원하면 width를 늘리거나 layout=wide)');
      grid = side;
    }
  }
  grid.title = spec.title || '';
  grid.diagram = effective.diagram;
  if (effective.diagram.line_type) {
    for (const cell of grid.cells) {
      if (!cell.text && !cell.fill && !cell.borderType) cell.borderType = effective.diagram.line_type;
    }
  }
  const maxW = Number(spec.options?.width || effective.diagram.max_width_mm);
  if (force) grid.fallbackToImage = false;
  if (totalWidth(grid) > maxW + 0.01 && !force) {
    grid.warnings.push(`도식 폭 ${totalWidth(grid).toFixed(0)}mm > 최대 ${maxW}mm`);
  }
  return grid;
}

const totalWidth = (grid) => grid.colWidths.reduce((a, b) => a + b, 0);
const totalHeight = (grid) => grid.rowHeights.reduce((a, b) => a + b, 0);

function fitBoxWidth(slots, profile, maxW) {
  let boxW = Number(profile.diagram.col_width_mm);
  let gap = Number(profile.diagram.col_gap_mm);
  if (slots <= 0 || slots * boxW + (slots - 1) * gap <= maxW) return [boxW, gap];
  gap = Math.max(2, gap * 0.5);
  boxW = (maxW - (slots - 1) * gap) / slots;
  return [boxW, gap];
}

function gridOrg(spec, profile) {
  const dia = profile.diagram;
  const warnings = [];
  const roots = parseTree(spec.lines);
  if (!roots.length) {
    return { rows: 1, cols: 1, colWidths: [dia.col_width_mm], rowHeights: [dia.row_height_mm], cells: [], warnings: ['도식 내용이 비어 있음'], fallbackToImage: false };
  }

  let boxCols = Number(dia.grid_resolution || 6);
  boxCols = Math.max(2, boxCols + (boxCols % 2));
  const half = boxCols / 2;

  const leaves = roots.reduce((s, r) => s + leafCount(r), 0);
  const depth = maxDepth(roots);
  const maxW = Number(spec.options?.width || dia.max_width_mm);
  let [boxW, gap] = fitBoxWidth(leaves, profile, maxW);

  let unit = boxW / boxCols;
  const gapCols = Math.max(2, 2 * Math.max(1, Math.round(gap / (2 * unit))));
  const stride = boxCols + gapCols;
  const cols = stride * leaves - gapCols;

  if (cols * unit > maxW) { unit = maxW / cols; boxW = unit * boxCols; }
  const tooNarrow = boxW < MIN_BOX_WIDTH_MM;
  if (tooNarrow) warnings.push(`같은 단계 상자가 ${leaves}개여서 폭이 ${boxW.toFixed(1)}mm까지 좁아짐`);
  else if (Math.abs(boxW - Number(dia.col_width_mm)) > 0.5) warnings.push(`도식 상자 폭을 ${boxW.toFixed(1)}mm로 자동 축소`);

  let slot = 0;
  const assign = (node) => {
    let center;
    if (!node.children.length) { center = stride * slot + half - 1; slot += 1; }
    else {
      const centers = node.children.map(assign);
      center = Math.floor((centers[0] + centers[centers.length - 1]) / 2);
    }
    node.center = center;
    return center;
  };
  roots.forEach(assign);

  const rows = depth ? 3 * depth - 2 : 1;
  const rowHeights = [];
  for (let d = 0; d < depth; d += 1) {
    rowHeights.push(Number(dia.row_height_mm));
    if (d < depth - 1) rowHeights.push(Number(dia.row_gap_mm) / 2, Number(dia.row_gap_mm) / 2);
  }

  const cells = [];
  for (const node of walk(roots)) {
    node.row = 3 * node.depth;
    const start = Math.max(0, Math.min(node.center - (half - 1), cols - boxCols));
    cells.push({
      row: node.row, col: start, text: node.text, borders: [...BOX_BORDERS],
      fill: node.style.fill || (node.depth === 0 ? dia.root_fill : dia.box_fill),
      char: node.depth === 0 ? 'diagram_root' : 'diagram',
      colSpan: boxCols, rowSpan: 1,
      textColor: node.style.color || null,
      borderColor: node.style.border || null,
      borderType: null,
    });
  }
  for (const node of walk(roots)) {
    if (!node.children.length) continue;
    const rowA = 3 * node.depth + 1;
    const rowB = rowA + 1;
    const byCenter = new Map(node.children.map((c) => [c.center, c]));
    const centers = [...byCenter.keys()].sort((a, b) => a - b);
    addBorder(cells, rowA, node.center, 'right');
    for (let col = centers[0] + 1; col <= centers[centers.length - 1]; col += 1) {
      const child = byCenter.get(col);
      addBorder(cells, rowB, col, 'top', child?.style.link_color, child?.style.link);
    }
    for (const col of centers) {
      const child = byCenter.get(col);
      addBorder(cells, rowB, col, 'right', child?.style.link_color, child?.style.link);
    }
  }

  return { rows, cols, colWidths: new Array(cols).fill(unit), rowHeights, cells, warnings, fallbackToImage: tooNarrow };
}

/** `라벨 | 칸 | 칸` 줄들을 단으로 묶는다 (diagram.py: parseBands 이식). */
function parseBands(lines) {
  const bands = [];
  for (const raw of lines) {
    const line = raw.trim();
    if (!line) continue;
    if (/^\|[\s:|-]+\|?$/.test(line)) continue;
    const parts = line.split('|').map((p) => p.trim());
    while (parts.length > 1 && !parts[parts.length - 1]) parts.pop();
    let head = parts[0];
    let cells = parts.slice(1);
    if (!cells.length) { head = ''; cells = [parts[0]]; }
    const row = cells.map((c) => splitAttrs(c))
      .filter(([text]) => text)
      .map(([text, attrs]) => [text, nodeStyle(attrs)]);
    if (!row.length) continue;
    if (head) {
      const [label, attrs] = splitAttrs(head);
      bands.push({ label, labelStyle: nodeStyle(attrs), rows: [row] });
    } else if (bands.length) {
      bands[bands.length - 1].rows.push(row);
    } else {
      bands.push({ label: '', labelStyle: {}, rows: [row] });
    }
  }
  return bands;
}

/** 전략체계도 (diagram.py: _grid_strategy 이식). */
function gridStrategy(spec, profile) {
  const dia = profile.diagram;
  const warnings = [];
  const bands = parseBands(spec.lines);
  if (!bands.length) {
    return { rows: 1, cols: 1, colWidths: [dia.col_width_mm], rowHeights: [dia.row_height_mm], cells: [], warnings: ['도식 내용이 비어 있음'], fallbackToImage: false };
  }

  const nCols = Math.max(...bands.flatMap((b) => b.rows.map((r) => r.length)), 1);
  const hasLabel = bands.some((b) => b.label);

  let boxCols = Number(dia.grid_resolution || 6);
  boxCols = Math.max(2, boxCols + (boxCols % 2));
  const half = boxCols / 2;

  const maxW = Number(spec.options?.width || dia.max_width_mm);
  const labelW = hasLabel ? Number(spec.options?.label_width || 22) : 0;
  let [boxW, gap] = fitBoxWidth(nCols, profile, maxW - labelW);
  let unit = boxW / boxCols;
  const gapCols = Math.max(2, 2 * Math.max(1, Math.round(gap / (2 * unit))));
  const stride = boxCols + gapCols;
  const contentCols = stride * nCols - gapCols;
  if (contentCols * unit > maxW - labelW) { unit = (maxW - labelW) / contentCols; boxW = unit * boxCols; }
  if (boxW < MIN_BOX_WIDTH_MM) warnings.push(`한 단에 칸이 ${nCols}개여서 폭이 ${boxW.toFixed(1)}mm까지 좁아짐`);

  const offset = hasLabel ? 1 : 0;
  const colWidths = (hasLabel ? [labelW] : []).concat(new Array(contentCols).fill(unit));
  const centre = (index, span = 1) => {
    const first = offset + stride * index + half - 1;
    const last = offset + stride * (index + span - 1) + half - 1;
    return Math.floor((first + last) / 2);
  };

  const rowH = Number(dia.row_height_mm);
  const rowGap = Number(dia.row_gap_mm);
  const innerGap = Math.max(1, rowGap / 3);

  const cells = [];
  const rowHeights = [];
  const bandRows = [];

  bands.forEach((band, b) => {
    if (b) {
      if (band.labelStyle.link === 'none') rowHeights.push(innerGap);
      else rowHeights.push(rowGap / 2, rowGap / 2);
    }
    const rowsHere = [];
    band.rows.forEach((row, r) => {
      if (r) rowHeights.push(innerGap);
      rowsHere.push(rowHeights.length);
      rowHeights.push(rowH);
    });
    bandRows.push(rowsHere);

    band.rows.forEach((row, r) => {
      const each = Math.max(1, Math.floor(nCols / row.length));
      row.forEach(([text, style], i) => {
        const start = offset + stride * (i * each);
        const width = boxCols + stride * (each - 1);
        const plain = style.border === 'none';
        cells.push({
          row: rowsHere[r], col: start, text, borders: plain ? [] : [...BOX_BORDERS],
          fill: style.fill || (plain ? null : dia.box_fill),
          char: 'diagram',
          colSpan: Math.min(width, colWidths.length - start), rowSpan: 1,
          textColor: style.color || null,
          borderColor: plain ? null : (style.border || null),
          borderType: null,
        });
      });
    });

    if (hasLabel && band.label) {
      const style = band.labelStyle;
      const plain = style.border === 'none';
      cells.push({
        row: rowsHere[0], col: 0, text: band.label,
        borders: plain ? [] : [...BOX_BORDERS],
        fill: style.fill || dia.root_fill,
        char: 'diagram_root',
        colSpan: 1, rowSpan: rowsHere[rowsHere.length - 1] - rowsHere[0] + 1,
        textColor: style.color || null,
        borderColor: plain ? null : (style.border || null),
        borderType: null,
      });
    }
  });

  for (let b = 1; b < bands.length; b += 1) {
    const upper = bands[b - 1];
    const lower = bands[b];
    if (lower.labelStyle.link === 'none') continue;
    const rowB = bandRows[b][0] - 1;
    const rowA = rowB - 1;
    let lineType = lower.labelStyle.link;
    lineType = (!lineType || lineType === 'none') ? null : lineType;
    const colour = lower.labelStyle.link_color || null;

    const topRow = upper.rows[upper.rows.length - 1];
    const bottomRow = lower.rows[0];
    const eachT = Math.max(1, Math.floor(nCols / topRow.length));
    const eachB = Math.max(1, Math.floor(nCols / bottomRow.length));
    const tops = topRow.map((_, i) => centre(i * eachT, eachT));
    const bottoms = bottomRow.map((_, i) => centre(i * eachB, eachB));

    for (const col of tops) addBorder(cells, rowA, col, 'right', colour, lineType);
    const same = tops.length === bottoms.length && tops.every((c, i) => c === bottoms[i]);
    if (!same) {
      const spread = [...new Set([...tops, ...bottoms])].sort((x, y) => x - y);
      for (let col = spread[0] + 1; col <= spread[spread.length - 1]; col += 1) {
        addBorder(cells, rowB, col, 'top', colour, lineType);
      }
    }
    for (const col of bottoms) addBorder(cells, rowB, col, 'right', colour, lineType);
  }

  return { rows: rowHeights.length, cols: colWidths.length, colWidths, rowHeights, cells, warnings, fallbackToImage: false };
}

/**
 * 세로 목록형 계층도 (diagram.py: _grid_org_side 이식).
 * 상자를 한 줄에 하나씩 쌓고 단계마다 오른쪽으로 들여쓴다 — 상자가 많아도 폭이 안 는다.
 */
function gridOrgSide(spec, profile) {
  const dia = profile.diagram;
  const warnings = [];
  const roots = parseTree(spec.lines);
  if (!roots.length) {
    return { rows: 1, cols: 1, colWidths: [dia.col_width_mm], rowHeights: [dia.row_height_mm], cells: [], warnings: ['도식 내용이 비어 있음'], fallbackToImage: false };
  }

  const nodes = [...walk(roots)];
  const depth = maxDepth(roots);
  const maxW = Number(spec.options?.width || dia.max_width_mm);

  const step = Math.max(4, Number(dia.col_gap_mm));
  const spineW = step / 2;
  let boxW = Number(dia.col_width_mm) * 2;
  if (step * (depth - 1) + boxW > maxW) {
    boxW = Math.max(MIN_BOX_WIDTH_MM, maxW - step * (depth - 1));
    warnings.push(`세로 목록형: 상자 폭을 ${boxW.toFixed(1)}mm로 맞춤`);
  }
  const colWidths = [];
  for (let d = 0; d < depth - 1; d += 1) colWidths.push(spineW, spineW);
  colWidths.push(boxW);
  const lastCol = colWidths.length - 1;

  const rowH = Number(dia.row_height_mm) / 2;
  const gapH = Math.max(1, Number(dia.row_gap_mm) / 3);
  const cells = [];
  const rowHeights = [];
  const rowOf = new Map();

  nodes.forEach((node, i) => {
    if (i) rowHeights.push(gapH);
    const top = rowHeights.length;
    rowOf.set(node, top);
    rowHeights.push(rowH, rowH);
    const col = Math.min(2 * node.depth, lastCol);
    cells.push({
      row: top, col, text: node.text, borders: [...BOX_BORDERS],
      fill: node.style.fill || (node.depth === 0 ? dia.root_fill : dia.box_fill),
      char: node.depth === 0 ? 'diagram_root' : 'diagram',
      colSpan: lastCol - col + 1, rowSpan: 2,
      textColor: node.style.color || null,
      borderColor: node.style.border || null,
      borderType: null,
    });
  });

  for (const node of nodes) {
    if (!node.children.length) continue;
    const spine = Math.min(2 * node.depth, lastCol);
    if (spine >= lastCol) continue;
    const last = node.children[node.children.length - 1];
    for (let row = rowOf.get(node) + 2; row < rowOf.get(last) + 1; row += 1) {
      addBorder(cells, row, spine, 'right');
    }
    for (const child of node.children) {
      addBorder(cells, rowOf.get(child) + 1, spine + 1, 'top',
        child.style.link_color, child.style.link);
    }
  }

  return { rows: rowHeights.length, cols: colWidths.length, colWidths, rowHeights, cells, warnings, fallbackToImage: false };
}

function addBorder(cells, row, col, edge, color = null, lineType = null) {
  const found = cells.find((c) => c.row === row && c.col === col);
  if (found) {
    if (!found.borders.includes(edge)) found.borders = [...new Set([...found.borders, edge])].sort();
    found.borderColor = color || found.borderColor || null;
    found.borderType = lineType || found.borderType || null;
    return;
  }
  cells.push({
    row, col, text: '', borders: [edge], fill: null, char: 'diagram', colSpan: 1, rowSpan: 1,
    textColor: null, borderColor: color || null, borderType: lineType || null,
  });
}

function gridFlow(spec, profile) {
  const dia = profile.diagram;
  const warnings = [];
  const steps = [];
  for (const line of spec.lines) {
    if (!line.trim()) continue;
    for (const part of line.trim().split(ARROW_SPLIT)) {
      if (!part.trim()) continue;
      const [text, attrs] = splitAttrs(part.trim());
      if (text) steps.push([text, nodeStyle(attrs)]);
    }
  }
  if (!steps.length) {
    return { rows: 1, cols: 1, colWidths: [dia.col_width_mm], rowHeights: [dia.row_height_mm], cells: [], warnings: ['도식 내용이 비어 있음'], fallbackToImage: false };
  }
  const direction = String(spec.options?.direction || 'right').toLowerCase();
  const rowH = Number(dia.row_height_mm);
  const maxW = Number(spec.options?.width || dia.max_width_mm);
  const cells = [];

  if (direction.startsWith('d')) {
    const rows = 2 * steps.length - 1;
    const boxW = Math.min(Number(dia.col_width_mm) * 2, maxW);
    const rowHeights = [];
    steps.forEach(([text, style], i) => {
      cells.push({
        row: 2 * i, col: 0, text, borders: [...BOX_BORDERS], fill: style.fill || dia.box_fill,
        char: 'diagram', colSpan: 1, rowSpan: 1,
        textColor: style.color || null, borderColor: style.border || null, borderType: null,
      });
      if (i < steps.length - 1) cells.push({ row: 2 * i + 1, col: 0, text: '▼', borders: [], fill: null, char: 'diagram', colSpan: 1, rowSpan: 1, textColor: null, borderColor: null, borderType: null });
    });
    for (let i = 0; i < rows; i += 1) rowHeights.push(i % 2 === 0 ? rowH : Number(dia.row_gap_mm));
    return { rows, cols: 1, colWidths: [boxW], rowHeights, cells, warnings, fallbackToImage: false };
  }

  const n = steps.length;
  const arrowW = Math.max(4, Number(dia.col_gap_mm));
  let boxW = Number(dia.col_width_mm);
  if (n * boxW + (n - 1) * arrowW > maxW) {
    boxW = Math.max(MIN_BOX_WIDTH_MM, (maxW - (n - 1) * arrowW) / n);
    warnings.push(`절차도 상자 폭을 ${boxW.toFixed(1)}mm로 자동 축소`);
  }
  const colWidths = [];
  steps.forEach(([text, style], i) => {
    cells.push({
      row: 0, col: 2 * i, text, borders: [...BOX_BORDERS], fill: style.fill || dia.box_fill,
      char: 'diagram', colSpan: 1, rowSpan: 1,
      textColor: style.color || null, borderColor: style.border || null, borderType: null,
    });
    colWidths.push(boxW);
    if (i < n - 1) {
      cells.push({ row: 0, col: 2 * i + 1, text: '→', borders: [], fill: null, char: 'diagram', colSpan: 1, rowSpan: 1, textColor: null, borderColor: null, borderType: null });
      colWidths.push(arrowW);
    }
  });
  return { rows: 1, cols: 2 * n - 1, colWidths, rowHeights: [rowH], cells, warnings, fallbackToImage: false };
}

function gridMatrix(spec, profile) {
  const dia = profile.diagram;
  const table = [];
  for (const line of spec.lines) {
    const s = line.trim();
    if (!s.startsWith('|')) continue;
    if (/^\|[\s:|-]+\|$/.test(s)) continue;
    table.push(s.slice(1, -1).split('|').map((p) => splitAttrs(p.trim())));
  }
  if (!table.length) {
    return { rows: 1, cols: 1, colWidths: [dia.col_width_mm], rowHeights: [dia.row_height_mm], cells: [], warnings: ['도식 내용이 비어 있음'], fallbackToImage: false };
  }
  const cols = Math.max(...table.map((r) => r.length));
  const maxW = Number(spec.options?.width || dia.max_width_mm);
  const colW = Math.min(Number(dia.col_width_mm), maxW / cols);
  const cells = [];
  table.forEach((row, r) => {
    for (let c = 0; c < cols; c += 1) {
      const [text, attrs] = row[c] ?? ['', {}];
      const style = nodeStyle(attrs);
      const isHead = r === 0 || c === 0;
      cells.push({
        row: r, col: c, text, borders: [...BOX_BORDERS],
        fill: style.fill || ((r === 0 && c === 0 && !text) ? dia.root_fill : (isHead ? dia.box_fill : null)),
        char: 'diagram', colSpan: 1, rowSpan: 1,
        textColor: style.color || null, borderColor: style.border || null, borderType: null,
      });
    }
  });
  return {
    rows: table.length, cols, colWidths: new Array(cols).fill(colW),
    rowHeights: new Array(table.length).fill(Number(dia.row_height_mm)),
    cells, warnings: [], fallbackToImage: false,
  };
}

// ──────────────────────────────────────────────────────────────
// XML 조각 (xmlgen.py 이식)
// ──────────────────────────────────────────────────────────────
const escapeXml = (s) => String(s)
  .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

const fontId = (key) => (key === 'bold' ? 0 : 1);

function charPrXml(id, sizePt, bold, color = '#000000', font = 0, borderFillId = 2) {
  const b = bold ? ' bold="1"' : '';
  const f = String(font);
  return `<hh:charPr id="${id}" height="${pt(sizePt)}" textColor="${color}" shadeColor="none"`
    + ` useFontSpace="0" useKerning="0" symMark="NONE" borderFillIDRef="${borderFillId}"${b}>`
    + `<hh:fontRef hangul="${f}" latin="${f}" hanja="${f}" japanese="${f}" other="${f}" symbol="${f}" user="${f}"/>`
    + '<hh:ratio hangul="100" latin="100" hanja="100" japanese="100" other="100" symbol="100" user="100"/>'
    + '<hh:spacing hangul="0" latin="0" hanja="0" japanese="0" other="0" symbol="0" user="0"/>'
    + '<hh:relSz hangul="100" latin="100" hanja="100" japanese="100" other="100" symbol="100" user="100"/>'
    + '<hh:offset hangul="0" latin="0" hanja="0" japanese="0" other="0" symbol="0" user="0"/>'
    + '<hh:underline type="NONE" shape="SOLID" color="#000000"/>'
    + '<hh:strikeout shape="NONE" color="#000000"/><hh:outline type="NONE"/>'
    + '<hh:shadow type="NONE" color="#C0C0C0" offsetX="10" offsetY="10"/></hh:charPr>';
}

function paraPrXml(id, { left = 0, indent = 0, align = 'JUSTIFY', spacingBelow = 0, lineSpacing = 180 }) {
  const body = '<hh:margin>'
    + `<hc:intent value="${indent}" unit="HWPUNIT"/>`
    + `<hc:left value="${left}" unit="HWPUNIT"/>`
    + '<hc:right value="0" unit="HWPUNIT"/><hc:prev value="0" unit="HWPUNIT"/>'
    + `<hc:next value="${spacingBelow}" unit="HWPUNIT"/></hh:margin>`
    + `<hh:lineSpacing type="PERCENT" value="${lineSpacing}" unit="HWPUNIT"/>`;
  return `<hh:paraPr id="${id}" tabPrIDRef="0" condense="0" fontLineHeight="0" snapToGrid="1"`
    + ' suppressLineNumbers="0" checked="0" textDir="LTR">'
    + `<hh:align horizontal="${align}" vertical="BASELINE"/>`
    + '<hh:heading type="NONE" idRef="0" level="0"/>'
    + '<hh:breakSetting breakLatinWord="KEEP_WORD" breakNonLatinWord="KEEP_WORD" widowOrphan="0"'
    + ' keepWithNext="0" keepLines="0" pageBreakBefore="0" lineWrap="BREAK"/>'
    + '<hh:autoSpacing eAsianEng="0" eAsianNum="0"/>'
    + '<hp:switch><hp:case hp:required-namespace="http://www.hancom.co.kr/hwpml/2016/HwpUnitChar">'
    + `${body}</hp:case><hp:default>${body}</hp:default></hp:switch>`
    + '<hh:border borderFillIDRef="2" offsetLeft="0" offsetRight="0" offsetTop="0" offsetBottom="0"'
    + ' connect="0" ignoreMargin="0"/></hh:paraPr>';
}

function borderFillXml(id, { borders = BOX_BORDERS, color = '#000000', fill = null, width = '0.12 mm', type = 'SOLID' }) {
  const edge = (name) => (borders.includes(name)
    ? `<hh:${name}Border type="${type}" width="${width}" color="${color}"/>`
    : `<hh:${name}Border type="NONE" width="${width}" color="${color}"/>`);
  const brush = fill
    ? `<hc:fillBrush><hc:winBrush faceColor="${fill}" hatchColor="#999999" alpha="0"/></hc:fillBrush>`
    : '';
  return `<hh:borderFill id="${id}" threeD="0" shadow="0" centerLine="NONE" breakCellSeparateLine="0">`
    + '<hh:slash type="NONE" Crooked="0" isCounter="0"/><hh:backSlash type="NONE" Crooked="0" isCounter="0"/>'
    + edge('left') + edge('right') + edge('top') + edge('bottom')
    + `<hh:diagonal type="NONE" width="${width}" color="${color}"/>${brush}</hh:borderFill>`;
}

const styleXml = (id, name, eng, paraPr, charPr, next) =>
  `<hh:style id="${id}" type="PARA" name="${escapeXml(name)}" engName="${escapeXml(eng)}"`
  + ` paraPrIDRef="${paraPr}" charPrIDRef="${charPr}" nextStyleIDRef="${next}" langID="1042" lockForm="0"/>`;

// ──────────────────────────────────────────────────────────────
// 엔진 (engine.py 이식)
// ──────────────────────────────────────────────────────────────
function nextId(xml, tag, fallback = 0) {
  const ids = [...xml.matchAll(new RegExp(`<${tag} id="(\\d+)"`, 'g'))].map((m) => Number(m[1]));
  return ids.length ? Math.max(...ids) + 1 : fallback;
}

const diagramTextCfg = (profile, color) => ({
  name: `도식(${color})`, size_pt: profile.diagram.font_size_pt, bold: true, font: 'bold',
  color, left_pt: 0, indent_pt: 0, spacing_below_pt: 0, line_spacing: 130, align: 'CENTER',
});

function styleConfigs(profile, textKeys = []) {
  const dia = profile.diagram;
  const out = profile.levels.map((lv) => [lv.key, lv]);
  out.push(['table_top', profile.table.top], ['table_mid', profile.table.mid],
    ['table_left', profile.table.left], ['body', profile.body]);
  out.push(['diagram', {
    name: '도식', size_pt: dia.font_size_pt, bold: true, font: 'bold',
    color: dia.box_color, left_pt: 0, indent_pt: 0, spacing_below_pt: 0,
    line_spacing: 130, align: 'CENTER',
  }]);
  out.push(['diagram_root', {
    name: '도식(강조)', size_pt: dia.font_size_pt, bold: true, font: 'bold',
    color: dia.root_color, left_pt: 0, indent_pt: 0, spacing_below_pt: 0,
    line_spacing: 130, align: 'CENTER',
  }]);
  for (const key of textKeys) out.push([key, diagramTextCfg(profile, key.slice(4))]);
  return out;
}

function planIds(headerXml, profile, diagramFills, textKeys = []) {
  let charId = nextId(headerXml, 'hh:charPr');
  let paraId = nextId(headerXml, 'hh:paraPr');
  const bfId = nextId(headerXml, 'hh:borderFill', 1);

  const ids = { styles: {}, chars: {}, paras: {}, borderBase: bfId, borderHeader: bfId + 1, diagramFills: new Map() };
  const keys = [...profile.levels.map((lv) => lv.key), 'table_top', 'table_mid', 'table_left', 'body', 'diagram', 'diagram_root', ...textKeys];
  for (const key of keys) {
    ids.chars[key] = charId; charId += 1;
    ids.paras[key] = paraId; paraId += 1;
  }
  let sid = 1;
  for (const lv of profile.levels) { ids.styles[lv.key] = sid; sid += 1; }
  for (const key of ['table_top', 'table_mid', 'table_left', 'body']) { ids.styles[key] = sid; sid += 1; }
  ids.styles.diagram = ids.styles.table_mid;
  ids.styles.diagram_root = ids.styles.table_mid;
  for (const key of textKeys) ids.styles[key] = ids.styles.table_mid;

  let fillId = bfId + 2;
  for (const key of diagramFills) { ids.diagramFills.set(key, fillId); fillId += 1; }
  return ids;
}

const refs = (ids, key) => {
  const k = key in ids.styles ? key : 'body';
  return { style: ids.styles[k], char: ids.chars[k], para: ids.paras[k] };
};

function patchHeader(xml, profile, ids, diagramFills, textKeys = []) {
  let x = xml;
  x = x.replace(/(<hh:font id="0" face=")([^"]+)(")/g, `$1${profile.fonts.bold}$3`);
  x = x.replace(/(<hh:font id="1" face=")([^"]+)(")/g, `$1${profile.fonts.light}$3`);

  x = x.replace(/<hh:paraPr id="0"[\s\S]*?<\/hh:paraPr>/, (block) =>
    block.replace(/(<hh:lineSpacing[^>]*value=")\d+(")/, `$1${Number(profile.body.line_spacing)}$2`));

  const cfgs = styleConfigs(profile, textKeys);
  const chars = cfgs.map(([key, cfg]) => charPrXml(
    ids.chars[key], cfg.size_pt ?? 12, Boolean(cfg.bold),
    cfg.color || '#000000', fontId(cfg.font || 'light'),
  )).join('');
  x = x.replace('</hh:charProperties>', `${chars}</hh:charProperties>`);

  const paras = cfgs.map(([key, cfg]) => paraPrXml(ids.paras[key], {
    left: pt(cfg.left_pt || 0),
    indent: cfg.indent_pt ? -pt(cfg.indent_pt) : 0,
    align: cfg.align || 'JUSTIFY',
    spacingBelow: pt(cfg.spacing_below_pt || 0),
    lineSpacing: Number(cfg.line_spacing ?? 180),
  })).join('');
  x = x.replace('</hh:paraProperties>', `${paras}</hh:paraProperties>`);

  let fills = borderFillXml(ids.borderBase, { color: profile.table.border_color })
    + borderFillXml(ids.borderHeader, { color: profile.table.border_color, fill: profile.table.header_bg });
  for (const [key, id] of ids.diagramFills) {
    const [borderPart, fillPart, colorPart, typePart] = key.split('|');
    const borders = borderPart ? borderPart.split(',') : [];
    fills += borderFillXml(id, {
      borders,
      color: colorPart || (fillPart ? profile.diagram.box_border : profile.diagram.line_color),
      fill: fillPart || null,
      width: `${Number(profile.diagram.line_width_mm)} mm`,
      type: typePart || 'SOLID',
    });
  }
  x = x.replace('</hh:borderFills>', `${fills}</hh:borderFills>`);

  for (const [container, item] of [['charProperties', 'hh:charPr'], ['paraProperties', 'hh:paraPr'], ['borderFills', 'hh:borderFill']]) {
    const block = new RegExp(`<hh:${container}\\b[\\s\\S]*?</hh:${container}>`).exec(x);
    if (block) {
      const count = (block[0].match(new RegExp(`<${item} id="`, 'g')) || []).length;
      x = x.replace(new RegExp(`(<hh:${container}\\s+itemCnt=")\\d+(")`), `$1${count}$2`);
    }
  }

  const styleItems = cfgs.filter(([key]) => key !== 'diagram' && key !== 'diagram_root' && !key.startsWith('dia:'));
  const maxSid = Math.max(...styleItems.map(([key]) => ids.styles[key]));
  const bg = '<hh:style id="0" type="PARA" name="바탕글" engName="Normal" paraPrIDRef="0"'
    + ' charPrIDRef="0" nextStyleIDRef="0" langID="1042" lockForm="0"/>';
  const custom = styleItems.map(([key, cfg]) => {
    const sid = ids.styles[key];
    return styleXml(sid, cfg.name || key, cfg.eng_name || key, ids.paras[key], ids.chars[key],
      sid < maxSid ? sid + 1 : sid);
  }).join('');
  x = x.replace(/<hh:styles\b[\s\S]*?<\/hh:styles>/,
    `<hh:styles itemCnt="${styleItems.length + 1}">${bg}${custom}</hh:styles>`);
  return x;
}

function autoPrefix(kind, n) {
  if (kind === 'AUTO_ROMAN') return n < ROMAN.length ? `${ROMAN[n]}. ` : `${n + 1}. `;
  if (kind === 'AUTO_NUM') return `${n + 1}. `;
  if (kind === 'AUTO_ALPHA') return n < 26 ? `${String.fromCharCode(65 + n)}. ` : `${n + 1}. `;
  if (kind === 'AUTO_HANGUL') return n < HANGUL.length ? `${HANGUL[n]}. ` : `${n + 1}. `;
  if (kind === 'AUTO_CIRCLED') return n < CIRCLED.length ? `${CIRCLED[n]} ` : `${n + 1}) `;
  return '';
}

function makeNumbering(profile) {
  const order = profile.levels.map((lv) => lv.key);
  const counters = new Map(order.map((k) => [k, 0]));
  return (key, kind) => {
    const idx = order.indexOf(key);
    const value = counters.get(key) || 0;
    const text = autoPrefix(kind, value);
    counters.set(key, value + 1);
    order.slice(idx + 1).forEach((deeper) => counters.set(deeper, 0));
    return text;
  };
}

const CELL_HEAD = 'name="" header="0" hasMargin="1" protect="0" editable="0" dirty="1"';
const SUBLIST_HEAD = 'id="" textDirection="HORIZONTAL" lineWrap="BREAK" vertAlign="CENTER"'
  + ' linkListIDRef="0" linkListNextIDRef="0" textWidth="0" textHeight="0" hasTextRef="0" hasNumRef="0"';

function makeIdGen() {
  let n = 1000000;
  return () => { n += 1; return n; };
}

function paraXml(nextIdFn, { para, style, char }, text) {
  const content = text ? `<hp:t>${escapeXml(text)}</hp:t>` : '<hp:t/>';
  return `<hp:p id="${nextIdFn()}" paraPrIDRef="${para}" styleIDRef="${style}" pageBreak="0"`
    + ` columnBreak="0" merged="0"><hp:run charPrIDRef="${char}">${content}</hp:run></hp:p>`;
}

function cellXml(nextIdFn, { row, col, colSpan = 1, rowSpan = 1, width, height, borderFill, style, text, margin }) {
  const inner = paraXml(nextIdFn, style, text);
  return `<hp:tc ${CELL_HEAD} borderFillIDRef="${borderFill}">`
    + `<hp:subList ${SUBLIST_HEAD}>${inner}</hp:subList>`
    + `<hp:cellAddr colAddr="${col}" rowAddr="${row}"/>`
    + `<hp:cellSpan colSpan="${colSpan}" rowSpan="${rowSpan}"/>`
    + `<hp:cellSz width="${width}" height="${height}"/>`
    + `<hp:cellMargin left="${margin}" right="${margin}" top="${margin}" bottom="${margin}"/></hp:tc>`;
}

function tableWrapper(nextIdFn, anchor, inner, { rows, cols, width, height, borderFill, treatAsChar }) {
  return `<hp:p id="${nextIdFn()}" paraPrIDRef="${anchor.para}" styleIDRef="${anchor.style}"`
    + ` pageBreak="0" columnBreak="0" merged="0"><hp:run charPrIDRef="${anchor.char}">`
    + `<hp:tbl id="${nextIdFn()}" zOrder="0" numberingType="TABLE" textWrap="TOP_AND_BOTTOM"`
    + ' textFlow="BOTH_SIDES" lock="0" dropcapstyle="None" pageBreak="CELL" repeatHeader="0"'
    + ` rowCnt="${rows}" colCnt="${cols}" cellSpacing="0" borderFillIDRef="${borderFill}" noAdjust="0">`
    + `<hp:sz width="${width}" widthRelTo="ABSOLUTE" height="${height}" heightRelTo="ABSOLUTE" protect="0"/>`
    + `<hp:pos treatAsChar="${treatAsChar ? 1 : 0}" affectLSpacing="0" flowWithText="1" allowOverlap="0"`
    + ' holdAnchorAndSO="0" vertRelTo="PARA" horzRelTo="COLUMN" vertAlign="TOP" horzAlign="LEFT"'
    + ' vertOffset="0" horzOffset="0"/>'
    + '<hp:outMargin left="0" right="0" top="0" bottom="0"/>'
    + '<hp:inMargin left="510" right="510" top="141" bottom="141"/>'
    + `${inner}</hp:tbl></hp:run></hp:p>`;
}

const fillKey = (cell, dia) => {
  const color = cell.borderColor || (cell.fill ? dia.box_border : dia.line_color);
  const type = cell.borderType || dia.line_type || 'SOLID';
  return `${[...cell.borders].sort().join(',')}|${cell.fill || ''}|${color}|${type}`;
};

const textColors = (grid) => [...new Set(grid.cells.map((c) => c.textColor).filter(Boolean))];

function collectDiagramFills(items, profile) {
  const keys = new Set();
  const textKeys = new Set();
  const grids = new Map();
  const warnings = [];
  items.forEach((item, index) => {
    if (item.type !== 'diagram') return;
    const render = item.spec.options?.render || profile.diagram.render;
    if (render === 'image') {
      warnings.push(`도식 '${item.spec.title || item.spec.type}': 웹 버전은 이미지 렌더를 `
        + '지원하지 않아 표로 만듭니다(파이썬판에서는 PNG로 그려집니다)');
    }
    const grid = buildGrid(item.spec, profile, true);
    warnings.push(...grid.warnings);
    grids.set(index, grid);
    keys.add('||' + profile.diagram.line_color + '|SOLID');       // 투명 셀
    for (const cell of grid.cells) keys.add(fillKey(cell, grid.diagram || profile.diagram));
    for (const color of textColors(grid)) textKeys.add(`dia:${color}`);
  });
  return { keys: [...keys], textKeys: [...textKeys], grids, warnings };
}

function contentTableXml(nextIdFn, item, profile, ids) {
  const cfg = profile.table;
  const cols = item.cols;
  const width = cfg.width_mm > 0 ? mm(cfg.width_mm) : mm(162.5);
  const colWidth = Math.floor(width / cols);
  const rowHeight = 3600;
  const margin = mm(cfg.cell_margin_mm || 0);
  const top = refs(ids, 'table_top');
  const mid = refs(ids, 'table_mid');

  let rowsXml = '';
  for (let r = 0; r < item.rows; r += 1) {
    let cells = '';
    for (let c = 0; c < cols; c += 1) {
      const isHeader = r === 0 && item.header !== false;
      cells += cellXml(nextIdFn, {
        row: r, col: c, width: colWidth, height: rowHeight,
        borderFill: isHeader ? ids.borderHeader : ids.borderBase,
        style: isHeader ? top : mid,
        text: item.data[r * cols + c] ?? '',
        margin,
      });
    }
    rowsXml += `<hp:tr>${cells}</hp:tr>`;
  }
  return tableWrapper(nextIdFn, anchorRefs(profile, ids), rowsXml, {
    rows: item.rows, cols, width, height: rowHeight * item.rows,
    borderFill: ids.borderBase, treatAsChar: cfg.treat_as_char,
  });
}

function diagramTableXml(nextIdFn, grid, profile, ids) {
  const width = mm(grid.colWidths.reduce((a, b) => a + b, 0));
  const height = mm(grid.rowHeights.reduce((a, b) => a + b, 0));
  const margin = mm(0.2);
  const dia = grid.diagram || profile.diagram;
  const blank = ids.diagramFills.get('||' + profile.diagram.line_color + '|SOLID');
  const byPos = new Map(grid.cells.map((cell) => [`${cell.row},${cell.col}`, cell]));
  const covered = new Set();
  for (const cell of grid.cells) {
    for (let c = cell.col; c < cell.col + cell.colSpan; c += 1) {
      for (let r = cell.row; r < cell.row + cell.rowSpan; r += 1) {
        if (r !== cell.row || c !== cell.col) covered.add(`${r},${c}`);
      }
    }
  }

  let rowsXml = '';
  for (let r = 0; r < grid.rows; r += 1) {
    let cells = '';
    for (let c = 0; c < grid.cols; c += 1) {
      if (covered.has(`${r},${c}`)) continue;
      const cell = byPos.get(`${r},${c}`);
      const colSpan = cell?.colSpan ?? 1;
      const rowSpan = cell?.rowSpan ?? 1;
      const cellWidth = mm(grid.colWidths.slice(c, c + colSpan).reduce((a, b) => a + b, 0));
      const cellHeight = mm(grid.rowHeights.slice(r, r + rowSpan).reduce((a, b) => a + b, 0));
      cells += cellXml(nextIdFn, {
        row: r, col: c, colSpan, rowSpan, width: cellWidth, height: cellHeight,
        borderFill: cell ? ids.diagramFills.get(fillKey(cell, dia)) : blank,
        style: refs(ids, cell?.textColor && `dia:${cell.textColor}` in ids.styles
          ? `dia:${cell.textColor}` : (cell?.char || 'diagram')),
        text: cell?.text || '',
        margin,
      });
    }
    rowsXml += `<hp:tr>${cells}</hp:tr>`;
  }

  let xml = tableWrapper(nextIdFn, anchorRefs(profile, ids), rowsXml, {
    rows: grid.rows, cols: grid.cols, width, height,
    borderFill: blank, treatAsChar: profile.table.treat_as_char,
  });
  if (grid.title) xml += paraXml(nextIdFn, refs(ids, 'table_mid'), grid.title);
  return xml;
}

function anchorRefs(profile, ids) {
  let key = profile.table.anchor_level;
  if (!key) {
    const body = bodyLevels(profile);
    key = body.length ? body[body.length - 1].key : 'body';
  }
  return refs(ids, key);
}

function buildSection(templateSection, profile, ids, items, grids) {
  const margin = profile.page.margin_mm;
  let head = templateSection.slice(0, templateSection.indexOf('</hp:p>') + '</hp:p>'.length);
  head = head.replace(/<hp:margin header="[^"]*"[^/]*\/>/,
    `<hp:margin header="${mm(margin.header)}" footer="${mm(margin.footer)}" gutter="0"`
    + ` left="${mm(margin.left)}" right="${mm(margin.right)}" top="${mm(margin.top)}"`
    + ` bottom="${mm(margin.bottom)}"/>`);

  const nextIdFn = makeIdGen();
  const numbering = makeNumbering(profile);
  const levelByKey = new Map(profile.levels.map((lv) => [lv.key, lv]));
  let body = '';

  items.forEach((item, index) => {
    if (item.type === 'blank') {
      body += paraXml(nextIdFn, refs(ids, 'body'), '');
    } else if (item.type === 'table') {
      body += contentTableXml(nextIdFn, item, profile, ids);
    } else if (item.type === 'diagram') {
      const grid = grids.get(index);
      if (grid) body += diagramTableXml(nextIdFn, grid, profile, ids);
    } else {
      const key = item.key || 'body';
      const level = levelByKey.get(key);
      let text = String(item.text ?? '');
      if (level) {
        const prefix = String(level.prefix || '');
        text = (prefix.startsWith('AUTO_') ? numbering(key, prefix) : prefix) + text;
      }
      body += paraXml(nextIdFn, refs(ids, key), text);
    }
  });

  return `${head}${body}</hs:sec>`;
}

/**
 * 템플릿 hwpx 바이트 + 프로파일 + 콘텐츠 → hwpx 바이트.
 * @returns {Promise<{bytes: Uint8Array, warnings: string[]}>}
 */
export async function buildDocument(templateBytes, userProfile, items) {
  const profile = mergeProfile(userProfile);
  const files = await unzip(templateBytes);
  const decoder = new TextDecoder();
  const encoder = new TextEncoder();

  const headerXml = decoder.decode(files.get('Contents/header.xml'));
  const sectionXml = decoder.decode(files.get('Contents/section0.xml'));

  const { keys, textKeys, grids, warnings } = collectDiagramFills(items, profile);
  const ids = planIds(headerXml, profile, keys, textKeys);

  files.set('Contents/header.xml', encoder.encode(patchHeader(headerXml, profile, ids, keys, textKeys)));
  files.set('Contents/section0.xml', encoder.encode(buildSection(sectionXml, profile, ids, items, grids)));

  return { bytes: await zip(files), warnings };
}

/** 마커 텍스트 한 번에 처리: 파싱 → 검사 → 생성 */
export async function buildFromText(templateBytes, userProfile, text) {
  const profile = mergeProfile(userProfile);
  const parsed = parseText(text, profile);
  const issues = lintItems(parsed.items, profile, parsed.lineOf, parsed.warnings);
  const { bytes, warnings } = await buildDocument(templateBytes, profile, parsed.items);
  return { bytes, warnings, issues, items: parsed.items, profile };
}

export const base64ToBytes = (b64) => {
  const binary = typeof atob === 'function' ? atob(b64) : Buffer.from(b64, 'base64').toString('binary');
  const out = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) out[i] = binary.charCodeAt(i);
  return out;
};

const API = {
  DEFAULT_PROFILE, mergeProfile, parseText, lintItems, parseDiagramBlock, buildGrid,
  buildDocument, buildFromText, base64ToBytes, mm, pt,
};
if (typeof window !== 'undefined') window.HwpxStudio = API;
export default API;
