/**
 * 도식 수집 (capture.py 이식).
 *
 * Mermaid·SVG·HTML을 읽어 `:::diagram` 블록 문자열로 바꾼다. 파이썬판과 같은
 * 결과를 내야 한다(tools/compare_js_python.py가 대조한다).
 */

import { normalizeColor } from './hwpx-studio.js';

const MM_ID = '[A-Za-z0-9_.]+';
const MM_NODE = new RegExp(
  `(${MM_ID})\\s*(\\[\\[|\\[\\(|\\[|\\(\\(|\\(|\\{\\{|\\{)\\s*"?(.*?)"?\\s*(\\]\\]|\\)\\]|\\]|\\)\\)|\\)|\\}\\}|\\})`, 'g');
const MM_EDGE = new RegExp(
  `(${MM_ID})(?:[\\[({][^\\]|)}]*[\\])}]+)?\\s*(-\\.-+>|-\\.-+|-{2,}>|-{2,}|={2,}>|={2,}|--[ox])\\s*(?:\\|[^|]*\\|)?\\s*(?=(${MM_ID}))`, 'g');
const MM_STYLE = new RegExp(`^\\s*style\\s+(${MM_ID})\\s+(.*)$`);
const MM_CLASSDEF = new RegExp(`^\\s*classDef\\s+(${MM_ID})\\s+(.*)$`);
const MM_CLASS = new RegExp(`^\\s*class\\s+([A-Za-z0-9_.,]+)\\s+(${MM_ID})`);
const MM_HEADER = /^\s*(?:flowchart|graph)\s+(TB|TD|BT|RL|LR)?/i;
const MM_TITLE = /^\s*title\s*:?\s*(.+)$/i;

const MERMAID_FENCE = /```\s*mermaid\s*\n([\s\S]*?)```/i;
const MERMAID_IN_HTML = /<(?:pre|div)[^>]*class="[^"]*mermaid[^"]*"[^>]*>([\s\S]*?)<\/(?:pre|div)>/i;
const SVG_IN_HTML = /<svg\b[\s\S]*?<\/svg>/i;

const ATTR_ORDER = ['fill', 'color', 'border', 'link', 'link_color'];

const unescapeHtml = (s) => String(s)
  .replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"')
  .replace(/&#39;/g, "'").replace(/&amp;/g, '&');

function nodeLine(text, style) {
  const attrs = ATTR_ORDER.filter((k) => style[k]).map((k) => `${k}=${style[k]}`).join(' ');
  return attrs ? `${text} {${attrs}}` : text;
}

// ──────────────────────────────────────────────────────────────
// 그래프 → 트리
// ──────────────────────────────────────────────────────────────
function treeLines(nodes, edges, warnings) {
  const byKey = new Map(nodes.map((n) => [n.key, n]));
  const order = nodes.map((n) => n.key);
  const children = new Map(order.map((k) => [k, []]));
  const parent = new Map();
  const edgeStyle = new Map();
  let dropped = 0;

  for (const edge of edges) {
    if (!byKey.has(edge.src) || !byKey.has(edge.dst)) continue;
    if (parent.has(edge.dst) || edge.dst === edge.src) { dropped += 1; continue; }
    parent.set(edge.dst, edge.src);
    edgeStyle.set(edge.dst, edge.style);
    children.get(edge.src).push(edge.dst);
  }
  if (dropped) {
    warnings.push(`한 상자에 들어오는 연결선이 여러 개여서 ${dropped}개는 계층에서 뺐다`
      + '(표 도식은 상자마다 부모 하나만 그린다). 필요하면 손으로 옮길 것');
  }

  const rank = new Map(order.map((k, i) => [k, i]));
  for (const group of children.values()) group.sort((a, b) => rank.get(a) - rank.get(b));

  const lines = [];
  const seen = new Set();
  const emit = (key, depth) => {
    if (seen.has(key)) return;
    seen.add(key);
    const node = byKey.get(key);
    const style = { ...node.style, ...(edgeStyle.get(key) || {}) };
    lines.push('  '.repeat(depth) + nodeLine(node.text, style));
    for (const child of children.get(key)) emit(child, depth + 1);
  };
  for (const key of order) if (!parent.has(key)) emit(key, 0);
  for (const key of order) if (!seen.has(key)) emit(key, 0);
  return lines;
}

function isChain(nodes, edges) {
  if (nodes.length < 2 || edges.length !== nodes.length - 1) return false;
  const out = new Map();
  const inn = new Map();
  for (const e of edges) {
    out.set(e.src, (out.get(e.src) || 0) + 1);
    inn.set(e.dst, (inn.get(e.dst) || 0) + 1);
  }
  return [...out.values()].every((v) => v === 1) && [...inn.values()].every((v) => v === 1);
}

function chainLine(nodes, edges) {
  const byKey = new Map(nodes.map((n) => [n.key, n]));
  const next = new Map(edges.map((e) => [e.src, e.dst]));
  const dsts = new Set(edges.map((e) => e.dst));
  let key = nodes.find((n) => !dsts.has(n.key))?.key;
  const steps = [];
  while (key && byKey.has(key) && steps.length <= byKey.size) {
    const node = byKey.get(key);
    steps.push(nodeLine(node.text, node.style));
    key = next.get(key);
  }
  return [steps.join(' → ')];
}

function makeSpec(nodes, edges, title, warnings, preferFlow = false) {
  if (!nodes.length) return { type: 'org', title, options: {}, lines: [] };
  if ((preferFlow || nodes.length > 2) && isChain(nodes, edges)) {
    return { type: 'flow', title, options: {}, lines: chainLine(nodes, edges) };
  }
  return { type: 'org', title, options: {}, lines: treeLines(nodes, edges, warnings) };
}

// ──────────────────────────────────────────────────────────────
// Mermaid
// ──────────────────────────────────────────────────────────────
function mermaidStyle(text) {
  const out = {};
  for (const part of text.split(/[,;]/)) {
    const i = part.indexOf(':');
    if (i < 0) continue;
    const key = part.slice(0, i).trim().toLowerCase();
    const value = part.slice(i + 1).trim();
    if (key === 'fill') { const c = normalizeColor(value); if (c) out.fill = c; }
    else if (key === 'stroke') { const c = normalizeColor(value); if (c) out.border = c; }
    else if (key === 'color') { const c = normalizeColor(value); if (c) out.color = c; }
    else if (key === 'stroke-dasharray' && value) out.link = 'dash';
  }
  return out;
}

export function fromMermaid(text, title = '') {
  const warnings = [];
  const nodes = [];
  const index = new Map();
  const edges = [];
  const classStyles = new Map();
  const pendingClass = [];
  let direction = '';

  const touch = (key, label) => {
    let node = index.get(key);
    if (!node) {
      node = { key, text: label || key, style: {} };
      index.set(key, node);
      nodes.push(node);
    } else if (label) node.text = label;
    return node;
  };

  for (const raw of text.split('\n')) {
    let line = raw.split('%%')[0].replace(/\s+$/, '');
    if (!line.trim()) continue;

    const head = MM_HEADER.exec(line);
    if (head) {
      direction = (head[1] || '').toUpperCase();
      const rest = line.slice(head[0].length).trim();
      if (!rest) continue;
      line = rest;
    }

    let m = MM_TITLE.exec(line);
    if (m && !title) { title = m[1].trim(); continue; }
    m = MM_CLASSDEF.exec(line);
    if (m) { classStyles.set(m[1], mermaidStyle(m[2])); continue; }
    m = MM_CLASS.exec(line);
    if (m) { pendingClass.push([m[1].split(',').map((k) => k.trim()), m[2]]); continue; }
    m = MM_STYLE.exec(line);
    if (m) { Object.assign(touch(m[1]).style, mermaidStyle(m[2])); continue; }

    for (const hit of line.matchAll(/([A-Za-z0-9_.]+):::([A-Za-z0-9_.]+)/g)) {
      pendingClass.push([[hit[1]], hit[2]]);
    }
    line = line.replace(/:::([A-Za-z0-9_.]+)/g, '');

    for (const hit of line.matchAll(MM_NODE)) {
      touch(hit[1], unescapeHtml(hit[3].trim()) || hit[1]);
    }
    for (const hit of line.matchAll(MM_EDGE)) {
      touch(hit[1]);
      touch(hit[3]);
      edges.push({ src: hit[1], dst: hit[3], style: hit[2].includes('.') ? { link: 'dash' } : {} });
    }
  }

  for (const [keys, cls] of pendingClass) {
    const style = classStyles.get(cls);
    if (!style) continue;
    for (const key of keys) if (index.has(key)) Object.assign(index.get(key).style, style);
  }
  if (!nodes.length) warnings.push('Mermaid에서 상자를 찾지 못했다(flowchart/graph 문법만 읽는다)');

  const spec = makeSpec(nodes, edges, title, warnings, direction === 'LR' || direction === 'RL');
  if (spec.type === 'flow' && (direction === 'TB' || direction === 'TD')) spec.options.direction = 'down';
  return { spec, source: 'mermaid', warnings };
}

// ──────────────────────────────────────────────────────────────
// SVG
// ──────────────────────────────────────────────────────────────
const num = (value, fallback = 0) => {
  const n = parseFloat(String(value ?? '').replace(/[^0-9.\-+eE]/g, ''));
  return Number.isFinite(n) ? n : fallback;
};

/**
 * SVG 요소 훑기. DOMParser에 기대지 않는다 — 브라우저와 Node(대조 도구)에서
 * 같은 결과가 나와야 하기 때문이다. 읽는 것은 rect·text·line·path·polyline뿐이라
 * 이 정도 훑기로 충분하다.
 */
function svgElements(text) {
  const out = [];
  const tagRe = /<([A-Za-z_][\w.:-]*)\b([^>]*?)(\/?)>/g;
  let m;
  while ((m = tagRe.exec(text)) !== null) {
    const tag = m[1].replace(/^.*:/, '').toLowerCase();
    if (!['rect', 'text', 'line', 'path', 'polyline'].includes(tag)) continue;
    const attrs = {};
    for (const a of m[2].matchAll(/([\w.:-]+)\s*=\s*"([^"]*)"|([\w.:-]+)\s*=\s*'([^']*)'/g)) {
      attrs[(a[1] || a[3]).toLowerCase()] = a[2] ?? a[4];
    }
    let inner = '';
    if (tag === 'text' && !m[3]) {                 // <text>…</text> 안의 글자
      const rest = text.slice(tagRe.lastIndex);
      const end = /<\/(?:[A-Za-z_][\w.:-]*:)?text\s*>/i.exec(rest);
      inner = unescapeHtml((end ? rest.slice(0, end.index) : rest).replace(/<[^>]*>/g, '')).split(/\s+/).filter(Boolean).join(' ');
    }
    out.push({ tag, attrs, inner });
  }
  return out;
}

function svgProps(attrs) {
  const props = {};
  for (const key of ['fill', 'stroke', 'stroke-dasharray', 'color']) {
    if (attrs[key]) props[key] = attrs[key];
  }
  for (const part of (attrs.style || '').split(';')) {
    const i = part.indexOf(':');
    if (i > 0) props[part.slice(0, i).trim().toLowerCase()] = part.slice(i + 1).trim();
  }
  return props;
}

function boxStyle(props) {
  const out = {};
  const fill = normalizeColor(props.fill);
  if (fill && (props.fill || '').toLowerCase() !== 'none') out.fill = fill;
  const border = normalizeColor(props.stroke);
  if (border) out.border = border;
  return out;
}

const pathPoints = (d) => {
  const nums = (String(d || '').match(/-?\d+(?:\.\d+)?/g) || []).map(Number);
  const out = [];
  for (let i = 0; i + 1 < nums.length; i += 2) out.push([nums[i], nums[i + 1]]);
  return out;
};

function nearestBox(boxes, x, y) {
  let best = null;
  let bestD = null;
  boxes.forEach((b, i) => {
    const dx = Math.max(b.x - x, 0, x - (b.x + b.w));
    const dy = Math.max(b.y - y, 0, y - (b.y + b.h));
    const d = dx * dx + dy * dy;
    if (bestD === null || d < bestD) { best = i; bestD = d; }
  });
  const tol = Math.max(...boxes.map((b) => b.h), 10) * 1.5;
  return bestD !== null && bestD <= tol * tol ? best : null;
}

function rowsToEdges(boxes) {
  if (boxes.length < 2) return [];
  const tol = Math.max(...boxes.map((b) => b.h)) * 0.6;
  const rows = [];
  boxes.forEach((b, i) => {
    if (rows.length && Math.abs(boxes[rows[rows.length - 1][0]].cy - b.cy) <= tol) {
      rows[rows.length - 1].push(i);
    } else rows.push([i]);
  });
  const edges = [];
  for (let d = 1; d < rows.length; d += 1) {
    for (const i of rows[d]) {
      const parent = rows[d - 1].reduce((best, j) =>
        (Math.abs(boxes[j].cx - boxes[i].cx) < Math.abs(boxes[best].cx - boxes[i].cx) ? j : best),
      rows[d - 1][0]);
      edges.push({ src: String(parent), dst: String(i), style: {} });
    }
  }
  return edges;
}

export function fromSvg(text, title = '') {
  const warnings = [];
  let boxes = [];
  const texts = [];
  const rawEdges = [];
  for (const { tag, attrs, inner } of svgElements(text)) {
    const props = svgProps(attrs);
    if (tag === 'rect') {
      boxes.push({
        x: num(attrs.x), y: num(attrs.y), w: num(attrs.width), h: num(attrs.height),
        text: '', style: boxStyle(props),
      });
    } else if (tag === 'text') {
      const content = inner.trim();
      if (content) texts.push([num(attrs.x), num(attrs.y), content, props]);
    } else if (tag === 'line') {
      rawEdges.push([[num(attrs.x1), num(attrs.y1)], [num(attrs.x2), num(attrs.y2)], props]);
    } else if (tag === 'path' || tag === 'polyline') {
      const points = pathPoints(tag === 'path' ? attrs.d : attrs.points);
      if (points.length >= 2) rawEdges.push([points[0], points[points.length - 1], props]);
    }
  }

  boxes = boxes.filter((b) => b.w > 1 && b.h > 1);
  if (!boxes.length) {
    warnings.push('SVG에서 상자(<rect>)를 찾지 못했다');
    return { spec: { type: 'org', title, options: {}, lines: [] }, source: 'svg', warnings };
  }
  const widest = Math.max(...boxes.map((b) => b.w * b.h));
  const kept = boxes.filter((b) => b.w * b.h < widest || boxes.length === 1);
  boxes = kept.length ? kept : boxes;
  for (const b of boxes) { b.cx = b.x + b.w / 2; b.cy = b.y + b.h / 2; }

  for (const [x, y, content, props] of texts) {
    let target = boxes.find((b) => x >= b.x - 2 && x <= b.x + b.w + 2 && y >= b.y - 2 && y <= b.y + b.h + 2);
    if (!target) {
      target = boxes.reduce((best, b) =>
        ((b.cx - x) ** 2 + (b.cy - y) ** 2 < (best.cx - x) ** 2 + (best.cy - y) ** 2 ? b : best), boxes[0]);
      if (Math.abs(target.cy - y) > target.h) continue;
    }
    target.text = target.text ? `${target.text} ${content}` : content;
    const color = normalizeColor(props.fill);
    if (color && !target.style.color) target.style.color = color;
  }

  boxes = boxes.filter((b) => b.text);
  if (!boxes.length) {
    warnings.push('상자 안에서 글자를 찾지 못했다');
    return { spec: { type: 'org', title, options: {}, lines: [] }, source: 'svg', warnings };
  }
  boxes.sort((a, b) => (Math.round(a.cy * 10) - Math.round(b.cy * 10)) || (a.cx - b.cx));

  const nodes = boxes.map((b, i) => ({ key: String(i), text: b.text, style: { ...b.style } }));
  let edges = [];
  const seen = new Set();
  for (const [[x1, y1], [x2, y2], props] of rawEdges) {
    const a = nearestBox(boxes, x1, y1);
    const b = nearestBox(boxes, x2, y2);
    if (a === null || b === null || a === b) continue;
    const [src, dst] = boxes[a].cy <= boxes[b].cy ? [a, b] : [b, a];
    if (seen.has(`${src},${dst}`)) continue;
    seen.add(`${src},${dst}`);
    const style = {};
    if (props['stroke-dasharray']) style.link = 'dash';
    const color = normalizeColor(props.stroke);
    if (color) style.link_color = color;
    edges.push({ src: String(src), dst: String(dst), style });
  }
  if (!edges.length) {
    edges = rowsToEdges(boxes);
    if (edges.length) {
      warnings.push('연결선을 찾지 못해 상자의 높이(같은 줄 = 같은 단계)로 계층을 세웠다 — 확인할 것');
    }
  }

  return { spec: makeSpec(nodes, edges, title, warnings), source: 'svg', warnings };
}

// ──────────────────────────────────────────────────────────────
// HTML / 자동 판별 / 직렬화
// ──────────────────────────────────────────────────────────────
export function fromHtml(text, title = '') {
  const m = MERMAID_FENCE.exec(text) || MERMAID_IN_HTML.exec(text);
  if (m) return { ...fromMermaid(unescapeHtml(m[1]), title), source: 'html(mermaid)' };
  const svg = SVG_IN_HTML.exec(text);
  if (svg) return { ...fromSvg(svg[0], title), source: 'html(svg)' };
  return { spec: { type: 'org', title, options: {}, lines: [] }, source: 'html',
    warnings: ['HTML 안에서 <svg>도 mermaid 블록도 찾지 못했다'] };
}

export function captureText(text, kind = 'auto', title = '') {
  let k = (kind || 'auto').toLowerCase();
  if (k === 'auto') {
    const head = text.replace(/^\s+/, '').slice(0, 400).toLowerCase();
    if (head.startsWith('<!doctype html') || head.startsWith('<html')
        || text.slice(0, 4000).toLowerCase().includes('<body')) k = 'html';
    else if (MERMAID_FENCE.test(text) || MERMAID_IN_HTML.test(text)) k = 'html';
    else if (text.slice(0, 4000).toLowerCase().includes('<svg')) k = 'svg';
    else k = 'mermaid';
  }
  if (k === 'svg') return fromSvg(text, title);
  if (k === 'html') return fromHtml(text, title);
  return fromMermaid(text, title);
}

export function specToText(spec) {
  let header = `type=${spec.type}`;
  if (spec.title) header += ` title="${spec.title}"`;
  for (const [key, value] of Object.entries(spec.options || {})) header += ` ${key}=${value}`;
  return `:::diagram ${header}\n${spec.lines.join('\n')}\n:::`;
}

export default { captureText, fromMermaid, fromSvg, fromHtml, specToText };
