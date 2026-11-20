import tempfile
import unittest
from pathlib import Path

from app import create_app
from app.auth.routes import DEMO_ACCOUNTS


class EngagementManagementTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        database = str(Path(self.temp_dir.name) / "test_tax_engagement.db")
        self.app = create_app({"TESTING": True, "SECRET_KEY": "test-secret", "DATABASE": database})
        self.client = self.app.test_client()
        response = self.client.post(
            "/api/auth/login",
            json={"username": DEMO_ACCOUNTS[0][0], "password": DEMO_ACCOUNTS[0][1]},
        )
        self.assertEqual(response.status_code, 200, response.get_json())
        response = self.client.post(
            "/api/clients",
            json={
                "client_name": "Engagement Test Client",
                "contact_name": "Alex Morgan",
                "email": "alex@example.test",
                "phone": "555-0110",
            },
        )
        self.assertEqual(response.status_code, 201, response.get_json())
        self.client_id = response.get_json()["client"]["client_id"]

    def tearDown(self):
        self.temp_dir.cleanup()

    def engagement_values(self, **overrides):
        values = {
            "client_id": self.client_id,
            "tax_year": "2026",
            "return_type": "Individual",
            "assigned_preparer": "Serena Parke",
            "engagement_start_date": "2026-01-15",
            "filing_deadline": "2026-04-15",
        }
        values.update(overrides)
        return values

    def create_engagement(self, **overrides):
        return self.client.post("/api/engagements", json=self.engagement_values(**overrides))

    def test_create_engagement_links_existing_client_and_defaults_status(self):
        response = self.create_engagement()
        self.assertEqual(response.status_code, 201, response.get_json())
        engagement = response.get_json()["engagement"]
        self.assertGreater(engagement["engagement_id"], 0)
        self.assertEqual(engagement["client_id"], self.client_id)
        self.assertEqual(engagement["client_name"], "Engagement Test Client")
        self.assertEqual(engagement["engagement_status"], "In Progress")
        listed = self.client.get("/api/engagements?q=Engagement%20Test").get_json()["engagements"]
        self.assertEqual(len(listed), 1)
        self.assertEqual(listed[0]["engagement_id"], engagement["engagement_id"])

    def test_return_type_options_and_tax_year_values_persist_on_create_and_update(self):
        return_types = (
            "Individual (1040)",
            "Partnership (1065)",
            "S Corporation (1120-S)",
            "C Corporation (1120)",
            "Trust / Estate (1041)",
            "Gift Tax (709)",
            "Estate Tax (706)",
            "Nonprofit (990)",
            "Private Foundation (990-PF)",
            "Foreign Corporation (1120-F)",
        )
        created_ids = []
        for index, return_type in enumerate(return_types):
            with self.subTest(return_type=return_type):
                year = str(2024 + index)
                response = self.create_engagement(tax_year=year, return_type=return_type)
                self.assertEqual(response.status_code, 201, response.get_json())
                saved = response.get_json()["engagement"]
                self.assertEqual(saved["tax_year"], int(year))
                self.assertEqual(saved["return_type"], return_type)
                created_ids.append(saved["engagement_id"])

        target_id = created_ids[0]
        updated = self.client.put(
            f"/api/engagements/{target_id}",
            json={
                "tax_year": "2019",
                "return_type": "Foreign Corporation (1120-F)",
                "assigned_preparer": "Serena Parke",
                "engagement_start_date": "2026-01-15",
                "filing_deadline": "2026-04-15",
            },
        )
        self.assertEqual(updated.status_code, 200, updated.get_json())
        refreshed = self.client.get("/api/engagements").get_json()["engagements"]
        persisted = next(item for item in refreshed if item["engagement_id"] == target_id)
        self.assertEqual(persisted["tax_year"], 2019)
        self.assertEqual(persisted["return_type"], "Foreign Corporation (1120-F)")
        self.assertEqual(len(refreshed), len(return_types))

    def test_create_rejects_missing_invalid_fields_and_unknown_client(self):
        for overrides in (
            {"return_type": ""},
            {"tax_year": "twenty twenty-six"},
            {"engagement_start_date": "2026-02-30"},
            {"filing_deadline": ""},
        ):
            with self.subTest(overrides=overrides):
                response = self.create_engagement(**overrides)
                self.assertEqual(response.status_code, 400)
        response = self.create_engagement(client_id=999999)
        self.assertEqual(response.status_code, 404)
        response = self.create_engagement(client_id=None)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.client.get("/api/engagements").get_json()["engagements"], [])

    def test_update_details_including_filing_deadline_keeps_status_separate(self):
        created = self.create_engagement().get_json()["engagement"]
        engagement_id = created["engagement_id"]
        status_response = self.client.patch(
            f"/api/engagements/{engagement_id}/status",
            json={"engagement_status": "Completed"},
        )
        self.assertEqual(status_response.status_code, 200)

        details = {
            "tax_year": "2027",
            "return_type": "Business",
            "assigned_preparer": "Professor",
            "engagement_start_date": "2026-03-01",
            "filing_deadline": "2027-09-15",
        }
        response = self.client.put(f"/api/engagements/{engagement_id}", json=details)
        self.assertEqual(response.status_code, 200, response.get_json())
        updated = response.get_json()["engagement"]
        self.assertEqual(updated["tax_year"], 2027)
        self.assertEqual(updated["return_type"], "Business")
        self.assertEqual(updated["assigned_preparer"], "Professor")
        self.assertEqual(updated["engagement_start_date"], "2026-03-01")
        self.assertEqual(updated["filing_deadline"], "2027-09-15")
        self.assertEqual(updated["engagement_status"], "Completed")

        rejected = self.client.put(
            f"/api/engagements/{engagement_id}",
            json={**details, "engagement_status": "Waiting on Client"},
        )
        self.assertEqual(rejected.status_code, 400)
        unchanged = self.client.get("/api/engagements").get_json()["engagements"][0]
        self.assertEqual(unchanged["engagement_status"], "Completed")

    def test_invalid_detail_update_does_not_change_existing_values(self):
        created = self.create_engagement().get_json()["engagement"]
        response = self.client.put(
            f"/api/engagements/{created['engagement_id']}",
            json={
                "tax_year": "2027",
                "return_type": "Business",
                "assigned_preparer": "Professor",
                "engagement_start_date": "2026-02-30",
                "filing_deadline": "2027-09-15",
            },
        )
        self.assertEqual(response.status_code, 400)
        current = self.client.get("/api/engagements").get_json()["engagements"][0]
        self.assertEqual(current["tax_year"], 2026)
        self.assertEqual(current["engagement_start_date"], "2026-01-15")
        self.assertEqual(current["filing_deadline"], "2026-04-15")
        self.assertEqual(current["engagement_status"], "In Progress")

    def test_status_update_accepts_all_approved_values_and_rejects_invalid_value(self):
        engagement_id = self.create_engagement().get_json()["engagement"]["engagement_id"]
        for status in ("In Progress", "Waiting on Client", "Completed"):
            with self.subTest(status=status):
                response = self.client.patch(
                    f"/api/engagements/{engagement_id}/status",
                    json={"engagement_status": status},
                )
                self.assertEqual(response.status_code, 200, response.get_json())
                self.assertEqual(response.get_json()["engagement"]["engagement_status"], status)

        response = self.client.patch(
            f"/api/engagements/{engagement_id}/status",
            json={"engagement_status": "On Hold"},
        )
        self.assertEqual(response.status_code, 400)
        current = self.client.get("/api/engagements").get_json()["engagements"][0]
        self.assertEqual(current["engagement_status"], "Completed")

    def test_engagement_operations_require_authentication(self):
        self.client.post("/api/auth/logout")
        self.assertEqual(self.client.get("/api/engagements").status_code, 401)
        self.assertEqual(self.client.post("/api/engagements", json=self.engagement_values()).status_code, 401)
        self.assertEqual(self.client.put("/api/engagements/1", json=self.engagement_values()).status_code, 401)
        self.assertEqual(
            self.client.patch("/api/engagements/1/status", json={"engagement_status": "Completed"}).status_code,
            401,
        )

    def test_both_demo_accounts_can_sign_in_and_out(self):
        for username, password, _display_name in DEMO_ACCOUNTS:
            with self.subTest(username=username):
                response = self.client.post(
                    "/api/auth/login", json={"username": username, "password": password}
                )
                self.assertEqual(response.status_code, 200)
                self.assertEqual(self.client.get("/api/auth/me").get_json()["user"]["username"], username)
                self.assertEqual(self.client.post("/api/auth/logout").status_code, 200)
                self.assertIsNone(self.client.get("/api/auth/me").get_json()["user"])


if __name__ == "__main__":
    unittest.main()
