import sqlite3
import tempfile
import unittest
from pathlib import Path

from app import create_app
from app.auth.routes import DEMO_ACCOUNTS
from app.db import get_db


class ClientManagementTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        database = str(Path(self.temp_dir.name) / "test_tax_engagement.db")
        self.app = create_app({"TESTING": True, "SECRET_KEY": "test-secret", "DATABASE": database})
        self.client = self.app.test_client()

    def tearDown(self):
        self.temp_dir.cleanup()

    def login(self, username, password):
        response = self.client.post(
            "/api/auth/login", json={"username": username, "password": password}
        )
        self.assertEqual(response.status_code, 200, response.get_json())

    def add_client(self, **overrides):
        values = {
            "client_name": "Northwind Design",
            "contact_name": "Taylor Reed",
            "email": "taylor@example.test",
            "phone": "555-0100",
        }
        values.update(overrides)
        return self.client.post("/api/clients", json=values)

    def test_client_operations_require_authentication(self):
        self.assertEqual(self.client.get("/api/clients").status_code, 401)
        self.assertEqual(self.client.post("/api/clients", json={"client_name": "Example"}).status_code, 401)
        self.assertEqual(self.client.put("/api/clients/1", json={"client_name": "Example"}).status_code, 401)
        self.assertEqual(self.client.delete("/api/clients/1").status_code, 401)

    def test_add_client_validates_and_persists_fields(self):
        self.login(*DEMO_ACCOUNTS[0][:2])
        response = self.add_client()
        self.assertEqual(response.status_code, 201, response.get_json())
        record = response.get_json()["client"]
        self.assertGreater(record["client_id"], 0)
        self.assertEqual(record["client_name"], "Northwind Design")
        self.assertEqual(record["contact_name"], "Taylor Reed")
        self.assertEqual(record["email"], "taylor@example.test")
        self.assertEqual(record["phone"], "555-0100")
        self.assertEqual(len(self.client.get("/api/clients").get_json()["clients"]), 1)

    def test_client_name_is_required(self):
        self.login(*DEMO_ACCOUNTS[0][:2])
        for payload in (
            {"contact_name": "Taylor Reed"},
            {"client_name": "  "},
        ):
            with self.subTest(payload=payload):
                response = self.client.post("/api/clients", json=payload)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.get_json()["error"], "Client name is required.")
        self.assertEqual(self.client.get("/api/clients").get_json()["clients"], [])

    def test_update_existing_client(self):
        self.login(*DEMO_ACCOUNTS[0][:2])
        client_id = self.add_client().get_json()["client"]["client_id"]
        response = self.client.put(
            f"/api/clients/{client_id}",
            json={
                "client_name": "Northwind Studio",
                "contact_name": "Morgan Reed",
                "email": "morgan@example.test",
                "phone": "555-0199",
            },
        )
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(response.get_json()["message"], "Client updated successfully.")
        self.assertEqual(self.client.get("/api/clients").get_json()["clients"][0]["client_name"], "Northwind Studio")

    def test_delete_client_without_engagement(self):
        self.login(*DEMO_ACCOUNTS[0][:2])
        client_id = self.add_client().get_json()["client"]["client_id"]
        response = self.client.delete(f"/api/clients/{client_id}")
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(self.client.get("/api/clients").get_json()["clients"], [])

    def test_delete_client_with_engagement_is_blocked_without_cascade(self):
        self.login(*DEMO_ACCOUNTS[0][:2])
        client_id = self.add_client().get_json()["client"]["client_id"]
        with self.app.app_context():
            db = get_db()
            db.execute(
                """INSERT INTO TAX_ENGAGEMENT
                   (client_id, tax_year, return_type, assigned_preparer,
                    engagement_start_date, filing_deadline)
                   VALUES (?, 2026, 'Individual', 'Serena Parke', '2026-01-01', '2026-04-15')""",
                (client_id,),
            )
            db.commit()

        response = self.client.delete(f"/api/clients/{client_id}")
        self.assertEqual(response.status_code, 409)
        self.assertIn("associated tax engagements exist", response.get_json()["error"])
        with self.app.app_context():
            self.assertIsNotNone(get_db().execute("SELECT 1 FROM CLIENT WHERE client_id = ?", (client_id,)).fetchone())
            self.assertEqual(get_db().execute("SELECT COUNT(*) FROM TAX_ENGAGEMENT WHERE client_id = ?", (client_id,)).fetchone()[0], 1)

    def test_both_demo_accounts_can_sign_in_and_out(self):
        for username, password, _display_name in DEMO_ACCOUNTS:
            with self.subTest(username=username):
                self.login(username, password)
                self.assertEqual(self.client.get("/api/auth/me").get_json()["user"]["username"], username)
                self.assertEqual(self.client.post("/api/auth/logout").status_code, 200)
                self.assertIsNone(self.client.get("/api/auth/me").get_json()["user"])


if __name__ == "__main__":
    unittest.main()
