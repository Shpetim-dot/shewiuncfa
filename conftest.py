import pytest

from app import cfa_core as platform


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    platform._hits.clear()
    yield
    platform._hits.clear()
