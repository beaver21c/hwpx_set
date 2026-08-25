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


def test_head_pattern_flags_a_missing_prefix(policy):
    """네모의 【】, 원의 () 처럼 정해 둔 머릿글이 빠지면 알린다."""
    from hwpx_studio.lint import lint_items
    from hwpx_studio.parser import parse_text

    profile = dict(policy)
    profile["rules"] = dict(policy["rules"],
                            head_pattern={"L1": r"^【[^】]+】", "L2": r"^\([^)]+\)"})
    text = ("# 서론\n## 배경\n□ 【배경 1】 정책 수요 변화\n○ (1) 고령화 심화\n"
            "- 가\n- 나\n○ 머릿글 없는 원\n- 다\n- 라\n□ 머릿글 없는 네모\n"
            "○ (1) 가\n- 마\n- 바\n○ (2) 나\n- 사\n- 아\n")
    parsed = parse_text(text, profile)
    heads = [i for i in lint_items(parsed.items, profile, parsed.line_of, parsed.warnings)
             if i.code == "head"]
    assert len(heads) == 2
    assert "머릿글 없는 원" in heads[0].message or "머릿글 없는 네모" in heads[0].message


def test_head_pattern_is_off_by_default(policy):
    from hwpx_studio.lint import lint_items
    from hwpx_studio.parser import parse_text

    parsed = parse_text("# 서론\n## 배경\n□ 머릿글 없음\n○ 이것도\n- 가\n- 나\n"
                        "○ 저것도\n- 다\n- 라\n□ 또\n○ 가\n- 마\n- 바\n○ 나\n- 사\n- 아\n",
                        policy)
    issues = lint_items(parsed.items, policy, parsed.line_of, parsed.warnings)
    assert not [i for i in issues if i.code == "head"]


def test_bad_head_pattern_is_reported_as_a_profile_error(policy):
    from hwpx_studio.profile import validate_profile

    profile = dict(policy)
    profile["rules"] = dict(policy["rules"], head_pattern={"L1": "["})
    assert any("head_pattern" in e for e in validate_profile(profile))

    profile["rules"] = dict(policy["rules"], head_pattern={"없는레벨": "^x"})
    assert any("없는레벨" in e for e in validate_profile(profile))
