"""Tests for Gunicorn access-log sanitization."""
import importlib.util
from pathlib import Path


CONFIG_PATH = Path(__file__).parents[1] / "gunicorn.conf.py"
SPEC = importlib.util.spec_from_file_location("gunicorn_config", CONFIG_PATH)
assert SPEC is not None
assert SPEC.loader is not None
GUNICORN_CONFIG = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GUNICORN_CONFIG)


def test_auth_callback_query_is_removed_from_access_log_environment() -> None:
    environ = {
        "RAW_URI": "/api/auth?code=secret-code&state=secret-state",
        "QUERY_STRING": "code=secret-code&state=secret-state",
        "PATH_INFO": "/api/auth",
    }

    sanitized_environ = GUNICORN_CONFIG._access_log_environ(environ, "/api/auth")

    assert sanitized_environ["RAW_URI"] == "/api/auth"
    assert sanitized_environ["QUERY_STRING"] == ""
    assert environ["RAW_URI"] == "/api/auth?code=secret-code&state=secret-state"
    assert environ["QUERY_STRING"] == "code=secret-code&state=secret-state"


def test_non_auth_query_is_unchanged_in_access_log_environment() -> None:
    environ = {
        "RAW_URI": "/api/orders?status=pending",
        "QUERY_STRING": "status=pending",
        "PATH_INFO": "/api/orders",
    }

    assert GUNICORN_CONFIG._access_log_environ(environ, "/api/orders") is environ
