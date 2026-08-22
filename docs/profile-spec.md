# 프로파일(JSON) 규격 v1

`schema`는 `hwpx-studio.profile.v1`이다. **부분 JSON을 허용**한다. 빠진 항목은 기본값과
병합되므로, 바꿀 값만 적어도 된다.

```bash
hwpx-studio init my.json --from policy-default   # 기준 프로파일 복사
hwpx-studio extract 기존문서.hwpx -o my.json      # 기존 hwpx에서 역생성
```

## 1. 최상위

| 키 | 뜻 |
|---|---|
| `name` | 프로파일 이름(문서에는 들어가지 않음) |
| `mode` | `outline`(개조식) / `narrative`(서술식) |
| `fonts` | `bold`, `light`, `fallback` — 한글 글꼴 이름. 미설치 글꼴은 뷰어가 대체 표시 |
| `page.margin_mm` | `left/right/top/bottom/header/footer` (mm) |
| `header_footer` | `header_text`, `page_number` (연동 예정, 현재 미적용) |
| `levels` | 레벨 목록. **순서 = 깊이, 개수 가변** |
| `body` | 서술식 본문 문단 서식 |
| `table` | 표 서식 + 표 셀 스타일 3종 |
| `image` | 그림 기본 폭·글자처럼 취급 |
| `diagram` | 도식 색·크기·렌더 방식 |
| `rules` | 검사 규칙(`min_children`, `period_policy`) |
| `signature` | 문서 끝 서명 문단(기본 빈 값 = 삽입 안 함) |

## 2. levels[]

| 키 | 뜻 | 예 |
|---|---|---|
| `key` | 내부 식별자. 본문·규칙에서 이 이름으로 참조 | `L1` |
| `name` | 한글 스타일명(한글 스타일 목록에 보임) | `네모` |
| `marker` | **입력**에서 이 레벨을 뜻하는 줄머리 | `□` |
| `prefix` | **출력**에 붙는 접두어. `AUTO_*`는 자동 번호 | `"□ "`, `AUTO_ROMAN` |
| `size_pt` | 글자 크기 | `14` |
| `bold` | 굵게 | `true` |
| `font` | `bold` / `light` (fonts의 어느 글꼴을 쓸지) | `bold` |
| `color` | 글자색 `#RRGGBB` | `#4c4c4c` |
| `left_pt` | 왼쪽 여백 | `10` |
| `indent_pt` | 내어쓰기(0이면 없음) | `15` |
| `spacing_below_pt` | 문단 아래 간격 | `3` |
| `line_spacing` | 줄 간격(%) | `170` |
| `align` | `JUSTIFY/LEFT/RIGHT/CENTER/DISTRIBUTE/DIVISION` | `JUSTIFY` |

`marker`를 비워 두면 `prefix`에서 유추한다(`"□ "` → `□`).

### 자동 번호(prefix)

| 값 | 출력 |
|---|---|
| `AUTO_ROMAN` | Ⅰ. Ⅱ. Ⅲ. |
| `AUTO_NUM` | 1. 2. 3. |
| `AUTO_ALPHA` | A. B. C. |
| `AUTO_HANGUL` | 가. 나. 다. |
| `AUTO_CIRCLED` | ① ② ③ |

상위 레벨의 번호가 올라가면 하위 레벨 번호는 1부터 다시 시작한다.

> 번호는 **텍스트로 삽입**한다(한글 번호매기기 기능 미사용). 한글에서 항목을 나중에
> 끼워 넣으면 번호가 자동으로 갱신되지 않는다.

## 3. table

| 키 | 뜻 |
|---|---|
| `border_color` / `header_bg` | 테두리색 / 머리행 배경색 |
| `width_mm` | 표 폭(0이면 자동) |
| `cell_margin_mm` | 셀 안쪽 여백 |
| `treat_as_char` | 글자처럼 취급(true) / 자리 차지(false) |
| `anchor_level` | 표·그림을 감싸는 문단에 적용할 레벨 key. 비우면 마지막 본문 레벨 |
| `top` / `mid` / `left` | 머리행 / 본문행 / 왼쪽정렬용 셀 스타일 |

## 4. diagram

`docs/diagram-guide.md` §3 참조.

## 5. rules

| 키 | 뜻 |
|---|---|
| `min_children` | `{"L1": 2}` — L1 아래 하위 항목 2개 이상 권장. lint의 `balance` 검사 |
| `period_policy` | `single_sentence_no_period`(기본) / `always_period` / `never_period` / `off` |

## 6. 검증

```python
from hwpx_studio.profile import load_profile, validate_profile
validate_profile(load_profile("my.json"))   # [] 이면 통과
```

검증이 잡는 것: `mode` 값, 레벨 `key` 중복, `marker` 중복, 크기·글꼴·정렬 값,
색상 형식, `anchor_level`·`min_children`이 없는 레벨을 가리키는 경우.

## 7. ID 배정 방식

프로파일에는 한글 내부 ID(charPr/paraPr/style)가 없다. 엔진이 템플릿의 `itemCnt`를
읽어 **비어 있는 번호부터 순서대로** 배정하므로, 레벨을 늘리거나 줄여도 ID 충돌이
생기지 않는다.
