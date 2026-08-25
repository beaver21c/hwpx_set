/**
 * 서식 없는 hwpx → 마커 텍스트 — hwpx_studio/assets/read_hwpx.py의 브라우저 이식.
 *
 * 파이썬 쪽이 단일 원본이다. 꾸러미에 들어가는 `read_hwpx.py`가 그 원본이고,
 * 이 파일은 웹에서 같은 일을 하도록 옮긴 것이다.
 * `tools/compare_js_python.py`가 두 결과를 맞대어 본다.
 */

import { unzip } from './zip.js';
import {
  attr, contentsOf, innerAt, num, refuseBinaryHwp, scan, unescapeXml,
} from './xml.js';

export const SYMBOL_LADDER = ['□', '■', '○', '●', '-', '–', '·', '･', '•', '※'];

export const NUMBER_PATTERNS = [
  ['ROMAN', /^[ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩ]+\s*[.)]\s+/],
  ['DIGIT_DOT', /^\d{1,2}\.\s+/],
  ['HANGUL', /^[가-힣]\.\s+/],
  ['DIGIT_PAREN', /^\d{1,2}\)\s+/],
  ['CIRCLED', /^[①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮]\s*/],
];

const SKIP = new Set(['footNote', 'endNote', 'header', 'footer', 'caption']);

// ──────────────────────────────────────────────────────────────
// header.xml
// ──────────────────────────────────────────────────────────────
function charSizes(header) {
  const out = {};
  for (const m of header.matchAll(/<hh:charPr\b([^>]*)>([\s\S]*?)<\/hh:charPr>/g)) {
    out[num(m[1], 'id')] = {
      size: num(m[1], 'height', 1000) / 100,
      bold: /<hh:bold\b/.test(m[2]) || ['1', 'true'].includes(attr(m[1], 'bold')),
    };
  }
  return out;
}

function leftMargins(header) {
  const out = {};
  for (const m of header.matchAll(/<hh:paraPr\b([^>]*)>([\s\S]*?)<\/hh:paraPr>/g)) {
    const margin = /<hh:margin\b[^>]*>([\s\S]*?)<\/hh:margin>/.exec(m[2]);
    const left = margin ? /<hc:left\b([^>]*)\/>/.exec(margin[1]) : null;
    out[num(m[1], 'id')] = left ? num(left[1], 'value') / 100 : 0;
  }
  return out;
}

// ──────────────────────────────────────────────────────────────
// 본문 읽기
// ──────────────────────────────────────────────────────────────
function textOf(xml) {
  let out = '';
  for (const m of xml.matchAll(/<hp:t\b[^>]*>([\s\S]*?)<\/hp:t>/g)) out += unescapeXml(m[1]);
  return out;
}

function noteText(xml) {
  return textOf(xml).trim();
}

/** 문단 하나에서 글자·각주 자리·첫 글자모양을 뽑는다(직계 run만 본다). */
function paragraphParts(inner) {
  let text = '';
  const notes = [];
  let charId = null;
  let depth = 0;
  let runStart = -1;

  for (const token of scan(inner)) {
    if (token.name === 'p' && token.raw === 'hp:p') {
      depth += token.close ? -1 : (token.selfClose ? 0 : 1);
      continue;
    }
    if (depth > 0) continue;                       // 표 셀 안 문단은 따로 읽는다
    if (token.name === 'run' && token.raw === 'hp:run' && !token.close) {
      if (charId === null && /charPrIDRef="/.test(token.attrs)) {
        charId = num(token.attrs, 'charPrIDRef');
      }
      runStart = token.end;
      continue;
    }
    if (token.name === 'run' && token.close && runStart >= 0) {
      const body = inner.slice(runStart, token.start);
      let skip = 0;
      for (const piece of scan(body)) {
        if (piece.start < skip) continue;
        if (piece.name === 'footNote' && !piece.close) {
          // 각주 본문은 본문 글자가 아니다. 통째로 건너뛴다.
          const block = innerAt(body, 'hp:footNote', piece.start);
          notes.push([text.length, block ? noteText(block.inner) : '']);
          skip = block ? block.end : piece.end;
        } else if (piece.name === 't' && !piece.close && !piece.selfClose) {
          const closed = body.indexOf('</hp:t>', piece.end);
          if (closed >= 0) { text += unescapeXml(body.slice(piece.end, closed)); skip = closed; }
        }
      }
      runStart = -1;
    }
  }
  return { text, notes, charId };
}

function cellText(cellXml) {
  const lines = [];
  for (const m of cellXml.matchAll(/<hp:p\b[^>]*>([\s\S]*?)<\/hp:p>/g)) {
    const value = textOf(m[1]).trim();
    if (value) lines.push(value);
  }
  return lines.join('<br>');
}

export function readBlocks(parts) {
  const header = parts['Contents/header.xml'] || '';
  const sizes = charSizes(header);
  const lefts = leftMargins(header);
  const blocks = [];

  const sections = Object.keys(parts)
    .filter((n) => /^Contents\/section\d+\.xml$/.test(n)).sort();
  for (const name of sections) readSection(parts[name], sizes, lefts, blocks);
  return blocks;
}

function readSection(section, sizes, lefts, blocks) {
  let cursor = 0;
  let skipUntil = 0;

  for (const token of scan(section)) {
    if (token.start < cursor || token.start < skipUntil) continue;
    if (token.close || token.selfClose) continue;

    if (SKIP.has(token.name)) {
      const block = innerAt(section, token.raw, token.start);
      skipUntil = block ? block.end : token.end;
      continue;
    }
    if (token.name === 'tbl' && token.raw === 'hp:tbl') {
      const block = innerAt(section, 'hp:tbl', token.start);
      if (!block) continue;
      const rows = [];
      for (const tr of block.inner.matchAll(/<hp:tr>([\s\S]*?)<\/hp:tr>/g)) {
        const cells = [...tr[1].matchAll(/<hp:tc\b[^>]*>([\s\S]*?)<\/hp:tc>/g)]
          .map((tc) => cellText(tc[1]));
        if (cells.length) rows.push(cells);
      }
      if (rows.length) blocks.push({ kind: 'table', rows, notes: [] });
      cursor = block.end;
      continue;
    }
    if (token.name === 'pic' && token.raw === 'hp:pic') {
      blocks.push({ kind: 'picture', text: '', notes: [] });
      const block = innerAt(section, 'hp:pic', token.start);
      cursor = block ? block.end : token.end;
      continue;
    }
    if (token.name === 'p' && token.raw === 'hp:p') {
      const block = innerAt(section, 'hp:p', token.start);
      if (!block) continue;
      if (/<hp:tbl[ >]|<hp:pic[ >]/.test(block.inner)) continue;   // 안쪽을 따로 훑는다
      const { text, notes, charId } = paragraphParts(block.inner);
      if (text.trim()) {
        const shape = sizes[charId === null ? 0 : charId] || { size: 10, bold: false };
        blocks.push({
          kind: 'para', text: text.trim(), notes,
          size_pt: shape.size, bold: shape.bold,
          left_pt: lefts[num(token.attrs, 'paraPrIDRef')] || 0,
          depth: 0, symbol: null, number: null,
        });
      }
      cursor = block.end;
    }
  }
}

// ──────────────────────────────────────────────────────────────
// 계층 추정
// ──────────────────────────────────────────────────────────────
function cutPrefix(block, size) {
  const rest = block.text.slice(size);
  const dropped = size + rest.length - rest.replace(/^\s+/, '').length;
  block.text = rest.trim();
  block.notes = block.notes.map(([offset, note]) => [Math.max(offset - dropped, 0), note]);
}

export function classify(blocks) {
  const notes = [];
  for (const block of blocks) {
    if (block.kind !== 'para') continue;
    const lead = block.text.slice(0, 1);
    if (SYMBOL_LADDER.includes(lead) && [' ', '　'].includes(block.text.slice(1, 2))) {
      block.symbol = lead;
      cutPrefix(block, 2);
      continue;
    }
    for (const [kind, pattern] of NUMBER_PATTERNS) {
      const m = pattern.exec(block.text);
      if (m) { block.number = kind; cutPrefix(block, m[0].length); break; }
    }
  }

  const paras = blocks.filter((b) => b.kind === 'para');
  const sizes = [...new Set(paras.map((b) => b.size_pt))].sort((a, b) => b - a);
  const numberKinds = NUMBER_PATTERNS.map(([k]) => k)
    .filter((k) => paras.some((b) => b.number === k));
  const symbols = SYMBOL_LADDER.filter((s) => paras.some((b) => b.symbol === s));

  if (numberKinds.length) notes.push(`줄머리 번호로 제목을 갈랐다: ${numberKinds.join(', ')}`);
  if (symbols.length) notes.push(`줄머리 기호로 본문 단계를 갈랐다: ${symbols.join(' ')}`);
  if (!numberKinds.length && !symbols.length) {
    notes.push('줄머리 기호·번호가 없어 **글자 크기만으로** 갈랐다 → 결과를 반드시 훑어볼 것');
  }

  for (const block of paras) {
    if (block.number) block.depth = numberKinds.indexOf(block.number);
    else if (block.symbol) block.depth = numberKinds.length + symbols.indexOf(block.symbol);
    else {
      const rank = sizes.indexOf(block.size_pt);
      block.depth = numberKinds.length + symbols.length + (rank < 0 ? sizes.length : rank);
    }
  }
  return notes;
}

// ──────────────────────────────────────────────────────────────
// 마커 텍스트로 쓰기
// ──────────────────────────────────────────────────────────────
export function toMarkerText(blocks, markers) {
  const depths = [...new Set(blocks.filter((b) => b.kind === 'para').map((b) => b.depth))]
    .sort((a, b) => a - b);
  const mapping = new Map();
  depths.forEach((d, i) => {
    mapping.set(d, markers.length ? markers[Math.min(i, markers.length - 1)] : '');
  });

  const lines = [];
  const definitions = [];
  let noteNo = 0;
  const blank = () => { if (lines.length && lines[lines.length - 1] !== '') lines.push(''); };

  for (const block of blocks) {
    if (block.kind === 'picture') {
      blank();
      lines.push('[그림 자리 — 도식이면 :::diagram 블록으로 옮길 것]');
      continue;
    }
    if (block.kind === 'table') {
      blank();
      const width = Math.max(...block.rows.map((r) => r.length));
      block.rows.forEach((row, i) => {
        const cells = [...row, ...Array(Math.max(0, width - row.length)).fill('')]
          .slice(0, width);
        lines.push(`| ${cells.join(' | ')} |`);
        if (i === 0) lines.push(`|${'---|'.repeat(width)}`);
      });
      lines.push('');
      continue;
    }

    let text = block.text;
    const ascending = [...block.notes].sort((a, b) => a[0] - b[0])
      .map(([offset, note], i) => [offset, note, noteNo + i + 1]);
    noteNo += ascending.length;
    for (const [offset, , number] of [...ascending].sort((a, b) => b[0] - a[0])) {
      const cut = Math.min(Math.max(offset, 0), text.length);
      text = `${text.slice(0, cut)}[^${number}]${text.slice(cut)}`;
    }
    for (const [, note, number] of ascending) definitions.push(`[^${number}]: ${note}`);

    const marker = mapping.get(block.depth) || '';
    lines.push(marker ? `${marker} ${text}`.trim() : text);
  }

  if (definitions.length) {
    lines.push('');
    lines.push(...definitions.sort(
      (a, b) => Number.parseInt(a.match(/\d+/)[0], 10) - Number.parseInt(b.match(/\d+/)[0], 10)));
  }
  return `${lines.join('\n').replace(/\s+$/, '')}\n`;
}

export function renderReadbackReport(blocks, markers, notes) {
  const paras = blocks.filter((b) => b.kind === 'para');
  const depths = [...new Set(paras.map((b) => b.depth))].sort((a, b) => a - b);
  const out = ['# 읽어 들인 결과', '',
    '**추정이다.** 아래 대응이 뜻과 다르면 나온 텍스트에서 마커를 고치면 된다.',
    '', '| 원본의 단계 | 근거 | 문단 수 | 이 양식의 마커 |', '|---|---|---|---|'];
  depths.forEach((depth, i) => {
    const members = paras.filter((b) => b.depth === depth);
    const first = members[0];
    const why = first.number ? `번호 ${first.number}`
      : (first.symbol ? `기호 \`${first.symbol}\`` : `글자 ${first.size_pt}pt`);
    const marker = markers.length ? markers[Math.min(i, markers.length - 1)] : '(없음)';
    out.push(`| ${i + 1}단계 | ${why} | ${members.length} | \`${marker}\` |`);
  });

  const tables = blocks.filter((b) => b.kind === 'table').length;
  const pics = blocks.filter((b) => b.kind === 'picture').length;
  const noteCount = blocks.reduce((sum, b) => sum + (b.notes ? b.notes.length : 0), 0);
  out.push('', `- 표 ${tables}개, 각주 ${noteCount}개, 그림 ${pics}개`);
  if (pics) {
    out.push('- **그림은 읽지 못한다.** `[그림 자리]`로 남겼다. 조직도·절차도라면 '
      + '그림을 보고 도식 블록으로 옮겨 적어야 한다');
  }
  out.push('', ...notes.map((n) => `- ${n}`));
  return `${out.join('\n')}\n`;
}

/** hwpx 바이트 + 대상 양식 → {text, report}. */
export async function readBack(buffer, form) {
  refuseBinaryHwp(buffer);
  const parts = contentsOf(await unzip(buffer));
  const blocks = readBlocks(parts);
  if (!blocks.length) throw new Error('읽을 내용이 없습니다.');
  const notes = classify(blocks);
  const markers = ((form || {}).levels || []).map((lv) => lv.marker).filter(Boolean);
  return {
    text: toMarkerText(blocks, markers),
    report: renderReadbackReport(blocks, markers, notes),
    blocks,
  };
}
