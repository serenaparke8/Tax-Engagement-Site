"""Explicit, one-time provisioning of production demonstration accounts."""

from sqlalchemy import text
from werkzeug.security import generate_password_hash


class AccountsAlreadyExist(RuntimeError):
    """Raised when provisioning is attempted against a non-empty USERS table."""


def provision_demo_accounts(connection, accounts):
    """Insert exactly two accounts; caller owns and commits the transaction."""
    if len(accounts) != 2:
        raise ValueError("Exactly two demonstration accounts are required.")

    normalized_usernames = [account[0].strip().casefold() for account in accounts]
    if any(not username for username in normalized_usernames) or len(set(normalized_usernames)) != 2:
        raise ValueError("Account usernames must be non-empty and unique.")
    if any(not password or not display_name.strip() for _, password, display_name in accounts):
        raise ValueError("Passwords and display names are required.")

    if connection.dialect.name == "postgresql":
        # Serialize concurrent first-time provisioning attempts. The transaction
        # releases this lock whether it succeeds or rolls back.
        connection.execute(text("LOCK TABLE users IN EXCLUSIVE MODE"))

    existing_count = connection.execute(text("SELECT COUNT(*) FROM users")).scalar_one()
    if existing_count:
        raise AccountsAlreadyExist("The USERS table is not empty; no accounts were added.")

    rows = [
        {
            "username": username.strip(),
            "password_hash": generate_password_hash(password),
            "display_name": display_name.strip(),
        }
        for username, password, display_name in accounts
    ]
    connection.execute(
        text(
            "INSERT INTO users (username, password_hash, display_name) "
            "VALUES (:username, :password_hash, :display_name)"
        ),
        rows,
    )
