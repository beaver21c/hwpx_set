# hwpx-studio

한국어 개조식·서술식 보고서를 **한글 문서(.hwpx)** 로 만들고, 반대로 **기존 hwpx의
서식을 읽어** 재사용 가능한 서식 프로파일로 되돌리는 도구.

한글 프로그램 없이 동작한다. 본문은 마커가 붙은 평범한 텍스트라서 어떤 AI로도,
사람이 직접이라도 쓸 수 있다.

```
서식(프로파일 JSON)  ─┐
                      ├─→  엔진  ─→  보고서.hwpx
본문(마커 텍스트)    ─┘

기존.hwpx  ─→  서식 추출  ─→  프로파일 JSON (+ 근거 리포트)
```

## 도식·조직도를 표로 옮기고 싶다면

문서·웹에 있는 조직도, 추진체계도, 절차도를 **한글에서 편집 가능한 표**로 만드는 길은
넷이다. 아래로 갈수록 설치가 필요하고, 대신 할 수 있는 게 는다.

| 어떻게 | 무엇이 필요한가 | 이럴 때 |
|---|---|---|
| **웹 앱**의 *도식 가져오기* 칸에 붙여 넣기 | 브라우저만 | Mermaid·SVG를 그대로 가진 경우 (가장 빠름) |
| **AI에게 받아쓰게** 한 뒤 웹 앱 본문에 붙여 넣기 | 브라우저 + 아무 AI | 원본이 **그림·캡처**뿐인 경우 |
| **Actions → 도식 가져오기** | GitHub 계정 | 저장소에 올려 둔 파일로 만들 때 |
| `hwpx-studio capture` | 파이썬 | 여러 개를 한꺼번에, 스크립트로 |

```bash
hwpx-studio capture examples/capture/org.mmd --title "위원회 구성" --hwpx 조직도.hwpx
```

그림밖에 없을 때는 AI에게 이렇게 시킨다 — 결과를 본문에 붙여 넣으면 된다.

> 이 조직도를 아래 형식으로 옮겨 줘. 2칸 들여쓰기가 한 단계 아래고,
> 상자 색은 `{fill=#RRGGBB color=#RRGGBB}`로 함께 적어 줘.
> ```
> :::diagram type=org title="조직 체계"
> 대표 {fill=#C00000 color=#FFFFFF}
>   기획부 {fill=#2E75B6 color=#FFFFFF}
>   운영부
> :::
> ```

자세한 건 `docs/diagram-guide.md`. 어디까지 닮게 만들 수 있고 무엇이 안 되는지는
`docs/diagram-capture-review.md`에 정리해 두었다.

## 3분 시작

### Claude Code / 로컬 Python

```bash
pip install -e .                       # 또는 pip install hwpx-studio

hwpx-studio build examples/input_outline.md -p policy-default -o 보고서.hwpx
hwpx-studio preview 보고서.hwpx -o preview.html      # HTML 근사 미리보기
```

### Colab (무료)

```python
!pip install -q hwpx-studio
%%writefile input.md
# 사업 추진 현황
## 추진 개요
□ 추진 배경
○ 개선 요구가 지속 제기됨
```
```python
!hwpx-studio build input.md -p policy-default -o 보고서.hwpx
from google.colab import files; files.download('보고서.hwpx')
```

`notebooks/colab_quickstart.ipynb`에 그대로 실행 가능한 노트북이 있다.

### 웹 앱 (설치 없이, 브라우저에서)

파이썬도 GitHub 계정도 필요 없다. 페이지를 열어 본문을 붙여 넣고 버튼을 누르면
`.hwpx` 파일이 바로 내려받아진다.

- **웹 페이지**: `main`에 올라가면 GitHub Pages로 자동 배포된다. 주소는
  `https://<사용자>.github.io/<저장소>/`
  단, **최초 1회** 저장소 Settings → Pages → Source를 `GitHub Actions`로 바꿔야 한다
  (워크플로 토큰으로는 Pages를 켤 수 없다)
- **단일 파일**: `python tools/build_standalone.py` → `dist/hwpx-studio.html` 한 개.
  이메일로 보내거나 USB에 넣어 두고 인터넷 없이 열어도 그대로 동작한다
  (CI의 `웹앱-단일파일` 아티팩트로도 받을 수 있다)

변환은 **브라우저 안에서만** 일어난다. 입력한 글은 어디로도 전송되지 않는다.

| 되는 것 | 안 되는 것 |
|---|---|
| 레벨 문단·자동 번호, 표, 조직도·절차도·매트릭스·전략체계도, 상자별 색 지정, **도식 가져오기(Mermaid·SVG)**, 본문 검사, 내장 서식 3종 | 그림 삽입, 이미지 도식(표로 대체), 기존 문서 서식 추출 |

브라우저 엔진(`docs/js/hwpx-studio.js`)은 파이썬 엔진을 이식한 것이다. 두 엔진이 같은
결과를 내는지 CI에서 매번 대조한다(`tools/compare_js_python.py`).

### GitHub에서 바로 실행 (설치 없이)

파이썬을 깔지 않고 GitHub 웹 화면에서 문서를 만들 수 있다. 셋 다 결과물은 실행 기록 아래
**Artifacts**에서 내려받는다.

| 방법 | 어디서 | 쓸 때 |
|---|---|---|
| **이슈 폼** | Issues → New issue → *보고서 생성 요청* | 본문을 여러 줄 그대로 붙여 넣을 때 (권장) |
| **Actions 폼** | Actions → *보고서 생성* → Run workflow | 저장소에 올려 둔 입력 파일로 만들 때 |
| **도식 가져오기** | Actions → *도식 가져오기* → Run workflow | Mermaid·SVG 파일을 도식 표로 옮길 때 |
| **서식 추출** | Actions → *서식 추출* → Run workflow | 기존 한글 문서에서 프로파일을 뽑을 때 |

- 이슈 폼: 본문 칸에 마커 텍스트를 붙여 넣고 프로파일·파일 이름·옵션을 고르면 자동으로
  생성되고, 결과 링크가 이슈에 댓글로 달린다. 본문을 고쳐 이슈를 수정하면 다시 만든다
  (저장소 구성원이 연 이슈에만 반응한다)
- Actions 폼: 입력 파일 경로·프로파일·도식 렌더 방식·`--strict` 여부를 고른다
- 도식 가져오기: 원본(`.mmd`·`.svg`·`.html`) 경로를 넣으면 도식 블록과 hwpx가 나오고,
  **읽은 블록이 실행 요약 화면에 그대로 표시**된다
- 서식 추출: 기준 문서(`.hwpx`)를 저장소에 올린 뒤 경로를 넣으면, 프로파일 JSON과
  **근거 리포트가 실행 요약 화면에 그대로 표시**된다
- 워크플로 폼은 파일이 기본 브랜치(`main`)에 있어야 Actions 탭에 나타난다(GitHub 제약)

CI(`.github/workflows/ci.yml`)는 푸시·PR마다 Python 3.10/3.12/3.13에서 테스트를 돌리고,
예제 3종과 조직도를 실제로 생성해 Artifacts로 올린다.

### 에이전트 스킬로 쓰기 (Claude Code 등)

보고서를 쓰다가 도식이 필요할 때 바로 표로 그려 넣도록, 스킬 폴더를 통째로 만들어 준다.

```bash
hwpx-studio export-skill policy-default -o ~/.claude/skills/hwpx-report-studio --standalone
```

- `SKILL.md` — 마커 규칙 + **도식 네 가지(조직도·절차도·격자·전략체계도)**, 색 지정,
  상자가 많을 때의 배치, 기존 도식을 옮기는 방법까지
- `scripts/build.py` — 마커 텍스트 → hwpx
- `scripts/capture.py` — Mermaid·SVG·HTML 도식 → 도식 블록(+hwpx)
- `profile.json` — 서식. `--standalone`이면 엔진까지 동봉되어 `pip install` 없이 돈다
  (`python-hwpx`만 있으면 된다)
- `prompt.txt` — 다른 AI(ChatGPT·Gemini 등)에 그대로 붙여넣을 지시문

**그림·캡처뿐인 도식**은 도구가 읽지 못한다. 그 경우 SKILL.md가 에이전트에게
"직접 그림을 보고 형식대로 받아쓴 뒤 사용자 확인을 받으라"고 지시한다.

집필 규칙까지 얹은 스킬(KIHASA 작업 절차·머릿글 규칙 포함)은 `skills/`에 있다.

```bash
python skills/build.py -o ~/.claude/skills      # 조립 + 설치
```

`skills/hwpx-report-studio/`의 손으로 쓴 SKILL.md·reference를 내보낸 뼈대 위에 덮어씌운다.
엔진이 바뀌어도 다시 만들면 되고, 집필 규칙은 사람이 관리한다.

## 할 수 있는 일

| 명령 | 하는 일 |
|---|---|
| `build` | 마커 텍스트 → hwpx (검사 후 생성, `--preview`로 HTML 동시 생성) |
| `extract` | 기존 hwpx → 프로파일 JSON + 근거 리포트 |
| `init` | 프로파일 새로 만들기(내장 프로파일 기준) |
| `lint` | 본문 규칙 검사(계층 균형·온점·기호·머릿글·각주 번호 자리·빈 줄) |
| `preview` | hwpx → HTML 근사 미리보기 |
| `diagram` | 도식만 단독 생성 (`"대표 > 기획부, 운영부"`) |
| `capture` | 남의 도식(Mermaid·SVG·HTML) → 도식 블록 (`--hwpx`로 문서까지) |
| `export-skill` | 프로파일 → 에이전트 스킬 폴더(SKILL.md + 빌드 스크립트 + 지시문) |

### 본문 예시

```
# 사업 추진 현황
## 추진 개요
□ 추진 배경 및 목적
○ 제도 개선 요구가 지속 제기되어 개선 방안을 마련[^1]
- 기존 절차의 처리 기간이 길어 이용자 불편이 누적
※ 세부 내용은 별도 자료로 정리

[^1]: 국무조정실(2024), 「규제혁신 추진계획」.

| 구분 | 목표 | 실적 |
|---|---|---|
| 처리 기간 | 14일 | 11일 |

:::diagram type=org title="추진 체계"
대표
  기획부
  운영부
:::
```

- 각주는 `[^1]`을 근거가 되는 말 뒤에 붙이고 내용은 `[^1]: …` 줄로 적는다. **8pt 회색**으로 들어가고 번호는 한글이 매긴다
- 도식 상자에 색을 줄 수 있다: `대표 {fill=#C00000 color=#FFFFFF}`, 점선 연결선은 `{link=dash}`
- 마커는 프로파일에서 바꿀 수 있고, 레벨 개수도 자유롭다
- `Ⅰ.` `1.` 같은 번호는 도구가 붙인다
- 자세한 규칙: `docs/writing-guide.md`, 도식: `docs/diagram-guide.md`, 각주: `docs/footnote-guide.md`

## 내장 프로파일

| 이름 | 구성 |
|---|---|
| `policy-default` | Ⅰ./1./□/○/-/·/※ 7레벨 (기존 생성기와 동일 서식) |
| `gov-3level` | Ⅰ./1./□/○/- 5레벨, 흑백 |
| `narrative` | 서술식(제목 + 본문 문단, 첫 줄 들여쓰기) |

프로파일 JSON은 `hwpx_studio/profiles/`에 있다(설치본에 함께 들어간다). 규격: `docs/profile-spec.md`

## 서식 읽기(extract)

```bash
hwpx-studio extract 기준문서.hwpx -o my.json --report report.md
```

- `header.xml`의 charPr/paraPr/style과 본문 첫 글자 패턴을 함께 보고 레벨을 추정한다
- 스타일을 쓰지 않은 문서(styleIDRef가 모두 0)는 `(paraPr, charPr)` 조합으로 묶는다
- **제목 상자**(1행짜리 표)에 든 제목도 레벨로 잡는다. 여러 행짜리 데이터 표의 셀 스타일은
  레벨에서 빼고 `table.top`/`table.mid`로 분리한다
- 굵기를 `bold` 속성 대신 **글꼴 이름**(`… Bold` / `… Light`)으로 구분한 문서도 역할을 맞춘다
- 쪽번호·셀 번호처럼 한두 글자짜리 문단이 모인 클러스터는 레벨에서 빼고 리포트에 남긴다
- 한글 바이너리(`.hwp`)는 읽지 못한다 → 한글에서 [다른 이름으로 저장] → HWPX 문서로 저장할 것
- **추정이므로 자동 확정하지 않는다.** 리포트에 클러스터별 빈도·접두 후보·근거를 남기니
  확인 후 사용할 것

## 확인된 것 / 확인 안 된 것

| 항목 | 상태 |
|---|---|
| 기존 생성기와 서식 패리티(11개 스타일 전 항목 일치) | 확인 (`tests/test_parity.py`) |
| 프로파일 주입 → 생성 → 재추출 왕복 일치 | 확인 (`tests/test_roundtrip.py`) |
| 스타일 미사용 문서의 레벨 복원 | 확인(합성 데이터) |
| 도식 표의 XML 구조·연결선 배치 | 확인 (`tests/test_diagram.py`) |
| 노드별 배경색·글자색·테두리색·점선 연결선 | 확인 (`tests/test_diagram.py`, 두 엔진 대조) |
| 상자가 많을 때 세로 목록형 자동 전환(폭이 늘지 않음) | 확인 (`tests/test_diagram.py`, 두 엔진 대조) |
| 전략체계도(미션·비전·핵심가치·전략과제 단 배치) | 확인 (`tests/test_diagram.py`, 두 엔진 대조) |
| Mermaid·SVG·HTML 도식 읽기(구조·색·점선) | 확인 (`tests/test_capture.py`) |
| 각주(쪽 아래·자동 번호·8pt 회색) | 확인 (`tests/test_footnote.py`, 표준 판독기로 재확인 + 두 엔진 대조) |
| 각주 번호 자리 검사(붙여쓰기·마침표·인용부호·제목) | 확인 (`tests/test_footnote.py`) |
| 미주 | 미구현 — `docs/footnote-guide.md` §5 |
| 그림(PNG·스캔)에서 도식 읽기 | 미구현 — AI에게 받아쓰게 하는 우회는 `docs/diagram-guide.md` §4 |
| 한글 화면에서 한 변 테두리 연결선 표시 | 확인(한글 모바일 뷰어) — `prototypes/README.md` |
| 한글로 직접 작성한 실제 문서의 추출 정확도 | 확인(1건) — 7레벨 전부 복원, 아래 참조 |
| 머리말·쪽번호 | 미구현 |

## 개발

```bash
pip install -e ".[dev,image]"
pytest -q

# 기존 생성기와의 패리티까지 검사하려면
HWPX_LEGACY_GENERATOR=/path/to/hwpx_generator.py pytest tests/test_parity.py
```

의존성은 `python-hwpx>=6.2,<7`(Apache-2.0)이며, 이미지 도식에만 matplotlib이 추가로 필요하다.

## 문서

- `docs/index.html` — 웹 앱(브라우저 변환기)
- `docs/writing-guide.md` — 본문 작성법
- `docs/diagram-guide.md` — 도식 작성법
- `docs/footnote-guide.md` — 각주 다는 법과 번호 자리
- `docs/diagram-capture-review.md` — 문서·웹 도식을 인식해 표로 재현하는 도구 검토
- `docs/profile-spec.md` — 프로파일 JSON 규격
- `skills/hwpx-report-studio/` — 에이전트 스킬(집필 규칙 + 도식)
- `docs/spec.md` — 설계 명세(원안)
