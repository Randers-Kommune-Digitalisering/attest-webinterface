from unittest.mock import MagicMock as Mock

import psycopg
import pytest

from backend.src import order_repository


@pytest.fixture
def db(monkeypatch: pytest.MonkeyPatch) -> tuple[Mock, Mock]:
    monkeypatch.setenv("DATABASE_URL", "postgresql://test")

    connect = Mock()
    connection = Mock()
    cursor = Mock()

    connect.return_value.__enter__.return_value = connection
    connection.cursor.return_value.__enter__.return_value = cursor

    monkeypatch.setattr(order_repository.psycopg, "connect", connect)

    return connect, cursor


@pytest.mark.parametrize(
    ("repository_function", "args", "expected_params", "sql_fragment"),
    [
        (
            order_repository.get_all_pending_orders,
            (),
            None,
            "WHERE o.status = 'pending_order'",
        ),
        (
            order_repository.get_pending_orders,
            (2, None),
            (2, None),
            "o.attest_subtype IS NOT DISTINCT FROM %s",
        ),
        (
            order_repository.get_pending_order_counts,
            (),
            None,
            "WHERE status = 'pending_order'",
        ),
        (
            order_repository.get_ordered_history,
            (),
            None,
            "WHERE o.status = 'ordered'",
        ),
        (
            order_repository.get_completed_history,
            (),
            None,
            "LIMIT 1000",
        ),
    ],
)
def test_read_functions_return_rows_and_execute_expected_query(
    db: tuple[Mock, Mock],
    repository_function: object,
    args: tuple,
    expected_params: tuple | None,
    sql_fragment: str,
) -> None:
    connect, cursor = db
    rows = [{"orderId": "order-1"}]
    cursor.fetchall.return_value = rows

    result = repository_function(*args)

    assert result == rows
    cursor.fetchall.assert_called_once_with()
    connect.assert_called_once_with(
        "postgresql://test",
        row_factory=order_repository.dict_row,
    )

    executed_query = cursor.execute.call_args.args[0]
    assert sql_fragment in executed_query

    if expected_params is None:
        cursor.execute.assert_called_once_with(executed_query)
    else:
        cursor.execute.assert_called_once_with(executed_query, expected_params)


def test_get_pending_orders_passes_numeric_subtype(
        db: tuple[Mock, Mock],
) -> None:
    _, cursor = db

    order_repository.get_pending_orders(2, 3)

    executed_query = cursor.execute.call_args.args[0]
    cursor.execute.assert_called_once_with(executed_query, (2, 3))


def test_get_completed_history_uses_latest_event_for_current_status(
        db: tuple[Mock, Mock],
) -> None:
    _, cursor = db

    order_repository.get_completed_history()

    query = cursor.execute.call_args.args[0]
    assert "e.status = o.status" in query
    assert "ORDER BY e.occurred_at DESC, e.event_id DESC" in query
    assert "NULLS LAST" in query


def test_mark_orders_as_ordered_returns_number_of_updated_orders(
        db: tuple[Mock, Mock],
) -> None:
    connect, cursor = db
    order_ids = ["order-1", "order-2", "order-3"]
    cursor.fetchall.return_value = [("order-1",), ("order-2",)]

    result = order_repository.mark_orders_as_ordered(order_ids, "actor@test.dk")

    assert result == 2
    cursor.execute.assert_called_once()
    query, params = cursor.execute.call_args.args
    assert "status = 'pending_order'" in query
    assert "INSERT INTO order_event" in query
    assert params == (order_ids, "actor@test.dk")
    connect.assert_called_once_with("postgresql://test")


def test_reject_order_returns_false_when_order_is_not_pending(
        db: tuple[Mock, Mock],
) -> None:
    _, cursor = db
    cursor.rowcount = 0

    result = order_repository.reject_order(
        "order-1",
        "actor@test.dk",
        "incorrect",
        "Beskrivelse",
    )

    assert result is False
    cursor.execute.assert_called_once()


def test_reject_order_records_event_after_successful_update(
        db: tuple[Mock, Mock],
) -> None:
    _, cursor = db
    cursor.rowcount = 1

    result = order_repository.reject_order(
        "order-1",
        "actor@test.dk",
        "other",
        "Beskrivelse",
    )

    assert result is True
    assert cursor.execute.call_count == 2
    assert cursor.execute.call_args_list[1].args[1] == (
        "order-1",
        "actor@test.dk",
        "other",
        "Beskrivelse",
    )


@pytest.mark.parametrize(
    ("repository_function", "args"),
    [
        (order_repository.get_all_pending_orders, ()),
        (order_repository.get_pending_orders, (2, None)),
        (order_repository.get_pending_order_counts, ()),
        (order_repository.get_ordered_history, ()),
        (order_repository.get_completed_history, ()),
        (order_repository.mark_orders_as_ordered, (["order-1"], "actor@test.dk")),
        (
            order_repository.reject_order,
            ("order-1", "actor@test.dk", "other", "Beskrivelse"),
        ),
    ],
)
def test_repository_functions_wrap_psycopg_errors(
    db: tuple[Mock, Mock],
    repository_function: object,
    args: tuple,
) -> None:
    _, cursor = db
    database_error = psycopg.Error("Database failure")
    cursor.execute.side_effect = database_error

    with pytest.raises(order_repository.DataBaseError) as exc_info:
        repository_function(*args)

    assert exc_info.value.__cause__ is database_error
