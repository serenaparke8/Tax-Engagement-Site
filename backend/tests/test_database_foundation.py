import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from sqlalchemy import text
from sqlalchemy import inspect

from app import create_app
from app.db import get_db, get_engine


class DatabaseFoundationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def create_isolated_app(self, config):
        with patch("app.load_local_environment"):
            with patch.dict(os.environ, {"TEM_ENV": "development"}, clear=True):
                return create_app(config)

    def test_local_configuration_keeps_sqlite_default_and_foreign_keys(self):
        database = self.temp_path / "local_test.db"
        app = self.create_isolated_app({
            "TESTING": True,
            "SECRET_KEY": "unit-test-only-signing-key",
            "DATABASE": str(database),
            "DEMO_ACCOUNTS": (),
        })

        self.assertEqual(app.config["DATABASE_BACKEND"], "sqlite")
        self.assertEqual(get_engine_from_app(app).dialect.name, "sqlite")
        self.assertTrue(database.is_file())
        with app.app_context():
            self.assertEqual(get_db().exec_driver_sql("PRAGMA foreign_keys").scalar_one(), 1)
            self.assertEqual(get_db().execute(text("SELECT COUNT(*) FROM CLIENT")).scalar_one(), 0)
            with get_engine().connect() as connection:
                self.assertEqual(connection.exec_driver_sql("PRAGMA foreign_keys").scalar(), 1)
        get_engine_from_app(app).dispose()

    def test_sqlite_schema_has_the_four_approved_tables_and_constraints(self):
        app = self.create_isolated_app({
            "TESTING": True,
            "SECRET_KEY": "unit-test-only-signing-key",
            "DATABASE": str(self.temp_path / "schema_test.db"),
            "DEMO_ACCOUNTS": (),
        })
        engine = get_engine_from_app(app)
        schema = inspect(engine)

        self.assertEqual(
            set(schema.get_table_names()),
            {"USERS", "CLIENT", "TAX_ENGAGEMENT", "REQUIRED_ITEM"},
        )
        expected_columns = {
            "USERS": {"user_id", "username", "password_hash", "display_name"},
            "CLIENT": {"client_id", "client_name", "contact_name", "email", "phone"},
            "TAX_ENGAGEMENT": {
                "engagement_id", "client_id", "tax_year", "return_type",
                "assigned_preparer", "engagement_start_date", "filing_deadline",
                "engagement_status",
            },
            "REQUIRED_ITEM": {
                "required_item_id", "engagement_id", "required_item_description", "item_status",
            },
        }
        expected_primary_keys = {
            "USERS": "user_id",
            "CLIENT": "client_id",
            "TAX_ENGAGEMENT": "engagement_id",
            "REQUIRED_ITEM": "required_item_id",
        }
        expected_types = {
            "USERS": {"user_id": "INTEGER", "username": "TEXT", "password_hash": "TEXT", "display_name": "TEXT"},
            "CLIENT": {"client_id": "INTEGER", "client_name": "TEXT", "contact_name": "TEXT", "email": "TEXT", "phone": "TEXT"},
            "TAX_ENGAGEMENT": {
                "engagement_id": "INTEGER", "client_id": "INTEGER", "tax_year": "INTEGER",
                "return_type": "TEXT", "assigned_preparer": "TEXT",
                "engagement_start_date": "TEXT", "filing_deadline": "TEXT",
                "engagement_status": "TEXT",
            },
            "REQUIRED_ITEM": {
                "required_item_id": "INTEGER", "engagement_id": "INTEGER",
                "required_item_description": "TEXT", "item_status": "TEXT",
            },
        }
        for table, names in expected_columns.items():
            columns = schema.get_columns(table)
            self.assertEqual({column["name"] for column in columns}, names)
            self.assertEqual(
                {column["name"]: str(column["type"]).upper() for column in columns},
                expected_types[table],
            )
            self.assertEqual(
                schema.get_pk_constraint(table)["constrained_columns"],
                [expected_primary_keys[table]],
            )

        self.assertEqual(schema.get_unique_constraints("USERS")[0]["column_names"], ["username"])
        self.assertEqual(schema.get_columns("TAX_ENGAGEMENT")[-1]["default"], "'In Progress'")
        self.assertEqual(schema.get_columns("REQUIRED_ITEM")[-1]["default"], "'Outstanding'")
        self.assertEqual(schema.get_foreign_keys("TAX_ENGAGEMENT")[0]["referred_table"], "CLIENT")
        self.assertEqual(schema.get_foreign_keys("TAX_ENGAGEMENT")[0]["options"].get("ondelete"), "RESTRICT")
        self.assertEqual(schema.get_foreign_keys("REQUIRED_ITEM")[0]["referred_table"], "TAX_ENGAGEMENT")
        self.assertEqual(schema.get_foreign_keys("REQUIRED_ITEM")[0]["options"].get("ondelete"), "RESTRICT")
        self.assertEqual(schema.get_indexes("TAX_ENGAGEMENT")[0]["name"], "idx_tax_engagement_client_id")
        self.assertEqual(schema.get_indexes("REQUIRED_ITEM")[0]["name"], "idx_required_item_engagement_id")
        self.assertIn("Waiting on Client", schema.get_check_constraints("TAX_ENGAGEMENT")[0]["sqltext"])
        self.assertIn("Received", schema.get_check_constraints("REQUIRED_ITEM")[0]["sqltext"])
        engine.dispose()

    def test_production_rejects_missing_postgresql_url_before_file_creation(self):
        database = self.temp_path / "must_not_be_created.db"
        with self.assertRaisesRegex(RuntimeError, "TEM_DATABASE_URL is required"):
            self.create_isolated_app({
                "TESTING": True,
                "TEM_ENV": "production",
                "SECRET_KEY": "s" * 48,
                "TEM_DATABASE_URL": None,
                "DATABASE": str(database),
                "DEMO_ACCOUNTS": (),
            })
        self.assertFalse(database.exists())

    def test_production_configures_postgresql_engine_without_connecting_or_sqlite_fallback(self):
        database = self.temp_path / "must_not_be_created.db"
        app = self.create_isolated_app({
            "TESTING": True,
            "TEM_ENV": "production",
            "SECRET_KEY": "s" * 48,
            "TEM_DATABASE_URL": "postgresql+psycopg://test_user@127.0.0.1/test_database",
            "DATABASE": str(database),
            "DEMO_ACCOUNTS": (),
        })

        engine = get_engine_from_app(app)
        self.assertEqual(app.config["DATABASE_BACKEND"], "postgresql")
        self.assertEqual(engine.dialect.name, "postgresql")
        self.assertFalse(database.exists())
        engine.dispose()

    def test_postgresql_request_connection_is_closed_at_request_teardown(self):
        app = self.create_isolated_app({
            "TESTING": True,
            "TEM_ENV": "production",
            "SECRET_KEY": "s" * 48,
            "TEM_DATABASE_URL": "postgresql+psycopg://test_user@127.0.0.1/test_database",
            "DATABASE": str(self.temp_path / "must_not_be_created.db"),
            "DEMO_ACCOUNTS": (),
        })
        original_engine = get_engine_from_app(app)

        class FakeConnection:
            closed = False

            def close(self):
                self.closed = True

        class FakeEngine:
            def __init__(self):
                self.connection = FakeConnection()

            def connect(self):
                return self.connection

            def dispose(self):
                pass

        fake_engine = FakeEngine()
        app.extensions["tems_database_engine"] = fake_engine
        try:
            with app.test_request_context("/api/health"):
                self.assertIs(get_db(), fake_engine.connection)
                self.assertFalse(fake_engine.connection.closed)
            self.assertTrue(fake_engine.connection.closed)
            self.assertFalse((self.temp_path / "must_not_be_created.db").exists())
        finally:
            original_engine.dispose()

    def test_postgresql_request_does_not_seed_accounts_automatically(self):
        app = self.create_isolated_app({
            "TESTING": True,
            "TEM_ENV": "production",
            "SECRET_KEY": "s" * 48,
            "TEM_DATABASE_URL": "postgresql+psycopg://test_user@127.0.0.1/test_database",
            "DATABASE": str(self.temp_path / "must_not_be_created.db"),
            "DEMO_ACCOUNTS": (("test-user", "test-password", "Test User"),),
        })
        original_engine = get_engine_from_app(app)

        class NoConnectionEngine:
            def connect(self):
                raise AssertionError("A health request must not seed production accounts.")

            def dispose(self):
                pass

        app.extensions["tems_database_engine"] = NoConnectionEngine()
        try:
            response = app.test_client().get("/api/health")
            self.assertEqual(response.status_code, 200)
            self.assertFalse((self.temp_path / "must_not_be_created.db").exists())
        finally:
            original_engine.dispose()


def get_engine_from_app(app):
    return app.extensions["tems_database_engine"]


if __name__ == "__main__":
    unittest.main()
