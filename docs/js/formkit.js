/**
 * 양식 hwpx 해부 — hwpx_studio/formkit.py의 브라우저 이식.
 *
 * 파이썬 쪽이 단일 원본이고 이 파일은 같은 결과를 내야 한다.
 * `tools/compare_js_python.py`가 두 엔진의 form.json을 맞대어 본다.
 *
 * DOMParser에 기대지 않는다. 브라우저와 Node(대조 도구) 양쪽에서 같아야 하기 때문이다.
 */

import { attr, innerAt, innerFrom, num, scan, unescapeXml } from './xml.js';

export const SCHEMA_ID = 'hwpx-studio/form@1';
export const HEADER_PATH = 'Contents/header.xml';

export const BULLET_MARKERS = '□○-·･•▪◦∙※◇◆▶';
export const HEADING_MARKERS = ['#', '##', '###', '####'];
export const FALLBACK_MARKERS = '□○-·※▪◇▶';

/**
 * 줄머리 기호를 **누가** 붙이는가. 양식마다 다르므로 고를 수 있어야 한다.
 *   auto   — 양식을 보고 정한다
 *   hangul — 한글에 맡긴다. 도구는 본문에 기호를 적지 않는다
 *   text   — 도구가 본문 텍스트에 적어 넣는다
 */
export const BULLET_SOURCES = ['auto', 'hangul', 'text'];

const LAYOUT_TABLE_MAX_CELLS = 3;

const ROMAN_CHARS = 'ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩⅪⅫ';
const SKIP_SUBTREES = new Set(['footNote', 'endNote', 'caption', 'header', 'footer']);

const CIRCLED_CHARS = '①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮';

const PREFIX_PATTERNS = [
  ['AUTO_CHAPTER', /^제\s?\d{1,2}\s?장\s/],
  ['AUTO_SECTION', /^제\s?\d{1,2}\s?절\s/],
  ['AUTO_ROMAN', new RegExp(`^[${ROMAN_CHARS}]+[.)]\\s`)],
  ['AUTO_NUM', /^\d{1,2}\.\s/],
  ['AUTO_PAREN', /^\d{1,2}\)\s/],
  ['AUTO_ALPHA', /^[A-Z][.)]\s/],
  ['AUTO_CIRCLED', new RegExp(`^[${CIRCLED_CHARS}]\\s?`)],
  ['AUTO_HANGUL', /^[가나다라마바사아자차카타파하][.)]\s/],
];

const KEY_BY_MARKER = {
  '□': 'box', '○': 'circle', '-': 'hyphen', '·': 'dot', '･': 'dot',
  '•': 'dot', '▪': 'dot', '◦': 'dot', '∙': 'dot', '※': 'note',
  '◇': 'diamond', '◆': 'diamond', '▶': 'arrow',
};

const PT = 100;      // 1pt = 100 HWPUNIT
const MM = 283.47;   // 1mm ≈ 283.47 HWPUNIT

//: 흔한 용지 [이름, 너비 mm, 높이 mm]
const PAPERS = [['A4', 210, 297], ['B5', 182, 257], ['A5', 148, 210],
  ['A3', 297, 420], ['B4', 257, 364], ['Letter', 216, 279]];

//: 표 주 스타일에 흔히 붙는 이름
const TABLE_NOTE_NAMES = ['표 주', '표주', '자료', '출처', '주석', '표 자료'];


const round2 = (value) => Math.round(value * 100) / 100;

/** 11.0 대신 11로 적는다. 파이썬 쪽 표기와 같아야 한다. */
const pt = (value) => String(Number(value));

// ──────────────────────────────────────────────────────────────
// header.xml 읽기
// ──────────────────────────────────────────────────────────────
export function bulletChars(header) {
  const out = {};
  for (const m of header.matchAll(/<hh:bullet\b([^>]*)>/g)) {
    const char = attr(m[1], 'char');
    if (char) out[num(m[1], 'id')] = char;
  }
  return out;
}

export function numberingFormats(header) {
  const out = {};
  for (const m of header.matchAll(/<hh:numbering\b([^>]*)>([\s\S]*?)<\/hh:numbering>/g)) {
    const id = num(m[1], 'id');
    const levels = {};
    for (const head of m[2].matchAll(/<hh:paraHead\b([^>]*)>([\s\S]*?)<\/hh:paraHead>/g)) {
      const text = head[2].trim();
      if (text) levels[num(head[1], 'level', 1)] = unescapeXml(text);
    }
    if (Object.keys(levels).length) out[id] = levels;
  }
  return out;
}

export function headings(header) {
  const out = {};
  for (const m of header.matchAll(/<hh:paraPr\b([^>]*)>([\s\S]*?)<\/hh:paraPr>/g)) {
    const node = /<hh:heading\b([^>]*)\/>/.exec(m[2]);
    if (!node) continue;
    out[num(m[1], 'id')] = {
      type: attr(node[1], 'type', 'NONE'),
      idRef: num(node[1], 'idRef'),
      level: num(node[1], 'level'),
    };
  }
  return out;
}

export function charProps(header) {
  const out = {};
  for (const m of header.matchAll(/<hh:charPr\b([^>]*)>([\s\S]*?)<\/hh:charPr>/g)) {
    const ref = /<hh:fontRef\b([^>]*)\/>/.exec(m[2]);
    out[num(m[1], 'id')] = {
      size_pt: round2(num(m[1], 'height', 1000) / PT),
      bold: /<hh:bold\b/.test(m[2]) || ['1', 'true'].includes(attr(m[1], 'bold')),
      color: (attr(m[1], 'textColor', '#000000')).toUpperCase(),
      font_id: ref ? num(ref[1], 'hangul') : 0,
    };
  }
  return out;
}

export function paraProps(header) {
  const out = {};
  for (const m of header.matchAll(/<hh:paraPr\b([^>]*)>([\s\S]*?)<\/hh:paraPr>/g)) {
    const body = m[2];
    const margin = /<hh:margin\b[^>]*>([\s\S]*?)<\/hh:margin>/.exec(body);
    const side = (tag) => {
      if (!margin) return 0;
      const node = new RegExp(`<hc:${tag}\\b([^>]*)/>`).exec(margin[1]);
      return node ? num(node[1], 'value') : 0;
    };
    const spacing = /<hh:lineSpacing\b([^>]*)\/>/.exec(body);
    const align = /<hh:align\b([^>]*)\/>/.exec(body);
    out[num(m[1], 'id')] = {
      left_pt: round2(side('left') / PT),
      indent_pt: round2(Math.abs(side('intent')) / PT),
      spacing_below_pt: round2(side('next') / PT),
      line_spacing: spacing ? Math.trunc(num(spacing[1], 'value', 160)) : 160,
      align: align ? attr(align[1], 'horizontal', 'JUSTIFY') : 'JUSTIFY',
    };
  }
  return out;
}

export function styles(header) {
  const out = {};
  for (const m of header.matchAll(/<hh:style\b([^>]*?)\/?>/g)) {
    out[num(m[1], 'id')] = {
      name: unescapeXml(attr(m[1], 'name')),
      eng_name: unescapeXml(attr(m[1], 'engName')),
      para_pr: num(m[1], 'paraPrIDRef'),
      char_pr: num(m[1], 'charPrIDRef'),
    };
  }
  return out;
}

export function fontFaces(header) {
  const out = {};
  for (const group of header.matchAll(
    /<hh:fontface\b([^>]*)>([\s\S]*?)<\/hh:fontface>/g)) {
    const hangul = attr(group[1], 'lang', '').toUpperCase() === 'HANGUL';
    for (const font of group[2].matchAll(/<hh:font\b([^>]*?)\/?>/g)) {
      const id = num(font[1], 'id');
      if (hangul || !(id in out)) out[id] = unescapeXml(attr(font[1], 'face'));
    }
  }
  return out;
}

// ──────────────────────────────────────────────────────────────
// section0.xml 읽기
// ──────────────────────────────────────────────────────────────
export function topLevelParagraphs(section) {
  const tops = [];
  let depth = 0;
  for (const token of scan(section)) {
    if (token.name !== 'p' || token.raw !== 'hp:p') continue;
    if (token.selfClose) {
      if (depth === 0) tops.push([token.start, token.end, `<${token.raw}${token.attrs}/>`]);
      continue;
    }
    if (token.close) {
      depth -= 1;
      if (depth === 0 && tops.length) tops[tops.length - 1][1] = token.end;
    } else {
      if (depth === 0) tops.push([token.start, null, `<${token.raw}${token.attrs}>`]);
      depth += 1;
    }
  }
  return tops.filter((entry) => entry[1] !== null);
}

/** 본문 문단 목록. 각주·캡션·머리말은 빼고, 표 안은 in_table로 표시한다. */
export function paragraphRecords(section) {
  const records = [];
  let justAfterTable = false;
  const openParas = [];        // 열려 있는 hp:p들
  const stack = [];            // 태그 이름 스택
  let skipDepth = 0;
  let tableDepth = 0;
  let dataTableDepth = 0;
  let cursor = 0;

  const text = (from, to) => {
    let out = '';
    for (const m of section.slice(from, to).matchAll(/<hp:t\b[^>]*>([\s\S]*?)<\/hp:t>/g)) {
      out += unescapeXml(m[1]);
    }
    return out;
  };

  for (const token of scan(section)) {
    const { name, raw, close, selfClose, attrs } = token;

    if (skipDepth > 0) {
      if (!selfClose && !close) skipDepth += 1;
      else if (close) skipDepth -= 1;
      continue;
    }
    if (!close && !selfClose && SKIP_SUBTREES.has(name)) { skipDepth = 1; continue; }

    if (name === 'tbl' && raw === 'hp:tbl') {
      if (close) { tableDepth -= 1; if (dataTableDepth > tableDepth) dataTableDepth = tableDepth; }
      else if (!selfClose) {
        tableDepth += 1;
        const block = innerFrom(section, 'hp:tbl', token.start);
        const rows = block ? (block.inner.match(/<hp:tr>/g) || []).length : 0;
        const cells = block ? (block.inner.match(/<hp:tc\b/g) || []).length : 0;
        if (rows > 1 || cells > LAYOUT_TABLE_MAX_CELLS) dataTableDepth = tableDepth;
        if (tableDepth === 1) justAfterTable = true;
        for (const para of openParas) para.hasObject = true;
      }
      continue;
    }
    if ((name === 'pic' || name === 'container') && !close) {
      // 그리기 개체 안 글자는 본문이 아니라 도형의 글자다. 장 표지가 그렇게 되어 있다.
      for (const para of openParas) para.hasObject = true;
      continue;
    }

    if (name === 'p' && raw === 'hp:p') {
      if (selfClose) continue;
      if (close) {
        const para = openParas.pop();
        stack.pop();
        if (para && !para.hasObject) {
          const body = text(para.bodyStart, token.start);
          const record = {
            style: num(para.attrs, 'styleIDRef'),
            para: num(para.attrs, 'paraPrIDRef'),
            char: para.char === null ? 0 : para.char,
            text: body.trim().slice(0, 80),
            in_table: para.inTable,
            after_table: false,
          };
          records.push(record);
          if (record.text) {
            // 빈 문단은 표와 주 사이의 간격일 뿐이라 표시를 먹지 않는다
            record.after_table = justAfterTable;
            justAfterTable = false;
          }
        }
        cursor = token.end;
      } else {
        openParas.push({
          attrs, bodyStart: token.end, char: null,
          inTable: dataTableDepth > 0, hasObject: false,
        });
        stack.push(name);
      }
      continue;
    }

    if (name === 'run' && !close && openParas.length) {
      const para = openParas[openParas.length - 1];
      if (para.char === null && /charPrIDRef="/.test(attrs)) para.char = num(attrs, 'charPrIDRef');
    }
  }
  void cursor;
  return records;
}

export function preambleCut(section, bodyStyles) {
  const wanted = new Set(bodyStyles.map(String));
  for (const [start, , tag] of topLevelParagraphs(section)) {
    const m = /styleIDRef="(\d+)"/.exec(tag);
    if (m && wanted.has(m[1])) return start;
  }
  const end = section.lastIndexOf('</hs:sec>');
  return end >= 0 ? end : section.length;
}

// ──────────────────────────────────────────────────────────────
// 쪽 설정·각주 모양·장 표지
// ──────────────────────────────────────────────────────────────
function paperName(widthMm, heightMm) {
  for (const [name, w, h] of PAPERS) {
    if ((Math.abs(widthMm - w) <= 2 && Math.abs(heightMm - h) <= 2)
      || (Math.abs(widthMm - h) <= 2 && Math.abs(heightMm - w) <= 2)) return name;
  }
  return `${widthMm}×${heightMm}mm`;
}

const round1 = (value) => Math.round(value * 10) / 10;

export function pageSetup(section) {
  const page = /<hp:pagePr\b([^>]*)>/.exec(section);
  const margin = /<hp:margin\b([^>]*)\/>/.exec(section);
  const width = page ? num(page[1], 'width', 59528) : 59528;
  const height = page ? num(page[1], 'height', 84186) : 84186;
  const side = (name) => {
    if (!margin) return 0;
    const m = new RegExp(`${name}="(-?\\d+)"`).exec(margin[1]);
    return m ? round1(Number.parseInt(m[1], 10) / MM) : 0;
  };
  const margins = {};
  for (const name of ['left', 'right', 'top', 'bottom', 'header', 'footer']) {
    margins[name] = side(name);
  }
  return {
    size: paperName(round1(width / MM), round1(height / MM)),
    width,
    height,
    orientation: width > height ? '가로' : '세로',
    margin_mm: margins,
    has_header: section.includes('<hp:header'),
    has_footer: section.includes('<hp:footer'),
    has_page_number: section.includes('<hp:pageNum'),
  };
}

const attrOf = (match, name, fallback = '') => {
  if (!match) return fallback;
  const found = new RegExp(`${name}="([^"]*)"`).exec(match[1]);
  return found ? found[1] : fallback;
};

export function footnoteShape(section) {
  const block = /<hp:footNotePr\b[\s\S]*?<\/hp:footNotePr>/.exec(section);
  if (!block) return null;
  const body = block[0];
  const fmt = /<hp:autoNumFormat\b([^>]*)\/>/.exec(body);
  const line = /<hp:noteLine\b([^>]*)\/>/.exec(body);
  const numbering = /<hp:numbering\b([^>]*)\/>/.exec(body);
  const place = /<hp:placement\b([^>]*)\/>/.exec(body);
  return {
    number_format: attrOf(fmt, 'type', 'DIGIT'),
    prefix_char: attrOf(fmt, 'prefixChar', ''),
    suffix_char: attrOf(fmt, 'suffixChar', ''),
    superscript: ['1', 'true'].includes(attrOf(fmt, 'supscript', '0')),
    line_type: attrOf(line, 'type', 'SOLID'),
    line_length: attrOf(line, 'length', '-1'),
    line_color: attrOf(line, 'color', '#000000'),
    restart: attrOf(numbering, 'type', 'CONTINUOUS'),
    place: attrOf(place, 'place', ''),
  };
}

export function chapterCover(preamble) {
  const alone = new RegExp(`<hp:t>([${ROMAN_CHARS}])</hp:t>`).exec(preamble);
  const titled = new RegExp(`<hp:t>([${ROMAN_CHARS}])\\.\\s*([^<]*)</hp:t>`).exec(preamble);
  if (!alone && !titled) return null;
  return {
    roman: (alone || titled)[1],
    title: titled ? titled[2].trim() : null,
    has_container: preamble.includes('<hp:container'),
    title_in_text: Boolean(titled),
  };
}

// ──────────────────────────────────────────────────────────────
// 표 골격
// ──────────────────────────────────────────────────────────────
function firstDataTable(section) {
  let from = 0;
  for (;;) {
    const block = innerFrom(section, 'hp:tbl', from);
    if (!block) return null;
    const chunk = section.slice(block.start, block.end);
    if ((chunk.match(/<hp:tr>/g) || []).length > 1) return chunk;
    from = block.end;
  }
}

function commonest(values, fallback) {
  if (!values.length) return fallback;
  const counts = new Map();
  for (const value of values) counts.set(value, (counts.get(value) || 0) + 1);
  let best = values[0];
  let bestCount = -1;
  for (const [value, count] of counts) {
    if (count > bestCount) { best = value; bestCount = count; }
  }
  return Number.parseInt(best, 10);
}

/** `> 옛 표 제목` → `> `. 번호 뒤에 오는 구분 기호만 남긴다. */
function captionTail(text) {
  const head = /^([^\w가-힣]*\s*)/.exec(text);
  return head ? head[1] : '';
}

function captionShape(tableXml) {
  const block = /<hp:caption\b[\s\S]*?<\/hp:caption>/.exec(tableXml);
  if (!block) return null;
  const cap = block[0];
  const open = /<hp:caption\b([^>]*)>/.exec(cap);
  const p = /<hp:p\b([^>]*)>/.exec(cap);
  const char = /charPrIDRef="(\d+)"/.exec(cap);
  const texts = [...cap.matchAll(/<hp:t>([\s\S]*?)<\/hp:t>/g)].map((m) => unescapeXml(m[1]));
  const auto = /<hp:autoNum\b[^>]*numType="(\w+)"/.exec(cap);
  const fmt = /<hp:autoNumFormat\b[^>]*\/>/.exec(cap);
  const before = texts.length ? texts[0] : '';
  const roman = new RegExp(`[${ROMAN_CHARS}]`).exec(before);
  return {
    side: attr(open ? open[1] : '', 'side', 'TOP'),
    chapter_roman: roman ? roman[0] : null,
    width: num(open ? open[1] : '', 'width', 8504),
    gap: num(open ? open[1] : '', 'gap', 850),
    style: p ? num(p[1], 'styleIDRef') : 0,
    para: p ? num(p[1], 'paraPrIDRef') : 0,
    char: char ? Number.parseInt(char[1], 10) : 0,
    auto_num: auto ? auto[1] : null,
    auto_num_format: fmt ? fmt[0] : null,
    // 양식에 들어 있던 표본 제목("> 옛 제목")은 버리고 구분 기호만 남긴다
    before: auto ? before : '',
    after: (auto && texts.length > 1) ? captionTail(texts[1]) : '',
    sample: texts.length ? texts[texts.length - 1].trim() : '',
  };
}

function tableSkeleton(section, notes) {
  const chunk = firstDataTable(section);
  if (!chunk) {
    notes.push('본문에서 데이터 표를 찾지 못해 표 골격은 기본값으로 채웠다 '
      + '→ 표를 쓸 양식이면 form.json의 table을 손으로 맞출 것');
    return {
      border_fill: 1, header_fill: 1, body_fill: 1,
      width: 39456, row_min_height: 1182,
      cell_margin: { left: 494, right: 494, top: 0, bottom: 0 },
      in_margin: { left: 141, right: 141, top: 141, bottom: 141 },
      cell_para: { style: 0, para: 0, char: 0 },
      caption: null,
      guessed: true,
    };
  }

  const rows = [...chunk.matchAll(/<hp:tr>[\s\S]*?<\/hp:tr>/g)].map((m) => m[0]);
  const fillsOf = (row) => [...row.matchAll(/<hp:tc\b[^>]*borderFillIDRef="(\d+)"/g)]
    .map((m) => m[1]);
  const firstCells = rows.length ? fillsOf(rows[0]) : [];
  const restCells = rows.slice(1).flatMap(fillsOf);

  const bodyFill = commonest(restCells, commonest(firstCells, 1));
  const headerFill = commonest(firstCells, bodyFill);
  if (headerFill === bodyFill && rows.length > 1) {
    notes.push('표 머리행과 본문행의 테두리·배경이 같다 → 머리행 강조가 없는 양식으로 본다');
  }

  let cellPara = { style: 0, para: 0, char: 0 };
  const cell = /<hp:tc\b[\s\S]*?<\/hp:tc>/.exec(chunk);
  if (cell) {
    const p = /<hp:p\b([^>]*)>/.exec(cell[0]);
    const char = /charPrIDRef="(\d+)"/.exec(cell[0]);
    if (p) {
      cellPara = {
        style: num(p[1], 'styleIDRef'),
        para: num(p[1], 'paraPrIDRef'),
        char: char ? Number.parseInt(char[1], 10) : 0,
      };
    }
  }

  const sides = (node, fallback) => {
    const out = {};
    for (const [side, value] of Object.entries(fallback)) {
      const m = node ? new RegExp(`${side}="(-?\\d+)"`).exec(node[0]) : null;
      out[side] = m ? Number.parseInt(m[1], 10) : value;
    }
    return out;
  };

  const margin = /<hp:cellMargin\b[^>]*>/.exec(chunk);
  const inMargin = /<hp:inMargin\b[^>]*>/.exec(chunk);
  const size = /<hp:sz\b([^>]*)>/.exec(chunk);
  const cellSz = /<hp:cellSz\b([^>]*)>/.exec(chunk);
  const open = /<hp:tbl\b([^>]*)>/.exec(chunk);

  return {
    border_fill: num(open ? open[1] : '', 'borderFillIDRef', 1),
    header_fill: headerFill,
    body_fill: bodyFill,
    width: size ? num(size[1], 'width', 39456) : 39456,
    row_min_height: cellSz ? num(cellSz[1], 'height', 1182) : 1182,
    cell_margin: sides(margin, { left: 494, right: 494, top: 0, bottom: 0 }),
    in_margin: sides(inMargin, { left: 141, right: 141, top: 141, bottom: 141 }),
    cell_para: cellPara,
    caption: captionShape(chunk),
    guessed: false,
  };
}

function tableWrapShape(section) {
  const table = innerFrom(section, 'hp:tbl', 0);
  if (!table) return null;
  const before = section.slice(0, table.start);
  const opens = [...before.matchAll(/<hp:p\b([^>]*)>/g)];
  if (!opens.length) return null;
  const last = opens[opens.length - 1];
  const char = /charPrIDRef="(\d+)"/.exec(before.slice(last.index));
  return {
    style: num(last[1], 'styleIDRef'),
    para: num(last[1], 'paraPrIDRef'),
    char: char ? Number.parseInt(char[1], 10) : 0,
  };
}

// ──────────────────────────────────────────────────────────────
// 레벨 추정
// ──────────────────────────────────────────────────────────────
export function guessPrefix(text) {
  if (!text) return null;
  for (const [name, pattern] of PREFIX_PATTERNS) {
    if (pattern.test(text)) return name;
  }
  const symbol = /^([^\w\s]{1,2})\s/.exec(text);
  return symbol ? symbol[1] : null;
}

function levelKey(marker, index, used) {
  let base = KEY_BY_MARKER[marker];
  if (base === undefined) {
    base = /^#+$/.test(marker) ? `h${marker.length}` : `level${index}`;
  }
  let key = base;
  let n = 2;
  while (used.includes(key)) { key = `${base}${n}`; n += 1; }
  return key;
}

/** 표 바로 아래 '자료：…' 줄의 레벨을 골라 낸다. 본문 레벨에서는 빼낸다. */
export function pickTableNote(levels, records, notes) {
  const after = new Map();
  const total = new Map();
  for (const rec of records) {
    if (rec.in_table || !rec.text) continue;
    const key = `${rec.style}|${rec.para}|${rec.char}`;
    total.set(key, (total.get(key) || 0) + 1);
    if (rec.after_table) after.set(key, (after.get(key) || 0) + 1);
  }

  let best = null;
  let reason = '';
  for (const level of levels) {
    // 제목은 표 주가 아니다(prefix에는 기호도 담기므로 번호 유형만 본다)
    if (HEADING_MARKERS.includes(level.marker) || level.auto_number
      || (level.prefix || '').startsWith('AUTO_')) continue;
    const key = `${level.style}|${level.para}|${level.char}`;
    const seen = total.get(key) || 0;
    const hits = after.get(key) || 0;
    const byName = TABLE_NOTE_NAMES.some((name) => level.name.includes(name));
    const byPlace = seen >= 2 && hits === seen;
    if (!byName && !byPlace) continue;
    const bestHits = best ? (after.get(`${best.style}|${best.para}|${best.char}`) || 0) : -1;
    if (hits > bestHits || best === null) {
      best = level;
      reason = byName ? '스타일 이름' : `표 바로 뒤에 ${hits}/${seen}번 나옴`;
    }
  }
  if (best === null) return null;
  levels.splice(levels.indexOf(best), 1);
  notes.push(`'${best.name}' 레벨을 **표 주**로 본다(${reason}). `
    + `\`${best.marker || '※'} 자료：…\`처럼 표 바로 아래에 쓴다`);
  return best;
}

function guessLevels(records, styleMap, paraMap, charMap, headingMap,
  bullets, numberings, notes) {
  const groups = new Map();
  for (const rec of records) {
    if (rec.in_table || !rec.text) continue;
    const key = `${rec.style}|${rec.para}|${rec.char}`;
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(rec);
  }

  const guesses = [];
  for (const [key, items] of groups) {
    const [styleId, paraId, charId] = key.split('|').map(Number);
    const style = styleMap[styleId] || {};
    const pp = paraMap[paraId] || {};
    const cp = charMap[charId] || {};
    const heading = headingMap[paraId] || {};

    let autoBullet = null;
    let autoNumber = null;
    if (heading.type === 'BULLET') {
      autoBullet = bullets[heading.idRef] || null;
    } else if (heading.type === 'NUMBER') {
      const levels = numberings[heading.idRef] || {};
      autoNumber = levels[(heading.level || 0) + 1] || levels[1] || null;
    }

    const leads = items
      .map((r) => r.text.slice(0, 1))
      .filter((lead, i) => BULLET_MARKERS.includes(lead)
        && [' ', '　'].includes(items[i].text.slice(1, 2)));
    const symbolInText = leads.length >= Math.max(1, Math.floor(items.length / 2))
      ? mostCommon(leads) : null;

    const prefixes = items.map((r) => guessPrefix(r.text)).filter(Boolean);
    const prefix = prefixes.length >= Math.max(1, Math.floor(items.length / 2))
      ? mostCommon(prefixes) : null;

    guesses.push({
      key: '', marker: '', name: style.name || `스타일${styleId}`,
      style: styleId, para: paraId, char: charId,
      auto_bullet: autoBullet, auto_number: autoNumber,
      prefix, symbol_in_text: symbolInText, invented: false,
      size_pt: cp.size_pt === undefined ? 12.0 : cp.size_pt,
      left_pt: pp.left_pt === undefined ? 0.0 : pp.left_pt,
      seen: items.length,
      samples: items.slice(0, 3).map((r) => r.text),
    });
  }

  guesses.sort((a, b) => (a.left_pt - b.left_pt) || (b.size_pt - a.size_pt));
  assignMarkers(guesses, notes);
  return guesses;
}

function mostCommon(values) {
  const counts = new Map();
  for (const value of values) counts.set(value, (counts.get(value) || 0) + 1);
  let best = values[0];
  let bestCount = -1;
  for (const [value, count] of counts) {
    if (count > bestCount) { best = value; bestCount = count; }
  }
  return best;
}

function assignMarkers(guesses, notes) {
  const usedKeys = [];
  const usedMarkers = new Set();
  let headingSeq = 0;

  guesses.forEach((g, i) => {
    let marker = '';
    if (g.auto_bullet && BULLET_MARKERS.includes(g.auto_bullet[0])) {
      marker = g.auto_bullet[0];
    } else if (g.auto_number || (g.prefix || '').startsWith('AUTO_')) {
      marker = HEADING_MARKERS[Math.min(headingSeq, HEADING_MARKERS.length - 1)];
      headingSeq += 1;
    } else if (g.symbol_in_text) {
      marker = g.symbol_in_text;
    }
    if (marker && usedMarkers.has(marker)) {
      notes.push(`마커 '${marker}'가 두 레벨에 겹친다(스타일 ${g.style}·${g.name}) `
        + '→ form.json에서 하나를 바꿀 것');
      marker = '';
    }
    if (!marker) {
      marker = [...FALLBACK_MARKERS].find((c) => !usedMarkers.has(c)) || '';
      if (marker) {
        g.invented = true;
        notes.push(`'${g.name}' 레벨에는 기호·번호 근거가 없어 마커를 \`${marker}\`로 `
          + '임의로 정했다. 이 마커로 부르면 그 스타일이 붙고 기호는 찍히지 않는다 '
          + '→ form.json에서 바꿔도 된다');
      }
    }
    if (marker) usedMarkers.add(marker);
    g.marker = marker;
    g.key = levelKey(marker || g.name, i, usedKeys);
    usedKeys.push(g.key);
  });
}

/** 고른 값이 양식과 어긋나면 말한다. 조용히 넘기면 기호가 겹치거나 사라진다. */
export function applyBulletSource(levels, source, notes) {
  if (!BULLET_SOURCES.includes(source)) {
    throw new Error(`글머리표 담당은 ${BULLET_SOURCES.join('·')} 중 하나여야 한다: ${source}`);
  }
  if (source === 'auto') return;
  for (const level of levels) {
    if (!level.marker || HEADING_MARKERS.includes(level.marker)) continue;
    if (source === 'hangul') {
      level.write_override = false;
      if (!level.auto_bullet) {
        notes.push(`'${level.name}' 레벨을 한글에 맡겼지만 이 양식에는 자동 글머리표가 `
          + `걸려 있지 않다 → \`${level.marker}\` 기호가 아무 데서도 찍히지 않는다. `
          + "한글에서 이 스타일에 글머리표를 걸거나 '도구가 붙임'으로 바꿀 것");
      }
    } else {
      level.write_override = true;
      if (level.auto_bullet) {
        notes.push(`'${level.name}' 레벨은 한글이 \`${level.auto_bullet}\`를 자동으로 `
          + '붙이는데 도구까지 적도록 골랐다 → 기호가 두 번 찍힌다. '
          + "한글에서 이 스타일의 글머리표를 끄거나 '한글에 맡김'으로 바꿀 것");
      }
    }
  }
}

function levelDict(g) {
  const writeMarker = g.write_override === undefined
    ? (g.symbol_in_text !== null && g.symbol_in_text !== undefined)
    : g.write_override;
  const numbering = g.auto_number ? null
    : ((g.prefix || '').startsWith('AUTO_') ? g.prefix : null);
  return {
    key: g.key, marker: g.marker, name: g.name,
    style: g.style, para: g.para, char: g.char,
    write_marker: writeMarker,
    numbering,
    marker_invented: g.invented,
    auto_bullet: g.auto_bullet,
    auto_number: g.auto_number,
    size_pt: g.size_pt,
    left_pt: g.left_pt,
    seen: g.seen,
    samples: g.samples.slice(0, 2),
  };
}

// ──────────────────────────────────────────────────────────────
// 조립
// ──────────────────────────────────────────────────────────────
function pickStyleByName(styleMap, names) {
  for (const [id, style] of Object.entries(styleMap)) {
    const label = (style.name || '').trim();
    const eng = (style.eng_name || '').trim();
    if (names.includes(label) || names.includes(eng)) return Number(id);
  }
  return null;
}

/**
 * 푼 hwpx(이름 → 문자열)를 받아 form.json에 담을 객체와 보고서를 만든다.
 * @param {Object} parts Contents/*.xml 내용
 * @param {string} name 양식 이름
 */
export function analyzeParts(parts, name = '양식', bullets = 'auto') {
  if (!parts[HEADER_PATH]) {
    throw new Error('hwpx 안에 Contents/header.xml이 없다 — 한글 문서가 맞는지 확인할 것');
  }
  const sectionNames = Object.keys(parts)
    .filter((n) => /^Contents\/section\d+\.xml$/.test(n)).sort();
  if (!sectionNames.length) throw new Error('hwpx 안에 본문(section0.xml)이 없다');

  const header = parts[HEADER_PATH];
  const section = parts[sectionNames[0]];
  const notes = [];
  if (sectionNames.length > 1) {
    notes.push(`구역이 ${sectionNames.length}개다 → 첫 구역(${sectionNames[0]})만 본문으로 쓴다. `
      + '나머지 구역은 템플릿에 그대로 남는다');
  }

  const styleMap = styles(header);
  const records = paragraphRecords(section);
  const guesses = guessLevels(records, styleMap, paraProps(header), charProps(header),
    headings(header), bulletChars(header), numberingFormats(header), notes);
  if (!guesses.length) {
    notes.push('본문 문단을 하나도 찾지 못했다 → 내용이 든 양식 파일인지 확인할 것');
  }

  const tableNote = pickTableNote(guesses, records, notes);
  applyBulletSource(guesses, bullets, notes);
  const bodyStyles = guesses.map((g) => g.style);
  if (tableNote) bodyStyles.push(tableNote.style);
  const cut = preambleCut(section, bodyStyles);
  const table = tableSkeleton(section, notes);
  const footnoteStyle = pickStyleByName(styleMap, ['각주', 'Footnote']);
  if (footnoteStyle === null) {
    notes.push("각주 스타일(이름 '각주')이 없다 → 각주를 쓰면 한글에서 서식이 흐트러질 수 있다");
  }

  const page = pageSetup(section);
  const noteShape = footnoteShape(section);
  const chapter = chapterCover(section.slice(0, cut));
  if (chapter && !chapter.title_in_text) {
    notes.push("장 표지에 로마자는 있으나 'Ⅱ. 제목' 꼴 제목을 찾지 못했다 "
      + '→ [장: 제목]으로는 번호만 바뀐다');
  }

  const base = styleMap[0] || { para_pr: 0, char_pr: 0 };
  const blank = { style: 0, para: base.para_pr, char: base.char_pr };
  const faces = fontFaces(header);
  const chars = charProps(header);
  const fonts = [...new Set(Object.values(chars)
    .map((cp) => faces[cp.font_id] || '').filter(Boolean))].sort();

  const form = {
    schema: SCHEMA_ID,
    name: name || '양식',
    template: 'template.hwpx',
    bullet_source: bullets,
    section: sectionNames[0],
    header: HEADER_PATH,
    preamble_bytes: cut,
    levels: guesses.map(levelDict),
    blank,
    table_wrap: tableWrapShape(section) || blank,
    table,
    page,
    chapter,
    table_note: tableNote === null ? null : {
      key: tableNote.key,
      marker: tableNote.marker || '※',
      name: tableNote.name,
      style: tableNote.style,
      para: tableNote.para,
      char: tableNote.char,
      write_marker: levelDict(tableNote).write_marker,
    },
    footnote: footnoteStyle === null ? null : {
      style: footnoteStyle,
      para: styleMap[footnoteStyle].para_pr,
      char: styleMap[footnoteStyle].char_pr,
      size_pt: (chars[styleMap[footnoteStyle].char_pr] || {}).size_pt,
      color: (chars[styleMap[footnoteStyle].char_pr] || {}).color,
      shape: noteShape,
    },
    fonts,
    notes,
  };
  return { form, report: renderFormReport(form, guesses), notes };
}

export function renderFormReport(form, levels) {
  const out = [`# 양식 해부 결과 — ${form.name}`, '',
    '이 결과는 **추정**이다. 마커와 레벨이 뜻대로 잡혔는지 보고, ',
    '다르면 `form.json`을 고친 뒤 다시 빌드하면 된다.', '',
    '## 찾아낸 레벨', '',
    '| 마커 | 레벨 | 스타일 | 크기 | 들여쓰기 | 기호·번호를 붙이는 쪽 | 나온 횟수 | 예시 |',
    '|---|---|---|---|---|---|---|---|'];
  for (const g of levels) {
    const numbering = g.auto_number ? null
      : ((g.prefix || '').startsWith('AUTO_') ? g.prefix : null);
    let who;
    if (g.auto_bullet) who = `한글이 자동으로 \`${g.auto_bullet}\``;
    else if (g.auto_number) who = `한글이 자동으로 번호(\`${g.auto_number}\`)`;
    else if (numbering) who = `도구가 번호(${numbering})`;
    else if (levelDict(g).write_marker) who = `도구가 \`${g.marker}\``;
    else who = '없음';
    const first = g.samples.length ? g.samples[0] : '';
    const sample = first.length > 24 ? `${first.slice(0, 24)}…` : first;
    out.push(`| \`${g.marker || '(없음)'}\` | ${g.key} | ${g.name}(${g.style}) | `
      + `${g.size_pt}pt | ${g.left_pt}pt | ${who} | ${g.seen} | ${sample} |`);
  }

  const table = form.table;
  out.push('', '## 표 골격', '',
    `- 표 테두리 채움 \`${table.border_fill}\`, 머리행 \`${table.header_fill}\`, `
    + `본문행 \`${table.body_fill}\``,
    `- 표 폭 ${table.width} HWPUNIT, 행 최소 높이 ${table.row_min_height}`,
    `- 셀 안 문단: 스타일 ${table.cell_para.style} / 문단모양 ${table.cell_para.para} / `
    + `글자모양 ${table.cell_para.char}`);
  if (table.guessed) out.push('- **표를 찾지 못해 기본값이다.** 표를 쓸 양식이면 손으로 맞출 것');
  out.push(`- 캡션: ${table.caption ? `있음 (${table.caption.before || ''}…)` : '없음'}`);

  const page = form.page || {};
  const margin = page.margin_mm || {};
  out.push('', '## 쪽 설정 (그대로 지켜진다)', '',
    `- 용지 ${page.size || '?'} ${page.orientation || ''}`,
    `- 여백(mm): 위 ${margin.top || 0} · 아래 ${margin.bottom || 0} · `
    + `왼 ${margin.left || 0} · 오른 ${margin.right || 0} · `
    + `머리말 ${margin.header || 0} · 꼬리말 ${margin.footer || 0}`);
  const marks = [['머리말', page.has_header], ['꼬리말', page.has_footer],
    ['쪽 번호', page.has_page_number]].filter(([, on]) => on).map(([name]) => name);
  out.push(marks.length ? `- ${marks.join(', ')}이(가) 있다`
    : '- 머리말·꼬리말·쪽 번호는 없다');

  const note = form.table_note;
  const chapter = form.chapter;
  if (note || chapter) {
    out.push('', '## 그 밖의 자리', '');
    if (note) {
      out.push(`- **표 주**: \`${note.marker} 자료：…\`를 표 바로 아래에 쓰면 `
        + `'${note.name}' 스타일이 붙는다`);
    }
    if (chapter) {
      out.push(`- **장 표지**: 지금 \`${chapter.roman}`
        + (chapter.title ? `. ${chapter.title}\`` : '\`')
        + '. `[장: 제목]`과 `--chapter N`으로 바꾼다');
    }
  }
  const caption = (form.table || {}).caption || {};
  if (caption.auto_num) {
    const shape = `${caption.before || ''}n${caption.after || ''}`;
    out.push(`- **표 번호**: \`${shape.trim()}\` 꼴로 한글이 매긴다`
      + (caption.chapter_roman ? ` (장 번호 ${caption.chapter_roman})` : ''));
  }

  const footnote = form.footnote || null;
  if (footnote) {
    const shape = footnote.shape || {};
    out.push('', '## 각주', '',
      `- 스타일 ${footnote.style}번 · ${pt(footnote.size_pt || 0)}pt · `
      + `${footnote.color || '?'}`,
      `- 번호 모양 \`${shape.prefix_char || ''}n${shape.suffix_char || ''}\` `
      + `(${shape.number_format || 'DIGIT'})`
      + (shape.superscript ? ', 위 첨자' : ''),
      `- 구분선 ${shape.line_type || '?'} ${shape.line_color || ''}`
      + `, 번호 매김 ${shape.restart || '?'}`);
  }

  out.push('', '## 보존 구간', '',
    `- \`${form.section}\`의 앞 ${form.preamble_bytes}바이트(용지 설정·표지·머리글)를 `
    + '그대로 두고 그 뒤 본문만 갈아 끼운다',
    `- \`${form.header}\`는 **손대지 않는다.** 자동 글머리표·번호매기기·글꼴이 그대로 산다`);
  if (form.fonts.length) out.push('', '## 쓰인 글꼴', '', form.fonts.join(', '));
  if (form.notes.length) {
    out.push('', '## 살펴볼 것', '', ...form.notes.map((n) => `- ${n}`));
  }
  return `${out.join('\n')}\n`;
}

export function dumpForm(form) {
  return `${JSON.stringify(form, null, 2)}\n`;
}
