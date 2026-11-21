import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from test_support import create_test_app, login_with_csrf, TEST_DEMO_ACCOUNTS


class EngagementDashboardTests(unittest.TestCase):
    TODAY = date(2026, 4, 10)

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        database = str(Path(self.temp_dir.name) / "test_tax_engagement.db")
        self.app = create_test_app(database)
        self.client = self.app.test_client()
        response = login_with_csrf(self.client, *TEST_DEMO_ACCOUNTS[0][:2])
        self.assertEqual(response.status_code, 200, response.get_json())

    def tearDown(self):
        self.temp_dir.cleanup()

    def add_client(self, name):
        response = self.client.post("/api/clients", json={"client_name": name})
        self.assertEqual(response.status_code, 201, response.get_json())
        return response.get_json()["client"]["client_id"]

    def add_engagement(self, client_id, **overrides):
        values = {
            "client_id": client_id,
            "tax_year": "2026",
            "return_type": "Individual (1040)",
            "assigned_preparer": "Serena Parke",
            "engagement_start_date": "2026-01-15",
            "filing_deadline": (self.TODAY + timedelta(days=2)).isoformat(),
        }
        values.update(overrides)
        status = values.pop("engagement_status", None)
        response = self.client.post("/api/engagements", json=values)
        self.assertEqual(response.status_code, 201, response.get_json())
        engagement_id = response.get_json()["engagement"]["engagement_id"]
        if status:
            response = self.client.patch(
                f"/api/engagements/{engagement_id}/status",
                json={"engagement_status": status},
            )
            self.assertEqual(response.status_code, 200, response.get_json())
        return engagement_id

    def get_dashboard(self):
        with patch("app.dashboard.routes.current_date", return_value=self.TODAY):
            return self.client.get("/api/dashboard")

    def test_dashboard_separates_active_and_completed_and_shows_deadline_summary(self):
        client_id = self.add_client("Dashboard Client")
        in_progress_id = self.add_engagement(client_id, filing_deadline=self.TODAY.isoformat())
        waiting_id = self.add_engagement(
            client_id,
            engagement_status="Waiting on Client",
            filing_deadline=(self.TODAY + timedelta(days=14)).isoformat(),
        )
        completed_id = self.add_engagement(
            client_id,
            engagement_status="Completed",
            tax_year="2025",
            return_type="Partnership (1065)",
            assigned_preparer="Professor",
            filing_deadline=(self.TODAY + timedelta(days=15)).isoformat(),
        )
        self.client.post(
            "/api/required-items",
            json={"engagement_id": in_progress_id, "required_item_description": "W-2"},
        )
        self.client.post(
            "/api/required-items",
            json={"engagement_id": in_progress_id, "required_item_description": "1099-INT"},
        )

        response = self.get_dashboard()
        self.assertEqual(response.status_code, 200, response.get_json())
        dashboard = response.get_json()["dashboard"]
        self.assertTrue(dashboard["has_engagements"])
        self.assertEqual(dashboard["summary"], {
            "active_engagements": 2,
            "waiting_on_client": 1,
            "deadlines_within_14_days": 2,
            "completed_engagements": 1,
        })
        self.assertEqual(
            [item["engagement_id"] for item in dashboard["active_engagements"]],
            [in_progress_id, waiting_id],
        )
        self.assertEqual(
            [item["engagement_status"] for item in dashboard["active_engagements"]],
            ["In Progress", "Waiting on Client"],
        )
        self.assertEqual(dashboard["active_engagements"][0]["client_name"], "Dashboard Client")
        self.assertEqual(dashboard["active_engagements"][0]["filing_deadline"], self.TODAY.isoformat())
        self.assertEqual(dashboard["active_engagements"][0]["outstanding_item_count"], 2)
        self.assertEqual(
            [item["engagement_id"] for item in dashboard["completed_engagements"]],
            [completed_id],
        )
        self.assertEqual(dashboard["completed_engagements"][0]["engagement_status"], "Completed")
        self.assertEqual(
            [item["days_remaining"] for item in dashboard["upcoming_deadlines"]],
            [0, 14],
        )

    def test_dashboard_returns_empty_state_when_database_has_no_engagements(self):
        response = self.get_dashboard()
        self.assertEqual(response.status_code, 200, response.get_json())
        dashboard = response.get_json()["dashboard"]
        self.assertFalse(dashboard["has_engagements"])
        self.assertEqual(dashboard["active_engagements"], [])
        self.assertEqual(dashboard["completed_engagements"], [])
        self.assertEqual(dashboard["upcoming_deadlines"], [])

    def test_dashboard_requires_authentication(self):
        self.client.post("/api/auth/logout")
        self.assertEqual(self.client.get("/api/dashboard").status_code, 401)


if __name__ == "__main__":
    unittest.main()
