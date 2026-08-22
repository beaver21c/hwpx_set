import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402

from hwpx_studio.profile import load_profile  # noqa: E402


@pytest.fixture
def policy():
    return load_profile("policy-default")


@pytest.fixture
def narrative():
    return load_profile("narrative")


@pytest.fixture
def repo_root():
    return ROOT
