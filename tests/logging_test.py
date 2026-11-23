from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from utils import logging as app_logging


def test_set_logging_configuration_ignores_errors_from_werzeug_patch() -> None:
    with patch.object(app_logging, "disable_endpoint_logs", side_effect=Exception("boom")):
        app_logging.set_logging_configuration(debug=True)  # must not raise despite exception


def test_disable_endpoint_logs_skips_only_disabled_endpoints() -> None:
    parent_log_request = MagicMock()
    serving = SimpleNamespace(
        WSGIRequestHandler=type("Handler", (), {"log_request": parent_log_request}),
    )

    app_logging.disable_endpoint_logs(serving, ("/healthz",))
    log_request = serving.WSGIRequestHandler.log_request

    log_request(SimpleNamespace(path="/healthz"), 200)
    parent_log_request.assert_not_called()

    handler = SimpleNamespace(path="/api/orders")
    log_request(handler, 200)
    parent_log_request.assert_called_once_with(handler, 200)


def test_disable_endpoint_logs_redacts_auth_query_from_requestline() -> None:
    logged_requestlines: list[str] = []
    serving = SimpleNamespace(
        WSGIRequestHandler=type(
            "Handler",
            (),
            {
                "log_request": lambda handler, *args, **kwargs: logged_requestlines.append(
                    handler.requestline,
                ),
            },
        ),
    )
    app_logging.disable_endpoint_logs(serving, ())
    handler = SimpleNamespace(
        path="/api/auth?code=secret-code&state=secret-state",
        requestline="GET /api/auth?code=secret-code&state=secret-state HTTP/1.1",
    )

    serving.WSGIRequestHandler.log_request(handler, 200)

    assert logged_requestlines == ["GET /api/auth HTTP/1.1"]
    assert handler.requestline == "GET /api/auth?code=secret-code&state=secret-state HTTP/1.1"


def test_disable_endpoint_logs_keeps_non_auth_query_in_requestline() -> None:
    parent_log_request = MagicMock()
    serving = SimpleNamespace(
        WSGIRequestHandler=type("Handler", (), {"log_request": parent_log_request}),
    )
    app_logging.disable_endpoint_logs(serving, ())
    handler = SimpleNamespace(
        path="/api/orders?status=pending",
        requestline="GET /api/orders?status=pending HTTP/1.1",
    )

    serving.WSGIRequestHandler.log_request(handler, 200)

    parent_log_request.assert_called_once_with(handler, 200)
