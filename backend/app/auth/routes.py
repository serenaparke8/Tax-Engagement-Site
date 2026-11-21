import secrets

from flask import current_app, jsonify, request, session
from werkzeug.security import check_password_hash, generate_password_hash

from ..db import get_db
from . import auth_bp


def seed_demo_accounts(db):
    count = db.execute("SELECT COUNT(*) FROM USERS").fetchone()[0]
    if count == 0:
        accounts = current_app.config.get("DEMO_ACCOUNTS", ())
        if not accounts:
            return
        db.executemany(
            "INSERT INTO USERS (username, password_hash, display_name) VALUES (?, ?, ?)",
            [
                (username, generate_password_hash(password), display_name)
                for username, password, display_name in accounts
            ],
        )
        db.commit()


@auth_bp.before_app_request
def ensure_demo_accounts():
    seed_demo_accounts(get_db())


@auth_bp.post("/login")
def login():
    payload = request.get_json(silent=True) or {}
    username = payload.get("username", "").strip()
    password = payload.get("password", "")
    if not username or not password:
        return jsonify(error="Enter both your username and password."), 400

    user = get_db().execute(
        "SELECT user_id, username, password_hash, display_name FROM USERS WHERE username = ?",
        (username,),
    ).fetchone()
    if user is None or not check_password_hash(user["password_hash"], password):
        return jsonify(error="The username or password is incorrect."), 401

    session.clear()
    session["user_id"] = user["user_id"]
    session["username"] = user["username"]
    session["display_name"] = user["display_name"]
    session["csrf_token"] = secrets.token_urlsafe(32)
    return jsonify(
        user={"username": user["username"], "display_name": user["display_name"]},
        csrf_token=session["csrf_token"],
    )


@auth_bp.get("/csrf")
def csrf_token():
    token = session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["csrf_token"] = token
    return jsonify(csrf_token=token)


@auth_bp.get("/me")
def current_user():
    if "user_id" not in session:
        return jsonify(user=None)
    return jsonify(
        user={"username": session["username"], "display_name": session["display_name"]}
    )


@auth_bp.post("/logout")
def logout():
    session.clear()
    session["csrf_token"] = secrets.token_urlsafe(32)
    return jsonify(status="signed_out", csrf_token=session["csrf_token"])
