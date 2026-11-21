import tempfile
import unittest
from pathlib import Path
from urllib.parse import urlencode

from test_support import create_test_app, login_with_csrf, TEST_DEMO_ACCOUNTS


class EngagementReportsTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        database = str(Path(self.temp_dir.name) / "test_tax_engagement.db")
        self.app = create_test_app(database)
        self.client = self.app.test_client()
        response = login_with_csrf(self.client, *TEST_DEMO_ACCOUNTS[0][:2])
        self.assertEqual(response.status_code, 200, response.get_json())
        self.client_ids = {
            "Alpha Client": self.add_client("Alpha Client"),
            "Beta Client": self.add_client("Beta Client"),
            "Gamma Client": self.add_client("Gamma Client"),
        }
        self.engagements = {
            "alpha": self.add_engagement(
                self.client_ids["Alpha Client"], 2024, "Individual (1040)", "Serena Parke", "In Progress"
            ),
            "beta": self.add_engagement(
                self.client_ids["Beta Client"], 2025, "Partnership (1065)", "Professor", "Waiting on Client"
            ),
            "gamma": self.add_engagement(
                self.client_ids["Gamma Client"], 2025, "C Corporation (1120)", "Serena Parke", "Completed"
            ),
        }

    def tearDown(self):
        self.temp_dir.cleanup()

    def add_client(self, name):
        response = self.client.post("/api/clients", json={"client_name": name})
        self.assertEqual(response.status_code, 201, response.get_json())
        return response.get_json()["client"]["client_id"]

    def add_engagement(self, client_id, year, return_type, preparer, status):
        response = self.client.post(
            "/api/engagements",
            json={
                "client_id": client_id,
                "tax_year": str(year),
                "return_type": return_type,
                "assigned_preparer": preparer,
                "engagement_start_date": "2026-01-15",
                "filing_deadline": "2026-04-15",
            },
        )
        self.assertEqual(response.status_code, 201, response.get_json())
        engagement_id = response.get_json()["engagement"]["engagement_id"]
        response = self.client.patch(
            f"/api/engagements/{engagement_id}/status",
            json={"engagement_status": status},
        )
        self.assertEqual(response.status_code, 200, response.get_json())
        return engagement_id

    def get_report(self, **filters):
        query = urlencode({key: value for key, value in filters.items() if value})
        path = "/api/reports/engagements" + (f"?{query}" if query else "")
        return self.client.get(path)

    def test_report_filters_by_status_tax_year_and_assigned_preparer(self):
        cases = (
            ({"status": "In Progress"}, [self.engagements["alpha"]]),
            ({"tax_year": "2025"}, [self.engagements["beta"], self.engagements["gamma"]]),
            ({"assigned_preparer": "Professor"}, [self.engagements["beta"]]),
        )
        for filters, expected_ids in cases:
            with self.subTest(filters=filters):
                response = self.get_report(**filters)
                self.assertEqual(response.status_code, 200, response.get_json())
                self.assertEqual(
                    [item["engagement_id"] for item in response.get_json()["engagements"]],
                    expected_ids,
                )

    def test_report_combines_filters_and_displays_required_engagement_fields(self):
        response = self.get_report(
            status="Waiting on Client", tax_year="2025", assigned_preparer="Professor"
        )
        self.assertEqual(response.status_code, 200, response.get_json())
        rows = response.get_json()["engagements"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0], {
            "client_name": "Beta Client",
            "engagement_id": self.engagements["beta"],
            "tax_year": 2025,
            "return_type": "Partnership (1065)",
            "assigned_preparer": "Professor",
            "engagement_start_date": "2026-01-15",
            "filing_deadline": "2026-04-15",
            "engagement_status": "Waiting on Client",
        })

    def test_report_options_come_from_existing_records(self):
        response = self.client.get("/api/reports/criteria")
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(response.get_json()["criteria"], {
            "statuses": ["In Progress", "Waiting on Client", "Completed"],
            "tax_years": [2025, 2024],
            "assigned_preparers": ["Professor", "Serena Parke"],
        })

    def test_report_returns_empty_results_for_nonmatching_criteria(self):
        response = self.get_report(status="Completed", tax_year="2024", assigned_preparer="Professor")
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(response.get_json()["engagements"], [])

    def test_invalid_filter_values_are_rejected(self):
        self.assertEqual(self.get_report(status="On Hold").status_code, 400)
        self.assertEqual(self.get_report(tax_year="not-a-year").status_code, 400)

    def test_report_endpoints_require_authentication(self):
        self.client.post("/api/auth/logout")
        self.assertEqual(self.client.get("/api/reports/criteria").status_code, 401)
        self.assertEqual(self.client.get("/api/reports/engagements").status_code, 401)


if __name__ == "__main__":
    unittest.main()
