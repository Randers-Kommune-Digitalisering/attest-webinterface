import pytest

from utils.config import DevConfig, ProdConfig, get_config_class_path


def test_plaintext_database_exception_is_development_only() -> None:
    assert DevConfig.ALLOW_UNENCRYPTED_DB_CONNECTIONS is True
    assert ProdConfig.ALLOW_UNENCRYPTED_DB_CONNECTIONS is False


@pytest.mark.parametrize(
    ("env", "expected"),
    [
        ("prod", "utils.config.ProdConfig"),
        ("PROD", "utils.config.ProdConfig"),
        ("dev", "utils.config.DevConfig"),
    ],
)
def test_get_config_class_path(monkeypatch: pytest.MonkeyPatch, env: str, expected: str) -> None:
    monkeypatch.setenv("FLASK_ENV", env)

    assert get_config_class_path() == expected


def test_get_config_class_path_rejects_invalid_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FLASK_ENV", "staging")

    with pytest.raises(ValueError, match="staging"):
        get_config_class_path()
