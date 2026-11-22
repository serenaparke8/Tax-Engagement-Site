import os
import secrets
import hmac
from pathlib import Path

from flask import Flask, jsonify, request, session

from .auth import auth_bp
from .clients import clients_bp
from .db import configure_database, init_db
from .dashboard import dashboard_bp
from .deadlines import deadlines_bp
from .engagements import engagements_bp
from .required_items import required_items_bp
from .reports import reports_bp


def load_local_environment():
    """Load simple KEY=VALUE entries from backend/.env without overriding OS values."""
    env_file = Path(__file__).resolve().parents[1] / ".env"
    if not env_file.is_file():
        return
    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        name = name.strip()
        value = value.strip()
        if not name.isidentifier():
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        os.environ.setdefault(name, value)


def configured_demo_accounts():
    accounts = []
    for index in (1, 2):
        prefix = f"TEM_DEMO_ACCOUNT_{index}_"
        username = os.environ.get(prefix + "USERNAME", "").strip()
        password = os.environ.get(prefix + "PASSWORD", "")
        display_name = os.environ.get(prefix + "DISPLAY_NAME", "").strip()
        if not any((username, password, display_name)):
            continue
        if not all((username, password, display_name)):
            raise RuntimeError(f"All {prefix}USERNAME, PASSWORD, and DISPLAY_NAME values are required.")
        accounts.append((username, password, display_name))
    return tuple(accounts)


def valid_production_secret(value):
    if not isinstance(value, str):
        return False
    normalized = value.strip().lower()
    return len(normalized) >= 32 and not any(
        marker in normalized for marker in ("replace-with", "placeholder", "change-me", "example")
    )


def create_app(test_config=None):
    load_local_environment()
    environment = os.environ.get("TEM_ENV", "development").strip().lower()
    configured_secret = os.environ.get("TEM_SECRET_KEY", "").strip()

    app = Flask(__name__)
    app.config.from_mapping(
        SECRET_KEY=configured_secret or secrets.token_urlsafe(48),
        TEM_ENV=environment,
        # Read seed credentials only in local development. Production users are
        # provisioned explicitly and never loaded from request configuration.
        DEMO_ACCOUNTS=(configured_demo_accounts() if environment != "production" else ()),
        TEM_DATABASE_URL=os.environ.get("TEM_DATABASE_URL"),
        DATABASE=os.environ.get(
            "TEM_DATABASE",
            str(Path(__file__).resolve().parents[1] / "instance" / "tax_engagement.db"),
        ),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=(environment == "production"),
        CSRF_PROTECTION_ENABLED=True,
    )
    if test_config:
        app.config.update(test_config)

    app.config["TEM_ENV"] = str(app.config.get("TEM_ENV", "development")).strip().lower()
    if app.config.get("TEM_ENV") == "production":
        secret_key = app.config.get("SECRET_KEY")
        if not valid_production_secret(secret_key):
            raise RuntimeError("A unique Flask SECRET_KEY of at least 32 characters is required in production.")
        if not app.config.get("TEM_DATABASE_URL"):
            raise RuntimeError(
                "TEM_DATABASE_URL is required when TEM_ENV=production; production cannot use SQLite."
            )
    if app.config.get("TEM_ENV") == "production":
        app.config["SESSION_COOKIE_SECURE"] = True

    @app.before_request
    def protect_state_changing_requests():
        if not app.config.get("CSRF_PROTECTION_ENABLED") or request.method in {"GET", "HEAD", "OPTIONS", "TRACE"}:
            return None
        requires_token = request.endpoint in {"auth.login", "auth.logout"} or "user_id" in session
        if not requires_token:
            return None
        expected = session.get("csrf_token", "")
        supplied = request.headers.get("X-CSRF-Token", "")
        if not expected or not supplied or not hmac.compare_digest(expected, supplied):
            return jsonify(error="The request could not be verified. Refresh the page and try again."), 403
        return None

    postgresql_url = app.config.pop("TEM_DATABASE_URL", None)
    configure_database(app, postgresql_url=postgresql_url)
    if app.config["DATABASE_BACKEND"] == "sqlite":
        Path(app.config["DATABASE"]).parent.mkdir(parents=True, exist_ok=True)
        init_db(app)
    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(clients_bp, url_prefix="/api/clients")
    app.register_blueprint(dashboard_bp, url_prefix="/api/dashboard")
    app.register_blueprint(engagements_bp, url_prefix="/api/engagements")
    app.register_blueprint(deadlines_bp, url_prefix="/api/deadlines")
    app.register_blueprint(reports_bp, url_prefix="/api/reports")
    app.register_blueprint(required_items_bp, url_prefix="/api/required-items")

    @app.get("/api/health")
    def health():
        return jsonify(status="ok", service="Tax Engagement Management System API")

    return app
