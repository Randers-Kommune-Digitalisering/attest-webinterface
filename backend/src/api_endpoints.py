"""
API endpoints for the Flask application.
"""
import logging
from flask import Blueprint, jsonify, request

from backend.src.order_repository import (
    get_pending_orders,
    get_all_pending_orders,
    get_pending_order_counts,
    get_ordered_history as fetch_ordered_history,
    get_completed_history as fetch_completed_history,
    mark_orders_as_ordered,
    reject_order,
    DataBaseError,
)

api = Blueprint("api", __name__, url_prefix="/api")
logger = logging.getLogger(__name__)


REJECTION_DESCRIPTIONS = {
    "incorrect": (
        "Fejl i CPR-nummer. CPR-nummeret findes ikke i CPR-registeret. "
        "Kontroller CPR-nummeret og prøv at bestille attesten igen."
    ),
    "duplicate": (
        "Duplikat bestilling. Bestillingen er en duplikat af en anden bestilling. "
        "Kontroller bestillingerne og prøv evt. at bestille attesten igen, "
        "hvis du mener der er tale om en fejl."
    ),
}


@api.get("/status")
def status() -> tuple[dict, int]:
    """
    Check the status of the API.

    Return: JSON response with API status and HTTP status code
    """
    return jsonify({"success": True}), 200


@api.get("/orders")
def get_all_orders() -> tuple[dict, int]:
    """
    Get all pending orders.

    Return: JSON response with all pending orders and HTTP status code
    """
    try:
        rows = get_all_pending_orders()
        return jsonify(rows), 200
    except DataBaseError as error:
        logger.error("Failed to fetch all orders: %s", error)
        return jsonify({"success": False, "error": str(error)}), 500


@api.get("/orders/<int:attest_type>/<string:sub_type>")
def get_orders(attest_type: int, sub_type: str) -> tuple[dict, int]:
    """
    Get pending orders for a specific attestation type and subtype.

    Param: attest_type: int: The attestation type.
    Param: sub_type: str: The attestation subtype. Can be "null" if not specified.
    Return: JSON response with pending orders and HTTP status code
    """
    if sub_type == "null":
        parsed_sub_type = None
    else:
        try:
            parsed_sub_type = int(sub_type)
        except ValueError:
            return jsonify({"success": False, "error": "Invalid attestation subtype"}), 400

    try:
        rows = get_pending_orders(attest_type, parsed_sub_type)
        return jsonify(rows), 200
    except DataBaseError as error:
        logger.error("Failed to fetch orders: %s", error)
        return jsonify({"success": False, "error": str(error)}), 500


@api.get("/ordercount")
def get_order_count() -> tuple[dict, int]:
    """
    Get the count of all pending orders.

    Return: JSON response with order counts and HTTP status code
    """
    try:
        rows = get_pending_order_counts()
        return jsonify(rows), 200
    except DataBaseError as error:
        logger.error("Failed to fetch order counts: %s", error)
        return jsonify({"success": False, "error": str(error)}), 500


@api.get("/history/ordered")
def get_ordered_history() -> tuple[dict, int]:
    """
    Get the history of ordered orders.

    Return: JSON response with ordered history and HTTP status code
    """
    try:
        rows = fetch_ordered_history()
        return jsonify(rows), 200
    except DataBaseError as error:
        logger.error("Failed to fetch ordered history: %s", error)
        return jsonify({"success": False, "error": str(error)}), 500


@api.get("/history/completed")
def get_completed_orders() -> tuple[dict, int]:
    """
    Get the history of completed orders.

    Return: JSON response with completed history and HTTP status code
    """
    try:
        rows = fetch_completed_history()
        return jsonify(rows), 200
    except DataBaseError as error:
        logger.error("Failed to fetch completed history: %s", error)
        return jsonify({"success": False, "error": str(error)}), 500


# TODO: ændr actor til noget passende
@api.post("/rejectorder/<string:order_id>")
def reject_order_endpoint(order_id: str) -> tuple[dict, int]:
    """
    Reject an order with a specified reason and description.

    Param: order_id: str: The ID of the order to reject.
    Return: JSON response indicating success or failure and HTTP status code
    """
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"success": False, "error": "Expected a JSON object"}), 400

    reason = payload.get("reason")
    description = payload.get("description")

    if reason not in {"incorrect", "duplicate", "other"}:
        return jsonify({"success": False, "error": "Invalid rejection reason"}), 400

    if reason == "other":
        if not isinstance(description, str) or not description.strip():
            return jsonify(
                {"success": False, "error": "Description is required for reason 'other'"},
            ), 400

        description = description.strip()
    else:
        description = REJECTION_DESCRIPTIONS[reason]

    try:
        success = reject_order(
            order_id=order_id,
            actor="webinterface",
            reason=reason,
            description=description,
            )
        return jsonify({"success": success}), 200
    except DataBaseError as error:
        logger.error("Failed to reject order: %s", error)
        return jsonify({"success": False, "error": str(error)}), 500


# TODO: ændr actor til noget passende
@api.post("/processorders")
def mark_order_as_ordered_endpoint() -> tuple[dict, int]:
    """
    Mark a list of orders as ordered.

    Return: JSON response indicating success or failure and HTTP status code
    """
    order_ids = request.get_json(silent=True)
    if (
        not isinstance(order_ids, list)
        or not order_ids
        or not all(isinstance(order_id, str) for order_id in order_ids)
    ):
        return jsonify({"success": False, "error": "Expected a list of order IDs"}), 400

    try:
        updated_count: int = mark_orders_as_ordered(
            order_ids=order_ids,
            actor="webinterface",
        )
        return jsonify({"success": True, "updated_count": updated_count}), 200
    except DataBaseError as error:
        logger.error("Failed to mark orders as ordered: %s", error)
        return jsonify({"success": False, "error": str(error)}), 500
