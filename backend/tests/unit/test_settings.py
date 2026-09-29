import pytest
from app.config import Settings
from pydantic import ValidationError


def test_live_providers_are_disabled_by_default() -> None:
    settings = Settings(
        database_url="postgresql+psycopg://test:test@localhost:5432/test",
        redis_url="redis://localhost:6379/0",
        jwt_secret="test-secret-that-is-at-least-32-characters",
    )
    assert settings.allow_live_providers is False


def test_csv_list_settings_are_parsed_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://test:test@localhost:5432/test")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("JWT_SECRET", "test-secret-that-is-at-least-32-characters")
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000")
    monkeypatch.setenv("ENABLED_PROVIDERS", "fake,fixture")
    settings = Settings()
    assert settings.cors_origins == ["http://localhost:5173", "http://localhost:3000"]
    assert settings.enabled_providers == ["fake", "fixture"]


def test_required_urls_fail_fast(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("REDIS_URL", raising=False)
    with pytest.raises(ValidationError):
        Settings(jwt_secret="test-secret-that-is-at-least-32-characters")
