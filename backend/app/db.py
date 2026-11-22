import sqlite3
from pathlib import Path

from flask import current_app, g
from sqlalchemy import (
    CheckConstraint,
    Column,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    Table,
    Text,
    create_engine,
    event,
    func,
)
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError
from sqlalchemy.pool import NullPool


SCHEMA = """
CREATE TABLE IF NOT EXISTS USERS (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE COLLATE NOCASE,
    password_hash TEXT NOT NULL,
    display_name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS CLIENT (
    client_id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_name TEXT NOT NULL,
    contact_name TEXT,
    email TEXT,
    phone TEXT
);

CREATE TABLE IF NOT EXISTS TAX_ENGAGEMENT (
    engagement_id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id INTEGER NOT NULL,
    tax_year INTEGER NOT NULL,
    return_type TEXT NOT NULL,
    assigned_preparer TEXT NOT NULL,
    engagement_start_date TEXT NOT NULL,
    filing_deadline TEXT NOT NULL,
    engagement_status TEXT NOT NULL DEFAULT 'In Progress'
        CHECK (engagement_status IN ('In Progress', 'Waiting on Client', 'Completed')),
    FOREIGN KEY (client_id) REFERENCES CLIENT (client_id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS REQUIRED_ITEM (
    required_item_id INTEGER PRIMARY KEY AUTOINCREMENT,
    engagement_id INTEGER NOT NULL,
    required_item_description TEXT NOT NULL,
    item_status TEXT NOT NULL DEFAULT 'Outstanding'
        CHECK (item_status IN ('Outstanding', 'Received')),
    FOREIGN KEY (engagement_id) REFERENCES TAX_ENGAGEMENT (engagement_id) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_tax_engagement_client_id
    ON TAX_ENGAGEMENT (client_id);
CREATE INDEX IF NOT EXISTS idx_required_item_engagement_id
    ON REQUIRED_ITEM (engagement_id);
"""


# SQLAlchemy metadata is the shared schema description for Alembic migrations.
metadata = MetaData()

users_table = Table(
    "users",
    metadata,
    Column("user_id", Integer, primary_key=True, autoincrement=True),
    Column("username", Text, nullable=False),
    Column("password_hash", Text, nullable=False),
    Column("display_name", Text, nullable=False),
)
Index("uq_users_username_lower", func.lower(users_table.c.username), unique=True)

client_table = Table(
    "client",
    metadata,
    Column("client_id", Integer, primary_key=True, autoincrement=True),
    Column("client_name", Text, nullable=False),
    Column("contact_name", Text),
    Column("email", Text),
    Column("phone", Text),
)

engagement_table = Table(
    "tax_engagement",
    metadata,
    Column("engagement_id", Integer, primary_key=True, autoincrement=True),
    Column("client_id", Integer, ForeignKey("client.client_id", ondelete="RESTRICT"), nullable=False),
    Column("tax_year", Integer, nullable=False),
    Column("return_type", Text, nullable=False),
    Column("assigned_preparer", Text, nullable=False),
    Column("engagement_start_date", Text, nullable=False),
    Column("filing_deadline", Text, nullable=False),
    Column("engagement_status", Text, nullable=False, server_default="In Progress"),
    CheckConstraint(
        "engagement_status IN ('In Progress', 'Waiting on Client', 'Completed')",
        name="ck_tax_engagement_status",
    ),
)
Index("idx_tax_engagement_client_id", engagement_table.c.client_id)

required_item_table = Table(
    "required_item",
    metadata,
    Column("required_item_id", Integer, primary_key=True, autoincrement=True),
    Column(
        "engagement_id",
        Integer,
        ForeignKey("tax_engagement.engagement_id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("required_item_description", Text, nullable=False),
    Column("item_status", Text, nullable=False, server_default="Outstanding"),
    CheckConstraint(
        "item_status IN ('Outstanding', 'Received')",
        name="ck_required_item_status",
    ),
)
Index("idx_required_item_engagement_id", required_item_table.c.engagement_id)


def normalize_postgresql_url(database_url):
    """Use Psycopg 3 for provider URLs that omit an explicit driver name."""
    try:
        url = make_url(database_url)
    except (ArgumentError, TypeError, ValueError) as error:
        raise RuntimeError("TEM_DATABASE_URL is not a valid PostgreSQL connection URL.") from error

    if url.drivername in {"postgres", "postgresql"}:
        url = url.set(drivername="postgresql+psycopg")
    elif url.drivername != "postgresql+psycopg":
        raise RuntimeError("TEM_DATABASE_URL must use a PostgreSQL connection URL.")
    if not url.host or not url.database:
        raise RuntimeError("TEM_DATABASE_URL must include a PostgreSQL host and database name.")
    placeholder_parts = (url.host, url.database, url.username or "")
    if any(
        marker in part.lower()
        for part in placeholder_parts
        for marker in ("replace-with", "placeholder", "example")
    ):
        raise RuntimeError("TEM_DATABASE_URL must contain real private PostgreSQL connection settings.")
    return url


def create_database_engine(database_url):
    """Create a lazy SQLAlchemy engine; this does not connect to the database."""
    engine_options = {"pool_pre_ping": True}
    if make_url(database_url).get_backend_name() == "sqlite":
        # Releasing a request connection also releases the file handle, which
        # matters for temporary SQLite databases on Windows.
        engine_options["poolclass"] = NullPool
    engine = create_engine(database_url, **engine_options)
    if engine.dialect.name == "sqlite":
        @event.listens_for(engine, "connect")
        def enable_sqlite_foreign_keys(dbapi_connection, _connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys = ON")
            cursor.close()
    return engine


def configure_database(app, postgresql_url=None):
    """Attach the SQLAlchemy connection foundation for the selected backend."""
    if app.config["TEM_ENV"] == "production":
        if not postgresql_url:
            raise RuntimeError(
                "TEM_DATABASE_URL is required when TEM_ENV=production; production cannot use SQLite."
            )
        url = normalize_postgresql_url(postgresql_url)
        app.config["DATABASE_BACKEND"] = "postgresql"
    else:
        # Local development and the existing tests remain on the original SQLite file.
        sqlite_path = Path(app.config["DATABASE"]).resolve().as_posix()
        from sqlalchemy.engine import URL

        url = URL.create("sqlite+pysqlite", database=sqlite_path)
        app.config["DATABASE_BACKEND"] = "sqlite"

    engine = create_database_engine(url)
    app.extensions["tems_database_engine"] = engine
    # Register cleanup for every configured backend. SQLite initialization is
    # separate and remains conditional in init_db below.
    app.teardown_appcontext(close_db)
    return engine


def get_engine():
    """Return the configured SQLAlchemy engine for future cross-database queries."""
    return current_app.extensions["tems_database_engine"]


def get_db():
    if "db" not in g:
        g.db = get_engine().connect()
    return g.db


def close_db(_error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db(app):
    # Keep the established SQLite schema initialization behavior local. This
    # path is only used for development; production schema is managed by Alembic.
    if app.config.get("DATABASE_BACKEND") == "sqlite":
        database_path = Path(app.config["DATABASE"])
        database_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(database_path)
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.executescript(SCHEMA)
            connection.commit()
        finally:
            connection.close()
