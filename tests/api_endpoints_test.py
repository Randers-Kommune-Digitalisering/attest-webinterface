"""Test for the Flask API endpoints."""
from unittest.mock import patch

import pytest
from flask.testing import FlaskClient

from backend.src.api_endpoints import REJECTION_DESCRIPTIONS
from backend.src.order_repository import DataBaseError


def test_status_returns_success(client: FlaskClient) -> None:
    response = client.get("/api/status")

    assert response.status_code == 200
    assert response.json == {"success": True}


@pytest.mark.parametrize(
    ("endpoint", "mock_target"),
    [
        ("/api/orders", "get_all_pending_orders"),
        ("/api/ordercount", "get_pending_order_counts"),
        ("/api/history/ordered", "fetch_ordered_history"),
        ("/api/history/completed", "fetch_completed_history"),
    ],
)
def test_read_endpoints_return_repository_rows(
    client: FlaskClient,
    endpoint: str,
    mock_target: str,
) -> None:
    rows = [{"id": "order-1"}]

    with patch(
        f"backend.src.api_endpoints.{mock_target}",
        return_value=rows,
    ) as repository_call:
        response = client.get(endpoint)

    assert response.status_code == 200
    assert response.json == rows
    repository_call.assert_called_once_with()


def test_get_orders_converts_null_subtype_to_none(
        client: FlaskClient,
) -> None:
    rows = [{"id": "order-1"}]

    with patch(
        "backend.src.api_endpoints.get_pending_orders",
        return_value=rows,
    ) as repository_call:
        response = client.get("/api/orders/2/null")

    assert response.status_code == 200
    assert response.get_json() == rows
    repository_call.assert_called_once_with(2, None)


def test_get_orders_converts_numeric_subtype(
        client: FlaskClient,
) -> None:
    with patch(
        "backend.src.api_endpoints.get_pending_orders",
        return_value=[],
    ) as repository_call:
        response = client.get("/api/orders/2/3")

    assert response.status_code == 200
    repository_call.assert_called_once_with(2, 3)


def test_get_orders_rejects_invalid_subtype(
        client: FlaskClient,
) -> None:
    with patch(
        "backend.src.api_endpoints.get_pending_orders",
    ) as repository_call:
        response = client.get("/api/orders/2/invalid")

    assert response.status_code == 400
    assert response.get_json() == {
        "success": False,
        "error": "Invalid attestation subtype",
    }
    repository_call.assert_not_called()


@pytest.mark.parametrize(
    "payload",
    [
        None,
        {},
        "not a list",
        [],
        ["order-1", 123],
    ],
)
def test_process_orders_rejects_invalid_payload(
    client: FlaskClient,
    payload: object,
) -> None:
    with patch(
        "backend.src.api_endpoints.mark_orders_as_ordered",
    ) as repository_call:
        response = client.post("/api/processorders", json=payload)

    assert response.status_code == 400
    assert response.get_json() == {
        "success": False,
        "error": "Expected a list of order IDs",
    }
    repository_call.assert_not_called()


def test_process_orders_marks_orders_with_actor_email(
    client: FlaskClient,
) -> None:
    with patch(
        "backend.src.api_endpoints.mark_orders_as_ordered",
        return_value=2,
    ) as repository_call:
        response = client.post(
            "/api/processorders",
            json=["order-1", "order-2"],
        )

    assert response.status_code == 200
    assert response.get_json() == {
        "success": True,
        "updated_count": 2,
    }
    repository_call.assert_called_once_with(
        order_ids=["order-1", "order-2"],
        actor="test@test.dk",
    )


@pytest.mark.parametrize(
    ("payload", "expected_error"),
    [
        (None, "Expected a JSON object"),
        ([], "Expected a JSON object"),
        ({}, "Invalid rejection reason"),
        (
            {"reason": "other", "description": "   "},
            "Description is required for reason 'other'",
        ),
        (
            {"reason": "unknown", "description": "Text"},
            "Invalid rejection reason",
        ),
    ],
)
def test_reject_order_rejects_invalid_payload(
    client: FlaskClient,
    payload: object,
    expected_error: str,
) -> None:
    with patch(
        "backend.src.api_endpoints.reject_order",
    ) as repository_call:
        response = client.post(
            "/api/rejectorder/order-1",
            json=payload,
        )

    assert response.status_code == 400
    assert response.get_json() == {
        "success": False,
        "error": expected_error,
    }
    repository_call.assert_not_called()


def test_reject_order_trims_custom_description(
        client: FlaskClient,
) -> None:
    with patch(
        "backend.src.api_endpoints.reject_order",
        return_value=True,
    ) as repository_call:
        response = client.post(
            "/api/rejectorder/order-1",
            json={
                "reason": "other",
                "description": "  Beskrivelse   ",
            },
        )

    assert response.status_code == 200
    assert response.get_json() == {"success": True}
    repository_call.assert_called_once_with(
        order_id="order-1",
        actor="test@test.dk",
        reason="other",
        description="Beskrivelse",
    )


@pytest.mark.parametrize(
    "reason",
    ["incorrect", "duplicate"],
)
def test_reject_order_uses_standard_description(
    client: FlaskClient,
    reason: str,
) -> None:
    with patch(
        "backend.src.api_endpoints.reject_order",
        return_value=True,
    ) as repository_call:
        response = client.post(
            "/api/rejectorder/order-1",
            json={"reason": reason},
        )

    assert response.status_code == 200
    repository_call.assert_called_once_with(
        order_id="order-1",
        actor="test@test.dk",
        reason=reason,
        description=REJECTION_DESCRIPTIONS[reason],
    )


def test_database_error_returns_server_error(
    client: FlaskClient,
) -> None:
    with patch(
        "backend.src.api_endpoints.get_all_pending_orders",
        side_effect=DataBaseError("Database unavailable"),
    ):
        response = client.get("/api/orders")

    assert response.status_code == 500
    assert response.get_json() == {
        "success": False,
        "error": "Database unavailable",
    }


@pytest.mark.parametrize(
    ("method", "endpoint", "mock_target", "payload"),
    [
        ("get", "/api/orders/2/3", "get_pending_orders", None),
        ("get", "/api/ordercount", "get_pending_order_counts", None),
        ("get", "/api/history/ordered", "fetch_ordered_history", None),
        ("get", "/api/history/completed", "fetch_completed_history", None),
        ("post", "/api/rejectorder/order-1", "reject_order", {"reason": "incorrect"}),
        ("post", "/api/processorders", "mark_orders_as_ordered", ["order-1"]),
    ],
)
def test_endpoints_return_server_error_on_database_error(
    client: FlaskClient,
    method: str,
    endpoint: str,
    mock_target: str,
    payload: object,
) -> None:
    with patch(
        f"backend.src.api_endpoints.{mock_target}",
        side_effect=DataBaseError("Database unavailable"),
    ):
        response = getattr(client, method)(endpoint, json=payload)

    assert response.status_code == 500
    assert response.get_json() == {
        "success": False,
        "error": "Database unavailable",
    }


@pytest.mark.parametrize(
    ("endpoint", "payload", "mock_target"),
    [
        ("/api/rejectorder/order-1", {"reason": "incorrect"}, "reject_order"),
        ("/api/processorders", ["order-1"], "mark_orders_as_ordered"),
    ],
)
def test_write_endpoints_require_actor_email(
    client: FlaskClient,
    endpoint: str,
    payload: object,
    mock_target: str,
) -> None:
    with client.session_transaction() as session:
        session["user"] = {}

    with patch(f"backend.src.api_endpoints.{mock_target}") as repository_call:
        response = client.post(endpoint, json=payload)

    assert response.status_code == 401
    assert response.get_json() == {
        "success": False,
        "error": "Not authenticated",
    }
    repository_call.assert_not_called()
