import os

import psycopg
from psycopg.rows import dict_row


class DataBaseError(Exception):
    pass


def get_all_pending_orders() -> list[dict]:
    query = """
        SELECT
            o.order_id AS "orderId",
            r.requested_at AS "requestedAt",
            r.requester_name AS "requesterName",
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
        ) as connection:
            with connection.cursor() as cursor:
                cursor.execute(query)
                return cursor.fetchall()
    except psycopg.Error as error:
        raise DataBaseError("Couldn't fetch all pending orders") from error


def get_pending_orders(attest_type: int, sub_type: int) -> list[dict]:
    query = """
        SELECT
            o.order_id AS "orderId",
            r.requested_at AS "requestedAt",
            r.requester_name AS "requesterName",
            r.requester_dq AS "requesterDq",
            r.subject_cpr AS "cpr"
        FROM attestation_order o
        JOIN attestation_request r ON r.request_id = o.request_id
        WHERE o.status = 'pending_order'
            AND o.attest_type = %s
            AND o.attest_subtype = %s
        ORDER BY r.requested_at DESC, r.requester_dq
    """

    try:
        with psycopg.connect(
            os.environ["DATABASE_URL"],
            row_factory=dict_row,
        ) as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, (attest_type, sub_type))
                return cursor.fetchall()
    except psycopg.Error as error:
        raise DataBaseError("couldn't fetch pending orders") from error


def get_pending_order_counts() -> list[dict]:
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
        ) as connection:
            with connection.cursor() as cursor:
                cursor.execute(query)
                return cursor.fetchall()
    except psycopg.Error as error:
        raise DataBaseError("couldn't fetch pending order counts") from error


def get_ordered_history() -> list[dict]:
    query = """
        SELECT
            r.requested_at AS "requestedAt",
            r.requester_name AS "requesterName",
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
        ) as connection:
            with connection.cursor() as cursor:
                cursor.execute(query)
                return cursor.fetchall()
    except psycopg.Error as error:
        raise DataBaseError("couldn't fetch ordered history") from error


def get_completed_history() -> list[dict]:
    query = """
        SELECT
            r.requested_at AS "requestedAt",
            r.requester_name AS "requesterName",
            r.requester_dq AS "requesterDq",
            r.subject_cpr AS "cpr",
            o.attest_type AS "attestType",
            o.attest_subtype AS "attestSubType",
            o.status AS "status",
        FROM attestation_order o
        JOIN attestation_request r ON r.request_id = o.request_id
        WHERE o.status IN ('received', 'journalized', 'notified', 'rejected')
        ORDER BY
            r.requested_at DESC,
            o.attest_type,
            o.attest_subtype,
            r.requester_dq
        LIMIT 1000
    """

    try:
        with psycopg.connect(
            os.environ["DATABASE_URL"],
            row_factory=dict_row,
        ) as connection:
            with connection.cursor() as cursor:
                cursor.execute(query)
                return cursor.fetchall()
    except psycopg.Error as error:
        raise DataBaseError("couldn't fetch completed history") from error


def mark_order_as_ordered(order_id: str, actor: str) -> bool:
    """
    Set a pending order to 'ordered' and append an audit event in one transaction.

    :param order_id: The attestation_order.order_id to update.
    :param actor: DQ number of the user performing the action.
    :return: True if the order was updated, False if it was not found or not pending.
    """
    update_query = """
        UPDATE attestation_order
        SET status = 'ordered', ordered_at = now()
        WHERE order_id = %s
            AND status = 'pending_order'
    """
    insert_event_query = """
        INSERT INTO order_event (order_id, status, actor)
        VALUES (%s, 'ordered', %s)
    """

    try:
        with psycopg.connect(os.environ["DATABASE_URL"]) as connection:
            with connection.cursor() as cursor:
                cursor.execute(update_query, (order_id,))
                if cursor.rowcount == 0:
                    return False
                cursor.execute(insert_event_query, (order_id, actor))
                return True
    except psycopg.Error as error:
        raise DataBaseError("couldn't mark order as ordered") from error
