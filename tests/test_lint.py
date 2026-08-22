from hwpx_studio.lint import has_blocking, lint_items
from hwpx_studio.parser import parse_text


def codes(issues):
    return [i.code for i in issues]


def test_balance_rule(policy):
    r = parse_text("## 절\n□ 하나\n○ 유일\n", policy)
    issues = lint_items(r.items, policy, r.line_of, r.warnings)
    assert "balance" in codes(issues)


def test_period_policy(policy):
    r = parse_text("○ 단문인데 온점이 있다.\n", policy)
    assert "period" in codes(lint_items(r.items, policy, r.line_of))


def test_title_is_exempt_from_period_rule(narrative):
    r = parse_text("# 제목\n본문이다.\n", narrative)
    issues = lint_items(r.items, narrative, r.line_of)
    assert "period" not in codes(issues)


def test_stray_marker_detected_only_as_token(policy):
    dirty = parse_text("○ 항목 □ 잘못 쓴 기호\n", policy)
    clean = parse_text("○ 계획 수립·예산 편성을 담당\n", policy)
    assert "symbol" in codes(lint_items(dirty.items, policy, dirty.line_of))
    assert "symbol" not in codes(lint_items(clean.items, policy, clean.line_of))


def test_table_needs_blank_lines(policy):
    r = parse_text("○ 항목\n| 구분 | 값 |\n| 가 | 1 |\n○ 다음\n", policy)
    issues = lint_items(r.items, policy, r.line_of)
    assert "spacing" in codes(issues)


def test_strict_blocks_on_warnings(policy):
    r = parse_text("## 절\n□ 하나\n○ 유일\n", policy)
    issues = lint_items(r.items, policy, r.line_of)
    assert has_blocking(issues, strict=True)
    assert not has_blocking(issues, strict=False)
