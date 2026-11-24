"""Tests for application-level endpoints in main."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from flask import Flask, redirect
from flask.testing import FlaskClient

from main import REQUIRED_ROLE, _minimal_userinfo, create_app
from utils.config import DevConfig, ProdConfig
from utils.database import DatabaseConfigurationError, DatabaseManager


class DummyAuthNotAllowedConfig(ProdConfig):
    DISABLE_KEYCLOAK = True


class KeycloakConfig(ProdConfig):
    DISABLE_KEYCLOAK = False
    SECRET_KEY = "test-secret"
    SESSION_COOKIE_SECURE = False
    KEYCLOAK_URL = "https://keycloak.test/"
    KEYCLOAK_REALM = "realm"
    KEYCLOAK_CLIENT_ID = "client"
    KEYCLOAK_CLIENT_SECRET = "client-secret"
    ATTEST_DB_TYPE = "postgres"
    ATTEST_DB_HOST = "db.example.invalid"
    ATTEST_DB_PORT = 5432
    ATTEST_DB_NAME = "attest_test"
    ATTEST_DB_USERNAME = "attest_test"
    ATTEST_DB_PASSWORD = "test-password"


class MissingSecretKeyConfig(KeycloakConfig):
    SECRET_KEY = "CHANGE_ME"


class MissingKeycloakConfig(KeycloakConfig):
    KEYCLOAK_URL = ""


def test_healthz(client: FlaskClient) -> None:
    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.get_json()["status"] == "ok"


def test_minimal_userinfo_returns_empty_dict_for_invalid_input() -> None:
    assert _minimal_userinfo(None, "client") == {}


def test_minimal_userinfo_keeps_only_needed_fields() -> None:
    userinfo = {
        "name": "Test Testsen",
        "email": "test@test.dk",
        "phone_number": "12345678",
        "resource_access": {"client": {"roles": ["attest-admin"]}},
    }

    assert _minimal_userinfo(userinfo, "client") == {
        "name": "Test Testsen",
        "email": "test@test.dk",
        "roles": ["attest-admin"],
    }


def test_minimal_userinfo_ignores_invalid_roles() -> None:
    userinfo = {"resource_access": {"client": {"roles": "attest-admin"}}}

    assert _minimal_userinfo(userinfo, "client") == {
        "name": None,
        "email": None,
        "roles": [],
    }


@pytest.fixture()
def keycloak_app() -> tuple[Flask, MagicMock]:
    with patch("main.OAuth") as oauth_class, patch("main.DatabaseManager"):
        app = create_app(config_object=KeycloakConfig)

    app.config["TESTING"] = True
    return app, oauth_class.return_value


def test_dummy_auth_not_allowed_raises() -> None:
    with pytest.raises(RuntimeError, match="DISABLE_KEYCLOAK"):
        create_app(config_object=DummyAuthNotAllowedConfig)


def test_dummy_userinfo_returns_dummy_user() -> None:
    class Cfg(DevConfig):
        DISABLE_KEYCLOAK = True
        SECRET_KEY = "test-secret"
        ATTEST_DB_TYPE = "postgres"
        ATTEST_DB_HOST = "db.example.invalid"
        ATTEST_DB_PORT = 5432
        ATTEST_DB_NAME = "attest_test"
        ATTEST_DB_USERNAME = "attest_test"
        ATTEST_DB_PASSWORD = "test-password"

    with patch("main.DatabaseManager"):
        client = create_app(config_object=Cfg).test_client()

    response = client.get("/api/userinfo")

    assert response.status_code == 200
    assert REQUIRED_ROLE in response.get_json()["roles"]


def test_database_manager_uses_config_without_creating_schema() -> None:
    with patch("main.DatabaseManager.from_config") as database_manager_factory:
        app = create_app(config_object=KeycloakConfig)

    database_manager_factory.assert_called_once_with(
        app.config,
        profile_name="attest_db",
        prefix="ATTEST_DB",
    )
    assert app.extensions["database_manager"] is database_manager_factory.return_value


def test_database_manager_requires_connection_settings() -> None:
    config = {
        "ATTEST_DB_TYPE": "postgres",
        "ATTEST_DB_HOST": "",
        "ATTEST_DB_NAME": "attest_test",
        "ATTEST_DB_USERNAME": "attest_test",
        "ATTEST_DB_PASSWORD": "test-password",
    }

    with pytest.raises(DatabaseConfigurationError, match="ATTEST_DB_HOST"):
        DatabaseManager.from_config(
            config,
            profile_name="attest_db",
            prefix="ATTEST_DB",
        )


def test_database_manager_rejects_invalid_port() -> None:
    config = {
        "ATTEST_DB_TYPE": "postgres",
        "ATTEST_DB_HOST": "db.example.invalid",
        "ATTEST_DB_NAME": "attest_test",
        "ATTEST_DB_USERNAME": "attest_test",
        "ATTEST_DB_PASSWORD": "test-password",
        "ATTEST_DB_PORT": "invalid",
    }

    with pytest.raises(DatabaseConfigurationError, match="ATTEST_DB_PORT"):
        DatabaseManager.from_config(
            config,
            profile_name="attest_db",
            prefix="ATTEST_DB",
        )


def test_database_manager_rejects_unsupported_database_type() -> None:
    config = {
        "ATTEST_DB_TYPE": "sqlite",
        "ATTEST_DB_HOST": "db.example.invalid",
        "ATTEST_DB_NAME": "attest_test",
        "ATTEST_DB_USERNAME": "attest_test",
        "ATTEST_DB_PASSWORD": "test-password",
    }

    with pytest.raises(DatabaseConfigurationError, match="ATTEST_DB_TYPE"):
        DatabaseManager.from_config(
            config,
            profile_name="attest_db",
            prefix="ATTEST_DB",
        )


def test_database_manager_rejects_out_of_range_port() -> None:
    config = {
        "ATTEST_DB_TYPE": "postgres",
        "ATTEST_DB_HOST": "db.example.invalid",
        "ATTEST_DB_NAME": "attest_test",
        "ATTEST_DB_USERNAME": "attest_test",
        "ATTEST_DB_PASSWORD": "test-password",
        "ATTEST_DB_PORT": "70000",
    }

    with pytest.raises(DatabaseConfigurationError, match="ATTEST_DB_PORT"):
        DatabaseManager.from_config(
            config,
            profile_name="attest_db",
            prefix="ATTEST_DB",
        )


def test_database_manager_factory_supports_custom_prefix() -> None:
    config = {
        "REPORTING_DB_TYPE": " postgres ",
        "REPORTING_DB_HOST": " db.example.invalid ",
        "REPORTING_DB_NAME": " attest_test ",
        "REPORTING_DB_USERNAME": " attest_test ",
        "REPORTING_DB_PASSWORD": " test-password ",
        "REPORTING_DB_PORT": "5432",
    }

    with patch.object(DatabaseManager, "__init__", return_value=None) as init:
        manager = DatabaseManager.from_config(
            config,
            profile_name="reporting_db",
            prefix="REPORTING_DB_",
        )

    assert isinstance(manager, DatabaseManager)
    init.assert_called_once_with(
        profile_name="reporting_db",
        db_type="postgres",
        database="attest_test",
        username="attest_test",
        password=" test-password ",
        host="db.example.invalid",
        port=5432,
    )
    assert "base_model" not in init.call_args.kwargs


@pytest.mark.parametrize(
    ("config", "message"),
    [
        (MissingSecretKeyConfig, "SECRET_KEY"),
        (MissingKeycloakConfig, "Keycloak"),
    ],
)
def test_keycloak_confic_validation(config: type, message: str) -> None:
    with pytest.raises(RuntimeError, match=message):
        create_app(config_object=config)


def test_keycloak_rejects_unauthenticated_requests(keycloak_app: tuple[Flask, MagicMock]) -> None:
    app, _ = keycloak_app

    response = app.test_client().get("/api/orders")

    assert response.status_code == 401
    assert response.get_json() == {"success": False, "error": "Not authenticated"}


def test_keycloak_allows_public_paths(keycloak_app: tuple[Flask, MagicMock]) -> None:
    app, _ = keycloak_app

    assert app.test_client().get("/healthz").status_code == 200


def test_frontend_served_without_login(
    keycloak_app: tuple[Flask, MagicMock],
    tmp_path: Path,
) -> None:
    app, _ = keycloak_app
    app.static_folder = str(tmp_path)
    (tmp_path / "index.html").write_text("<html>Vue app</html>", encoding="utf-8")
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "app.js").write_text("Vue asset", encoding="utf-8")

    client = app.test_client()
    for route in ("/", "/orders", "/history"):
        response = client.get(route)
        assert response.status_code == 200
        assert b"Vue app" in response.data

    assert client.get("/assets/app.js").data == b"Vue asset"
    assert client.get("/assets/missing.js").status_code == 404
    assert client.get("/api/orders").status_code == 401


def test_login_redirects_to_keycloak(keycloak_app: tuple[Flask, MagicMock]) -> None:
    app, oauth = keycloak_app
    oauth.keycloak.authorize_redirect.return_value = redirect("https://keycloak.test/auth")

    response = app.test_client().get("/api/login")

    assert response.status_code == 302
    oauth.keycloak.authorize_redirect.assert_called_once()


def test_auth_stores_minimal_user_and_redirects(keycloak_app: tuple[Flask, MagicMock]) -> None:
    app, oauth = keycloak_app
    oauth.keycloak.authorize_access_token.return_value = {
        "userinfo": {
            "name": "Test Testsen",
            "email": "test@test.dk",
            "resource_access": {"client": {"roles": [REQUIRED_ROLE]}},
        },
    }
    client = app.test_client()

    response = client.get("/api/auth")

    assert response.status_code == 302
    assert response.headers["Location"] == "/"
    userinfo = client.get("/api/userinfo")
    assert userinfo.status_code == 200
    assert userinfo.get_json()["roles"] == [REQUIRED_ROLE]


def test_auth_without_required_role_is_forbidden(keycloak_app: tuple[Flask, MagicMock]) -> None:
    app, oauth = keycloak_app
    oauth.keycloak.authorize_access_token.return_value = {
        "userinfo": {"resource_access": {"client": {"roles": []}}},
    }
    client = app.test_client()

    response = client.get("/api/auth")

    assert response.status_code == 403
    assert client.get("/api/userinfo").status_code == 401
