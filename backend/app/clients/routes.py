from flask import jsonify, request, session
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from ..db import get_db
from . import clients_bp


CLIENT_FIELDS = ("client_name", "contact_name", "email", "phone")
OPTIONAL_CLIENT_FIELDS = ("contact_name", "email", "phone")


@clients_bp.before_request
def require_authenticated_user():
    if "user_id" not in session:
        return jsonify(error="Sign in to manage client records."), 401
    return None


def read_client_values(payload):
    if not isinstance(payload, dict):
        return None, "Submit client information as a JSON object."

    values = {}
    for field in CLIENT_FIELDS:
        value = payload.get(field, "")
        if value is None and field in OPTIONAL_CLIENT_FIELDS:
            value = ""
        if not isinstance(value, str):
            return None, f"{field.replace('_', ' ').capitalize()} must be text."
        values[field] = value.strip()

    if not values["client_name"]:
        return None, "Client name is required."

    for field in OPTIONAL_CLIENT_FIELDS:
        if not values[field]:
            values[field] = None
    return values, None


def serialize_client(row):
    return {field: row[field] for field in ("client_id", *CLIENT_FIELDS)}


@clients_bp.get("")
def list_clients():
    rows = get_db().execute(text(
        """SELECT client_id, client_name, contact_name, email, phone
           FROM CLIENT ORDER BY LOWER(client_name), client_id"""
    )).mappings().all()
    return jsonify(clients=[serialize_client(row) for row in rows])


@clients_bp.post("")
def add_client():
    values, error = read_client_values(request.get_json(silent=True))
    if error:
        return jsonify(error=error), 400

    db = get_db()
    result = db.execute(text(
        """INSERT INTO CLIENT (client_name, contact_name, email, phone)
           VALUES (:client_name, :contact_name, :email, :phone)
           RETURNING client_id"""),
        values,
    )
    client_id = result.scalar_one()
    db.commit()
    row = db.execute(text(
        """SELECT client_id, client_name, contact_name, email, phone
           FROM CLIENT WHERE client_id = :client_id"""),
        {"client_id": client_id},
    ).mappings().first()
    return jsonify(client=serialize_client(row), message="Client added successfully."), 201


@clients_bp.put("/<int:client_id>")
def update_client(client_id):
    values, error = read_client_values(request.get_json(silent=True))
    if error:
        return jsonify(error=error), 400

    db = get_db()
    existing = db.execute(text("SELECT client_id FROM CLIENT WHERE client_id = :client_id"), {"client_id": client_id}).first()
    if existing is None:
        return jsonify(error="Client record not found."), 404

    db.execute(text(
        """UPDATE CLIENT
           SET client_name = :client_name,
               contact_name = :contact_name,
               email = :email,
               phone = :phone
           WHERE client_id = :client_id"""),
        {**values, "client_id": client_id},
    )
    db.commit()
    row = db.execute(text(
        """SELECT client_id, client_name, contact_name, email, phone
           FROM CLIENT WHERE client_id = :client_id"""),
        {"client_id": client_id},
    ).mappings().first()
    return jsonify(client=serialize_client(row), message="Client updated successfully.")


@clients_bp.delete("/<int:client_id>")
def delete_client(client_id):
    db = get_db()
    existing = db.execute(text("SELECT client_id FROM CLIENT WHERE client_id = :client_id"), {"client_id": client_id}).first()
    if existing is None:
        return jsonify(error="Client record not found."), 404

    engagement = db.execute(text("SELECT 1 FROM TAX_ENGAGEMENT WHERE client_id = :client_id LIMIT 1"), {"client_id": client_id}).first()
    if engagement is not None:
        return jsonify(
            error="This client cannot be deleted because associated tax engagements exist."
        ), 409

    try:
        db.execute(text("DELETE FROM CLIENT WHERE client_id = :client_id"), {"client_id": client_id})
        db.commit()
    except IntegrityError:
        db.rollback()
        return jsonify(
            error="This client cannot be deleted because associated tax engagements exist."
        ), 409
    return jsonify(message="Client deleted successfully.")
