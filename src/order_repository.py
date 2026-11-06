"""Database queries and operations for attestation orders."""

import os
from functools import lru_cache

from attest_data_model import (AttestationOrder, AttestationRequest,
                               OrderEvent, OrderStatus)
from sqlalchemy import Select, create_engine, func, select, update
from sqlalchemy.engine import Engine
from sqlalchemy.engine.url import URL
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session


class DataBaseError(Exception):
    """Error accessing attestation orders."""


@lru_cache(maxsize=1)
def _engine() -> Engine:
    required_variables = (
        "ATTEST_DB_HOST",
        "ATTEST_DB_PORT",
        "ATTEST_DB_NAME",
        "ATTEST_DB_USERNAME",
        "ATTEST_DB_PASSWORD",
    )
    missing_variables = [
        variable for variable in required_variables if not os.environ.get(variable)
    ]
    if missing_variables:
        missing = ", ".join(missing_variables)
        raise DataBaseError(f"Missing database configuration: {missing}")

    try:
        url = URL.create(
            "postgresql+psycopg",
            username=os.environ["ATTEST_DB_USERNAME"],
            password=os.environ["ATTEST_DB_PASSWORD"],
            host=os.environ["ATTEST_DB_HOST"],
            port=int(os.environ["ATTEST_DB_PORT"]),
            database=os.environ["ATTEST_DB_NAME"],
        )
    except ValueError as error:
        raise DataBaseError("ATTEST_DB_PORT must be a valid port number") from error

    return create_engine(url)


def _order_columns() -> tuple:
    return (
        AttestationOrder.order_id.label("orderId"),
        AttestationRequest.requested_at.label("requestedAt"),
        AttestationRequest.requester_name.label("requesterName"),
        AttestationRequest.requester_email.label("requesterEmail"),
        AttestationRequest.requester_dq.label("requesterDq"),
        AttestationRequest.subject_cpr.label("cpr"),
    )


def get_all_pending_orders() -> list[dict]:
    """Fetch all pending orders, newest requests first."""
    statement = (
        select(*_order_columns())
        .join(AttestationOrder.request)
        .where(AttestationOrder.status == OrderStatus.PENDING_ORDER)
        .order_by(
            AttestationRequest.requested_at.desc(),
            AttestationRequest.requester_dq,
        )
    )
    return _fetch(statement, "Couldn't fetch all pending orders")


def get_pending_orders(attest_type: int, sub_type: int | None) -> list[dict]:
    """Fetch pending orders matching an attestation type and nullable subtype."""
    statement = (
        select(*_order_columns())
        .join(AttestationOrder.request)
        .where(
            AttestationOrder.status == OrderStatus.PENDING_ORDER,
            AttestationOrder.attest_type == attest_type,
            AttestationOrder.attest_subtype == sub_type,
        )
        .order_by(
            AttestationRequest.requested_at.desc(),
            AttestationRequest.requester_dq,
        )
    )
    return _fetch(statement, "Couldn't fetch pending orders")


def get_pending_order_counts() -> list[dict]:
    """Count pending orders by attestation type and subtype."""
    statement = (
        select(
            AttestationOrder.attest_type.label("attestType"),
            AttestationOrder.attest_subtype.label("attestSubType"),
            func.count().label("count"),
        )
        .where(AttestationOrder.status == OrderStatus.PENDING_ORDER)
        .group_by(AttestationOrder.attest_type, AttestationOrder.attest_subtype)
    )
    return _fetch(statement, "Couldn't fetch pending order counts")


def get_ordered_history() -> list[dict]:
    """Fetch orders currently marked as ordered."""
    statement = (
        select(
            *_order_columns()[1:],
            AttestationOrder.attest_type.label("attestType"),
            AttestationOrder.attest_subtype.label("attestSubType"),
            AttestationOrder.ordered_at.label("orderedAt"),
        )
        .select_from(AttestationOrder)
        .join(AttestationOrder.request)
        .where(AttestationOrder.status == OrderStatus.ORDERED)
        .order_by(
            AttestationRequest.requested_at.desc(),
            AttestationOrder.attest_type,
            AttestationOrder.attest_subtype,
            AttestationRequest.requester_dq,
        )
    )
    return _fetch(statement, "Couldn't fetch ordered history")


def get_completed_history() -> list[dict]:
    """Fetch up to 1000 completed orders with their latest current-status event."""
    latest_event = (
        select(OrderEvent.occurred_at)
        .where(
            OrderEvent.order_id == AttestationOrder.order_id,
            OrderEvent.status == AttestationOrder.status,
        )
        .order_by(OrderEvent.occurred_at.desc(), OrderEvent.event_id.desc())
        .limit(1)
        .correlate(AttestationOrder)
        .scalar_subquery()
    )
    statement = (
        select(
            *_order_columns()[1:],
            AttestationOrder.attest_type.label("attestType"),
            AttestationOrder.attest_subtype.label("attestSubType"),
            AttestationOrder.status.label("status"),
            latest_event.label("processedAt"),
        )
        .select_from(AttestationOrder)
        .join(AttestationOrder.request)
        .where(
            AttestationOrder.status.in_(
                (
                    OrderStatus.UNDER_REVIEW,
                    OrderStatus.JOURNALIZED,
                    OrderStatus.SENT_TO_REQUESTER,
                    OrderStatus.RECEIVED,
                    OrderStatus.REJECTED,
                ),
            ),
        )
        .order_by(
            latest_event.desc().nulls_last(),
            AttestationRequest.requested_at.desc(),
        )
        .limit(1000)
    )
    rows = _fetch(statement, "Couldn't fetch completed history")
    for row in rows:
        row["status"] = row["status"].value

    return rows


def mark_orders_as_ordered(order_ids: list[str], actor: str) -> int:
    """Mark pending orders ordered and add one event per changed order atomically."""
    try:
        with Session(_engine()) as session, session.begin():
            changed_ids = session.scalars(
                update(AttestationOrder)
                .where(
                    AttestationOrder.order_id.in_(order_ids),
                    AttestationOrder.status == OrderStatus.PENDING_ORDER,
                )
                .values(status=OrderStatus.ORDERED, ordered_at=func.now())
                .returning(AttestationOrder.order_id),
            ).all()
            session.add_all(
                OrderEvent(order_id=order_id, status=OrderStatus.ORDERED, actor=actor)
                for order_id in changed_ids
            )
            return len(changed_ids)
    except SQLAlchemyError as error:
        raise DataBaseError("Couldn't mark orders as ordered") from error


def reject_order(order_id: str, actor: str, reason: str, description: str) -> bool:
    """Reject a pending order and record its reason in the same transaction."""
    try:
        with Session(_engine()) as session, session.begin():
            changed_id = session.scalar(
                update(AttestationOrder)
                .where(
                    AttestationOrder.order_id == order_id,
                    AttestationOrder.status == OrderStatus.PENDING_ORDER,
                )
                .values(status=OrderStatus.REJECTED)
                .returning(AttestationOrder.order_id),
            )
            if changed_id is None:
                return False

            session.add(
                OrderEvent(
                    order_id=changed_id,
                    status=OrderStatus.REJECTED,
                    actor=actor,
                    rejection_reason=reason,
                    rejection_description=description,
                ),
            )
            return True
    except SQLAlchemyError as error:
        raise DataBaseError("Couldn't reject order") from error


def _fetch(statement: Select, message: str) -> list[dict]:
    try:
        with Session(_engine()) as session:
            return [dict(row) for row in session.execute(statement).mappings()]
    except SQLAlchemyError as error:
        raise DataBaseError(message) from error
