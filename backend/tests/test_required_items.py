import tempfile
import unittest
from pathlib import Path
from sqlalchemy import text

from app.db import get_db
from test_support import create_test_app, login_with_csrf, TEST_DEMO_ACCOUNTS


class RequiredItemTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        database = str(Path(self.temp_dir.name) / "test_required_items.db")
        self.app = create_test_app(database)
        self.client = self.app.test_client()
        response = login_with_csrf(self.client, *TEST_DEMO_ACCOUNTS[0][:2])
        self.assertEqual(response.status_code, 200, response.get_json())

        client_response = self.client.post(
            "/api/clients",
            json={
                "client_name": "Required Item Test Client",
                "contact_name": "Taylor Example",
                "email": "taylor@example.test",
                "phone": "555-0122",
            },
        )
        self.assertEqual(client_response.status_code, 201, client_response.get_json())
        self.client_id = client_response.get_json()["client"]["client_id"]

        engagement_response = self.client.post(
            "/api/engagements",
            json={
                "client_id": self.client_id,
                "tax_year": "2026",
                "return_type": "Individual (1040)",
                "assigned_preparer": "Serena Parke",
                "engagement_start_date": "2026-01-15",
                "filing_deadline": "2026-04-15",
            },
        )
        self.assertEqual(engagement_response.status_code, 201, engagement_response.get_json())
        self.engagement_id = engagement_response.get_json()["engagement"]["engagement_id"]

    def tearDown(self):
        self.temp_dir.cleanup()

    def add_item(self, description="Signed organizer"):
        return self.client.post(
            "/api/required-items",
            json={
                "engagement_id": self.engagement_id,
                "required_item_description": description,
            },
        )

    def create_another_engagement(self):
        response = self.client.post(
            "/api/engagements",
            json={
                "client_id": self.client_id,
                "tax_year": "2025",
                "return_type": "Partnership (1065)",
                "assigned_preparer": "Serena Parke",
                "engagement_start_date": "2025-01-15",
                "filing_deadline": "2025-04-15",
            },
        )
        self.assertEqual(response.status_code, 201, response.get_json())
        return response.get_json()["engagement"]["engagement_id"]

    def test_add_required_item_links_engagement_and_defaults_to_outstanding(self):
        response = self.add_item("Prior-year tax return")
        self.assertEqual(response.status_code, 201, response.get_json())
        item = response.get_json()["required_item"]
        self.assertGreater(item["required_item_id"], 0)
        self.assertEqual(item["engagement_id"], self.engagement_id)
        self.assertEqual(item["client_id"], self.client_id)
        self.assertEqual(item["client_name"], "Required Item Test Client")
        self.assertEqual(item["tax_year"], 2026)
        self.assertEqual(item["return_type"], "Individual (1040)")
        self.assertEqual(item["required_item_description"], "Prior-year tax return")
        self.assertEqual(item["item_status"], "Outstanding")

        with self.app.app_context():
            saved = get_db().execute(text(
                "SELECT engagement_id, required_item_description, item_status "
                "FROM REQUIRED_ITEM WHERE required_item_id = :required_item_id"),
                {"required_item_id": item["required_item_id"]},
            ).first()
        self.assertEqual(tuple(saved), (self.engagement_id, "Prior-year tax return", "Outstanding"))

    def test_add_required_item_requires_description_and_existing_engagement(self):
        for description in ("", "   ", None, 42):
            with self.subTest(description=description):
                response = self.client.post(
                    "/api/required-items",
                    json={"engagement_id": self.engagement_id, "required_item_description": description},
                )
                self.assertEqual(response.status_code, 400)

        missing_engagement = self.client.post(
            "/api/required-items",
            json={"required_item_description": "Signed organizer"},
        )
        self.assertEqual(missing_engagement.status_code, 400)
        unknown_engagement = self.client.post(
            "/api/required-items",
            json={"engagement_id": 999999, "required_item_description": "Signed organizer"},
        )
        self.assertEqual(unknown_engagement.status_code, 404)

    def test_all_predefined_options_and_custom_items_can_be_added(self):
        predefined_items = (
            "Driver's License",
            "Social Security Cards",
            "Prior Year Tax Return",
            "Dependent Information",
            "W-2",
            "1099-NEC",
            "1099-MISC",
            "1099-INT",
            "1099-DIV",
            "1099-R",
            "SSA-1099",
            "1099-K",
            "Mortgage Interest Statement (1098)",
            "Property Tax Statement",
            "Charitable Contribution Records",
            "Medical Expense Records",
            "Business Income Records",
            "Business Expense Records",
            "Mileage Log",
            "Form 1098-T",
            "Student Loan Interest Statement (1098-E)",
            "Estimated Tax Payments",
            "Health Insurance Information",
        )
        for description in (*predefined_items, "Custom signed authorization"):
            with self.subTest(description=description):
                response = self.add_item(description)
                self.assertEqual(response.status_code, 201, response.get_json())
                saved = response.get_json()["required_item"]
                self.assertEqual(saved["required_item_description"], description)
                self.assertEqual(saved["item_status"], "Outstanding")

    def test_duplicate_description_is_blocked_for_same_engagement_but_allowed_for_another(self):
        first = self.add_item("  W-2  ")
        self.assertEqual(first.status_code, 201, first.get_json())

        duplicate = self.add_item(" w-2 ")
        self.assertEqual(duplicate.status_code, 409)
        self.assertIn("already listed", duplicate.get_json()["error"].lower())
        current_items = self.client.get(
            f"/api/required-items?engagement_id={self.engagement_id}"
        ).get_json()["required_items"]
        self.assertEqual(len(current_items), 1)

        other_engagement_id = self.create_another_engagement()
        allowed = self.client.post(
            "/api/required-items",
            json={
                "engagement_id": other_engagement_id,
                "required_item_description": "w-2",
            },
        )
        self.assertEqual(allowed.status_code, 201, allowed.get_json())
        saved = allowed.get_json()["required_item"]
        self.assertEqual(saved["engagement_id"], other_engagement_id)
        self.assertEqual(saved["required_item_description"], "w-2")
        self.assertEqual(saved["item_status"], "Outstanding")

    def test_status_updates_persist_and_outstanding_view_excludes_received(self):
        received_response = self.add_item("Prior-year tax return")
        outstanding_response = self.add_item("Proof of estimated payments")
        self.assertEqual(received_response.status_code, 201)
        self.assertEqual(outstanding_response.status_code, 201)
        received_item = received_response.get_json()["required_item"]
        outstanding_item = outstanding_response.get_json()["required_item"]

        update = self.client.patch(
            f"/api/required-items/{received_item['required_item_id']}/status",
            json={"item_status": "Received"},
        )
        self.assertEqual(update.status_code, 200, update.get_json())
        self.assertEqual(update.get_json()["required_item"]["item_status"], "Received")

        engagement_items = self.client.get(
            f"/api/required-items?engagement_id={self.engagement_id}"
        ).get_json()["required_items"]
        refreshed_received = next(
            item for item in engagement_items
            if item["required_item_id"] == received_item["required_item_id"]
        )
        self.assertEqual(refreshed_received["item_status"], "Received")

        outstanding = self.client.get("/api/required-items/outstanding")
        self.assertEqual(outstanding.status_code, 200)
        rows = outstanding.get_json()["required_items"]
        self.assertEqual([row["required_item_id"] for row in rows], [outstanding_item["required_item_id"]])
        self.assertEqual(rows[0]["item_status"], "Outstanding")
        self.assertEqual(rows[0]["client_name"], "Required Item Test Client")
        self.assertEqual(rows[0]["engagement_id"], self.engagement_id)
        self.assertEqual(rows[0]["tax_year"], 2026)
        self.assertEqual(rows[0]["return_type"], "Individual (1040)")

        with self.app.app_context():
            saved_status = get_db().execute(text(
                "SELECT item_status FROM REQUIRED_ITEM WHERE required_item_id = :required_item_id"),
                {"required_item_id": received_item["required_item_id"]},
            ).mappings().first()["item_status"]
        self.assertEqual(saved_status, "Received")

    def test_invalid_status_keeps_existing_status(self):
        item = self.add_item().get_json()["required_item"]
        response = self.client.patch(
            f"/api/required-items/{item['required_item_id']}/status",
            json={"item_status": "Pending"},
        )
        self.assertEqual(response.status_code, 400)
        current = self.client.get(
            f"/api/required-items?engagement_id={self.engagement_id}"
        ).get_json()["required_items"][0]
        self.assertEqual(current["item_status"], "Outstanding")

    def test_delete_required_item_removes_only_item_and_preserves_client_engagement(self):
        deleted_item = self.add_item("Outstanding item to delete").get_json()["required_item"]
        retained_item = self.add_item("Received item to retain").get_json()["required_item"]
        received_update = self.client.patch(
            f"/api/required-items/{retained_item['required_item_id']}/status",
            json={"item_status": "Received"},
        )
        self.assertEqual(received_update.status_code, 200)

        response = self.client.delete(f"/api/required-items/{deleted_item['required_item_id']}")
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertIn("deleted successfully", response.get_json()["message"].lower())

        listed_items = self.client.get(
            f"/api/required-items?engagement_id={self.engagement_id}"
        ).get_json()["required_items"]
        self.assertEqual(
            [item["required_item_id"] for item in listed_items],
            [retained_item["required_item_id"]],
        )
        outstanding_items = self.client.get("/api/required-items/outstanding").get_json()["required_items"]
        self.assertNotIn(deleted_item["required_item_id"], [item["required_item_id"] for item in outstanding_items])
        self.assertEqual(outstanding_items, [])

        with self.app.app_context():
            db = get_db()
            self.assertEqual(db.execute(text("SELECT COUNT(*) FROM CLIENT WHERE client_id = :client_id"), {"client_id": self.client_id}).scalar_one(), 1)
            self.assertEqual(db.execute(text("SELECT COUNT(*) FROM TAX_ENGAGEMENT WHERE engagement_id = :engagement_id"), {"engagement_id": self.engagement_id}).scalar_one(), 1)
            self.assertEqual(db.execute(text("SELECT COUNT(*) FROM REQUIRED_ITEM WHERE required_item_id = :required_item_id"), {"required_item_id": deleted_item["required_item_id"]}).scalar_one(), 0)
            self.assertEqual(db.execute(text("SELECT COUNT(*) FROM REQUIRED_ITEM WHERE required_item_id = :required_item_id"), {"required_item_id": retained_item["required_item_id"]}).scalar_one(), 1)

        missing = self.client.delete(f"/api/required-items/{deleted_item['required_item_id']}")
        self.assertEqual(missing.status_code, 404)

    def test_required_item_operations_require_authentication(self):
        self.client.post("/api/auth/logout")
        self.assertEqual(
            self.client.get(f"/api/required-items?engagement_id={self.engagement_id}").status_code,
            401,
        )
        self.assertEqual(self.client.get("/api/required-items/outstanding").status_code, 401)
        self.assertEqual(
            self.client.post(
                "/api/required-items",
                json={"engagement_id": self.engagement_id, "required_item_description": "Organizer"},
            ).status_code,
            401,
        )
        self.assertEqual(
            self.client.patch("/api/required-items/1/status", json={"item_status": "Received"}).status_code,
            401,
        )
        self.assertEqual(self.client.delete("/api/required-items/1").status_code, 401)


if __name__ == "__main__":
    unittest.main()
