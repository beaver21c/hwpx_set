# 자료 관리 체계

□ 데이터베이스 구성

:::diagram type=db title="지원사업 DB 구성"
[회원]
  *회원ID
  이름
  생년월일
  연락처
[신청]
  *신청ID
  +회원ID
  +사업코드
  신청일
  처리상태
[사업]
  *사업코드
  사업명
  소관부처
회원 → 신청 → 사업
:::

□ 색을 준 구성

:::diagram type=db title="색 지정" width=120
[가구 {fill=#C00000 color=#FFFFFF}]
  *가구ID
  세대주명 {fill=#FFF2CC}
[급여]
  *급여ID
  +가구ID
급여 → 가구
:::
