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
    DataBaseError
)

api = Blueprint("api", __name__, url_prefix="/api")
logger = logging.getLogger(__name__)


@api.get("/status", methods=["GET"])
def status():
    return jsonify({"success": True}), 200


@api.get("/orders", methods=["GET"])
def get_all_orders():
    try:
        rows = get_all_pending_orders()
        return jsonify(rows), 200
    except DataBaseError as error:
        logger.error("Failed to fetch all orders: %s", error)
        return jsonify({"success": False, "error": str(error)}), 500


@api.get("/orders/<int:attest_type>/<string:sub_type>", methods=["GET"])
def get_orders(attest_type: int, sub_type: str):
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


@api.get("/ordercount", methods=["GET"])
def get_order_count():
    try:
        rows = get_pending_order_counts()
        return jsonify(rows), 200
    except DataBaseError as error:
        logger.error("Failed to fetch order counts: %s", error)
        return jsonify({"success": False, "error": str(error)}), 500


@api.get("/history/ordered", methods=["GET"])
def get_ordered_history():
    try:
        rows = fetch_ordered_history()
        return jsonify(rows), 200
    except DataBaseError as error:
        logger.error("Failed to fetch ordered history: %s", error)
        return jsonify({"success": False, "error": str(error)}), 500


@api.get("/history/completed", methods=["GET"])
def get_completed_orders():
    try:
        rows = fetch_completed_history()
        return jsonify(rows), 200
    except DataBaseError as error:
        logger.error("Failed to fetch completed history: %s", error)
        return jsonify({"success": False, "error": str(error)}), 500


#TODO: ændr actor til noget passende
@api.post("/rejectorder/<string:order_id>", methods=["POST"])
def reject_order_endpoint(order_id: str):
    try:
        success = reject_order(order_id=order_id, actor="webinterface")
        return jsonify({"success": success}), 200
    except DataBaseError as error:
        logger.error("Failed to reject order: %s", error)
        return jsonify({"success": False, "error": str(error)}), 500


#TODO: ændr actor til noget passende
@api.post("/processorders", methods=["POST"])
def mark_order_as_ordered_endpoint():
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
            actor="webinterface"
        )
        return jsonify({"success": True, "updated_count": updated_count}), 200
    except DataBaseError as error:
        logger.error("Failed to mark orders as ordered: %s", error)
        return jsonify({"success": False, "error": str(error)}), 500
