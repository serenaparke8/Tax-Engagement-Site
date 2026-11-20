import sqlite3

from flask import jsonify, request, session

from ..db import get_db
from . import required_items_bp


ITEM_STATUSES = ("Outstanding", "Received")


@required_items_bp.before_request
def require_authenticated_user():
    if "user_id" not in session:
        return jsonify(error="Sign in to manage required items."), 401
    return None


def parse_positive_id(value):
    if isinstance(value, bool):
        return None
    try:
        identifier = int(value)
    except (TypeError, ValueError):
        return None
    if identifier <= 0 or str(value).strip() != str(identifier):
        return None
    return identifier


def required_item_select_sql(where=""):
    return f"""SELECT ri.required_item_id, ri.engagement_id,
                      ri.required_item_description, ri.item_status,
                      e.client_id, c.client_name, e.tax_year, e.return_type
               FROM REQUIRED_ITEM AS ri
               JOIN TAX_ENGAGEMENT AS e ON e.engagement_id = ri.engagement_id
               JOIN CLIENT AS c ON c.client_id = e.client_id
               {where}"""


def serialize_required_item(row):
    return {key: row[key] for key in (
        "required_item_id",
        "engagement_id",
        "required_item_description",
        "item_status",
        "client_id",
        "client_name",
        "tax_year",
        "return_type",
    )}


@required_items_bp.get("")
def list_engagement_items():
    engagement_id = parse_positive_id(request.args.get("engagement_id"))
    if engagement_id is None:
        return jsonify(error="Select a valid tax engagement."), 400

    db = get_db()
    engagement = db.execute(
        "SELECT engagement_id FROM TAX_ENGAGEMENT WHERE engagement_id = ?",
        (engagement_id,),
    ).fetchone()
    if engagement is None:
        return jsonify(error="Tax engagement not found."), 404

    rows = db.execute(
        required_item_select_sql("WHERE ri.engagement_id = ? ORDER BY ri.required_item_id"),
        (engagement_id,),
    ).fetchall()
    return jsonify(required_items=[serialize_required_item(row) for row in rows])


@required_items_bp.get("/outstanding")
def list_outstanding_items():
    rows = get_db().execute(
        required_item_select_sql(
            "WHERE ri.item_status = 'Outstanding' "
            "ORDER BY e.filing_deadline, c.client_name COLLATE NOCASE, ri.required_item_id"
        )
    ).fetchall()
    return jsonify(required_items=[serialize_required_item(row) for row in rows])


@required_items_bp.post("")
def add_required_item():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify(error="Submit required-item information as a JSON object."), 400

    engagement_id = parse_positive_id(payload.get("engagement_id"))
    if engagement_id is None:
        return jsonify(error="Select a valid tax engagement."), 400
    description = payload.get("required_item_description")
    if not isinstance(description, str) or not description.strip():
        return jsonify(error="Required-item description is required."), 400

    db = get_db()
    try:
        db.execute("BEGIN IMMEDIATE")
        engagement = db.execute(
            "SELECT engagement_id FROM TAX_ENGAGEMENT WHERE engagement_id = ?",
            (engagement_id,),
        ).fetchone()
        if engagement is None:
            db.rollback()
            return jsonify(error="Tax engagement not found."), 404

        existing_descriptions = db.execute(
            "SELECT required_item_description FROM REQUIRED_ITEM WHERE engagement_id = ?",
            (engagement_id,),
        ).fetchall()
        normalized_description = description.strip().casefold()
        if any(row["required_item_description"].strip().casefold() == normalized_description
               for row in existing_descriptions):
            db.rollback()
            return jsonify(
                error="That item is already listed for this engagement. Choose a different item."
            ), 409

        cursor = db.execute(
            """INSERT INTO REQUIRED_ITEM (engagement_id, required_item_description)
               VALUES (?, ?)""",
            (engagement_id, description.strip()),
        )
        db.commit()
    except sqlite3.IntegrityError:
        db.rollback()
        return jsonify(error="The required item could not be saved."), 400

    row = db.execute(
        required_item_select_sql("WHERE ri.required_item_id = ?"),
        (cursor.lastrowid,),
    ).fetchone()
    return jsonify(
        required_item=serialize_required_item(row),
        message="Required item added successfully.",
    ), 201


@required_items_bp.patch("/<int:required_item_id>/status")
def update_required_item_status(required_item_id):
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify(error="Submit a required-item status."), 400
    status = payload.get("item_status")
    if status not in ITEM_STATUSES:
        return jsonify(error="Select Outstanding or Received."), 400

    db = get_db()
    existing = db.execute(
        "SELECT required_item_id FROM REQUIRED_ITEM WHERE required_item_id = ?",
        (required_item_id,),
    ).fetchone()
    if existing is None:
        return jsonify(error="Required item not found."), 404

    try:
        db.execute(
            "UPDATE REQUIRED_ITEM SET item_status = ? WHERE required_item_id = ?",
            (status, required_item_id),
        )
        db.commit()
    except sqlite3.IntegrityError:
        db.rollback()
        return jsonify(error="The required-item status could not be updated; the previous status was kept."), 400

    row = db.execute(
        required_item_select_sql("WHERE ri.required_item_id = ?"),
        (required_item_id,),
    ).fetchone()
    return jsonify(
        required_item=serialize_required_item(row),
        message="Required-item status updated successfully.",
    )


@required_items_bp.delete("/<int:required_item_id>")
def delete_required_item(required_item_id):
    db = get_db()
    existing = db.execute(
        "SELECT required_item_id FROM REQUIRED_ITEM WHERE required_item_id = ?",
        (required_item_id,),
    ).fetchone()
    if existing is None:
        return jsonify(error="Required item not found."), 404

    try:
        db.execute(
            "DELETE FROM REQUIRED_ITEM WHERE required_item_id = ?",
            (required_item_id,),
        )
        db.commit()
    except sqlite3.IntegrityError:
        db.rollback()
        return jsonify(error="The required item could not be deleted."), 409

    return jsonify(message="Required item deleted successfully.")
