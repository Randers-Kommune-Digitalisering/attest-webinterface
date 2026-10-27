"""Shared pytest fixtures."""

import pytest
from flask import Flask
from flask.testing import FlaskClient

from backend.src.main import create_app
from backend.src.utils.config import DevConfig


class TestConfig(DevConfig):
    TESTING = True
    DISABLE_KEYCLOAK = True
    SECRET_KEY = "test-secret"


@pytest.fixture()
def app() -> Flask:
    return create_app(config_object=TestConfig)


@pytest.fixture()
def client(app: Flask) -> FlaskClient:
    return app.test_client()
