# 도식 예시 모음

## 조직도·체계도

□ 계층 구조는 2칸 들여쓰기로 쓴다

:::diagram type=org title="조직 체계"
대표
  기획부
    기획팀
    예산팀
  운영부
  연구부
:::

## 절차도

□ 가로 흐름

:::diagram type=flow title="처리 절차"
접수 → 검토 → 심의 → 통보
:::

□ 세로 흐름

:::diagram type=flow direction=down title="단계별 절차"
계획 수립 → 시범 적용 → 평가 → 확대
:::

## 매트릭스

□ 행·열 비교표

:::diagram type=matrix title="역할 분담"
| | 중앙 | 지방 |
| 기획 | 본부 | 지역본부 |
| 집행 | 사업단 | 현장사무소 |
:::

## 이미지 렌더

□ 화살표가 필요하거나 폭이 넘칠 때는 `render=image`

:::diagram type=org render=image title="이미지로 그린 체계도"
총괄
  가부서
  나부서
  다부서
:::
