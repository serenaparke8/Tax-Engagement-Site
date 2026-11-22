import tempfile
import unittest
from pathlib import Path

from sqlalchemy import text
from werkzeug.security import check_password_hash

from app import create_app
from app.auth.provisioning import AccountsAlreadyExist, provision_demo_accounts


class DemoAccountProvisioningTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database = str(Path(self.temp_dir.name) / "provisioning_test.db")
        self.app = create_app({
            "TESTING": True,
            "SECRET_KEY": "unit-test-only-signing-key",
            "DATABASE": self.database,
            "DEMO_ACCOUNTS": (),
        })
        self.engine = self.app.extensions["tems_database_engine"]

    def tearDown(self):
        self.engine.dispose()
        self.temp_dir.cleanup()

    def test_provisions_two_accounts_with_compatible_password_hashes(self):
        accounts = (
            ("reviewer-one", "private-test-password-one", "Reviewer One"),
            ("reviewer-two", "private-test-password-two", "Reviewer Two"),
        )
        with self.engine.begin() as connection:
            provision_demo_accounts(connection, accounts)

        with self.engine.connect() as connection:
            rows = connection.execute(
                text("SELECT username, password_hash, display_name FROM USERS ORDER BY username")
            ).mappings().all()
        self.assertEqual([row["username"] for row in rows], ["reviewer-one", "reviewer-two"])
        self.assertEqual([row["display_name"] for row in rows], ["Reviewer One", "Reviewer Two"])
        self.assertTrue(check_password_hash(rows[0]["password_hash"], accounts[0][1]))
        self.assertTrue(check_password_hash(rows[1]["password_hash"], accounts[1][1]))
        self.assertNotEqual(rows[0]["password_hash"], accounts[0][1])

    def test_refuses_provisioning_when_any_account_already_exists(self):
        with self.engine.begin() as connection:
            connection.execute(
                text("INSERT INTO USERS (username, password_hash, display_name) VALUES (:u, :p, :d)"),
                {"u": "existing", "p": "already-hashed", "d": "Existing Account"},
            )

        with self.assertRaises(AccountsAlreadyExist):
            with self.engine.begin() as connection:
                provision_demo_accounts(connection, (
                    ("new-one", "private-test-password-one", "New One"),
                    ("new-two", "private-test-password-two", "New Two"),
                ))

        with self.engine.connect() as connection:
            self.assertEqual(connection.execute(text("SELECT COUNT(*) FROM USERS")).scalar_one(), 1)
            self.assertEqual(
                connection.execute(text("SELECT username FROM USERS")).scalar_one(),
                "existing",
            )


if __name__ == "__main__":
    unittest.main()
