"""One-time interactive provisioning for two PostgreSQL demo accounts.

Run after applying the Alembic schema migration. The command never prints
passwords, password hashes, or database connection details.
"""

import getpass
import os
import sys
import warnings

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app import create_app, load_local_environment
from app.auth.provisioning import AccountsAlreadyExist, provision_demo_accounts


def _hidden_password(prompt):
    # Fail closed if this terminal cannot hide input; getpass otherwise may
    # warn and fall back to visible input.
    with warnings.catch_warnings():
        warnings.simplefilter("error", getpass.GetPassWarning)
        return getpass.getpass(prompt)


def collect_accounts():
    accounts = []
    for number in (1, 2):
        print(f"Demo account {number}")
        username = input("Username: ").strip()
        display_name = input("Display name: ").strip()
        password = _hidden_password("New password (input hidden): ")
        confirmation = _hidden_password("Confirm new password (input hidden): ")
        if password != confirmation:
            raise ValueError("The password entries did not match.")
        if not username or not display_name or not password:
            raise ValueError("Username, display name, and password are required.")
        accounts.append((username, password, display_name))
    return tuple(accounts)


def main():
    app = None
    engine = None
    try:
        load_local_environment()
        # Fail before prompting or constructing an app that might initialize
        # the local SQLite database.
        if os.environ.get("TEM_ENV", "").strip().lower() != "production":
            raise RuntimeError("Provisioning requires TEM_ENV=production.")
        if not os.environ.get("TEM_DATABASE_URL", "").strip():
            raise RuntimeError("Provisioning requires a PostgreSQL connection setting.")
        if not sys.stdin.isatty() or not sys.stdout.isatty():
            raise RuntimeError("Provisioning requires an interactive terminal with hidden password input.")

        app = create_app()
        engine = app.extensions["tems_database_engine"]
        if app.config.get("DATABASE_BACKEND") != "postgresql":
            raise RuntimeError("Provisioning requires TEM_ENV=production and a PostgreSQL URL.")

        # Avoid collecting credentials at all when the one-time setup has
        # already happened. The locked transactional check below closes races.
        with engine.connect() as connection:
            if connection.execute(text("SELECT COUNT(*) FROM users")).scalar_one():
                raise AccountsAlreadyExist("The USERS table is not empty; no accounts were added.")

        accounts = collect_accounts()

        with engine.begin() as connection:
            provision_demo_accounts(connection, accounts)
        print("Two demonstration accounts were provisioned successfully.")
        return 0
    except AccountsAlreadyExist:
        print("Provisioning stopped: the USERS table already contains account records.", file=sys.stderr)
        return 1
    except (ValueError, RuntimeError, getpass.GetPassWarning, EOFError):
        print("Provisioning stopped. Check the setup instructions and secure terminal configuration.", file=sys.stderr)
        return 1
    except SQLAlchemyError:
        # Avoid printing SQLAlchemy exception details: they can include bound values.
        print("Provisioning failed. Check the database connection and confirm the schema migration is applied.", file=sys.stderr)
        return 1
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
