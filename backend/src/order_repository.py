"""Database queries and operations for attestation orders."""

import os

import psycopg
from psycopg.rows import dict_row


class DataBaseError(Exception):
    """Custom exception for database-related errors."""
    pass


def get_all_pending_orders() -> list[dict]:
    """
    Fetch all pending attestation orders from the database.

    Return: List of dictionaries representing pending orders.
    """
    query = """
        SELECT
            o.order_id AS "orderId",
            r.requested_at AS "requestedAt",
            r.requester_name AS "requesterName",
            r.requester_email AS "requesterEmail",
            r.requester_dq AS "requesterDq",
            r.subject_cpr AS "cpr"
        FROM attestation_order o
        JOIN attestation_request r ON r.request_id = o.request_id
        WHERE o.status = 'pending_order'
        ORDER BY r.requested_at DESC, r.requester_dq
    """

    try:
        with psycopg.connect(
            os.environ["DATABASE_URL"],
            row_factory=dict_row,
        ) as connection, connection.cursor() as cursor:
            cursor.execute(query)
            return cursor.fetchall()
    except psycopg.Error as error:
        raise DataBaseError("Couldn't fetch all pending orders") from error


def get_pending_orders(attest_type: int, sub_type: int | None) -> list[dict]:
    """
    Fetch pending attestation orders for a specific attestation type and subtype.

    Param: attest_type: int: The attestation type.
    Param: sub_type: int | None: The attestation subtype. Can be None if not specified.
    Return: List of dictionaries representing pending orders.
    """
    query = """
        SELECT
            o.order_id AS "orderId",
            r.requested_at AS "requestedAt",
            r.requester_name AS "requesterName",
            r.requester_email AS "requesterEmail",
            r.requester_dq AS "requesterDq",
            r.subject_cpr AS "cpr"
        FROM attestation_order o
        JOIN attestation_request r ON r.request_id = o.request_id
        WHERE o.status = 'pending_order'
            AND o.attest_type = %s
            AND o.attest_subtype IS NOT DISTINCT FROM %s
        ORDER BY r.requested_at DESC, r.requester_dq
    """

    try:
        with psycopg.connect(
            os.environ["DATABASE_URL"],
            row_factory=dict_row,
        ) as connection, connection.cursor() as cursor:
            cursor.execute(query, (attest_type, sub_type))
            return cursor.fetchall()
    except psycopg.Error as error:
        raise DataBaseError("couldn't fetch pending orders") from error


def get_pending_order_counts() -> list[dict]:
    """
    Fetch counts of all pending attestation orders grouped by attestation type and subtype.

    Return: List of dictionaries representing pending order counts.
    """
    query = """
        SELECT
            attest_type AS "attestType",
            attest_subtype AS "attestSubType",
            COUNT(*) AS "count"
        FROM attestation_order
        WHERE status = 'pending_order'
        GROUP BY attest_type, attest_subtype
    """

    try:
        with psycopg.connect(
            os.environ["DATABASE_URL"],
            row_factory=dict_row,
        ) as connection, connection.cursor() as cursor:
            cursor.execute(query)
            return cursor.fetchall()
    except psycopg.Error as error:
        raise DataBaseError("couldn't fetch pending order counts") from error


def get_ordered_history() -> list[dict]:
    """
    Fetch the history of ordered attestation orders.

    Return: List of dictionaries representing ordered history.
    """
    query = """
        SELECT
            r.requested_at AS "requestedAt",
            r.requester_name AS "requesterName",
            r.requester_email AS "requesterEmail",
            r.requester_dq AS "requesterDq",
            r.subject_cpr AS "cpr",
            o.attest_type AS "attestType",
            o.attest_subtype AS "attestSubType",
            o.ordered_at AS "orderedAt"
        FROM attestation_order o
        JOIN attestation_request r ON r.request_id = o.request_id
        WHERE o.status = 'ordered'
        ORDER BY
            r.requested_at DESC,
            o.attest_type,
            o.attest_subtype,
            r.requester_dq
    """

    try:
        with psycopg.connect(
            os.environ["DATABASE_URL"],
            row_factory=dict_row,
        ) as connection, connection.cursor() as cursor:
            cursor.execute(query)
            return cursor.fetchall()
    except psycopg.Error as error:
        raise DataBaseError("couldn't fetch ordered history") from error


def get_completed_history() -> list[dict]:
    """
    Fetch the history of completed attestation orders.

    Return: List of dictionaries representing completed history.
    """
    query = """
        SELECT
            r.requested_at AS "requestedAt",
            r.requester_name AS "requesterName",
            r.requester_email AS "requesterEmail",
            r.requester_dq AS "requesterDq",
            r.subject_cpr AS "cpr",
            o.attest_type AS "attestType",
            o.attest_subtype AS "attestSubType",
            o.status AS "status",
            event.occurred_at AS "processedAt"
        FROM attestation_order o
        JOIN attestation_request r ON r.request_id = o.request_id
        LEFT JOIN LATERAL (
                    SELECT e.occurred_at
                    FROM order_event e
                    WHERE e.order_id = o.order_id
                        AND e.status = o.status
                    ORDER BY e.occurred_at DESC, e.event_id DESC
                    LIMIT 1
                    ) event ON true
        WHERE o.status IN (
            'under_review',
            'journalized',
            'sent_to_requester',
            'received',
            'rejected'
        )
        ORDER BY
            event.occurred_at DESC NULLS LAST,
            r.requested_at DESC
        LIMIT 1000
    """

    try:
        with psycopg.connect(
            os.environ["DATABASE_URL"],
            row_factory=dict_row,
        ) as connection, connection.cursor() as cursor:
            cursor.execute(query)
            return cursor.fetchall()
    except psycopg.Error as error:
        raise DataBaseError("couldn't fetch completed history") from error


def mark_orders_as_ordered(order_ids: list[str], actor: str) -> int:
    """
    Mark specified pending orders as 'ordered' and record an audit event in a single transaction.

    Param: order_ids: list[str]: The attestation_order.order_id values to update.
    Param: actor: str: Email of the user performing the action.
    Return: The number of orders that were updated.
    """
    query = """
        WITH updated_orders AS (
            UPDATE attestation_order
            SET status = 'ordered', ordered_at = now()
            WHERE order_id = ANY(%s)
                AND status = 'pending_order'
            RETURNING order_id
        )
        INSERT INTO order_event (order_id, status, actor)
        SELECT order_id, 'ordered', %s
        FROM updated_orders
        RETURNING order_id
    """

    try:
        with psycopg.connect(os.environ["DATABASE_URL"]) as connection, connection.cursor() as cursor:
            cursor.execute(query, (order_ids, actor))
            return len(cursor.fetchall())
    except psycopg.Error as error:
        raise DataBaseError("couldn't mark orders as ordered") from error


def reject_order(order_id: str, actor: str, reason: str, description: str) -> bool:
    """
    Reject a pending order and record an audit event.

    Param: order_id: str: The attestation_order.order_id to reject.
    Param: actor: str: Email of the user performing the action.
    Param: reason: str: The reason for rejection.
    Param: description: str: Detailed description of the rejection.
    Return: True if the order was successfully rejected, False otherwise.
    """
    query = """
        UPDATE attestation_order
        SET status = 'rejected'
        WHERE order_id = %s
        AND status = 'pending_order'
    """
    insert_event_query = """
        INSERT INTO order_event (order_id, status, actor, rejection_reason, rejection_description)
        VALUES(%s, 'rejected', %s, %s, %s)
"""

    try:
        with psycopg.connect(
            os.environ["DATABASE_URL"],
            row_factory=dict_row,
        ) as connection, connection.cursor() as cursor:
            cursor.execute(query, (order_id,))
            if cursor.rowcount == 0:
                return False

            cursor.execute(insert_event_query, (order_id, actor, reason, description))
            return True
    except psycopg.Error as error:
        raise DataBaseError("couldn't reject order") from error
