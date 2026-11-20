import sqlite3

from flask import current_app, g


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


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(_error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db(app):
    app.teardown_appcontext(close_db)
    with app.app_context():
        db = get_db()
        db.executescript(SCHEMA)
        db.commit()
