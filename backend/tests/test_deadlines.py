import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from test_support import create_test_app, login_with_csrf, TEST_DEMO_ACCOUNTS


class UpcomingDeadlinesTests(unittest.TestCase):
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

    def add_engagement(self, client_id, filing_deadline, **overrides):
        values = {
            "client_id": client_id,
            "tax_year": "2026",
            "return_type": "Individual (1040)",
            "assigned_preparer": "Serena Parke",
            "engagement_start_date": "2026-01-15",
            "filing_deadline": filing_deadline,
        }
        values.update(overrides)
        response = self.client.post("/api/engagements", json=values)
        self.assertEqual(response.status_code, 201, response.get_json())
        return response.get_json()["engagement"]["engagement_id"]

    def get_upcoming(self):
        with patch("app.deadlines.routes.current_date", return_value=self.TODAY):
            return self.client.get("/api/deadlines/upcoming")

    def test_inclusive_window_excludes_past_and_day_fifteen_and_sorts(self):
        client_id = self.add_client("Boundary Client")
        self.add_engagement(client_id, (self.TODAY - timedelta(days=1)).isoformat())
        due_today_id = self.add_engagement(client_id, self.TODAY.isoformat())
        due_in_two_days_id = self.add_engagement(client_id, (self.TODAY + timedelta(days=2)).isoformat())
        due_day_fourteen_id = self.add_engagement(client_id, (self.TODAY + timedelta(days=14)).isoformat())
        self.add_engagement(client_id, (self.TODAY + timedelta(days=15)).isoformat())

        response = self.get_upcoming()
        self.assertEqual(response.status_code, 200, response.get_json())
        deadlines = response.get_json()["deadlines"]
        self.assertEqual(
            [item["engagement_id"] for item in deadlines],
            [due_today_id, due_in_two_days_id, due_day_fourteen_id],
        )
        self.assertEqual([item["days_remaining"] for item in deadlines], [0, 2, 14])

    def test_deadline_results_include_correct_client_and_engagement_information(self):
        client_id = self.add_client("Correct Client Name")
        engagement_id = self.add_engagement(
            client_id,
            (self.TODAY + timedelta(days=4)).isoformat(),
            tax_year="2025",
            return_type="Partnership (1065)",
        )

        response = self.get_upcoming()
        result = response.get_json()["deadlines"][0]
        self.assertEqual(result["client_id"], client_id)
        self.assertEqual(result["client_name"], "Correct Client Name")
        self.assertEqual(result["engagement_id"], engagement_id)
        self.assertEqual(result["tax_year"], 2025)
        self.assertEqual(result["return_type"], "Partnership (1065)")
        self.assertEqual(result["filing_deadline"], "2026-04-14")
        self.assertEqual(result["days_remaining"], 4)

    def test_engagement_without_a_filing_date_is_excluded_and_empty_list_returned(self):
        client_id = self.add_client("No Deadline Client")
        engagement_id = self.add_engagement(client_id, "2026-04-10")
        with self.app.app_context():
            from app.db import get_db

            get_db().execute(
                "UPDATE TAX_ENGAGEMENT SET filing_deadline = '' WHERE engagement_id = ?",
                (engagement_id,),
            )
            get_db().commit()

        response = self.get_upcoming()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["deadlines"], [])

    def test_deadline_endpoint_requires_authentication(self):
        self.client.post("/api/auth/logout")
        response = self.client.get("/api/deadlines/upcoming")
        self.assertEqual(response.status_code, 401)


if __name__ == "__main__":
    unittest.main()
