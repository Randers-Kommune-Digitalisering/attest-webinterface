"""Behavioral tests for attestation order persistence."""

import datetime

import pytest
from attest_data_model import (AttestationOrder, AttestationRequest, Base,
                               OrderEvent, OrderStatus)
from sqlalchemy import create_engine, event, select
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

import attest_database


class SQLiteDatabaseManager:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def get_session(self) -> Session:
        return Session(self._engine)


@pytest.fixture
def db() -> Engine:
    engine = create_engine("sqlite://", poolclass=StaticPool)
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def database_manager(db: Engine) -> SQLiteDatabaseManager:
    return SQLiteDatabaseManager(db)


def test_pending_reads_and_counts_preserve_response_shape(
    db: Engine,
    database_manager: SQLiteDatabaseManager,
) -> None:
    _seed(db)
    rows = attest_database.get_all_pending_orders(database_manager)
    assert [row["orderId"] for row in rows] == ["pending-null", "pending-number"]
    assert set(rows[0]) == {
        "orderId", "requestedAt", "requesterName", "requesterEmail",
        "requesterDq", "cpr",
    }
    assert rows[0]["requesterEmail"] == "requester@example.invalid"
    assert [
        row["orderId"]
        for row in attest_database.get_pending_orders(2, None, database_manager)
    ] == ["pending-null"]
    assert [
        row["orderId"]
        for row in attest_database.get_pending_orders(2, 3, database_manager)
    ] == ["pending-number"]
    assert attest_database.get_pending_orders(1, None, database_manager) == []
    assert attest_database.get_pending_order_counts(database_manager) == [
        {"attestType": 2, "attestSubType": None, "count": 1},
        {"attestType": 2, "attestSubType": 3, "count": 1},
    ]


def test_history_preserves_columns_latest_event_and_nulls_last(
    db: Engine,
    database_manager: SQLiteDatabaseManager,
) -> None:
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

    ordered = attest_database.get_ordered_history(database_manager)
    assert len(ordered) == 1
    assert set(ordered[0]) == {
        "requestedAt", "requesterName", "requesterEmail", "requesterDq",
        "cpr", "attestType", "attestSubType", "orderedAt",
    }
    completed = attest_database.get_completed_history(database_manager)
    assert len(completed) == 2
    assert completed[0]["status"] == "journalized"
    assert completed[0]["processedAt"] == latest.replace(tzinfo=None)
    assert completed[1]["status"] == "rejected"
    assert completed[1]["processedAt"] is None
    assert set(completed[0]) == {
        "requestedAt", "requesterName", "requesterEmail", "requesterDq",
        "cpr", "attestType", "attestSubType", "status", "processedAt",
    }


def test_ordering_changes_only_pending_orders_and_adds_events(
    db: Engine,
    database_manager: SQLiteDatabaseManager,
) -> None:
    _seed(db)
    assert attest_database.mark_orders_as_ordered(
        ["pending-null", "pending-number", "ordered", "missing", "pending-null"],
        "actor@example.invalid",
        database_manager,
    ) == 2
    assert attest_database.mark_orders_as_ordered(
        ["pending-null"], "actor@example.invalid",
        database_manager,
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


def test_rejection_records_details_only_for_pending_order(
    db: Engine,
    database_manager: SQLiteDatabaseManager,
) -> None:
    _seed(db)
    assert attest_database.reject_order(
        "pending-null", "actor@example.invalid", "other", "Example description",
        database_manager,
    )
    assert not attest_database.reject_order(
        "pending-null", "actor@example.invalid", "other", "Again",
        database_manager,
    )
    assert not attest_database.reject_order(
        "ordered", "actor@example.invalid", "other", "Again",
        database_manager,
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
        (attest_database.mark_orders_as_ordered, (["pending-null"], "actor")),
        (attest_database.reject_order, ("pending-null", "actor", "other", "Example")),
    ],
)
def test_event_failure_rolls_back_status(
    db: Engine,
    database_manager: SQLiteDatabaseManager,
    repository_function: object,
    args: tuple,
) -> None:
    _seed(db)

    def fail_event(*_args: object) -> None:
        raise SQLAlchemyError("Simulated event write failure")

    event.listen(OrderEvent, "before_insert", fail_event)
    try:
        with pytest.raises(attest_database.DataBaseError) as exc_info:
            repository_function(*args, database_manager)

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
        (attest_database.get_all_pending_orders, ()),
        (attest_database.get_pending_orders, (2, None)),
        (attest_database.get_pending_order_counts, ()),
        (attest_database.get_ordered_history, ()),
        (attest_database.get_completed_history, ()),
        (attest_database.mark_orders_as_ordered, (["pending-null"], "actor")),
        (attest_database.reject_order, ("pending-null", "actor", "other", "Example")),
    ],
)
def test_database_errors_are_wrapped(
    repository_function: object,
    args: tuple,
) -> None:
    engine = create_engine("sqlite://", poolclass=StaticPool)
    database_manager = SQLiteDatabaseManager(engine)
    try:
        with pytest.raises(attest_database.DataBaseError) as exc_info:
            repository_function(*args, database_manager)

        assert isinstance(exc_info.value.__cause__, SQLAlchemyError)
    finally:
        engine.dispose()


def test_completed_history_is_limited_to_1000(
    db: Engine,
    database_manager: SQLiteDatabaseManager,
) -> None:
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

    assert len(attest_database.get_completed_history(database_manager)) == 1000


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
