import os
from pathlib import Path

from flask import Flask, jsonify

from .auth import auth_bp
from .clients import clients_bp
from .db import init_db
from .engagements import engagements_bp


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("TEM_SECRET_KEY", "***REMOVED***"),
        DATABASE=os.environ.get(
            "TEM_DATABASE",
            str(Path(__file__).resolve().parents[1] / "instance" / "tax_engagement.db"),
        ),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
    )
    if test_config:
        app.config.update(test_config)

    Path(app.config["DATABASE"]).parent.mkdir(parents=True, exist_ok=True)
    init_db(app)
    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(clients_bp, url_prefix="/api/clients")
    app.register_blueprint(engagements_bp, url_prefix="/api/engagements")

    @app.get("/api/health")
    def health():
        return jsonify(status="ok", service="Tax Engagement Management System API")

    return app
