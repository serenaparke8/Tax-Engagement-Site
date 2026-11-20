import sqlite3
from datetime import date

from flask import jsonify, request, session

from ..db import get_db
from . import engagements_bp


DETAIL_FIELDS = (
    "tax_year",
    "return_type",
    "assigned_preparer",
    "engagement_start_date",
    "filing_deadline",
)
ENGAGEMENT_STATUSES = ("In Progress", "Waiting on Client", "Completed")


@engagements_bp.before_request
def require_authenticated_user():
    if "user_id" not in session:
        return jsonify(error="Sign in to manage tax engagements."), 401
    return None


def serialize_engagement(row):
    return {key: row[key] for key in (
        "engagement_id",
        "client_id",
        "client_name",
        "client_contact_name",
        "client_email",
        "client_phone",
        *DETAIL_FIELDS,
        "engagement_status",
    )}


def read_detail_values(payload):
    if not isinstance(payload, dict):
        return None, "Submit engagement information as a JSON object."
    if "engagement_status" in payload:
        return None, "Update engagement status through the separate status operation."

    raw_tax_year = payload.get("tax_year")
    if isinstance(raw_tax_year, bool):
        return None, "Tax year must be a positive whole number."
    try:
        tax_year = int(raw_tax_year)
    except (TypeError, ValueError):
        return None, "Tax year must be a positive whole number."
    if tax_year <= 0 or str(raw_tax_year).strip() != str(tax_year):
        return None, "Tax year must be a positive whole number."

    values = {"tax_year": tax_year}
    for field in ("return_type", "assigned_preparer"):
        value = payload.get(field)
        if not isinstance(value, str) or not value.strip():
            return None, f"{field.replace('_', ' ').capitalize()} is required."
        values[field] = value.strip()

    for field in ("engagement_start_date", "filing_deadline"):
        value = payload.get(field)
        if not isinstance(value, str) or not value.strip():
            return None, f"{field.replace('_', ' ').capitalize()} is required."
        try:
            parsed = date.fromisoformat(value)
        except ValueError:
            return None, f"{field.replace('_', ' ').capitalize()} must be a valid date in YYYY-MM-DD format."
        if parsed.isoformat() != value:
            return None, f"{field.replace('_', ' ').capitalize()} must be a valid date in YYYY-MM-DD format."
        values[field] = value

    return values, None


def engagement_select_sql(where=""):
    return f"""SELECT e.engagement_id, e.client_id, c.client_name,
                      c.contact_name AS client_contact_name,
                      c.email AS client_email, c.phone AS client_phone,
                      e.tax_year, e.return_type, e.assigned_preparer,
                      e.engagement_start_date, e.filing_deadline,
                      e.engagement_status
               FROM TAX_ENGAGEMENT AS e
               JOIN CLIENT AS c ON c.client_id = e.client_id
               {where}"""


@engagements_bp.get("")
def list_engagements():
    search = (request.args.get("q") or "").strip()
    db = get_db()
    if search:
        pattern = f"%{search}%"
        rows = db.execute(
            engagement_select_sql(
                """WHERE c.client_name LIKE ? COLLATE NOCASE
                   OR CAST(e.tax_year AS TEXT) LIKE ?
                   OR e.return_type LIKE ? COLLATE NOCASE
                   OR e.assigned_preparer LIKE ? COLLATE NOCASE
                   OR e.engagement_status LIKE ? COLLATE NOCASE"""
            ) + " ORDER BY e.filing_deadline, e.engagement_id DESC",
            (pattern, pattern, pattern, pattern, pattern),
        ).fetchall()
    else:
        rows = db.execute(
            engagement_select_sql() + " ORDER BY e.filing_deadline, e.engagement_id DESC"
        ).fetchall()
    return jsonify(engagements=[serialize_engagement(row) for row in rows])


@engagements_bp.post("")
def create_engagement():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify(error="Submit engagement information as a JSON object."), 400
    raw_client_id = payload.get("client_id")
    if isinstance(raw_client_id, bool):
        return jsonify(error="Select an existing client."), 400
    try:
        client_id = int(raw_client_id)
    except (TypeError, ValueError):
        return jsonify(error="Select an existing client."), 400
    if client_id <= 0 or str(raw_client_id).strip() != str(client_id):
        return jsonify(error="Select an existing client."), 400

    values, error = read_detail_values(payload)
    if error:
        return jsonify(error=error), 400

    db = get_db()
    client = db.execute("SELECT client_id FROM CLIENT WHERE client_id = ?", (client_id,)).fetchone()
    if client is None:
        return jsonify(error="The selected client does not exist."), 404

    try:
        cursor = db.execute(
            """INSERT INTO TAX_ENGAGEMENT
               (client_id, tax_year, return_type, assigned_preparer,
                engagement_start_date, filing_deadline)
               VALUES (:client_id, :tax_year, :return_type, :assigned_preparer,
                       :engagement_start_date, :filing_deadline)""",
            {**values, "client_id": client_id},
        )
        db.commit()
    except sqlite3.IntegrityError:
        db.rollback()
        return jsonify(error="The engagement could not be saved. Confirm the selected client and submitted information."), 400

    row = db.execute(
        engagement_select_sql("WHERE e.engagement_id = ?"), (cursor.lastrowid,)
    ).fetchone()
    return jsonify(
        engagement=serialize_engagement(row),
        message="Tax engagement created successfully.",
    ), 201


@engagements_bp.put("/<int:engagement_id>")
def update_engagement_details(engagement_id):
    values, error = read_detail_values(request.get_json(silent=True))
    if error:
        return jsonify(error=error), 400

    db = get_db()
    existing = db.execute(
        "SELECT engagement_id FROM TAX_ENGAGEMENT WHERE engagement_id = ?",
        (engagement_id,),
    ).fetchone()
    if existing is None:
        return jsonify(error="Tax engagement not found."), 404

    assignments = ", ".join(f"{field} = :{field}" for field in DETAIL_FIELDS)
    db.execute(
        f"UPDATE TAX_ENGAGEMENT SET {assignments} WHERE engagement_id = :engagement_id",
        {**values, "engagement_id": engagement_id},
    )
    db.commit()
    row = db.execute(
        engagement_select_sql("WHERE e.engagement_id = ?"), (engagement_id,)
    ).fetchone()
    return jsonify(
        engagement=serialize_engagement(row),
        message="Tax engagement information updated successfully.",
    )


@engagements_bp.patch("/<int:engagement_id>/status")
def update_engagement_status(engagement_id):
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify(error="Submit an engagement status."), 400
    status = payload.get("engagement_status")
    if status not in ENGAGEMENT_STATUSES:
        return jsonify(error="Select one of the approved engagement statuses."), 400

    db = get_db()
    existing = db.execute(
        "SELECT engagement_id FROM TAX_ENGAGEMENT WHERE engagement_id = ?",
        (engagement_id,),
    ).fetchone()
    if existing is None:
        return jsonify(error="Tax engagement not found."), 404

    try:
        db.execute(
            "UPDATE TAX_ENGAGEMENT SET engagement_status = ? WHERE engagement_id = ?",
            (status, engagement_id),
        )
        db.commit()
    except sqlite3.IntegrityError:
        db.rollback()
        return jsonify(error="The engagement status could not be updated; the previous status was kept."), 400

    row = db.execute(
        engagement_select_sql("WHERE e.engagement_id = ?"), (engagement_id,)
    ).fetchone()
    return jsonify(
        engagement=serialize_engagement(row),
        message="Tax engagement status updated successfully.",
    )
