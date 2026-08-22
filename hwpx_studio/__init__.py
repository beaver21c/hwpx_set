"""hwpx-studio: 서식 프로파일 기반 한국어 보고서 hwpx 생성·서식 추출 도구."""

from .profile import (  # noqa: F401
    DEFAULT_PROFILE,
    SCHEMA_ID,
    list_builtin_profiles,
    load_profile,
    merge_profile,
    save_profile,
    validate_profile,
)

__version__ = "0.1.0"


def build(profile, contents, out_path=None):
    """프로파일 + 콘텐츠 → hwpx (engine.build_document 지연 임포트)."""
    from .engine import build_document

    return build_document(profile, contents, out_path)


def extract(source, **kwargs):
    """hwpx → 프로파일 (extractor.extract_profile 지연 임포트)."""
    from .extractor import extract_profile

    return extract_profile(source, **kwargs)
