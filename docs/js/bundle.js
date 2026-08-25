/**
 * 양식 꾸러미 만들기 — hwpx_studio/export_form.py의 브라우저 이식.
 *
 * 안내문 본문은 여기에 적지 않는다. `assets.js`의 FORM_TEMPLATES가 파이썬 쪽과
 * **같은 틀**이고, 여기서는 자리표만 채운다. 빌더·되돌리기 파이썬 스크립트도
 * 저장소 원본을 그대로 실어 나른다.
 */

import { FORM_SCRIPTS, FORM_TEMPLATES } from '../assets.js';
import { analyzeParts, dumpForm } from './formkit.js';
import { unzip, zip } from './zip.js';
import { contentsOf, refuseBinaryHwp } from './xml.js';

export const BUILDER = 'build_form.py';
export const READER = 'read_hwpx.py';
export const FORM_JSON = 'form.json';
export const TEMPLATE = 'template.hwpx';

const encoder = new TextEncoder();

/** hwpx 바이트 → {이름: 텍스트} (Contents/*.xml만). */
export async function readContents(buffer) {
  refuseBinaryHwp(buffer);
  const out = contentsOf(await unzip(buffer));
  if (!Object.keys(out).length) throw new Error('hwpx 안에서 본문을 찾지 못했습니다.');
  return out;
}

export function slug(name) {
  let out = '';
  for (const ch of String(name).toLowerCase()) {
    if (/[a-z0-9]/.test(ch)) out += ch;
    else if (' _-.'.includes(ch)) out += '-';
  }
  out = out.replace(/^-+|-+$/g, '');
  while (out.includes('--')) out = out.replace('--', '-');
  // 너무 짧거나 숫자뿐이면 이름 구실을 못 한다
  if (out.length < 3 || /^\d+$/.test(out.replace(/-/g, ''))) return `hwpx-form-${tag(name)}`;
  return out;
}

/** 이름에서 뽑는 짧고 안정된 꼬리표(FNV-1a 32비트). 파이썬 쪽과 같아야 한다. */
export function tag(name) {
  let value = 0x811c9dc5;
  for (const byte of encoder.encode(String(name))) {
    value = Math.imul(value ^ byte, 0x01000193) >>> 0;
  }
  return (value.toString(36) || '0').slice(0, 6);
}

export function markerRows(form) {
  const rows = ['| 마커 | 뜻 | 기호·번호를 붙이는 쪽 |', '|---|---|---|'];
  for (const lv of form.levels || []) {
    let who;
    if (lv.auto_bullet) who = `한글이 자동으로 \`${lv.auto_bullet}\` — 본문에 쓰지 말 것`;
    else if (lv.auto_number) who = '한글이 자동으로 번호 — 본문에 쓰지 말 것';
    else if (lv.numbering) who = `도구가 번호를 매김(${lv.numbering})`;
    else if (lv.write_marker) who = `도구가 \`${lv.marker}\`를 붙임`;
    else who = '없음';
    rows.push(`| \`${lv.marker || '(마커 없음)'}\` | ${lv.name || ''} ${lv.size_pt}pt | ${who} |`);
  }
  return rows.join('\n');
}

export function sampleText(form) {
  const bodies = [
    '추진 배경 및 목적',
    '제도 개선 요구가 이어져 개선 방안을 마련',
    '기존 절차의 처리 기간이 길어 이용자 불편이 누적',
    '현장 실사 대상은 무작위 층화 표본으로 뽑음',
    '실사 기간은 2025년 9월~11월',
  ];
  const headings = ['사업 추진 현황', '추진 개요', '세부 내용', '참고'];
  const lines = [];
  (form.levels || []).forEach((lv, i) => {
    if (!lv.marker) return;
    let text = bodies[i % bodies.length];
    if (lv.marker.startsWith('#')) {
      text = headings[Math.min((lv.marker.match(/#/g) || []).length - 1, 3)];
    }
    lines.push(`${lv.marker} ${text}`);
  });
  if (!lines.length) lines.push('내용을 한 줄에 하나씩 적는다');

  lines.push('', '[표: 연도별 처리 실적]', '{cols=30,35,35}',
    '| 구분 | 2024년 | 2025년 |', '|---|---|---|',
    '| 처리 건수 | 1,204건 | 1,388건 |',
    '| 평균 처리 기간 | 14일 | 11일 |', '');
  if (!(form.table || {}).caption) lines.splice(lines.length > 8 ? -8 : 0, 0, '');

  const first = (form.levels || []).find(
    (lv) => lv.marker && !lv.marker.startsWith('#'));
  if (form.footnote) {
    lines.push(`${first ? first.marker : ''} 처리 기간이 3일 줄었다[^1]`.trim(), '',
      '[^1]: 통계청(2025), 「행정통계」, 87쪽.');
  }
  return `${lines.join('\n')}\n`;
}

export function bundleFields(form) {
  const name = form.name || '양식';
  return {
    name,
    slug: slug(name),
    markers: markerRows(form),
    footnote: form.footnote ? '각주는 근거가 되는 말 뒤에 `[^1]`로 단다. ' : '',
  };
}

export function render(template, fields) {
  let out = template;
  for (const [key, value] of Object.entries(fields)) {
    out = out.split(`{{${key}}}`).join(value);
  }
  return out;
}

/**
 * 양식 hwpx 바이트 → 꾸러미.
 * @returns {{files: Map<string, Uint8Array>, form: object, report: string}}
 */
export async function buildBundle(buffer, name) {
  const parts = await readContents(buffer);
  const { form, report } = analyzeParts(parts, name);
  const fields = bundleFields(form);

  const files = new Map();
  files.set(TEMPLATE, new Uint8Array(buffer));
  files.set(FORM_JSON, encoder.encode(dumpForm(form)));
  files.set(BUILDER, encoder.encode(FORM_SCRIPTS[BUILDER]));
  files.set(READER, encoder.encode(FORM_SCRIPTS[READER]));
  for (const [filename, template] of Object.entries(FORM_TEMPLATES)) {
    files.set(filename, encoder.encode(render(template, fields)));
  }
  files.set('해부보고서.md', encoder.encode(report));
  files.set('예시.md', encoder.encode(sampleText(form)));
  return { files, form, report };
}

/** 꾸러미를 폴더 한 겹을 둔 zip으로 묶는다(.skill로 써도 된다). */
export async function packBundle(files, root) {
  const packed = new Map();
  for (const [name, data] of files) packed.set(`${root}/${name}`, data);
  return zip(packed, []);
}
