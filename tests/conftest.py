import pytest

from app import auth as auth_mod
from app import cfa_core as platform


@pytest.fixture(autouse=True)
def _fast_password_hashing(monkeypatch):
    """Argon2 with production parameters takes ~1 s per hash; tests need speed, not security."""
    monkeypatch.setenv("CFA_ARGON2_TIME_COST", "1")
    monkeypatch.setenv("CFA_ARGON2_MEMORY_COST", "8192")
    monkeypatch.setenv("CFA_ARGON2_PARALLELISM", "1")
    auth_mod._HASHER = auth_mod._hasher()
    yield
    auth_mod._HASHER = auth_mod._hasher()


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    platform._hits.clear()
    auth_mod.reset_throttle()
    yield
    platform._hits.clear()
    auth_mod.reset_throttle()


@pytest.fixture(autouse=True)
def _isolate_auth_schema():
    """Each test gets a fresh database path, so forget which schemas were created."""
    auth_mod._ensured.clear()
    yield
    auth_mod._ensured.clear()
