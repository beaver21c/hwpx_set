/** 웹 UI 연결부. 엔진은 hwpx-studio.js, 자산(템플릿·프로파일)은 assets.js. */

import { HWPX_PROFILES, HWPX_TEMPLATE_B64 } from '../assets.js';
import { base64ToBytes, buildFromText, buildGrid, lintItems, mergeProfile,
         parseDiagramBlock, parseText } from './hwpx-studio.js';
import { captureText, specToText } from './capture.js';
import { buildBundle, packBundle, readContents } from './bundle.js';
import { analyzeParts } from './formkit.js';
import { readBack } from './readback.js';

const STORAGE_KEY = 'hwpx-studio.draft.v1';

const $ = (id) => document.getElementById(id);
const bodyText = $('body-text');
const profileSelect = $('profile');
const filename = $('filename');
const statusEl = $('status');
const issuesEl = $('issues');
const reportPanel = $('report-panel');

const SAMPLES = {
  research: `# 연구의 배경과 목적
## 연구의 필요성
### 문제 제기
차상위계층 지원제도는 부처별로 나뉘어 운영되어 왔다. 그 결과 같은 가구가 제도마다 다른 기준으로 심사받는 일이 생긴다.
#### 제도 간 기준의 차이
소득인정액 산정 방식이 제도마다 달라, 한 제도에서 수급 자격이 인정된 가구가 다른 제도에서는 탈락하는 사례가 확인된다[^1].
##### 산정 방식의 세 갈래
재산의 소득환산율, 부양의무자 기준, 근로소득 공제율이 제도마다 다르게 적용된다.
### 연구의 목적
본 연구는 차상위계층 지원제도의 연계 실태를 확인하고 통합지원 방안을 제시하는 데 목적이 있다.

## 연구의 내용과 방법
### 연구 내용
제도 현황 분석, 수급 실태 분석, 해외 사례 검토, 개선 방안 도출의 네 부분으로 구성하였다.

표) 연도별 차상위계층 지원 실적

| 구분 | 2023년 | 2024년 | 2025년 |
|---|---|---|---|
| 지원 가구 | 12,480 | 13,205 | 14,116 |
| 지원 금액(억 원) | 1,204 | 1,388 | 1,502 |
| 평균 처리 기간(일) | 21 | 17 | 14 |

※ 주: 각 연도 12월 말 기준이다.
※ 출처: ○○부. (2025). 『△△사업 운영현황』. 47쪽.

### 연구 방법
행정자료 분석과 심층면접을 병행하였다. 심층면접은 45개 지방자치단체의 담당자를 대상으로 하였다[^2].

[^1]: ○○정책연구원. (2024). 『△△제도 실태조사』. 112쪽.
[^2]: 면접 기간은 2025년 9월부터 11월까지이다.
`,
  diagram: `# 추진 체계

## 조직

□ 부서 구성

:::diagram type=org title="추진 체계"
대표
  기획부
    기획팀
    예산팀
  운영부
  연구부
:::

○ 총괄 부서가 계획 수립과 점검을 맡는다
- 기획부는 계획 수립과 예산 편성을 담당
- 운영부는 현장 집행과 민원 대응을 담당

□ 처리 절차

:::diagram type=flow title="처리 절차"
접수 → 검토 → 심의 → 통보
:::

○ 단계별 처리 기한을 지침에 명시
- 보완 요구가 있으면 기한을 다시 산정
- 결과는 문서로 통보
`,
  narrative: `# 개요

이 문서는 서술식 예시다. 서술식에서는 #과 ##만 제목으로 인식하고, 나머지 줄은 본문 문단이 된다.

빈 줄이 문단을 나눈다. 줄머리 기호를 붙이지 않아도 된다.

## 표

표와 도식은 서술식에서도 같은 방식으로 넣는다.

| 구분 | 1차 | 2차 |
|---|---|---|
| 참여 기관 | 8개소 | 12개소 |
`,
};

let template = null;

function currentProfile() {
  return mergeProfile(HWPX_PROFILES[profileSelect.value]);
}

function setStatus(text, kind = '') {
  statusEl.textContent = text;
  statusEl.className = `status ${kind}`;
}

function renderMarkers() {
  const profile = currentProfile();
  const rows = profile.levels.map((lv) => {
    const prefix = String(lv.prefix || '');
    const shown = prefix.startsWith('AUTO_')
      ? { 'AUTO_ROMAN': 'Ⅰ. Ⅱ. Ⅲ.', 'AUTO_NUM': '1. 2. 3.', 'AUTO_ALPHA': 'A. B. C.',
        'AUTO_HANGUL': '가. 나. 다.', 'AUTO_CIRCLED': '① ② ③' }[prefix] || '자동 번호'
      : prefix.trim() || '—';
    return `<tr><td><code>${lv.marker || '(없음)'}</code></td><td>${shown}</td><td>${lv.name}</td></tr>`;
  });
  if (profile.mode === 'narrative') {
    rows.push('<tr><td><code>(마커 없음)</code></td><td>본문 문단</td><td>본문</td></tr>');
  }
  $('marker-table').innerHTML = rows.join('');
}

function renderIssues(issues, extraWarnings = []) {
  const all = [
    ...extraWarnings.map((message) => ({ severity: 'warn', line: 0, code: 'build', message })),
    ...issues,
  ];
  if (!all.length) {
    reportPanel.hidden = false;
    issuesEl.innerHTML = '<li>지적 사항 없음</li>';
    return;
  }
  reportPanel.hidden = false;
  issuesEl.innerHTML = all.map((issue) => {
    const where = issue.line ? `${issue.line}행` : '문서';
    return `<li class="${issue.severity === 'error' ? 'error' : ''}">`
      + `<span class="where">${where}</span>${escapeHtml(issue.message)}</li>`;
  }).join('');
}

const escapeHtml = (s) => String(s)
  .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

function updateStat() {
  const text = bodyText.value;
  const lines = text ? text.split('\n').length : 0;
  const profile = currentProfile();
  const parsed = parseText(text, profile);
  const paras = parsed.items.filter((i) => i.type === 'para').length;
  const tables = parsed.items.filter((i) => i.type === 'table').length;
  const diagrams = parsed.items.filter((i) => i.type === 'diagram').length;
  const parts = [`${lines}줄`, `문단 ${paras}개`];
  if (tables) parts.push(`표 ${tables}개`);
  if (diagrams) parts.push(`도식 ${diagrams}개`);
  $('stat').textContent = parts.join(' · ');
  try { localStorage.setItem(STORAGE_KEY, text); } catch { /* 저장 불가해도 무시 */ }
}

function runCheck() {
  const profile = currentProfile();
  const parsed = parseText(bodyText.value, profile);
  const issues = lintItems(parsed.items, profile, parsed.lineOf, parsed.warnings);
  renderIssues(issues);
  const errors = issues.filter((i) => i.severity === 'error').length;
  setStatus(issues.length
    ? `검사 완료 — 오류 ${errors}건 / 경고 ${issues.length - errors}건`
    : '검사 완료 — 지적 사항 없음', errors ? 'bad' : 'ok');
  return issues;
}

async function runBuild() {
  const button = $('build');
  const text = bodyText.value.trim();
  if (!text) { setStatus('본문을 입력하세요.', 'bad'); return; }

  button.disabled = true;
  setStatus('만드는 중…');
  try {
    if (!template) template = base64ToBytes(HWPX_TEMPLATE_B64);
    const result = await buildFromText(template, HWPX_PROFILES[profileSelect.value], text);
    renderIssues(result.issues, result.warnings);

    let name = (filename.value || '보고서.hwpx').trim().replace(/[\\/]/g, '');
    if (!name.endsWith('.hwpx')) name += '.hwpx';

    const blob = new Blob([result.bytes], { type: 'application/hwp+zip' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = name;
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);

    const size = result.bytes.length.toLocaleString('ko-KR');
    setStatus(`${name} 저장됨 (${size} bytes)`, 'ok');
  } catch (error) {
    console.error(error);
    setStatus(`만들지 못했습니다: ${error.message}`, 'bad');
  } finally {
    button.disabled = false;
  }
}

const CAPTURE_SAMPLES = {
  mermaid: `flowchart TD
    A[○○위원회] --> B[기획분과]
    A --> C[운영분과]
    A -.-> D[자문단]
    B --> E[정책팀]
    B --> F[예산팀]
    style A fill:#C00000,color:#FFFFFF
    classDef body fill:#2E75B6,color:#FFFFFF
    class B,C body
    style D fill:#FFF2CC,stroke:#BF8F00`,
  svg: `<svg xmlns="http://www.w3.org/2000/svg" width="600" height="300">
  <rect x="230" y="20" width="140" height="40" fill="#C00000" stroke="#000000"/>
  <text x="300" y="45" fill="#FFFFFF">위원회</text>
  <rect x="60" y="140" width="140" height="40" fill="#2E75B6" stroke="#1F3864"/>
  <text x="130" y="165" fill="#FFFFFF">기획분과</text>
  <rect x="400" y="140" width="140" height="40" fill="#FFF2CC" stroke="#BF8F00"/>
  <text x="470" y="165" fill="#000000">자문단</text>
  <line x1="300" y1="60" x2="130" y2="140" stroke="#1F3864"/>
  <path d="M300,60 L470,100 L470,140" stroke="#BF8F00" fill="none" stroke-dasharray="4 3"/>
</svg>`,
};

/** 붙여 넣은 도식을 읽어 본문 끝에 도식 블록으로 덧붙인다. */
function runCapture() {
  const source = $('capture-text').value.trim();
  const status = $('capture-status');
  const say = (message, kind = '') => {
    status.textContent = message;
    status.className = `status ${kind}`.trim();
  };
  if (!source) { say('읽을 내용을 붙여 넣으세요.', 'bad'); return; }

  let result;
  try {
    result = captureText(source, 'auto', $('capture-title').value.trim());
  } catch (error) {
    console.error(error);
    say(`읽지 못했습니다: ${error.message}`, 'bad');
    return;
  }
  if (!result.spec.lines.length) {
    say(result.warnings[0] || '도식을 찾지 못했습니다.', 'bad');
    return;
  }

  const block = specToText(result.spec);
  const body = bodyText.value.replace(/\s*$/, '');
  bodyText.value = `${body ? `${body}\n\n` : ''}${block}\n`;
  bodyText.scrollTop = bodyText.scrollHeight;
  updateStat();

  const boxes = result.spec.type === 'flow'
    ? result.spec.lines.join(' ').split('→').length
    : result.spec.lines.length;
  const note = result.warnings.length ? ` — ${result.warnings.join(' / ')}` : '';
  say(`${result.source}에서 상자 ${boxes}개를 읽어 본문에 넣었습니다${note}`,
    result.warnings.length ? '' : 'ok');
}

// ──────────────────────────────────────────────────────────────
// 공통 거들기
// ──────────────────────────────────────────────────────────────
function saveFile(data, name, type = 'application/octet-stream') {
  const blob = new Blob([data], { type });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = name.replace(/[\\/]/g, '');
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function statusOf(id) {
  return (text, kind = '') => {
    const node = $(id);
    node.textContent = text;
    node.className = `status${kind ? ` ${kind}` : ''}`;
  };
}

async function fileBytes(input) {
  const file = input.files && input.files[0];
  if (!file) return null;
  return { buffer: await file.arrayBuffer(), name: file.name };
}

const stripExtension = (name) => name.replace(/\.hwpx$/i, '');

// ──────────────────────────────────────────────────────────────
// ② 도식을 한글 표로
// ──────────────────────────────────────────────────────────────

/** 작성 예시. 이름·설명·본문. 미리보기는 같은 엔진으로 그 자리에서 그린다. */
const DIAGRAM_SAMPLES = [
  {
    key: 'org',
    name: '조직도 · 체계도',
    type: 'type=org',
    why: '2칸 들여쓰면 한 단계 아래입니다. 연결선은 도구가 긋습니다.',
    source: `:::diagram type=org title="추진 체계"
○○위원회 {fill=#C00000 color=#FFFFFF}
  기획분과
    정책팀
    예산팀
  운영분과
  자문단 {fill=#FFF2CC link=dash}
:::`,
  },
  {
    key: 'matrix',
    name: '매트릭스',
    type: 'type=matrix',
    why: '표를 그대로 씁니다. 첫 줄과 첫 칸이 머리가 됩니다.',
    source: `:::diagram type=matrix title="과제별 추진 일정"
| 구분 | 1단계(2026) | 2단계(2027) | 3단계(2028) |
| 제도 정비 | 실태조사 | 개정안 마련 | 시행 |
| 전달체계 | 시범사업 | 대상 확대 | 정착 |
| 정보화 | 시스템 설계 | 구축 | 운영·고도화 |
:::`,
  },
  {
    key: 'flow',
    name: '절차도',
    type: 'type=flow',
    why: '화살표로 잇습니다. 세로로 두려면 direction=down.',
    source: `:::diagram type=flow title="신청 처리 절차"
접수 → 자격 확인 → 심의 → 결정 통보 → 지급
:::`,
  },
  {
    key: 'db',
    name: 'DB 구성',
    type: 'type=db',
    why: '[테이블] 아래 필드를 적습니다. * 는 기본키, + 는 외래키입니다.',
    source: `:::diagram type=db title="지원사업 DB 구성"
[회원]
  *회원ID
  이름
  생년월일
  연락처
[신청]
  *신청ID
  +회원ID
  +사업코드
  신청일
  처리상태
[사업]
  *사업코드
  사업명
  소관부처
회원 → 신청 → 사업
:::`,
  },
  {
    key: 'strategy',
    name: '전략체계도',
    type: 'type=strategy',
    why: '왼쪽이 단 이름, 오른쪽이 칸들. | 로 시작하면 위 단의 다음 줄입니다.',
    source: `:::diagram type=strategy title="경영전략 체계도" label_width=24
미션 {fill=#17375E color=#FFFFFF} | 국민의 삶의 질 향상에 기여한다 {fill=#EAEFF9 color=#17375E}
핵심가치 {fill=#3EA9A9 color=#FFFFFF} | 존중 | 연계 | 형평 | 신뢰
4대 전략방향 {fill=#5CBF7A color=#FFFFFF} | 대상자 발굴 | 서비스 연계 | 전달체계 | 돌봄 현장
| 위기가구 발굴 | 퇴원지원 연계 | 통합창구 운영 | 처우 개선
:::`,
  },
];

/** 붙여 넣은 것이 도식 문법이면 그대로, Mermaid·SVG면 읽어서 spec으로. */
function diagramSpecOf(source, title) {
  const text = String(source || '').trim();
  if (!text) throw new Error('도식을 쓰거나 붙여 넣으세요.');

  let spec;
  let from = '직접 쓴 도식';
  let warnings = [];
  if (/^\s*:::diagram\b/m.test(text)) {
    const lines = text.split(/\r?\n/);
    const start = lines.findIndex((l) => /^\s*:::diagram\b/.test(l));
    const body = [];
    for (let i = start + 1; i < lines.length; i += 1) {
      if (lines[i].trim() === ':::') break;
      body.push(lines[i]);
    }
    spec = parseDiagramBlock(lines[start].trim().replace(/^:::diagram\s*/, ''), body);
  } else {
    const read = captureText(text, 'auto', title);
    if (!read.spec.lines.length) throw new Error(read.warnings[0] || '도식을 찾지 못했습니다.');
    spec = read.spec;
    from = read.source;
    warnings = read.warnings;
  }
  if (!spec.lines.length) throw new Error('도식 내용이 비어 있습니다.');
  if (!spec.title && title) spec.title = title;
  return { spec, from, warnings };
}

const captureSay = statusOf('capture-status');

/** GridPlan을 HTML 표로. 근사 미리보기다(연결선은 실제로 칸의 한 변 테두리). */
function gridToHtml(grid) {
  const dia = grid.diagram || {};
  const px = 3.2;                                   // 1mm를 몇 px로 볼지
  const at = new Map(grid.cells.map((c) => [`${c.row},${c.col}`, c]));
  const covered = new Set();
  for (const c of grid.cells) {
    for (let r = c.row; r < c.row + (c.rowSpan || 1); r += 1) {
      for (let k = c.col; k < c.col + (c.colSpan || 1); k += 1) {
        if (r !== c.row || k !== c.col) covered.add(`${r},${k}`);
      }
    }
  }

  const rows = [];
  for (let r = 0; r < grid.rows; r += 1) {
    const tds = [];
    for (let c = 0; c < grid.cols; c += 1) {
      if (covered.has(`${r},${c}`)) continue;
      const cell = at.get(`${r},${c}`);
      const style = [`height:${(grid.rowHeights[r] || 9) * px}px`];
      if (cell) {
        const line = cell.borderColor
          || (cell.fill ? (dia.box_border || '#1F3864') : (dia.line_color || '#1F3864'));
        for (const side of ['top', 'right', 'bottom', 'left']) {
          if ((cell.borders || []).includes(side)) {
            style.push(`border-${side}:1px solid ${line}`);
          }
        }
        if (cell.fill) style.push(`background:${cell.fill}`);
        if (cell.textColor) style.push(`color:${cell.textColor}`);
      }
      const span = cell && (cell.colSpan || 1) > 1 ? ` colspan="${cell.colSpan}"` : '';
      const rspan = cell && (cell.rowSpan || 1) > 1 ? ` rowspan="${cell.rowSpan}"` : '';
      tds.push(`<td${span}${rspan} style="${style.join(';')}">${escapeHtml(cell ? cell.text : '')}</td>`);
    }
    rows.push(`<tr>${tds.join('')}</tr>`);
  }
  const cols = grid.colWidths.map((w) => `<col style="width:${w * px}px">`).join('');
  const caption = grid.title
    ? `<p class="gridtitle">&lt;${escapeHtml(grid.title)}&gt;</p>` : '';
  return `<table class="gridview" style="width:${grid.colWidths.reduce((a, b) => a + b, 0) * px}px">`
    + `<colgroup>${cols}</colgroup><tbody>${rows.join('')}</tbody></table>${caption}`;
}

/** 위 칸의 내용을 미리보기로 그린다. 실패하면 이유를 남기고 false. */
function drawCapturePreview(quiet = false) {
  const view = $('capture-view');
  let read;
  try {
    read = diagramSpecOf($('capture-text').value, $('capture-title').value.trim());
  } catch (error) {
    view.hidden = true;
    if (!quiet) captureSay(error.message, 'bad');
    return null;
  }
  const grid = buildGrid(read.spec, mergeProfile(HWPX_PROFILES[profileSelect.value]));
  view.innerHTML = gridToHtml(grid);
  view.hidden = false;
  const notes = [...read.warnings, ...grid.warnings];
  captureSay(`${read.from} — 상자 ${grid.cells.filter((c) => c.text).length}개`
    + (notes.length ? ` · ${notes.join(' / ')}` : ''), notes.length ? '' : 'ok');
  return { read, grid };
}

/** 도식 하나만 든 한글파일을 만들어 곧바로 내려받는다. */
async function downloadDiagram() {
  const button = $('capture-download');
  let read;
  try {
    read = diagramSpecOf($('capture-text').value, $('capture-title').value.trim());
  } catch (error) {
    captureSay(error.message, 'bad');
    return;
  }
  button.disabled = true;
  captureSay('만드는 중…');
  try {
    if (!template) template = base64ToBytes(HWPX_TEMPLATE_B64);
    const result = await buildFromText(template, HWPX_PROFILES[profileSelect.value],
      `${specToText(read.spec)}\n`);
    let name = ($('capture-filename').value || '도식.hwpx').trim().replace(/[\\/]/g, '');
    if (!name.endsWith('.hwpx')) name += '.hwpx';
    saveFile(result.bytes, name, 'application/hwp+zip');
    drawCapturePreview(true);
    const notes = [...read.warnings, ...(result.warnings || [])];
    captureSay(`${name} 저장됨 (${result.bytes.length.toLocaleString('ko-KR')} bytes)`
      + (notes.length ? ` · ${notes.join(' / ')}` : ''), 'ok');
  } catch (error) {
    console.error(error);
    captureSay(`만들지 못했습니다: ${error.message}`, 'bad');
  } finally {
    button.disabled = false;
  }
}

/** 작성 예시 목록을 그린다(미리보기까지 같은 엔진으로). */
let samplesDrawn = false;
function drawDiagramSamples() {
  if (samplesDrawn) return;
  const host = $('diagram-samples');
  if (!host) return;
  const profile = mergeProfile(HWPX_PROFILES[profileSelect.value]);
  host.innerHTML = DIAGRAM_SAMPLES.map((sample) => {
    let preview = '';
    try {
      const { spec } = diagramSpecOf(sample.source, '');
      preview = gridToHtml(buildGrid(spec, profile));
    } catch (error) {
      preview = `<p class="hint">미리보기를 그리지 못했습니다: ${escapeHtml(error.message)}</p>`;
    }
    return `<div class="sample">
      <div class="sample-head">
        <h3>${escapeHtml(sample.name)} <code>${escapeHtml(sample.type)}</code></h3>
        <button type="button" class="ghost" data-diagram-sample="${sample.key}">이 예시 넣기</button>
      </div>
      <p class="hint">${escapeHtml(sample.why)}</p>
      <div class="sample-body">
        <pre>${escapeHtml(sample.source)}</pre>
        <div class="gridwrap">${preview}</div>
      </div>
    </div>`;
  }).join('');
  host.querySelectorAll('[data-diagram-sample]').forEach((button) => {
    button.addEventListener('click', () => {
      const sample = DIAGRAM_SAMPLES.find((s) => s.key === button.dataset.diagramSample);
      $('capture-text').value = sample.source;
      $('capture-filename').value = `${sample.name.replace(/\s*·\s*/g, '-')}.hwpx`;
      drawCapturePreview();
      $('capture-text').scrollIntoView({ behavior: 'smooth', block: 'center' });
    });
  });
  samplesDrawn = true;
}


/**
 * 보고서 마크다운을 아주 얕게 HTML로. 표·제목·목록·굵게·코드만 본다.
 * 우리가 만든 문자열만 넣으므로 값은 언제나 escapeHtml을 거친다.
 */
function renderMarkdown(text) {
  const inline = (value) => escapeHtml(value)
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  const out = [];
  let table = null;

  const closeTable = () => {
    if (!table) return;
    const [head, ...rows] = table;
    out.push('<table><thead><tr>'
      + head.map((c) => `<th>${inline(c)}</th>`).join('')
      + '</tr></thead><tbody>'
      + rows.map((r) => `<tr>${r.map((c) => `<td>${inline(c)}</td>`).join('')}</tr>`).join('')
      + '</tbody></table>');
    table = null;
  };

  for (const line of text.split('\n')) {
    const row = line.trim();
    if (row.startsWith('|') && row.endsWith('|')) {
      const cells = row.slice(1, -1).split('|').map((c) => c.trim());
      if (cells.every((c) => /^:?-{2,}:?$/.test(c))) continue;   // 구분 줄
      (table = table || []).push(cells);
      continue;
    }
    closeTable();
    if (!row) continue;
    if (row.startsWith('## ')) out.push(`<h2>${inline(row.slice(3))}</h2>`);
    else if (row.startsWith('# ')) out.push(`<h1>${inline(row.slice(2))}</h1>`);
    else if (row.startsWith('- ')) {
      if (!out.length || !out[out.length - 1].startsWith('<ul>')) out.push('<ul></ul>');
      const last = out.length - 1;
      out[last] = out[last].replace('</ul>', `<li>${inline(row.slice(2))}</li></ul>`);
    } else out.push(`<p>${inline(row)}</p>`);
  }
  closeTable();
  return out.join('');
}

// ──────────────────────────────────────────────────────────────
// ① 양식으로 도구 만들기
// ──────────────────────────────────────────────────────────────
let bundleState = null;

async function runFormkit() {
  const say = statusOf('form-status');
  const button = $('form-run');
  const picked = await fileBytes($('form-file'));
  if (!picked) { say('양식 파일(.hwpx)을 고르세요.', 'bad'); return; }

  button.disabled = true;
  say('해부하는 중…');
  try {
    const name = ($('form-name').value || '').trim() || stripExtension(picked.name);
    const bullets = $('form-bullets').value;
    const { files, form, report } = await buildBundle(picked.buffer, name, bullets);
    bundleState = { files, form };
    $('form-report').innerHTML = renderMarkdown(report);
    $('form-result').hidden = false;
    const invented = (form.levels || []).filter((lv) => lv.marker_invented).length;
    const clash = (form.notes || []).filter(
      (note) => note.includes('두 번 찍힌다') || note.includes('찍히지 않는다')).length;
    say(`레벨 ${form.levels.length}개를 찾았습니다`
      + (invented ? ` (그 가운데 ${invented}개는 마커를 임의로 정했습니다)` : '')
      + `. 꾸러미 ${files.size}개 파일 준비됨.`
      + (clash ? ` ⚠ 글머리 기호 선택이 양식과 어긋나는 레벨 ${clash}개 — 아래를 볼 것.` : ''),
    clash ? 'bad' : 'ok');
  } catch (error) {
    console.error(error);
    bundleState = null;
    $('form-result').hidden = true;
    say(error.message || '읽지 못했습니다.', 'bad');
  } finally {
    button.disabled = false;
  }
}

async function downloadBundle(extension) {
  if (!bundleState) return;
  const say = statusOf('form-status');
  const { files, form } = bundleState;
  const packed = await packBundle(files, form.name);
  saveFile(packed, `${form.name}.${extension}`, 'application/zip');
  say(`${form.name}.${extension} 저장됨 (${packed.length.toLocaleString('ko-KR')} bytes)`, 'ok');
}

// ──────────────────────────────────────────────────────────────
// ③ 서식 없는 문서를 양식에 맞추기
// ──────────────────────────────────────────────────────────────
let convertState = null;

async function runConvert() {
  const say = statusOf('convert-status');
  const button = $('convert-run');
  const picked = await fileBytes($('convert-file'));
  if (!picked) { say('내용이 든 파일(.hwpx)을 고르세요.', 'bad'); return; }

  button.disabled = true;
  say('읽는 중…');
  try {
    const formFile = await fileBytes($('convert-form'));
    let form = null;
    let bundle = null;
    if (formFile) {
      const name = stripExtension(formFile.name);
      bundle = await buildBundle(formFile.buffer, name);
      form = bundle.form;
    }
    const { text, report } = await readBack(picked.buffer, form);
    $('convert-text').value = text;
    $('convert-report').innerHTML = renderMarkdown(report);
    $('convert-result').hidden = false;
    $('convert-bundle').hidden = !bundle;
    convertState = { text, bundle, name: stripExtension(picked.name) };
    say(form
      ? `${form.name} 양식의 마커로 되돌렸습니다. 근거를 확인하세요.`
      : '되돌렸습니다. 양식 파일을 같이 올리면 그 양식의 마커로 맞춰 줍니다.', 'ok');
  } catch (error) {
    console.error(error);
    convertState = null;
    $('convert-result').hidden = true;
    say(error.message || '읽지 못했습니다.', 'bad');
  } finally {
    button.disabled = false;
  }
}

async function downloadConverted() {
  if (!convertState) return;
  saveFile(convertState.text, `${convertState.name}.md`, 'text/markdown');
}

async function downloadConvertBundle() {
  if (!convertState || !convertState.bundle) return;
  const say = statusOf('convert-status');
  const { files, form } = convertState.bundle;
  const withDraft = new Map(files);
  withDraft.set('원고.md', new TextEncoder().encode(convertState.text));
  const packed = await packBundle(withDraft, form.name);
  saveFile(packed, `${form.name}.zip`, 'application/zip');
  say(`원고가 든 꾸러미를 저장했습니다 (${packed.length.toLocaleString('ko-KR')} bytes). `
    + 'AI에 통째로 주고 "원고.md를 다듬어 build_form.py로 만들어 달라"고 하세요.', 'ok');
}

// ──────────────────────────────────────────────────────────────
// 서비스 전환
// ──────────────────────────────────────────────────────────────
const LANE_KEY = 'hwpx-studio.lane.v1';

function showLane(lane) {
  document.querySelectorAll('[data-lane]').forEach((button) => {
    button.setAttribute('aria-pressed', String(button.dataset.lane === lane));
  });
  document.querySelectorAll('[data-panel]').forEach((panel) => {
    panel.hidden = panel.dataset.panel !== lane;
  });
  if (lane === 'diagram') drawDiagramSamples();
  try { localStorage.setItem(LANE_KEY, lane); } catch { /* 무시 */ }
}

function init() {
  for (const [name, profile] of Object.entries(HWPX_PROFILES)) {
    const option = document.createElement('option');
    option.value = name;
    option.textContent = `${profile.name} (${name})`;
    profileSelect.append(option);
  }
  profileSelect.value = 'policy-default';

  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved) bodyText.value = saved;
  } catch { /* 접근 불가해도 무시 */ }

  renderMarkers();
  updateStat();

  bodyText.addEventListener('input', updateStat);
  profileSelect.addEventListener('change', () => { renderMarkers(); updateStat(); });
  $('build').addEventListener('click', runBuild);
  $('capture-run').addEventListener('click', runCapture);
  $('capture-download').addEventListener('click', downloadDiagram);
  $('capture-preview').addEventListener('click', () => drawCapturePreview());
  document.querySelectorAll('[data-capture-sample]').forEach((button) => {
    button.addEventListener('click', () => {
      $('capture-text').value = CAPTURE_SAMPLES[button.dataset.captureSample];
    });
  });
  $('check').addEventListener('click', runCheck);
  $('form-run').addEventListener('click', runFormkit);
  $('form-bullets').addEventListener('change', () => {
    if ($('form-file').files.length) runFormkit();      // 고르면 곧바로 다시 해부한다
  });
  $('form-download').addEventListener('click', () => downloadBundle('zip'));
  $('form-download-skill').addEventListener('click', () => downloadBundle('skill'));
  $('convert-run').addEventListener('click', runConvert);
  $('convert-download').addEventListener('click', downloadConverted);
  $('convert-bundle').addEventListener('click', downloadConvertBundle);
  $('convert-copy').addEventListener('click', () => {
    if (!convertState) return;
    bodyText.value = convertState.text;
    updateStat();
    showLane('write');
    setStatus('되돌린 원고를 본문 칸에 넣었습니다.');
  });
  document.querySelectorAll('[data-lane]').forEach((button) => {
    button.addEventListener('click', () => showLane(button.dataset.lane));
  });
  let lane = 'form';
  try { lane = localStorage.getItem(LANE_KEY) || 'form'; } catch { /* 무시 */ }
  showLane(document.querySelector(`[data-panel="${lane}"]`) ? lane : 'form');
  document.querySelectorAll('[data-sample]').forEach((button) => {
    button.addEventListener('click', () => {
      bodyText.value = SAMPLES[button.dataset.sample];
      const forSample = { narrative: 'narrative', research: 'kihasa-research' };
      profileSelect.value = forSample[button.dataset.sample] || 'policy-default';
      renderMarkers();
      updateStat();
      setStatus('예시를 불러왔습니다.');
    });
  });
}

init();
