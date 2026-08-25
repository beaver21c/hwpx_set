/**
 * 아주 작은 XML 훑기 — 해부(formkit)와 되돌리기(readback)가 함께 쓴다.
 *
 * DOMParser에 기대지 않는다. 브라우저와 Node(대조 도구) 양쪽에서 같아야 하고,
 * 단일 HTML로 묶을 때 한 벌만 있어야 하기 때문이다.
 */

const TAG_SOURCE = '<(\\/?)([\\w:]+)((?:[^>"\']|"[^"]*"|\'[^\']*\')*?)(\\/?)>';

/**
 * 태그를 하나씩 내놓는다.
 *
 * 정규식을 호출마다 새로 만든다. 하나를 나눠 쓰면 중첩 호출이 `lastIndex`를
 * 초기화해 바깥 반복이 처음으로 되돌아간다(무한 반복).
 */
export function* scan(xml) {
  const re = new RegExp(TAG_SOURCE, 'g');
  let m;
  while ((m = re.exec(xml)) !== null) {
    yield {
      close: m[1] === '/',
      name: m[2].includes(':') ? m[2].split(':')[1] : m[2],
      raw: m[2],
      attrs: m[3],
      selfClose: m[4] === '/',
      start: m.index,
      end: m.index + m[0].length,
    };
  }
}

export function attr(text, name, fallback = '') {
  const m = new RegExp(`\\b${name}="([^"]*)"`).exec(text || '');
  return m ? m[1] : fallback;
}

export function num(text, name, fallback = 0) {
  const value = Number.parseFloat(attr(text, name, ''));
  return Number.isFinite(value) ? value : fallback;
}

export function unescapeXml(text) {
  return text.replace(/&lt;/g, '<').replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"').replace(/&apos;/g, "'").replace(/&amp;/g, '&');
}

/**
 * `start` 자리에서 여는 태그 하나의 안쪽을 떼어 낸다. 자기 이름의 중첩을 센다.
 * @returns {{inner: string, start: number, end: number}|null}
 */
export function innerAt(xml, tag, start) {
  const head = xml.indexOf('>', start);
  if (head < 0) return null;
  if (xml[head - 1] === '/') return { inner: '', start, end: head + 1 };   // 빈 태그
  let depth = 1;
  const walker = new RegExp(`<${tag}[ >]|</${tag}>`, 'g');
  walker.lastIndex = head + 1;
  let m;
  while ((m = walker.exec(xml)) !== null) {
    depth += m[0].startsWith('</') ? -1 : 1;
    if (depth === 0) {
      return { inner: xml.slice(head + 1, m.index), start, end: walker.lastIndex };
    }
  }
  return null;
}

/** `from` 뒤에서 처음 나오는 여는 태그의 안쪽. 없으면 null. */
export function innerFrom(xml, tag, from = 0) {
  const open = new RegExp(`<${tag}[ >]`, 'g');
  open.lastIndex = from;
  const first = open.exec(xml);
  return first ? innerAt(xml, tag, first.index) : null;
}

export const decodeUtf8 = (bytes) => new TextDecoder().decode(bytes);

/** 푼 hwpx(Map)에서 Contents/*.xml만 골라 문자열로. */
export function contentsOf(entries) {
  const out = {};
  for (const [name, bytes] of entries) {
    if (name.startsWith('Contents/') && name.endsWith('.xml')) {
      out[name] = decodeUtf8(bytes);
    }
  }
  return out;
}

//: 한글 바이너리(.hwp) 서명. hwpx(zip)와 헷갈리지 않게 먼저 걸러 낸다.
const HWP_MAGIC = [0xd0, 0xcf, 0x11, 0xe0];

export function refuseBinaryHwp(buffer) {
  const head = new Uint8Array(buffer.slice(0, 4));
  if (HWP_MAGIC.every((byte, i) => head[i] === byte)) {
    throw new Error('한글 바이너리(.hwp) 파일입니다. 한글에서 [다른 이름으로 저장] → '
      + "파일 형식 'HWPX 문서'로 저장한 뒤 올려 주세요.");
  }
}
