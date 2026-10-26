from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from backend.src.utils import logging as app_logging


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
