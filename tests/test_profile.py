from hwpx_studio.profile import (
    level_by_key,
    list_builtin_profiles,
    merge_profile,
    validate_profile,
)


def test_builtin_profiles_are_valid():
    names = list_builtin_profiles()
    assert {"policy-default", "gov-3level", "narrative"} <= set(names)


def test_partial_profile_merges_defaults():
    p = merge_profile({"levels": [{"key": "L1", "prefix": "□ ", "size_pt": 14}]})
    lv = level_by_key(p, "L1")
    assert lv["marker"] == "□"                      # prefix에서 마커 유추
    assert lv["line_spacing"] == 160                # 기본값 병합
    assert p["table"]["border_color"] == "#999999"  # 미지정 절도 기본값으로 채워짐
    assert validate_profile(p) == []


def test_levels_are_variable_length(policy):
    trimmed = merge_profile({**policy, "levels": policy["levels"][:3],
                             "table": {**policy["table"], "anchor_level": "L1"},
                             "rules": {"min_children": {"title2": 2}}})
    assert len(trimmed["levels"]) == 3
    assert validate_profile(trimmed) == []


def test_validation_catches_dangling_level_reference(policy):
    trimmed = merge_profile({**policy, "levels": policy["levels"][:3]})
    errors = validate_profile(trimmed)
    assert any("anchor_level" in e for e in errors)
    assert any("min_children" in e for e in errors)


def test_validation_catches_duplicate_marker():
    p = merge_profile({"levels": [
        {"key": "A", "marker": "□", "prefix": "□ "},
        {"key": "B", "marker": "□", "prefix": "□ "},
    ]})
    errors = validate_profile(p)
    assert any("중복" in e for e in errors)


def test_validation_catches_bad_values():
    p = merge_profile({"mode": "weird", "levels": [
        {"key": "A", "size_pt": 0, "font": "heavy", "align": "MIDDLE", "color": "red"},
    ]})
    errors = validate_profile(p)
    assert len(errors) >= 4
