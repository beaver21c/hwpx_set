# 노드별 색 지정 도식

□ 조직도: 상자마다 색을 다르게

:::diagram type=org title="색을 지정한 조직 체계"
대표 {fill=#C00000 color=#FFFFFF}
  기획부 {fill=#2E75B6 color=#FFFFFF}
    기획팀
  운영부 {fill=#70AD47 color=#FFFFFF}
  감사실 {fill=#FFF2CC border=#BF8F00 link=dash link_color=#808080}
:::

□ 절차도: 마지막 단계만 강조

:::diagram type=flow title="처리 절차"
접수 → 검토 → 심의 → 통보 {fill=#C00000 color=#FFFFFF}
:::

□ 블록 전체 색 바꾸기

:::diagram type=org box_fill=#F2F2F2 root_fill=#404040 line_color=#808080 line_style=dash title="흑백 체계도"
총괄
  가부서
  나부서
:::

□ 매트릭스: 칸별 강조

:::diagram type=matrix title="역할 분담"
| | 중앙 | 지방 |
| 기획 | 본부 {fill=#FFF2CC} | 지역본부 |
| 집행 | 사업단 | 현장사무소 {fill=#DEEBF7} |
:::
