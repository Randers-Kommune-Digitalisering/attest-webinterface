"""Tests for application-level endpoints in main."""

from unittest.mock import MagicMock, patch

import pytest
from flask import Flask, redirect
from flask.testing import FlaskClient

from backend.src.main import REQUIRED_ROLE, create_app, _minimal_userinfo
from backend.src.utils.config import DevConfig, ProdConfig


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
    with patch("backend.src.main.OAuth") as oauth_class:
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

    client = create_app(config_object=Cfg).test_client()

    response = client.get("/api/userinfo")

    assert response.status_code == 200
    assert REQUIRED_ROLE in response.get_json()["roles"]


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
