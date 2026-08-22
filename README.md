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

### 다른 AI(ChatGPT·Gemini 등)로 본문만 받기

```bash
hwpx-studio export-skill policy-default -o ./my-skill
cat ./my-skill/prompt.txt        # 그대로 붙여넣으면 규칙에 맞는 본문이 나온다
```

## 할 수 있는 일

| 명령 | 하는 일 |
|---|---|
| `build` | 마커 텍스트 → hwpx (검사 후 생성, `--preview`로 HTML 동시 생성) |
| `extract` | 기존 hwpx → 프로파일 JSON + 근거 리포트 |
| `init` | 프로파일 새로 만들기(내장 프로파일 기준) |
| `lint` | 본문 규칙 검사(계층 균형·온점·기호·빈 줄) |
| `preview` | hwpx → HTML 근사 미리보기 |
| `diagram` | 도식만 단독 생성 (`"대표 > 기획부, 운영부"`) |
| `export-skill` | 프로파일 → 에이전트 스킬 폴더(SKILL.md + 빌드 스크립트 + 지시문) |

### 본문 예시

```
# 사업 추진 현황
## 추진 개요
□ 추진 배경 및 목적
○ 제도 개선 요구가 지속 제기되어 개선 방안을 마련
- 기존 절차의 처리 기간이 길어 이용자 불편이 누적
※ 세부 내용은 별도 자료로 정리

| 구분 | 목표 | 실적 |
|---|---|---|
| 처리 기간 | 14일 | 11일 |

:::diagram type=org title="추진 체계"
대표
  기획부
  운영부
:::
```

- 마커는 프로파일에서 바꿀 수 있고, 레벨 개수도 자유롭다
- `Ⅰ.` `1.` 같은 번호는 도구가 붙인다
- 자세한 규칙: `docs/writing-guide.md`, 도식: `docs/diagram-guide.md`

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
- **추정이므로 자동 확정하지 않는다.** 리포트에 클러스터별 빈도·접두 후보·근거를 남기니
  확인 후 사용할 것

## 확인된 것 / 확인 안 된 것

| 항목 | 상태 |
|---|---|
| 기존 생성기와 서식 패리티(11개 스타일 전 항목 일치) | 확인 (`tests/test_parity.py`) |
| 프로파일 주입 → 생성 → 재추출 왕복 일치 | 확인 (`tests/test_roundtrip.py`) |
| 스타일 미사용 문서의 레벨 복원 | 확인(합성 데이터) |
| 도식 표의 XML 구조·연결선 배치 | 확인 (`tests/test_diagram.py`) |
| 한글 화면에서 한 변 테두리 연결선 표시 | 확인(한글 모바일 뷰어) — `prototypes/README.md` |
| 한글로 직접 작성한 실제 문서의 추출 정확도 | 미확인(검증용 파일 필요) |
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

- `docs/writing-guide.md` — 본문 작성법
- `docs/diagram-guide.md` — 도식 작성법
- `docs/profile-spec.md` — 프로파일 JSON 규격
- `docs/spec.md` — 설계 명세(원안)
