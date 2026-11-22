import tempfile
import unittest
from pathlib import Path

from app import create_app
from test_support import TEST_DEMO_ACCOUNTS, create_test_app, login_with_csrf


class ApplicationSecurityTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        database = str(Path(self.temp_dir.name) / "test_security.db")
        self.app = create_test_app(database)
        self.client = self.app.test_client()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_login_requires_csrf_token_and_rotates_it_after_sign_in(self):
        account = TEST_DEMO_ACCOUNTS[0]
        token = self.client.get("/api/auth/csrf").get_json()["csrf_token"]

        rejected = self.client.post(
            "/api/auth/login", json={"username": account[0], "password": account[1]}
        )
        self.assertEqual(rejected.status_code, 403)

        accepted = self.client.post(
            "/api/auth/login",
            json={"username": account[0], "password": account[1]},
            headers={"X-CSRF-Token": token},
        )
        self.assertEqual(accepted.status_code, 200, accepted.get_json())
        self.assertNotEqual(accepted.get_json()["csrf_token"], token)
        self.assertEqual(accepted.get_json()["user"]["username"], account[0])

    def test_authenticated_state_changes_require_session_csrf_token(self):
        response = login_with_csrf(self.client, *TEST_DEMO_ACCOUNTS[0][:2])
        self.assertEqual(response.status_code, 200)

        rejected = self.client.post("/api/clients", json={"client_name": "No token"}, headers={"X-CSRF-Token": "wrong"})
        self.assertEqual(rejected.status_code, 403)

        accepted = self.client.post("/api/clients", json={"client_name": "With token"})
        self.assertEqual(accepted.status_code, 201, accepted.get_json())

    def test_logout_requires_csrf_and_returns_a_fresh_anonymous_token(self):
        login = login_with_csrf(self.client, *TEST_DEMO_ACCOUNTS[0][:2])
        old_token = login.get_json()["csrf_token"]
        self.client.environ_base["HTTP_X_CSRF_TOKEN"] = "invalid"
        self.assertEqual(self.client.post("/api/auth/logout").status_code, 403)

        self.client.environ_base["HTTP_X_CSRF_TOKEN"] = old_token
        logout = self.client.post("/api/auth/logout")
        self.assertEqual(logout.status_code, 200)
        self.assertNotEqual(logout.get_json()["csrf_token"], old_token)
        self.assertIsNone(self.client.get("/api/auth/me").get_json()["user"])

    def test_production_requires_secret_and_marks_session_cookie_secure(self):
        with self.assertRaisesRegex(RuntimeError, "SECRET_KEY"):
            create_app({
                "TESTING": True,
                "TEM_ENV": "production",
                "SECRET_KEY": "",
                "DATABASE": str(Path(self.temp_dir.name) / "missing_secret.db"),
                "DEMO_ACCOUNTS": TEST_DEMO_ACCOUNTS,
            })
        with self.assertRaisesRegex(RuntimeError, "32 characters"):
            create_app({
                "TESTING": True,
                "TEM_ENV": "production",
                "SECRET_KEY": "too-short",
                "DATABASE": str(Path(self.temp_dir.name) / "weak_secret.db"),
                "DEMO_ACCOUNTS": TEST_DEMO_ACCOUNTS,
            })
        with self.assertRaisesRegex(RuntimeError, "unique"):
            create_app({
                "TESTING": True,
                "TEM_ENV": "production",
                "SECRET_KEY": "replace-with-a-unique-random-secret",
                "DATABASE": str(Path(self.temp_dir.name) / "placeholder_secret.db"),
                "DEMO_ACCOUNTS": TEST_DEMO_ACCOUNTS,
            })

        production_app = create_app({
            "TESTING": True,
            "TEM_ENV": "production",
            "SECRET_KEY": "test-only-production-signing-key",
            "TEM_DATABASE_URL": "postgresql+psycopg://test_user@127.0.0.1/test_database",
            "DATABASE": str(Path(self.temp_dir.name) / "production_cookie.db"),
            "DEMO_ACCOUNTS": TEST_DEMO_ACCOUNTS,
        })
        self.assertTrue(production_app.config["SESSION_COOKIE_SECURE"])
        self.assertTrue(production_app.config["SESSION_COOKIE_HTTPONLY"])
        self.assertEqual(production_app.config["SESSION_COOKIE_SAMESITE"], "Lax")
        production_app.extensions["tems_database_engine"].dispose()


if __name__ == "__main__":
    unittest.main()
