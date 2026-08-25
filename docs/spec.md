> **구현 현황 메모(착수분)**
>
> 이 문서는 착수 시점의 설계 원안이다. 실제 구현과 다른 점은 아래와 같다.
>
> - §11.2 착수 전 결정은 권고안대로 정했다: ① 레벨 **가변**, ② 도식 기본 **표**,
>   ③ 검증용 실제 hwpx 미제공(M3의 실파일 평가는 보류), ④ 브라우저 앱(M6) 제외,
>   ⑤ 화살표는 flow의 `→`/`▼` 문자 + `render=image` 폴백으로 처리
> - §4 저장소 구조 중 `profiles/`는 `hwpx_studio/profiles/`로 옮겼다(설치본에 포함시키기 위함).
>   `templates/`의 SKILL 템플릿·prompt 조각은 별도 파일 대신 `hwpx_studio/export_skill.py`에 포함
> - §7.3 org 레이아웃은 원안(리프 수 × 2 + 1, 상자 1칸)과 달리 **균일 폭 열 격자**로 구현했다.
>   상자를 짝수 개 열로 병합해 그 경계를 중심선으로 삼으므로 연결선이 상자 **가운데**에 맞는다
>   (원안·프로토타입은 상자 왼쪽 변에 붙었다). 근거: `docs/diagram-guide.md` §4
> - 진행 단계: M0~M5, M7-0, M7-1, M7-2 완료 / M6(브라우저 앱)은 미착수
> - **M3 실파일 평가 1건 수행**: 한글로 직접 작성한 hwpx에서 7레벨 전부 복원.
>   그 과정에서 드러난 결함 3건(제목 상자 안 제목 누락, 글꼴 이름 기반 굵기 오판,
>   쪽번호 클러스터 혼입)을 고치고 `tests/test_extractor_real.py`로 고정했다.
>   검사에 쓴 실제 문서는 저장소에 포함하지 않는다
> - **M7-0 확인됨**: 셀 한 변 테두리 연결선은 한글에서 정상 표시된다(한글 모바일 뷰어).
>   §7.4의 대안(배경색 셀 대체)은 불필요. 근거·프로토타입과의 차이는 `prototypes/README.md`
>
> - **M8 양식 보존 방식 추가(설계 원안 밖)**: 원안은 서식을 프로파일로 옮겨 적어
>   문서를 새로 짓는 길 하나뿐이었다. 그 길로는 한글의 자동 글머리표·번호매기기
>   (`paraPr`의 `hh:heading`)를 옮기지 못한다. 그래서 양식 파일을 **템플릿으로 그대로
>   두고 본문 문단만 갈아 끼우는** 길을 더했다(`formkit.py` → `assets/build_form.py`).
>   `header.xml`을 한 바이트도 건드리지 않으므로 서식이 재현이 아니라 **보존**된다.
>   근거·한계는 `docs/form-guide.md`
> - **M9 되돌리기 추가**: 서식 없는 hwpx를 마커 텍스트로 되돌린다
>   (`assets/read_hwpx.py`). 줄머리 기호·번호·글자 크기를 근거로 계층을 **추정**하고
>   근거를 보고서로 남긴다. 그림은 읽지 못한다
> - **M6(브라우저 앱) 착수·완료**: 웹 앱은 네 갈래(양식 꾸러미·도식·되돌리기·바로
>   쓰기)로 나뉜다. 해부·되돌리기는 브라우저에도 이식했고
>   `tools/compare_js_python.py`가 두 엔진의 `form.json`과 마커 텍스트를 대조한다

> ---

# hwpx-studio 설계 명세서 (통합본, Claude Code 착수용)

> 목적: 한국어 개조식·서술식 보고서를 `.hwpx`로 생성하는 **공개 도구**. 서식 커스터마이징(프로파일), 기존 hwpx 서식 불러오기, 도식(조직도·체계도·절차도) 삽입을 포함
> 작성 기준일: 2026-08-22 / 기반: 기존 `hwpx-report` 스킬(hwpx_generator.py v6) + python-hwpx 6.2.1
> 지위 표기: [1차 확인] 샌드박스 실행·검증 / [논리적 추론] 코드 구조 근거 / [미확인] 검증 미실시
> 공개 원칙: 특정 기관·개인 식별 정보, 내부 문서명, 조직명 포함 금지. 예시는 모두 일반 명칭(대표/기획부/운영부, 정책 사업 평가 등) 사용

---

## 0. 요약

- 설계 결정 4건
  1. **서식(프로파일 JSON) ↔ 본문(마커 텍스트) ↔ 엔진(변환기) 3분리**. 현재 단일 py파일 혼재 구조 해체
  2. 본문 입력 = 줄 단위 마커 텍스트(`# / ## / □ / ○ / - / · / ※ / |표| / ![img]` + `:::diagram` 블록). Claude·GPT·Gemini 등 어떤 AI든 동일 규칙으로 생성 가능, 사람이 직접 수정 가능 → **AI 의존 최소화**
  3. 스타일 불러오기 = hwpx `header.xml`(charPr/paraPr/style) + 본문 첫 글자 패턴 분석 → 프로파일 JSON 역생성. 자동 확정 금지, 리포트 확인 후 저장
  4. 도식 = 텍스트 블록(들여쓰기 트리·`→` 흐름)으로 기술 → 도구가 **표 셀 테두리**로 그리거나(기본) **이미지**로 렌더(폴백)
- 실험 결과(§2): 프로파일 주입→생성→재추출 왕복 일치, 표 기반 조직도 XML 생성 [1차 확인]. 한글 프로그램 직접 작성 문서의 추출 정확도, 한 변 테두리 연결선의 한글 화면 표시는 [미확인]
- 권장 아키텍처: **Python 패키지 + 프로파일 JSON**(옵션 A) 우선 → 스킬 내보내기는 서브커맨드 → 브라우저 앱(옵션 C)은 2단계
- 착수 전 결정(§11): ① 레벨 가변 vs 고정 7슬롯 ② 도식 기본 렌더(표 vs 이미지) ③ 검증용 실제 hwpx 제공 ④ 브라우저 앱 포함 여부

---

## 1. 현행 구조 분석 [1차 확인]

### 1.1 기존 스킬 구성
```
hwpx-report/
├── SKILL.md                      # 6단계 절차, 레벨 체계, 계층 균형 규칙
├── scripts/hwpx_generator.py     # 1,109행 = 설정영역(26~293) + 엔진(295~1107)
├── templates/report_contents_skeleton.py
└── reference/{level-system, hierarchy-rules, examples, code-structure}.md
```

### 1.2 엔진 동작 원리
- `python-hwpx`의 `blank_document_bytes()` 템플릿 → `header.xml` 정규식 패치(폰트 id 0/1 교체, charPr 7~17·paraPr 20~28·style 1~10 주입, borderFill 3~4 추가) → `add_paragraph(style_id_ref, char_pr_id_ref)` → `section0.xml` 후처리(paraPrIDRef 보정, 표/그림 속성 패치)
- 글머리 기호는 **텍스트 접두어(prefix)로 직접 삽입**(한글 번호매기기 기능 미사용). 로마자·숫자는 카운터 생성
- 레벨 슬롯 고정 7개(title, title2, L1~L5) + 표 스타일 3개 + 바탕글. ID가 5개 지점(`LMAP`, `styles_cfg`, `para_cfgs`, `style_defs`, `STYLE_TO_PARA`)에 하드코딩

### 1.3 범용화 저해 요인
| 요인 | 현상 | 영향 |
|---|---|---|
| 설정·본문·엔진 단일 파일 | 본문 교체 위해 1,100행 파일 편집 | AI가 파일 전체를 다루어야 함 → 토큰 소모·오편집 |
| 본문 = Python 튜플 리스트 | `(2, "…")` 문법·이스케이프 | 비개발자·타 AI 생성 오류 [논리적 추론] |
| 레벨/ID 하드코딩 | 레벨 추가·삭제 불가 | 개인별 체계 대응 불가 |
| `SAVE_PATH` Windows 절대경로 | 타 환경 첫 실행 실패 | Colab 등 |
| 검증 수단 부재 | 한글 없이는 결과 확인 불가 | 반복 수정 비용 |
| 도식 미지원 | 조직도·체계도는 별도 제작 | 문서 완결성 저하 |

---

## 2. 실험 결과 (Ubuntu · Python 3.12 · python-hwpx 6.2.1)

### 2.1 본문·서식
| # | 실험 | 결과 | 지위 |
|---|---|---|---|
| 1 | 번들 생성기 실행 | hwpx 생성 성공(`SAVE_PATH`만 변경) | [1차 확인] |
| 2 | 생성 hwpx → 스타일 역추출(`prototypes/extract_style.py`) | 7레벨+표 3스타일의 size/bold/color/font/left/indent/spacing/line_spacing/align 전부 복원. 접두 기호(Ⅰ. 1. □ ○ - · ※) 첫 글자 빈도로 추정 성공 | [1차 확인] |
| 3 | styleIDRef 전부 0인 문서에서 `(paraPr, charPr)` 클러스터링 | 10개 클러스터로 레벨 복원(스타일 미사용 문서 대리 실험) | [1차 확인, 합성 데이터] |
| 4 | 마커 텍스트 → 콘텐츠 리스트(`prototypes/md2contents.py`) | 제목·5레벨·마크다운 표·그림·빈 줄 변환 | [1차 확인] |
| 5 | 프로파일 JSON 주입→생성→재추출(`prototypes/build.py`) | 폰트·여백·크기·색·기호 주입값 = 재추출값 | [1차 확인] |
| 6 | HTML 근사 미리보기 | `hwpx.tools.layout_preview` 로 페이지·여백·문단·표 근사 HTML. LibreOffice는 hwpx 변환 실패 | [1차 확인] |
| 7 | 의존성 | python-hwpx Apache-2.0, `lxml>=4.9` 의존(생성 경로에서 실제 import), 휠 650KB | [1차 확인] |

보정 사항: paraPr의 margin/lineSpacing이 `hp:switch/hp:case` 내부 중첩 → `.//hh:margin` 탐색 필요 / en dash(–) 등 비표준 기호는 "선행 비문자 기호 1~2자 + 공백" 일반 패턴으로 인식

### 2.2 도식
| # | 실험 | 결과 | 지위 |
|---|---|---|---|
| A | 표 생성 + 셀 병합(`merge_cells('A1:C1')`) | 성공. `cellSpan colSpan=3`. 셀 API(`cell(r,c)`, `set_size`, 셀 내 `add_paragraph`/`add_table`) 존재 | [1차 확인] |
| B | 셀 테두리 4변 개별 지정 | `ensure_border_fill(active_borders=['right'])` 등 변별 SOLID/NONE. `border_type` DASH/DOT/DOUBLE_SLIM, 채움색·그라데이션 지원 | [1차 확인] |
| C | 표 기반 조직도(대표 → 기획부/운영부/연구부) | 상자 셀(4변+채움)·연결선 셀(한 변)·투명 셀 → XML 정상(`prototypes/orgchart_table.py`, `.hwpx`) | [1차 확인: XML] / [미확인: 한글 화면] |
| D | 도형 `add_rectangle`·`add_line`(treat_as_char=False) | 삽입 성공. 그러나 `hp:offset x=0 y=0` 고정, 좌표 인자 없음 → 절대 배치는 XML 직접 패치 필요. `set_draw_text`로 도형 내 글자 가능 | [1차 확인] |
| E | 근사 미리보기의 도식 표시 | 상자 셀 렌더, 단일 변 테두리(연결선) 미렌더 → 미리보기로 선 검증 불가 | [1차 확인] |

기타: `add_chart`(chartML)는 "Experimental contract" 표기 → 미채택. `merge_table_cells`/`ensure_border_fill`은 6.0에서 `doc.tables.merge_cells`/`doc.styles.ensure_border_fill`로 이동, 7.0 제거 예고 → 신 API 사용

---

## 3. 아키텍처 옵션

| 구분 | A. Python 패키지 + 프로파일 JSON | B. 스킬 생성기 | C. 브라우저 JS 앱(GitHub Pages) |
|---|---|---|---|
| 구성 | `pip install hwpx-studio` 또는 단일 zip. CLI + 라이브러리 | 설정 → SKILL.md + py 번들 생성 | JSZip으로 hwpx(zip+XML) 브라우저 내 생성. Python 불필요 |
| Claude Code | ◎ | ◎ | △ |
| Colab | ◎ | ○ | △ |
| ChatGPT(코드 실행) | ○ 인터넷 차단 → 휠 업로드 설치(lxml 사전설치 [미확인]) | ○ | ◎ 텍스트만 생성 후 웹 변환 |
| 무료 계정 적합성 | ○ | ○ | ◎ |
| 스타일 불러오기 | ◎ 실험 2·3 | A 의존 | ○ DOMParser 이식 가능 [논리적 추론] |
| 표·그림·도식 | ◎ 엔진 재사용 | ◎ | △ 표 XML 직접 생성(포팅 비용 최대) |
| 개발 비용 | 중 | 소(A 위 래퍼) | 대 |

권장 순서: **A → B(A의 `export-skill` 서브커맨드로 흡수) → C(2단계, A의 규격 공유)**

제외 대안
- 한글 번호매기기/글머리표 기능(`hh:numbering`, `hh:bullet`) 사용: 편집 시 자동 갱신 장점. `ensure_numbering` 동작 범위 [미확인], 기존 문서 호환 불리 → v2 검토
- DOCX 경유: 서식 손실 빈번 [논리적 추론], hwpx 직접 생성이 이미 동작

---

## 4. 저장소 구조

```
hwpx-studio/
├── README.md                      # 3분 시작(Claude Code / Colab / GPT 각 1절)
├── pyproject.toml                 # python-hwpx>=6.2,<7
├── hwpx_studio/
│   ├── engine.py                  # 프로파일 구동형 생성 엔진
│   ├── profile.py                 # 스키마·검증·기본값 병합
│   ├── parser.py                  # 마커 텍스트 → 콘텐츠 리스트
│   ├── diagram.py                 # :::diagram 블록 → 표/이미지
│   ├── extractor.py               # hwpx → 프로파일 JSON
│   ├── preview.py                 # HTML 근사 미리보기
│   ├── lint.py                    # 계층 균형·기호 중복·온점·각주 번호 자리 검사
│   ├── export_skill.py            # 프로파일 → 스킬 폴더
│   └── cli.py
├── profiles/
│   ├── policy-default.json        # 기존 생성기 값(Ⅰ./1./□/○/-/·/※ 7레벨)
│   ├── gov-3level.json            # □/○/- 3레벨
│   └── narrative.json             # 서술식
├── templates/SKILL.template.md, prompt_snippets/
├── examples/input_outline.md, input_narrative.md, input_diagram.md
├── docs/
│   ├── index.html                 # (2단계) 프로파일 편집기 → JS 변환기
│   ├── writing-guide.md           # 본문 작성법
│   └── diagram-guide.md           # 도식 작성법(§12 참조)
├── tests/test_roundtrip.py, test_parser.py, test_diagram.py, fixtures/
└── notebooks/colab_quickstart.ipynb
```

---

## 5. 프로파일 JSON 규격 (v1)

```jsonc
{
  "schema": "hwpx-studio.profile.v1",
  "name": "정책보고서 기본",
  "mode": "outline",                        // outline(개조식) | narrative(서술식)
  "fonts": { "bold": "맑은 고딕", "light": "맑은 고딕", "fallback": "맑은 고딕" },
  "page": { "size": "A4", "margin_mm": { "left":20,"right":20,"top":10,"bottom":10,"header":10,"footer":10 } },
  "header_footer": { "header_text": "", "page_number": false },   // python-hwpx set_header_text/set_page_number 연동 [미확인]
  "levels": [                                                       // 순서 = 깊이, 개수 가변
    { "key":"title",  "name":"장", "marker":"#",  "prefix":"AUTO_ROMAN", "size_pt":18, "bold":true,  "font":"bold",  "color":"#2a56a1", "left_pt":0,  "indent_pt":0,  "spacing_below_pt":10, "line_spacing":180, "align":"JUSTIFY" },
    { "key":"title2", "name":"절", "marker":"##", "prefix":"AUTO_NUM",   "size_pt":16, "bold":true,  "font":"bold",  "color":"#1F3864", "left_pt":0,  "indent_pt":0,  "spacing_below_pt":10, "line_spacing":180 },
    { "key":"L1", "name":"네모",   "marker":"□", "prefix":"□ ", "size_pt":14,   "bold":true,  "font":"bold",  "color":"#4c4c4c", "left_pt":0,  "indent_pt":0,  "spacing_below_pt":5, "line_spacing":170 },
    { "key":"L2", "name":"원",     "marker":"○", "prefix":"○ ", "size_pt":13,   "bold":false, "font":"light", "left_pt":10, "indent_pt":15, "spacing_below_pt":3, "line_spacing":170 },
    { "key":"L3", "name":"하이픈", "marker":"-", "prefix":"- ", "size_pt":12.5, "bold":false, "font":"light", "left_pt":20, "indent_pt":15, "spacing_below_pt":1, "line_spacing":165 },
    { "key":"L4", "name":"점",     "marker":"·", "prefix":"· ", "size_pt":12,   "bold":false, "font":"light", "left_pt":32, "indent_pt":15, "spacing_below_pt":1, "line_spacing":160 },
    { "key":"L5", "name":"참고",   "marker":"※", "prefix":"※ ", "size_pt":10,   "bold":false, "font":"light", "color":"#666666", "left_pt":40, "indent_pt":15, "spacing_below_pt":1, "line_spacing":130 }
  ],
  "body":  { "size_pt":12, "font":"light", "line_spacing":160, "first_line_indent_pt":10 },   // 서술식 본문
  "table": { "border_color":"#999999", "header_bg":"#4472C4", "width_mm":162.5, "cell_margin_mm":0.3, "treat_as_char":true,
             "top":  { "size_pt":11, "bold":true,  "font":"bold",  "color":"#FFFFFF", "align":"CENTER" },
             "mid":  { "size_pt":11, "bold":false, "font":"light", "align":"CENTER" },
             "left": { "size_pt":11, "bold":false, "font":"light", "align":"LEFT", "indent_pt":12 } },
  "image": { "default_width_mm":120, "treat_as_char":true },
  "diagram": { "render":"table", "box_fill":"#DCE6F1", "box_border":"#1F3864", "root_fill":"#1F3864", "root_color":"#FFFFFF",
               "line_width_mm":0.3, "font_size_pt":11, "col_width_mm":18, "row_height_mm":8, "max_width_mm":160,
               "image_backend":"matplotlib" },
  "rules": { "min_children": { "title2":2, "L1":2, "L2":2 }, "period_policy":"single_sentence_no_period" }
}
```
원칙: 필드명은 기존 `STYLE_*` dict와 1:1 동일(이전 비용 최소) / `marker`(입력)와 `prefix`(출력) 분리 / `levels` 길이 가변 → 엔진이 ID 순차 할당 / 미지정 필드는 기본값 병합(부분 JSON 허용)

---

## 6. 본문 입력 규격 (마커 텍스트)

```
# 장 제목              → title   (Ⅰ. Ⅱ. 자동)
## 절 제목             → title2  (1. 2. 자동)
□ 주제                 → L1      (마커는 profile.levels[].marker)
○ 주요 / - 설명 / · 세부 / ※ 참고
(빈 줄)                → 블록 구분
| 구분 | 2024 | 2025 | → 연속 파이프 행 = 표(첫 행 헤더, |---| 행 무시)
![](그림.png)          → 그림
:::diagram … :::       → 도식(§7)
마커 없는 줄           → narrative: 본문 문단 / outline: 들여쓰기 깊이 → 레벨 폴백
```
- 마커 충돌: "마커 + 공백" 조합만 인식(음수 `-3%` 등 보호). 마크다운 `-`·`*` 불릿 습관은 들여쓰기 폴백으로 흡수
- 자동 기호 중복(`□ □ 주제`)은 1회만 인식 + lint 경고
- narrative 모드: `#`/`##`만 제목, 나머지 줄은 `body` 문단, 빈 줄 = 문단 구분

---

## 7. 도식(조직도·체계도·절차도) 규격

### 7.1 구현 경로 비교
| 구분 | ① 표 기반(기본) | ② 도형 기반 | ③ 이미지 삽입(폴백) |
|---|---|---|---|
| 원리 | 격자 셀에 상자·연결선을 테두리로 표현 | 사각형·선 개체 좌표 배치 | PNG 생성 → `image` 삽입 |
| 한글에서 편집 | ◎ 셀 글자 수정·행 추가(공공문서 관행과 일치) | ○ 정렬 수작업 | × 재생성 |
| 구현 난이도 | 중(트리 → 격자 좌표) | 상(XML 위치 패치) | 하(기존 image 경로) |
| 표현 범위 | 계층형·가로/세로 흐름·매트릭스 | 자유형(곡선·화살표) | 무제한 |
| 화살표 | × → 셀 내 `→ ▼` 문자 대체 | ○ `headStyle/tailStyle` | ◎ |
| 의존성 | python-hwpx만 | + 자체 XML | + matplotlib(Colab 기본) 또는 graphviz |
| JS 이식 | ○ | △ | ◎ |

권장: v1 = ① + ③ 병행(`render: table|image`), 기본 `table`. ②는 화살표·사선 수요 확인 후 v2

### 7.2 입력 블록
```
:::diagram type=org title="조직 체계"
대표
  기획부
    기획팀
    예산팀
  운영부
  연구부
:::

:::diagram type=flow direction=right
접수 → 검토 → 심의 → 통보
:::

:::diagram type=matrix
| | 중앙 | 지방 |
| 기획 | 본부 | 지역본부 |
| 집행 | 사업단 | 현장사무소 |
:::
```
- `type`: `org`(상하 계층) / `flow`(`→` 1줄, direction=right|down) / `matrix`(격자)
- 트리 들여쓰기 2칸(마크다운 중첩 목록과 동일 → AI 생성 난이도 최소)
- 옵션: `render=table|image`, `title`(표 캡션), `width=mm`

### 7.3 레이아웃 알고리즘(① org형)
1. 트리 파싱 → 노드별 리프 수(서브트리 폭)
2. 격자 폭 = 리프 수 × 2 + 1(노드 사이 간격 셀). 깊이당 3행(상자/세로선/가로 버스) + 마지막 깊이 1행
3. 노드 열 = 서브트리 중앙. 부모 아래 셀 오른쪽 변 세로선 → 가로 버스(첫~마지막 자식 구간, 아래 변) → 자식 위 셀 오른쪽 변 세로선
4. 상자 폭 부족 시 `col_width_mm` 축소 또는 인접 빈 셀 병합
5. 폭 > `max_width_mm` → `render=image` 자동 폴백 + 경고
- 실험 C는 3단·3부서를 수작업 좌표로 검증. 일반화는 [논리적 추론], M7에서 구현·테스트

### 7.4 선행 검증 필수 [미확인]
`prototypes/orgchart_table.hwpx`를 **한글(뷰어)에서 열어 연결선 표시 확인**. 표시 안 되면 ①은 상자만 그리고 연결선은 ③으로 대체하거나, 연결선 셀을 가는 높이의 채움 셀(테두리 대신 배경색)로 바꾸는 대안 검토

---

## 8. 모듈 설계

### 8.1 engine.py
- 입력 `profile: dict`, `contents: list`, `out_path` / 전역 제거
- 기존 엔진 변경 5지점
  | 지점 | 현행 | 변경 |
  |---|---|---|
  | `_patch_header` (C)(D)(F) | charPr 7~17, paraPr 20~28, style 1~10 하드코딩 | 템플릿 itemCnt 읽어 `base_id`부터 levels+표3+body 순 동적 할당, ID 맵 반환 |
  | `STYLE_TO_PARA` | 고정 | ID 맵에서 생성 |
  | `_patch_block_paragraphs` | 표/그림 외곽 문단 하이픈 고정 | `table.anchor_level`(기본: 마지막 본문 레벨) |
  | `create_report` `LMAP` | 7슬롯 | `levels[i].key` → ID 맵 |
  | 전역 설정값 | 모듈 전역 | 함수 인자 |
- 유지: XML 정규식 패치, 접두어 삽입, 표/그림 후처리
- 패리티 테스트: `policy-default.json` + 기존 예시 → 현행 생성기 출력과 스타일 속성 동일(ID 번호 상이 허용)
- 경량 대안(§11-①): 고정 7슬롯 + `enabled:false` → 실험 5 방식(전역 주입)으로 즉시 동작, 7레벨 초과·순서 변경 불가

### 8.2 parser.py — §6 규칙 구현. `:::diagram` 블록은 `diagram.py`로 위임
### 8.3 diagram.py — §7. 출력은 `("diagram", spec)` 항목 → 엔진이 표 생성 또는 PNG 생성 후 image 경로로 치환
### 8.4 extractor.py
1. `header.xml` 파싱: fonts, charPr(height/bold/textColor/fontRef), paraPr(`.//hh:margin`, `.//hh:lineSpacing`, align), styles
2. `section*.xml` 순회: 문단별 `(styleIDRef, paraPrIDRef, 첫 run charPrIDRef)` + 텍스트 40자
3. 클러스터 키: styleIDRef≠0이면 styleID, 전부 0이면 `(paraPr, charPr)`
4. 접두 기호 추정: 첫 토큰 "비문자 기호 1~2자" 또는 `로마자.`/`숫자.` → prefix·marker 후보, 빈도 1위 채택·2위 이하 `candidates` 보존
5. 레벨 순서: `left_pt` 오름차순 → 동률 시 size 내림차순. 로마자/숫자 prefix·상위 size는 title/title2
6. 표 스타일: `hp:tbl` 내부 문단 charPr을 첫 행/이후 행으로 분리
7. 출력: JSON + `extract_report.md`(클러스터별 예시·빈도·근거). 사용자 확인 후 저장
- 한글 번호매기기 기능 문서(`hh:heading type=NUMBER|BULLET`)는 `"prefix":"UNKNOWN_AUTO"` 표시 [논리적 추론]

### 8.5 lint.py — 계층 균형(`rules.min_children`), 기호 중복, 온점, 머릿글, 각주 번호 자리(`rules.footnote_position`), 표·도식 앞뒤 빈 줄. 모두 경고. `--strict` 시 오류면 중단
### 8.6 preview.py — `render_layout_preview()` 래퍼. 고지: "근사 미리보기. 글꼴·줄바꿈·도식 연결선은 한글 뷰어에서 확인"
### 8.7 export_skill.py — 프로파일 → `SKILL.md`(레벨표·마커·균형 규칙 치환) + `scripts/build.py`(`--standalone`: 엔진+파서+프로파일 1파일 인라인) + `prompt.txt`(타 AI용 300자 지시문)
### 8.8 cli.py
```
hwpx-studio init     [--from policy-default] profile.json   # 질문 최소: 레벨 수, 모드, 폰트 2종, 여백
hwpx-studio extract  ref.hwpx -o profile.json [--report]
hwpx-studio build    input.md -p profile.json -o out.hwpx [--lint strict] [--preview]
hwpx-studio lint     input.md -p profile.json
hwpx-studio preview  out.hwpx -o preview.html
hwpx-studio diagram  "대표 > 기획부, 운영부" -o org.hwpx      # 도식 단독 생성(빠른 시험용)
hwpx-studio export-skill profile.json -o ./my-skill [--standalone]
```

---

## 9. 플랫폼별 사용 시나리오

| 플랫폼 | 설치 | 본문 생성 | 변환 |
|---|---|---|---|
| Claude Code | `pip install hwpx-studio` 또는 export-skill 스킬 등록 | 스킬 절차(미리보기→승인) | 자동 build |
| Colab(무료) | `!pip install hwpx-studio` | 아무 AI → 셀에 붙여넣기 | 셀 실행 → `files.download()` |
| ChatGPT 무료 | 휠+zip 업로드 후 설치 [미확인: 계정 제약] | `prompt.txt` → 텍스트 | 세션 내 build 또는 Colab 변환 |
| 로컬 Python | pip | — | CLI |
| (2단계) 브라우저 | 없음 | 아무 AI | 페이지 붙여넣기 → 다운로드 |

최소 경로: **텍스트 생성(어디서든) → Colab 1셀 변환** — 무료·AI 의존 최소 요구에 가장 부합

---

## 10. 구현 로드맵

| 단계 | 산출물 | 완료 기준 |
|---|---|---|
| M0 | 구조(§4), pyproject, `policy-default.json` | 기존 py 값 → JSON 변환 스크립트 생성(수기 금지) |
| M1 | `engine.py` 프로파일 구동·동적 ID | 패리티 테스트 통과 |
| M2 | `parser.py`, `lint.py` | 실험 4 입력 + 엣지(음수, md 불릿) 통과 |
| M3 | `extractor.py` + 리포트 | 왕복 일치 + **실제 hwpx 2~3건** 레벨 복원률 수기 평가 |
| M4 | `cli.py`, Colab 노트북, README | Colab 무료 런타임 설치→변환→다운로드 1회 통과 |
| M5 | `export_skill.py`, 템플릿, prompt.txt | 산출 스킬로 문서 1건 생성 |
| M6 (선택) | `docs/index.html` | 프로파일 편집·텍스트 변환(표·도식 제외) |
| M7-0 | 도식 선행 검증 | `orgchart_table.hwpx` 한글 뷰어 확인(사용자) |
| M7-1 | `diagram.py` org/flow/matrix 표 생성 | 샘플 5건(깊이 2~4, 노드 3~15) 생성·lint 통과 |
| M7-2 | 이미지 폴백(matplotlib 우선, graphviz 선택) | Colab에서 PNG 생성·삽입 |
| M7-3 | 프로파일 `diagram` 절, prompt.txt 블록 규칙, `docs/diagram-guide.md` | 타 AI가 규칙만으로 유효 블록 생성 [미확인] |

각 단계 착수 전 이전 단계 테스트 재확인. M3·M7-0은 실제 확인 전 완료 선언 금지

---

## 11. 리스크·결정 사항

### 11.1 리스크
| 항목 | 지위 | 대응 |
|---|---|---|
| 한글 직접 작성 문서 추출 정확도 | [미확인] | M3 실제 파일 검증, 리포트 확인 절차 기본 |
| 한 변 테두리 연결선의 한글 표시 | [미확인] | M7-0 선행 확인, 대안 §7.4 |
| python-hwpx 7.0 API 변경 | [논리적 추론](6.0 이동 경고 다수) | `<7` 고정, 신 API 사용 |
| ChatGPT 무료 코드 실행 제약 | [미확인] | Colab 경로 1순위 안내 |
| 글꼴 미설치 | [논리적 추론] | `fonts.fallback` 필드, 뷰어 대체 표시 |
| 머리말/쪽번호 | [미확인] | M1에서 API 시험 후 포함 결정 |
| 시각 검증 불가 | [1차 확인] | HTML 근사 + 한글 뷰어 병행 |
| 접두어 텍스트 방식 | [논리적 추론] | 한글 편집 시 번호 미갱신 → v2 번호매기기 검토 |

### 11.2 착수 전 결정 (사용자 확인)
1. **레벨 가변(권장) vs 고정 7슬롯** — M1 범위 결정
2. **도식 기본 렌더**: 표(편집 가능) vs 이미지(표시 확실) — 문서 관행 기준
3. **검증용 실제 hwpx 2~3건** 제공 여부 — M3 평가 전제
4. **브라우저 앱(M6)** 포함 여부 — 포함 시 M0에서 JSON Schema 고정
5. 화살표 필요 여부 — 필요 시 ② 도형 기반 v1 편입 판단

---

## 12. 사용자용 문서 (docs/)

- `docs/diagram-guide.md`: 도식 작성법(별도 파일 동봉). "클릭"이 아닌 **텍스트로 쓰면 도구가 그린다**는 방식 설명, 한글에서 직접 그리는 방법과 비교, 3가지 유형 예시, 수정·한글 편집 요령
- `docs/writing-guide.md`(M4): 본문 마커 규칙·개조식 작성 요령·AI 지시문

---

## 부록 A. 프로토타입(`prototypes/`)
- `extract_style.py` 추출기 / `md2contents.py` 파서 / `build.py` 프로파일 주입 빌더 / `orgchart_table.py` 표 기반 조직도 / 샘플 JSON·md·hwpx
- 재현: 기존 `hwpx_generator.py`를 같은 폴더에 두고 `python build.py profile_test.json sample_input.md out.hwpx`

## 부록 B. 타 AI용 생성 지시문 초안(prompt.txt, outline)
```
아래 규칙으로 보고서 본문만 텍스트로 작성. 서식 설명·코드블록 금지.
줄머리 마커: "# "=장, "## "=절, "□ "=주제, "○ "=주요, "- "=설명, "· "=세부, "※ "=참고. 마커 뒤 공백 1칸.
Ⅰ. 1. 같은 번호와 □○-· 기호는 마커 외에 본문에 쓰지 말 것.
절 아래 □ 2개 이상, □ 아래 ○ 2개 이상, ○ 아래 - 2개 이상.
한 항목 한 줄, 단문은 온점 생략, 두 문장 이상이면 온점. 경어체 금지.
표는 | 구분 | 값 | 형식, 앞뒤 빈 줄.
조직도·체계도는 :::diagram type=org 와 ::: 사이에 2칸 들여쓰기 트리로, 절차도는 :::diagram type=flow 안에 "A → B → C" 한 줄로.
확인되지 않은 수치·출처는 쓰지 말고 [확인 필요]로 표시.
```
