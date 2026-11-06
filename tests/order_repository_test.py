"""Behavioral tests for attestation order persistence."""

import datetime
from unittest.mock import Mock

import pytest
from attest_data_model import (AttestationOrder, AttestationRequest, Base,
                               OrderEvent, OrderStatus)
from sqlalchemy import create_engine, event, select
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

import order_repository


@pytest.fixture
def db(monkeypatch: pytest.MonkeyPatch) -> Engine:
    engine = create_engine("sqlite://", poolclass=StaticPool)
    Base.metadata.create_all(engine)
    monkeypatch.setattr(order_repository, "_engine", lambda: engine)
    yield engine
    engine.dispose()


def test_pending_reads_and_counts_preserve_response_shape(db: Engine) -> None:
    _seed(db)
    rows = order_repository.get_all_pending_orders()
    assert [row["orderId"] for row in rows] == ["pending-null", "pending-number"]
    assert set(rows[0]) == {
        "orderId", "requestedAt", "requesterName", "requesterEmail",
        "requesterDq", "cpr",
    }
    assert rows[0]["requesterEmail"] == "requester@example.invalid"
    assert [row["orderId"] for row in order_repository.get_pending_orders(2, None)] == [
        "pending-null",
    ]
    assert [row["orderId"] for row in order_repository.get_pending_orders(2, 3)] == [
        "pending-number",
    ]
    assert order_repository.get_pending_orders(1, None) == []
    assert order_repository.get_pending_order_counts() == [
        {"attestType": 2, "attestSubType": None, "count": 1},
        {"attestType": 2, "attestSubType": 3, "count": 1},
    ]


def test_history_preserves_columns_latest_event_and_nulls_last(db: Engine) -> None:
    _seed(db)
    first = datetime.datetime(2025, 1, 3, tzinfo=datetime.timezone.utc)
    latest = datetime.datetime(2025, 1, 4, tzinfo=datetime.timezone.utc)
    with Session(db) as session, session.begin():
        session.get(AttestationOrder, "pending-number").status = OrderStatus.REJECTED
        session.add_all(
            [
                OrderEvent(
                    order_id="completed", status=OrderStatus.JOURNALIZED,
                    occurred_at=first, actor="actor",
                ),
                OrderEvent(
                    order_id="completed", status=OrderStatus.RECEIVED,
                    occurred_at=latest, actor="actor",
                ),
                OrderEvent(
                    order_id="completed", status=OrderStatus.JOURNALIZED,
                    occurred_at=latest, actor="actor",
                ),
            ],
        )

    ordered = order_repository.get_ordered_history()
    assert len(ordered) == 1
    assert set(ordered[0]) == {
        "requestedAt", "requesterName", "requesterEmail", "requesterDq",
        "cpr", "attestType", "attestSubType", "orderedAt",
    }
    completed = order_repository.get_completed_history()
    assert len(completed) == 2
    assert completed[0]["status"] == "journalized"
    assert completed[0]["processedAt"] == latest.replace(tzinfo=None)
    assert completed[1]["status"] == "rejected"
    assert completed[1]["processedAt"] is None
    assert set(completed[0]) == {
        "requestedAt", "requesterName", "requesterEmail", "requesterDq",
        "cpr", "attestType", "attestSubType", "status", "processedAt",
    }


def test_ordering_changes_only_pending_orders_and_adds_events(db: Engine) -> None:
    _seed(db)
    assert order_repository.mark_orders_as_ordered(
        ["pending-null", "pending-number", "ordered", "missing", "pending-null"],
        "actor@example.invalid",
    ) == 2
    assert order_repository.mark_orders_as_ordered(
        ["pending-null"], "actor@example.invalid",
    ) == 0
    with Session(db) as session:
        orders = session.scalars(select(AttestationOrder)).all()
        assert {o.order_id for o in orders if o.status == OrderStatus.ORDERED} == {
            "pending-null", "pending-number", "ordered",
        }
        assert all(
            order.ordered_at is not None
            for order in orders if order.order_id.startswith("pending")
        )
        events = session.scalars(select(OrderEvent)).all()
        assert {entry.order_id for entry in events} == {
            "pending-null", "pending-number",
        }
        assert all(entry.actor == "actor@example.invalid" for entry in events)


def test_rejection_records_details_only_for_pending_order(db: Engine) -> None:
    _seed(db)
    assert order_repository.reject_order(
        "pending-null", "actor@example.invalid", "other", "Example description",
    )
    assert not order_repository.reject_order(
        "pending-null", "actor@example.invalid", "other", "Again",
    )
    assert not order_repository.reject_order(
        "ordered", "actor@example.invalid", "other", "Again",
    )
    with Session(db) as session:
        entry = session.scalar(select(OrderEvent))
        assert entry.rejection_reason == "other"
        assert entry.rejection_description == "Example description"
        assert entry.status == OrderStatus.REJECTED
        assert session.get(AttestationOrder, "pending-null").status == OrderStatus.REJECTED


@pytest.mark.parametrize(
    ("repository_function", "args"),
    [
        (order_repository.mark_orders_as_ordered, (["pending-null"], "actor")),
        (order_repository.reject_order, ("pending-null", "actor", "other", "Example")),
    ],
)
def test_event_failure_rolls_back_status(
    db: Engine,
    repository_function: object,
    args: tuple,
) -> None:
    _seed(db)

    def fail_event(*_args: object) -> None:
        raise SQLAlchemyError("Simulated event write failure")

    event.listen(OrderEvent, "before_insert", fail_event)
    try:
        with pytest.raises(order_repository.DataBaseError) as exc_info:
            repository_function(*args)

        assert isinstance(exc_info.value.__cause__, SQLAlchemyError)
        with Session(db) as session:
            assert session.get(
                AttestationOrder, "pending-null",
            ).status == OrderStatus.PENDING_ORDER
            assert session.scalar(select(OrderEvent)) is None
    finally:
        event.remove(OrderEvent, "before_insert", fail_event)


@pytest.mark.parametrize(
    ("repository_function", "args"),
    [
        (order_repository.get_all_pending_orders, ()),
        (order_repository.get_pending_orders, (2, None)),
        (order_repository.get_pending_order_counts, ()),
        (order_repository.get_ordered_history, ()),
        (order_repository.get_completed_history, ()),
        (order_repository.mark_orders_as_ordered, (["pending-null"], "actor")),
        (order_repository.reject_order, ("pending-null", "actor", "other", "Example")),
    ],
)
def test_database_errors_are_wrapped(
    monkeypatch: pytest.MonkeyPatch,
    repository_function: object,
    args: tuple,
) -> None:
    engine = create_engine("sqlite://", poolclass=StaticPool)
    monkeypatch.setattr(order_repository, "_engine", lambda: engine)
    try:
        with pytest.raises(order_repository.DataBaseError) as exc_info:
            repository_function(*args)

        assert isinstance(exc_info.value.__cause__, SQLAlchemyError)
    finally:
        engine.dispose()


def test_missing_database_configuration_is_explicit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for variable in (
        "ATTEST_DB_HOST",
        "ATTEST_DB_PORT",
        "ATTEST_DB_NAME",
        "ATTEST_DB_USERNAME",
        "ATTEST_DB_PASSWORD",
    ):
        monkeypatch.delenv(variable, raising=False)

    order_repository._engine.cache_clear()
    with pytest.raises(order_repository.DataBaseError, match="ATTEST_DB_HOST"):
        order_repository.get_all_pending_orders()


def test_database_credentials_create_psycopg_url_safely(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    create_engine_mock = Mock()
    monkeypatch.setenv("ATTEST_DB_HOST", "db.example.invalid")
    monkeypatch.setenv("ATTEST_DB_PORT", "5433")
    monkeypatch.setenv("ATTEST_DB_NAME", "test")
    monkeypatch.setenv("ATTEST_DB_USERNAME", "db-user")
    monkeypatch.setenv("ATTEST_DB_PASSWORD", "p@ss:/word")
    monkeypatch.setattr(order_repository, "create_engine", create_engine_mock)
    order_repository._engine.cache_clear()

    order_repository._engine()
    order_repository._engine()

    create_engine_mock.assert_called_once()
    url = create_engine_mock.call_args.args[0]
    assert url.drivername == "postgresql+psycopg"
    assert url.username == "db-user"
    assert url.password == "p@ss:/word"
    assert url.host == "db.example.invalid"
    assert url.port == 5433
    assert url.database == "test"
    order_repository._engine.cache_clear()


def test_invalid_database_port_is_explicit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ATTEST_DB_HOST", "localhost")
    monkeypatch.setenv("ATTEST_DB_PORT", "invalid")
    monkeypatch.setenv("ATTEST_DB_NAME", "test")
    monkeypatch.setenv("ATTEST_DB_USERNAME", "user")
    monkeypatch.setenv("ATTEST_DB_PASSWORD", "password")
    order_repository._engine.cache_clear()

    with pytest.raises(order_repository.DataBaseError, match="ATTEST_DB_PORT"):
        order_repository._engine()

    order_repository._engine.cache_clear()


def test_completed_history_is_limited_to_1000(db: Engine) -> None:
    with Session(db) as session, session.begin():
        request = _request(
            "bulk-request",
            datetime.datetime(2025, 1, 1, tzinfo=datetime.timezone.utc),
        )
        request.orders = [
            AttestationOrder(
                order_id=f"completed-{index}",
                attest_type=index,
                status=OrderStatus.RECEIVED,
            )
            for index in range(1001)
        ]
        session.add(request)

    assert len(order_repository.get_completed_history()) == 1000


def _request(request_id: str, requested_at: datetime.datetime) -> AttestationRequest:
    return AttestationRequest(
        request_id=request_id,
        requester_dq=request_id,
        requester_name="Example Requester",
        requester_email="requester@example.invalid",
        subject_cpr="0000000000",
        is_approved=True,
        requested_at=requested_at,
    )


def _seed(db: Engine) -> None:
    newer = datetime.datetime(2025, 1, 2, tzinfo=datetime.timezone.utc)
    older = datetime.datetime(2025, 1, 1, tzinfo=datetime.timezone.utc)
    with Session(db) as session, session.begin():
        session.add_all(
            [
                _request("newer", newer),
                _request("older", older),
            ],
        )
        session.add_all(
            [
                AttestationOrder(
                    order_id="pending-null",
                    request_id="newer",
                    attest_type=2,
                    attest_subtype=None,
                    status=OrderStatus.PENDING_ORDER,
                ),
                AttestationOrder(
                    order_id="pending-number",
                    request_id="older",
                    attest_type=2,
                    attest_subtype=3,
                    status=OrderStatus.PENDING_ORDER,
                ),
                AttestationOrder(
                    order_id="ordered",
                    request_id="older",
                    attest_type=1,
                    status=OrderStatus.ORDERED,
                    ordered_at=older,
                ),
                AttestationOrder(
                    order_id="completed",
                    request_id="newer",
                    attest_type=1,
                    status=OrderStatus.JOURNALIZED,
                ),
            ],
        )
