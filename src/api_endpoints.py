"""
API endpoints for the Flask application.
"""
import logging
from flask import Blueprint, jsonify

from order_repository import (
    get_pending_orders,
    get_all_pending_orders,
    get_pending_order_counts,
    get_ordered_history as fetch_ordered_history,
    get_completed_history as fetch_completed_history,
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


@api.get("/orders/<int:attest_type>/<int:sub_type>", methods=["GET"])
def get_orders(attest_type: int, sub_type: int):
    try:
        rows = get_pending_orders(attest_type, sub_type)
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
