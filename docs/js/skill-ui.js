/**
 * ★ 스킬 만들기 — 내장 서식에서 시작해 고치고 싶은 것만 바꿔 스킬 zip을 받는다.
 *
 * 서식(프로파일) 하나를 들고 있고, 칸마다 `data-path`로 그 서식의 한 값에 묶인다.
 * 위계(레벨) 표만 따로 그린다. 고친 서식은 이 브라우저에만 저장한다.
 */

import { HWPX_PROFILES, HWPX_TEMPLATE_B64 } from '../assets.js';
import { base64ToBytes, buildFromText, PAPER_SIZES } from './hwpx-studio.js';
import { buildSkill, packSkill, skillMarkerRows, skillSampleText } from './skillpack.js';

const STATE_KEY = 'hwpx-studio.skill.v1';
const PAPER_CHOICES = ['A4', 'B5', 'A5', 'A3', 'B4', 'Letter', '크라운판', '신국판', '국판', '4x6배판'];
/** 시작 서식별 스킬 영문 이름(claude.ai·ChatGPT 목록에 보이는 이름) */
const PRESET_IDS = {
  'kihasa-research': 'hwpx-crown-report', 'policy-default': 'hwpx-policy-report',
  'gov-3level': 'hwpx-gov-report', narrative: 'hwpx-narrative-report',
};
const DEFAULT_PRESET = 'kihasa-research';

const $ = (id) => document.getElementById(id);
const clone = (value) => JSON.parse(JSON.stringify(value));

/** 자동 번호·캡션 머리. 값이 AUTO_*가 아니면 '글자 직접' */
const HEAD_OPTIONS = [
  ['', '없음'],
  ['AUTO_CHAPTER', '제1장'],
  ['AUTO_SECTION', '제1절'],
  ['AUTO_ROMAN', 'Ⅰ.'],
  ['AUTO_NUM', '1.'],
  ['AUTO_HANGUL', '가.'],
  ['AUTO_PAREN', '1)'],
  ['AUTO_ALPHA', 'A.'],
  ['AUTO_CIRCLED', '①'],
  ['AUTO_TABLE', '〈표 1-1〉 캡션'],
  ['AUTO_FIGURE', '〔그림 1-1〕 캡션'],
  ['TEXT', '기호·글자 직접'],
];

const ALIGNS = [['JUSTIFY', '양쪽'], ['LEFT', '왼쪽'], ['CENTER', '가운데'], ['RIGHT', '오른쪽']];

/** 위계 표의 칸: [머리글, 레벨 키, 종류, 폭(rem)] */
const LEVEL_COLUMNS = [
  ['이름', 'name', 'text', 7],
  ['입력 마커', 'marker', 'text', 4],
  ['머리', 'prefix', 'head', 8],
  ['크기', 'size_pt', 'number', 3.6],
  ['굵게', 'bold', 'check', 2],
  ['글꼴', 'font', 'font', 4.5],
  ['왼쪽 여백', 'left_pt', 'number', 3.6],
  ['내어쓰기', 'indent_pt', 'number', 3.6],
  ['첫 줄', 'first_line_indent_pt', 'number', 3.6],
  ['위 간격', 'spacing_above_pt', 'number', 3.6],
  ['아래 간격', 'spacing_below_pt', 'number', 3.6],
  ['줄 간격%', 'line_spacing', 'number', 3.8],
  ['정렬', 'align', 'align', 4.5],
];

let profile = null;
let preset = DEFAULT_PRESET;
let skillName = '';
let skillId = '';

function presetName(key) {
  return (HWPX_PROFILES[key] && HWPX_PROFILES[key].name) || key;
}

function save() {
  try {
    localStorage.setItem(STATE_KEY, JSON.stringify({ preset, profile, name: skillName, id: skillId }));
  } catch { /* 저장 못 해도 동작에는 지장 없다 */ }
}

function load() {
  try {
    const saved = JSON.parse(localStorage.getItem(STATE_KEY) || 'null');
    if (saved && saved.profile && HWPX_PROFILES[saved.preset]) {
      preset = saved.preset;
      profile = saved.profile;
      skillName = saved.name || presetName(preset);
      skillId = saved.id || PRESET_IDS[preset] || '';
      return;
    }
  } catch { /* 깨진 저장값은 버린다 */ }
  startFrom(DEFAULT_PRESET);
}

function startFrom(key) {
  preset = key;
  profile = clone(HWPX_PROFILES[key]);
  skillName = presetName(key);
  skillId = PRESET_IDS[key] || '';
}

// ──────────────────────────────────────────────────────────────
// 서식 값 읽고 쓰기
// ──────────────────────────────────────────────────────────────
function getPath(obj, path) {
  return path.split('.').reduce((cur, key) => (cur == null ? undefined : cur[key]), obj);
}

function setPath(obj, path, value) {
  const keys = path.split('.');
  let cur = obj;
  keys.slice(0, -1).forEach((key) => {
    if (cur[key] == null || typeof cur[key] !== 'object') cur[key] = {};
    cur = cur[key];
  });
  cur[keys[keys.length - 1]] = value;
}

/** 서식에 값이 없을 때 칸에 보일 기본값(엔진 기본값과 같게) */
const FALLBACK = {
  'page.margin_mm.header': 10, 'page.margin_mm.footer': 10,
  'table.border_color': '#999999', 'table.header_bg': '#4472C4', 'table.top.color': '#FFFFFF',
  'table.top.bold': true, 'table.top.size_pt': 11, 'table.mid.size_pt': 11, 'table.width_mm': 162.5,
  'diagram.box_fill': '#DCE6F1', 'diagram.box_border': '#1F3864', 'diagram.box_color': '#000000',
  'diagram.root_fill': '#1F3864', 'diagram.root_color': '#FFFFFF', 'diagram.line_color': '#1F3864',
  'diagram.font_size_pt': 11, 'diagram.max_width_mm': 160,
  'footnote.size_pt': 8, 'footnote.color': '#808080',
  'rules.period_policy': 'single_sentence_no_period',
  'body.size_pt': 12, 'body.line_spacing': 160, 'body.first_line_indent_pt': 0, 'body.letter_spacing': 0,
  mode: 'outline',
};

function fillFields() {
  document.querySelectorAll('[data-panel="skill"] [data-path]').forEach((field) => {
    const path = field.dataset.path;
    let value = getPath(profile, path);
    if (value === undefined || value === null || value === '') value = FALLBACK[path] ?? '';
    if (field.type === 'color') field.value = String(value || '#000000').slice(0, 7);
    else if (field.dataset.type === 'bool') field.value = String(Boolean(value));
    else field.value = value;
  });
  const paper = $('skill-paper');
  const page = profile.page || {};
  const match = PAPER_CHOICES.map((key) => [key, PAPER_SIZES[key]]).find(([, [w, h]]) =>
    Number(page.width_mm) === w && Number(page.height_mm) === h);
  paper.value = page.width_mm && page.height_mm
    ? (match ? match[0] : 'custom')
    : (PAPER_CHOICES.includes(page.size) ? page.size : 'A4');
  $('skill-name').value = skillName;
  $('skill-id').value = skillId;
  $('skill-preset').value = preset;
}

function readField(field) {
  if (field.type === 'number') return field.value === '' ? 0 : Number(field.value);
  if (field.dataset.type === 'bool') return field.value === 'true';
  if (field.type === 'color') return field.value.toUpperCase();
  return field.value;
}

// ──────────────────────────────────────────────────────────────
// 위계 표
// ──────────────────────────────────────────────────────────────
function cellInput(level, index, [, key, kind, width]) {
  const style = `style="width:${width}rem"`;
  const data = `data-level="${index}" data-key="${key}"`;
  const value = level[key] ?? '';
  const esc = (s) => String(s).replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;');
  if (kind === 'check') return `<input type="checkbox" ${data} ${level.bold ? 'checked' : ''}>`;
  if (kind === 'number') return `<input type="number" step="0.5" ${style} ${data} value="${esc(value)}">`;
  if (kind === 'font') {
    return `<select ${style} ${data}><option value="bold"${value === 'bold' ? ' selected' : ''}>제목</option>`
      + `<option value="light"${value !== 'bold' ? ' selected' : ''}>본문</option></select>`;
  }
  if (kind === 'align') {
    return `<select ${style} ${data}>${ALIGNS.map(([v, label]) =>
      `<option value="${v}"${(value || 'JUSTIFY') === v ? ' selected' : ''}>${label}</option>`).join('')}</select>`;
  }
  if (kind === 'head') {
    const auto = String(value).startsWith('AUTO_');
    const choice = auto ? value : (String(value).trim() ? 'TEXT' : '');
    const select = `<select ${style} data-level="${index}" data-key="prefix-kind">${HEAD_OPTIONS.map(([v, label]) =>
      `<option value="${v}"${choice === v ? ' selected' : ''}>${label}</option>`).join('')}</select>`;
    const text = choice === 'TEXT'
      ? `<input type="text" style="width:3rem" data-level="${index}" data-key="prefix-text" value="${esc(String(value).trim())}">`
      : '';
    return select + text;
  }
  return `<input type="text" ${style} ${data} value="${esc(value)}" spellcheck="false">`;
}

function drawLevels() {
  const head = `<thead><tr><th></th>${LEVEL_COLUMNS.map(([label]) => `<th>${label}</th>`).join('')}<th></th></tr></thead>`;
  const rows = profile.levels.map((level, i) => `<tr>
      <td class="nowrap"><button type="button" class="ghost mini" data-move="${i}" data-dir="-1" aria-label="위로">▲</button><button type="button" class="ghost mini" data-move="${i}" data-dir="1" aria-label="아래로">▼</button></td>
      ${LEVEL_COLUMNS.map((col) => `<td>${cellInput(level, i, col)}</td>`).join('')}
      <td><button type="button" class="ghost mini" data-remove="${i}" aria-label="삭제">✕</button></td>
    </tr>`).join('');
  $('skill-levels').innerHTML = head + `<tbody>${rows}</tbody>`;
}

function onLevelInput(event) {
  const field = event.target;
  const index = Number(field.dataset.level);
  if (Number.isNaN(index) || !profile.levels[index]) return;
  const level = profile.levels[index];
  const key = field.dataset.key;
  if (key === 'prefix-kind') {
    if (field.value === 'TEXT') level.prefix = `${level.marker || '·'} `;
    else level.prefix = field.value;
    drawLevels();
  } else if (key === 'prefix-text') {
    level.prefix = field.value ? `${field.value.trim()} ` : '';
  } else if (key === 'bold') {
    level.bold = field.checked;
  } else if (field.type === 'number') {
    level[key] = field.value === '' ? 0 : Number(field.value);
  } else {
    level[key] = field.value;
  }
  changed();
}

function onLevelClick(event) {
  const button = event.target.closest('button');
  if (!button) return;
  if (button.dataset.remove !== undefined) {
    profile.levels.splice(Number(button.dataset.remove), 1);
  } else if (button.dataset.move !== undefined) {
    const from = Number(button.dataset.move);
    const to = from + Number(button.dataset.dir);
    if (to < 0 || to >= profile.levels.length) return;
    [profile.levels[from], profile.levels[to]] = [profile.levels[to], profile.levels[from]];
  } else return;
  drawLevels();
  changed();
}

function addLevel() {
  const last = profile.levels[profile.levels.length - 1] || {};
  const used = new Set(profile.levels.map((lv) => lv.key));
  let n = profile.levels.length + 1;
  while (used.has(`L${n}`)) n += 1;
  profile.levels.push({
    key: `L${n}`, name: `단계${n}`, marker: '', prefix: '',
    size_pt: last.size_pt || 11, bold: false, font: 'light', color: '#000000',
    left_pt: (last.left_pt || 0) + 10, indent_pt: 0, spacing_above_pt: 0, spacing_below_pt: 0,
    line_spacing: last.line_spacing || 160, align: 'JUSTIFY',
  });
  drawLevels();
  changed();
}

// ──────────────────────────────────────────────────────────────
// 검사·미리보기·내려받기
// ──────────────────────────────────────────────────────────────
function problems() {
  const out = [];
  const keys = new Set();
  const markers = new Set();
  let blank = 0;
  profile.levels.forEach((lv, i) => {
    const where = `${i + 1}번째 단계(${lv.name || lv.key})`;
    if (keys.has(lv.key)) out.push(`${where}: 내부 이름이 겹침`);
    keys.add(lv.key);
    if (lv.marker) {
      if (markers.has(lv.marker)) out.push(`${where}: 입력 마커 '${lv.marker}'가 다른 단계와 겹침`);
      markers.add(lv.marker);
    } else if (!String(lv.prefix || '').startsWith('AUTO_')) blank += 1;
    if (!(Number(lv.size_pt) > 0)) out.push(`${where}: 글자 크기가 0`);
  });
  if (blank > 1) out.push('마커를 비운 본문 단계가 둘 이상 — 마커 없이 쓴 줄은 첫째 단계로만 갑니다');
  if (!profile.levels.length && profile.mode !== 'narrative') out.push('단계가 하나도 없음');
  return out;
}

function renderMarkers() {
  const rows = skillMarkerRows(mergeForTable()).split('\n').filter((row) => !/^\|---/.test(row));
  const cells = (row) => row.slice(1, -1).split('|').map((c) => c.trim()
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/`([^`]+)`/g, '<code>$1</code>'));
  const [head, ...body] = rows;
  $('skill-markers').innerHTML = `<table><thead><tr>${cells(head).map((c) => `<th>${c}</th>`).join('')}</tr></thead>`
    + `<tbody>${body.map((r) => `<tr>${cells(r).map((c) => `<td>${c}</td>`).join('')}</tr>`).join('')}</tbody></table>`;
}

/** markerRows는 병합된 서식을 기대한다(비어 있는 칸의 기본값) */
function mergeForTable() {
  const merged = clone(profile);
  merged.levels = merged.levels.map((lv) => ({ ...lv, marker: lv.marker || '' }));
  merged.body = merged.body || { size_pt: 12 };
  return merged;
}

function say(text, kind = '') {
  const el = $('skill-status');
  el.textContent = text;
  el.className = `status ${kind}`;
}

function changed() {
  renderMarkers();
  $('skill-json').value = JSON.stringify(profile, null, 2);
  save();
  const found = problems();
  if (found.length) say(`확인할 것: ${found.join(' / ')}`, 'bad');
  else say('');
}

function saveFile(data, name, type) {
  const url = URL.createObjectURL(new Blob([data], { type }));
  const a = document.createElement('a');
  a.href = url;
  a.download = name;
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function stamped() {
  const out = clone(profile);
  out.name = skillName || out.name;
  return out;
}

async function downloadSkill() {
  const found = problems();
  if (found.length) { say(`먼저 고칠 것: ${found.join(' / ')}`, 'bad'); return; }
  const { files, fields } = buildSkill(stamped(), skillName, base64ToBytes(HWPX_TEMPLATE_B64), skillId);
  const packed = await packSkill(files, fields.slug);
  saveFile(packed, `${fields.name}.zip`, 'application/zip');
  say(`${fields.name}.zip 저장됨 (스킬 이름 ${fields.slug}). 풀지 말고 그대로 올리세요.`, 'ok');
}

async function downloadSample() {
  try {
    const text = skillSampleText(profile);
    const { bytes, issues } = await buildFromText(base64ToBytes(HWPX_TEMPLATE_B64), profile, text);
    saveFile(bytes, `${skillName || '예시'}-예시.hwpx`, 'application/octet-stream');
    const errors = issues.filter((i) => i.severity === 'error').length;
    say(`예시 문서를 저장했습니다. 한글에서 열어 모양을 확인하세요${errors ? ` (오류 ${errors}건)` : ''}.`, 'ok');
  } catch (error) {
    console.error(error);
    say(error.message || '예시 문서를 만들지 못했습니다.', 'bad');
  }
}

// ──────────────────────────────────────────────────────────────
export function initSkillLane() {
  const presetSelect = $('skill-preset');
  for (const [key, value] of Object.entries(HWPX_PROFILES)) {
    const option = document.createElement('option');
    option.value = key;
    option.textContent = key === DEFAULT_PRESET ? `${value.name} — 기본` : value.name;
    presetSelect.append(option);
  }
  const paper = $('skill-paper');
  for (const name of PAPER_CHOICES) {
    const [w, h] = PAPER_SIZES[name];
    paper.append(new Option(`${name} (${w}×${h})`, name));
  }
  paper.append(new Option('직접 입력', 'custom'));

  load();
  fillFields();
  drawLevels();
  changed();

  presetSelect.addEventListener('change', () => {
    startFrom(presetSelect.value);
    fillFields();
    drawLevels();
    changed();
  });
  $('skill-reset').addEventListener('click', () => {
    startFrom(preset);
    fillFields();
    drawLevels();
    changed();
    say('시작 서식으로 되돌렸습니다.', 'ok');
  });
  $('skill-name').addEventListener('input', (event) => { skillName = event.target.value; save(); });
  $('skill-id').addEventListener('input', (event) => { skillId = event.target.value; save(); });
  paper.addEventListener('change', () => {
    if (paper.value !== 'custom') {
      const [w, h] = PAPER_SIZES[paper.value];
      profile.page = { ...(profile.page || {}), size: paper.value, width_mm: w, height_mm: h };
      fillFields();
      changed();
    }
  });
  document.querySelectorAll('[data-panel="skill"] [data-path]').forEach((field) => {
    field.addEventListener('change', () => {
      setPath(profile, field.dataset.path, readField(field));
      if (field.dataset.path.startsWith('page.width') || field.dataset.path.startsWith('page.height')) {
        profile.page.size = '직접';
        fillFields();
      }
      changed();
    });
  });
  const levels = $('skill-levels');
  levels.addEventListener('change', onLevelInput);
  levels.addEventListener('click', onLevelClick);
  $('skill-level-add').addEventListener('click', addLevel);
  $('skill-json-apply').addEventListener('click', () => {
    try {
      const parsed = JSON.parse($('skill-json').value);
      if (!parsed || typeof parsed !== 'object' || !Array.isArray(parsed.levels)) {
        throw new Error('levels 배열이 있는 JSON이어야 합니다');
      }
      profile = parsed;
      fillFields();
      drawLevels();
      changed();
      say('JSON을 적용했습니다.', 'ok');
    } catch (error) {
      say(`JSON을 읽지 못했습니다: ${error.message}`, 'bad');
    }
  });
  $('skill-download').addEventListener('click', downloadSkill);
  $('skill-sample').addEventListener('click', downloadSample);
}
