import tempfile
import unittest
from pathlib import Path
from sqlalchemy import text

from app.db import get_db
from test_support import create_test_app, login_with_csrf, TEST_DEMO_ACCOUNTS


class ClientManagementTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        database = str(Path(self.temp_dir.name) / "test_tax_engagement.db")
        self.app = create_test_app(database)
        self.client = self.app.test_client()

    def tearDown(self):
        self.temp_dir.cleanup()

    def login(self, username, password):
        response = login_with_csrf(self.client, username, password)
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
        self.login(*TEST_DEMO_ACCOUNTS[0][:2])
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
        self.login(*TEST_DEMO_ACCOUNTS[0][:2])
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
        self.login(*TEST_DEMO_ACCOUNTS[0][:2])
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
        self.login(*TEST_DEMO_ACCOUNTS[0][:2])
        client_id = self.add_client().get_json()["client"]["client_id"]
        response = self.client.delete(f"/api/clients/{client_id}")
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(self.client.get("/api/clients").get_json()["clients"], [])

    def test_delete_client_with_engagement_is_blocked_without_cascade(self):
        self.login(*TEST_DEMO_ACCOUNTS[0][:2])
        client_id = self.add_client().get_json()["client"]["client_id"]
        with self.app.app_context():
            db = get_db()
            db.execute(text(
                """INSERT INTO TAX_ENGAGEMENT
                   (client_id, tax_year, return_type, assigned_preparer,
                    engagement_start_date, filing_deadline)
                   VALUES (:client_id, 2026, 'Individual', 'Serena Parke', '2026-01-01', '2026-04-15')"""),
                {"client_id": client_id},
            )
            db.commit()

        response = self.client.delete(f"/api/clients/{client_id}")
        self.assertEqual(response.status_code, 409)
        self.assertIn("associated tax engagements exist", response.get_json()["error"])
        with self.app.app_context():
            self.assertIsNotNone(get_db().execute(text("SELECT 1 FROM CLIENT WHERE client_id = :client_id"), {"client_id": client_id}).first())
            self.assertEqual(get_db().execute(text("SELECT COUNT(*) FROM TAX_ENGAGEMENT WHERE client_id = :client_id"), {"client_id": client_id}).scalar_one(), 1)

    def test_both_demo_accounts_can_sign_in_and_out(self):
        for username, password, _display_name in TEST_DEMO_ACCOUNTS:
            with self.subTest(username=username):
                self.login(username, password)
                self.assertEqual(self.client.get("/api/auth/me").get_json()["user"]["username"], username)
                self.assertEqual(self.client.post("/api/auth/logout").status_code, 200)
                self.assertIsNone(self.client.get("/api/auth/me").get_json()["user"])

    def test_login_username_lookup_remains_case_insensitive(self):
        username, password, _display_name = TEST_DEMO_ACCOUNTS[0]
        response = login_with_csrf(self.client, username.upper(), password)
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(self.client.get("/api/auth/me").get_json()["user"]["username"], username)


if __name__ == "__main__":
    unittest.main()
