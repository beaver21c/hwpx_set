"""HWPUNIT 변환 헬퍼."""

from __future__ import annotations

PT = 100          # 1pt = 100 HWPUNIT
MM = 283.47       # 1mm ≈ 283.47 HWPUNIT (A4 기준 59528/210)


def mm(value: float) -> int:
    return round(float(value) * MM)


def pt(value: float) -> int:
    return round(float(value) * PT)
