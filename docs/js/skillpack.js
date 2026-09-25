/**
 * 서식(프로파일) → Claude·ChatGPT 스킬 zip. 파이썬 `hwpx_studio/skillpack.py` 이식.
 *
 * 틀(SKILL.md·README.md)과 빌더(hwpx_build.py)는 assets.js에 복제돼 있다.
 * 두 쪽이 같은 파일을 만드는지는 tests/test_skillpack.py가 대조한다.
 */

import { SKILL_BUILDER_SOURCE, SKILL_TEMPLATES } from '../assets.js';
import { shortName, slug } from './bundle.js';
import { mergeProfile } from './hwpx-studio.js';
import { zip } from './zip.js';

const encoder = new TextEncoder();

export const AUTO_LABELS = {
  AUTO_ROMAN: 'Ⅰ. Ⅱ. Ⅲ.',
  AUTO_NUM: '1. 2. 3.',
  AUTO_ALPHA: 'A. B. C.',
  AUTO_HANGUL: '가. 나. 다.',
  AUTO_CIRCLED: '① ② ③',
  AUTO_CHAPTER: '제1장 제2장',
  AUTO_SECTION: '제1절 제2절',
  AUTO_PAREN: '1) 2) 3)',
};

export const PERIOD_RULES = {
  single_sentence_no_period: '한 문장이면 온점을 찍지 않고, 두 문장 이상이면 찍는다',
  always_period: '모든 문장을 온점으로 끝낸다',
  never_period: '온점을 찍지 않는다',
  off: '온점은 검사하지 않는다',
};

/** 숫자를 사람이 읽을 모양으로(파이썬 fmt_num과 같게). */
export const fmtNum = (value) => String(Math.round(Number(value) * 1e4) / 1e4);

/** 캡션 번호가 찍히는 모양(1장 첫 번째). kind = table | figure */
export function captionSample(profile, kind) {
  const fmt = String((profile.captions || {})[kind] || '');
  return fmt.split('{장}').join('1').split('{번호}').join('1');
}

function head(level, profile) {
  const prefix = String(level.prefix || '');
  if (prefix === 'AUTO_TABLE' || prefix === 'AUTO_FIGURE') {
    const kind = prefix === 'AUTO_TABLE' ? 'table' : 'figure';
    const title = kind === 'table' ? '표 제목' : '그림 제목';
    return `${captionSample(profile, kind)} (${title}) (도구가 매김)`;
  }
  if (prefix.startsWith('AUTO_')) return `${AUTO_LABELS[prefix] || prefix} (도구가 매김)`;
  if (prefix.trim()) return `\`${prefix.trim()}\` (도구가 붙임)`;
  return '없음';
}

export function skillMarkerRows(profile) {
  const rows = ['| 입력 마커 | 단계 | 문서에 찍히는 머리 | 글자 |', '|---|---|---|---|'];
  for (const lv of profile.levels) {
    const marker = lv.marker ? `\`${lv.marker}\`` : '(마커 없이 쓴 줄)';
    const size = `${fmtNum(lv.size_pt || 0)}pt${lv.bold ? ' 굵게' : ''}`;
    rows.push(`| ${marker} | ${lv.name || lv.key} | ${head(lv, profile)} | ${size} |`);
  }
  if (profile.mode === 'narrative') {
    rows.push(`| (마커 없이 쓴 줄) | 본문 | 없음 | ${fmtNum(profile.body.size_pt || 0)}pt |`);
  }
  return rows.join('\n');
}

function captionMarker(profile, kind) {
  const found = profile.levels.find((lv) => lv.prefix === kind && lv.marker);
  return found ? String(found.marker) : '';
}

export function captionLines(profile) {
  const table = captionMarker(profile, 'AUTO_TABLE');
  const figure = captionMarker(profile, 'AUTO_FIGURE');
  const out = [];
  if (table) out.push(`- 표 제목: 표 바로 위에 \`${table} 제목\` 한 줄. 번호(${captionSample(profile, 'table')})는 도구가 매긴다`);
  if (figure) out.push(`- 그림·도식 제목: 도식 바로 위에 \`${figure} 제목\` 한 줄. 번호는 도구가 매긴다`);
  if (!out.length) out.push('- 이 서식에는 표·그림 번호 단계가 없다. 도식 제목은 블록의 `title="…"`로 준다');
  return out.join('\n');
}

export function pageLine(profile) {
  const page = profile.page;
  const margin = page.margin_mm || {};
  let size = String(page.size || '');
  if (page.width_mm && page.height_mm) {
    size = `${size} ${fmtNum(page.width_mm)}×${fmtNum(page.height_mm)}mm`.trim();
  }
  return `${size}, 여백 왼쪽 ${fmtNum(margin.left || 0)}·오른쪽 ${fmtNum(margin.right || 0)}`
    + `·위 ${fmtNum(margin.top || 0)}·아래 ${fmtNum(margin.bottom || 0)}mm`;
}

export function skillFields(userProfile, name, id = '') {
  const profile = mergeProfile(userProfile);
  const flat = String(name || profile.name || '보고서').split(/\s+/).filter(Boolean).join(' ');
  const rules = profile.rules || {};
  return {
    name: flat,
    slug: slug(String(id).trim() || flat),
    short: shortName(flat),
    mode: profile.mode === 'narrative'
      ? '서술식 — `#`·`##` 제목 밖의 줄은 모두 본문 문단이 된다'
      : '개조식 — 줄머리 마커로 단계를 가른다',
    markers: skillMarkerRows(profile),
    captions: captionLines(profile),
    page: pageLine(profile),
    fonts: `제목 ${profile.fonts.bold || ''} / 본문 ${profile.fonts.light || ''}`,
    period: PERIOD_RULES[rules.period_policy || ''] || '기본 규칙',
  };
}

export function skillSampleText(userProfile) {
  const profile = mergeProfile(userProfile);
  const lines = [];
  const captions = new Set(['AUTO_TABLE', 'AUTO_FIGURE']);
  for (const lv of profile.levels) {
    if (captions.has(lv.prefix)) continue;
    const text = `${lv.name || lv.key} 단계의 예시 문장이다.`;
    lines.push(lv.marker ? `${lv.marker} ${text}` : text);
  }
  if (profile.mode === 'narrative') {
    lines.push('본문 문단의 예시다. 근거가 되는 말 뒤에 각주를 단다[^1].');
  } else {
    const body = profile.levels.filter((lv) => !String(lv.prefix || '').startsWith('AUTO_'));
    const lead = body.length && body[0].marker ? `${body[0].marker} ` : '';
    lines.push(`${lead}근거가 되는 말 뒤에 각주를 단다[^1]`);
  }
  const table = captionMarker(profile, 'AUTO_TABLE');
  const figure = captionMarker(profile, 'AUTO_FIGURE');
  lines.push('');
  if (table) lines.push(`${table} 연도별 실적`, '');
  lines.push('| 구분 | 2024년 | 2025년 |', '|---|---|---|',
    '| 처리 건수 | 1,204 | 1,388 |', '| 처리 기간(일) | 14 | 11 |', '');
  if (figure) lines.push(`${figure} 추진 체계`, '');
  lines.push(':::diagram type=org title="추진 체계"', '총괄', '  기획부', '  운영부', ':::',
    '', '[^1]: ○○청. (2025). 『행정통계』. 12쪽.', '');
  return lines.join('\n');
}

export function renderSkill(template, fields) {
  let out = template;
  for (const [key, value] of Object.entries(fields)) out = out.split(`{{${key}}}`).join(value);
  return out;
}

/**
 * 서식 → 스킬 파일들.
 * @returns {{files: Map<string, Uint8Array>, fields: object}}
 */
export function buildSkill(profile, name, templateBytes, id = '') {
  const fields = skillFields(profile, name, id);
  const files = new Map();
  files.set('SKILL.md', encoder.encode(renderSkill(SKILL_TEMPLATES['SKILL.md'], fields)));
  files.set('README.md', encoder.encode(renderSkill(SKILL_TEMPLATES['README.md'], fields)));
  files.set('profile.json', encoder.encode(`${JSON.stringify(profile, null, 2)}\n`));
  files.set('template.hwpx', new Uint8Array(templateBytes));
  files.set('예시.md', encoder.encode(skillSampleText(profile)));
  files.set('scripts/hwpx_build.py', encoder.encode(SKILL_BUILDER_SOURCE));
  return { files, fields };
}

/** zip으로 묶는다. 맨 위 폴더 이름 = 스킬 이름(claude.ai 조건). */
export async function packSkill(files, root) {
  const packed = new Map();
  for (const [path, data] of files) packed.set(`${root}/${path}`, data);
  return zip(packed, []);
}
