"""Shared pytest fixtures."""

from unittest.mock import patch

import pytest
from flask import Flask
from flask.testing import FlaskClient

from utils.database import DatabaseManager

# Importing main creates the Gunicorn app, so keep tests isolated from a live DB.
with patch.object(DatabaseManager, "from_config"):
    from main import create_app

from utils.config import DevConfig


class TestConfig(DevConfig):
    TESTING = True
    DISABLE_KEYCLOAK = True
    SECRET_KEY = "test-secret"
    ATTEST_DB_TYPE = "postgres"
    ATTEST_DB_HOST = "db.example.invalid"
    ATTEST_DB_PORT = 5432
    ATTEST_DB_NAME = "attest_test"
    ATTEST_DB_USERNAME = "attest_test"
    ATTEST_DB_PASSWORD = "test-password"


@pytest.fixture()
def app() -> Flask:
    with patch("main.DatabaseManager.from_config") as database_manager_factory:
        app = create_app(config_object=TestConfig)

    app.extensions["database_manager"] = database_manager_factory.return_value
    return app


@pytest.fixture()
def client(app: Flask) -> FlaskClient:
    return app.test_client()
