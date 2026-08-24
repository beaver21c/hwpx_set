/** 웹 UI 연결부. 엔진은 hwpx-studio.js, 자산(템플릿·프로파일)은 assets.js. */

import { HWPX_PROFILES, HWPX_TEMPLATE_B64 } from '../assets.js';
import { base64ToBytes, buildFromText, lintItems, mergeProfile, parseText } from './hwpx-studio.js';
import { captureText, specToText } from './capture.js';

const STORAGE_KEY = 'hwpx-studio.draft.v1';

const $ = (id) => document.getElementById(id);
const bodyText = $('body-text');
const profileSelect = $('profile');
const filename = $('filename');
const statusEl = $('status');
const issuesEl = $('issues');
const reportPanel = $('report-panel');

const SAMPLES = {
  outline: `# 사업 추진 현황
## 추진 개요
□ 추진 배경 및 목적
○ 제도 개선 요구가 지속 제기되어 개선 방안을 마련
- 기존 절차의 처리 기간이 길어 이용자 불편이 누적
- 담당 부서별 기준이 달라 안내가 일관되지 않음
○ 이용자 편의 개선과 처리 기간 단축을 목표로 설정
- 목표는 부서 협의를 거쳐 확정
- 세부 지표는 분기별로 점검

□ 지표별 실적

| 구분 | 목표 | 실적 |
|---|---|---|
| 처리 기간 | 14일 | 11일 |
| 이용 건수 | 1,000건 | 1,240건 |

○ 처리 기간은 목표 대비 3일 단축
- 사전 검토 절차를 통합한 효과로 판단
- 접수량이 많은 기간에는 지연 사례가 발생
○ 이용 건수는 목표를 상회[^1]
- 안내 창구 확대가 주된 요인
- 재방문 비율은 [확인 필요]

[^1]: 내부 행정통계, 2025년 상반기 기준.
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
  document.querySelectorAll('[data-capture-sample]').forEach((button) => {
    button.addEventListener('click', () => {
      $('capture-text').value = CAPTURE_SAMPLES[button.dataset.captureSample];
    });
  });
  $('check').addEventListener('click', runCheck);
  document.querySelectorAll('[data-sample]').forEach((button) => {
    button.addEventListener('click', () => {
      bodyText.value = SAMPLES[button.dataset.sample];
      if (button.dataset.sample === 'narrative') profileSelect.value = 'narrative';
      else profileSelect.value = 'policy-default';
      renderMarkers();
      updateStat();
      setStatus('예시를 불러왔습니다.');
    });
  });
}

init();
