"""Interactively rotate both existing TEMS demo-account passwords.

Run from the backend directory with the project's virtual environment. Passwords
are read with echo disabled, hashed for SQLite, and written to the ignored local
environment file so a future empty demo database uses the same credentials.
"""

import getpass
import argparse
import os
import sqlite3
import tempfile
from pathlib import Path

from werkzeug.security import check_password_hash, generate_password_hash

from app import load_local_environment


BACKEND_DIR = Path(__file__).resolve().parent
ENV_FILE = BACKEND_DIR / ".env"
ACCOUNTS = ((1, "serena"), (2, "professor"))
BUSINESS_TABLES = ("CLIENT", "TAX_ENGAGEMENT", "REQUIRED_ITEM")


def read_local_env():
    result = {}
    for raw_line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line and not line.startswith("#") and "=" in line:
            name, value = line.split("=", 1)
            result[name.strip()] = value.strip().strip("\"'")
    return result


def env_text_with_passwords(original_text, passwords):
    replacements = {
        f"TEM_DEMO_ACCOUNT_{index}_PASSWORD": password
        for index, password in passwords.items()
    }
    updated = []
    seen = set()
    for raw_line in original_text.splitlines(keepends=True):
        stripped = raw_line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            name, _value = stripped.split("=", 1)
            name = name.strip()
            if name in replacements:
                updated.append(f'{name}="{replacements[name]}"\n')
                seen.add(name)
                continue
        updated.append(raw_line)
    if seen != set(replacements):
        raise RuntimeError("Required demo account settings are missing from backend/.env.")
    return "".join(updated)


def write_env_atomically(content):
    fd, temp_name = tempfile.mkstemp(prefix=".tems-env-rotation-", dir=ENV_FILE.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as output:
            output.write(content)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temp_name, ENV_FILE)
    except Exception:
        Path(temp_name).unlink(missing_ok=True)
        raise


def table_snapshot(database):
    with sqlite3.connect(f"file:{database.as_posix()}?mode=ro", uri=True) as db:
        counts = {
            table: db.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
            for table in ("USERS", *BUSINESS_TABLES)
        }
        schema = db.execute(
            "SELECT type, name, sql FROM sqlite_master "
            "WHERE type IN ('table','index','trigger','view') ORDER BY type,name"
        ).fetchall()
        integrity = db.execute("PRAGMA integrity_check").fetchone()[0]
    return counts, schema, integrity


def main():
    parser = argparse.ArgumentParser(description="Safely rotate existing TEMS demo account passwords.")
    parser.add_argument("--backup", required=True, type=Path, help="Previously created database backup to verify")
    args = parser.parse_args()

    load_local_environment()
    database = Path(os.environ.get("TEM_DATABASE", BACKEND_DIR / "instance" / "tax_engagement.db"))
    if not database.is_absolute():
        database = (BACKEND_DIR / database).resolve()
    else:
        database = database.resolve()
    if not database.is_file() or not ENV_FILE.is_file():
        raise RuntimeError("The configured database or local environment file is missing; nothing was changed.")
    backup = args.backup.resolve()
    if not backup.is_file() or backup == database:
        raise RuntimeError("A separate verified database backup is required; nothing was changed.")
    source_snapshot = table_snapshot(database)
    backup_snapshot = table_snapshot(backup)
    if source_snapshot[2] != "ok" or backup_snapshot[2] != "ok" or source_snapshot[:2] != backup_snapshot[:2]:
        raise RuntimeError("The backup does not match the current database; nothing was changed.")
    print(f"Verified database backup: {backup}")

    original_env = ENV_FILE.read_text(encoding="utf-8")
    env_values = read_local_env()
    previous_passwords = {
        index: env_values.get(f"TEM_DEMO_ACCOUNT_{index}_PASSWORD", "")
        for index, _username in ACCOUNTS
    }
    if not all(previous_passwords.values()):
        raise RuntimeError("Existing demo seed settings could not be verified; nothing was changed.")

    with sqlite3.connect(f"file:{database.as_posix()}?mode=ro", uri=True) as db:
        rows = {
            username: db.execute(
                "SELECT user_id, password_hash FROM USERS WHERE username = ?", (username,)
            ).fetchone()
            for _index, username in ACCOUNTS
        }
        if any(row is None for row in rows.values()):
            raise RuntimeError("Both expected demo accounts must exist; nothing was changed.")
        if any(
            not check_password_hash(rows[username][1], previous_passwords[index])
            for index, username in ACCOUNTS
        ):
            raise RuntimeError("Local seed settings do not match the stored accounts; nothing was changed.")

    new_passwords = {}
    for index, username in ACCOUNTS:
        while True:
            first = getpass.getpass(f"Enter a new password for {username} (hidden, at least 12 characters): ")
            confirmation = getpass.getpass(f"Confirm the new password for {username} (hidden): ")
            if first != confirmation:
                print("The entries did not match. Please try again.")
                continue
            if len(first) < 12 or not first.strip():
                print("Use a nonblank password with at least 12 characters.")
                continue
            if first == previous_passwords[index]:
                print("Choose a new password different from the current one.")
                continue
            new_passwords[index] = first
            break
    if new_passwords[1] == new_passwords[2]:
        raise RuntimeError("Use distinct passwords for the two accounts; nothing was changed.")

    changed_env = env_text_with_passwords(original_env, new_passwords)
    new_hashes = {index: generate_password_hash(password) for index, password in new_passwords.items()}
    original_counts = {}
    original_schema = None
    env_replaced = False
    with sqlite3.connect(database) as db:
        db.execute("PRAGMA foreign_keys = ON")
        db.execute("BEGIN IMMEDIATE")
        try:
            for table in ("USERS", *BUSINESS_TABLES):
                original_counts[table] = db.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
            original_schema = db.execute(
                "SELECT type, name, sql FROM sqlite_master "
                "WHERE type IN ('table','index','trigger','view') ORDER BY type,name"
            ).fetchall()
            for index, username in ACCOUNTS:
                result = db.execute(
                    "UPDATE USERS SET password_hash = ? WHERE username = ?",
                    (new_hashes[index], username),
                )
                if result.rowcount != 1:
                    raise RuntimeError("An expected account could not be updated; transaction rolled back.")
                saved_hash = db.execute(
                    "SELECT password_hash FROM USERS WHERE username = ?", (username,)
                ).fetchone()[0]
                if not check_password_hash(saved_hash, new_passwords[index]):
                    raise RuntimeError("Password-hash verification failed; transaction rolled back.")

            write_env_atomically(changed_env)
            env_replaced = True
            db.commit()
        except Exception:
            db.rollback()
            if env_replaced:
                write_env_atomically(original_env)
            raise

    with sqlite3.connect(f"file:{database.as_posix()}?mode=ro", uri=True) as db:
        final_counts = {
            table: db.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
            for table in original_counts
        }
        final_schema = db.execute(
            "SELECT type, name, sql FROM sqlite_master "
            "WHERE type IN ('table','index','trigger','view') ORDER BY type,name"
        ).fetchall()
        integrity = db.execute("PRAGMA integrity_check").fetchone()[0]
        hashes = {
            username: db.execute(
                "SELECT password_hash FROM USERS WHERE username = ?", (username,)
            ).fetchone()[0]
            for _index, username in ACCOUNTS
        }
    if final_counts != original_counts or final_schema != original_schema or integrity != "ok":
        raise RuntimeError("Post-rotation database verification failed; preserve the verified backup for recovery.")

    from app import create_app

    app = create_app({"TESTING": True})
    for index, username in ACCOUNTS:
        new_client = app.test_client()
        new_csrf = new_client.get("/api/auth/csrf").get_json()["csrf_token"]
        new_login = new_client.post(
            "/api/auth/login",
            json={"username": username, "password": new_passwords[index]},
            headers={"X-CSRF-Token": new_csrf},
        )
        if new_login.status_code != 200:
            raise RuntimeError("A new password failed the authentication check.")

        old_client = app.test_client()
        old_csrf = old_client.get("/api/auth/csrf").get_json()["csrf_token"]
        old_login = old_client.post(
            "/api/auth/login",
            json={"username": username, "password": previous_passwords[index]},
            headers={"X-CSRF-Token": old_csrf},
        )
        if old_login.status_code != 401:
            raise RuntimeError("The prior password was not rejected by authentication.")
        if check_password_hash(hashes[username], previous_passwords[index]):
            raise RuntimeError("The prior password still matches the stored hash.")

    print("Both existing accounts now authenticate with their new passwords.")
    print("Both prior passwords were rejected; database record counts and schema are unchanged.")
    print("Local seed settings were updated. No password or hash was displayed.")
    print("Database integrity check: ok.")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # Avoid echoing exception details that could expose sensitive configuration.
        print("Rotation stopped safely. No password or hash was displayed.")
        raise SystemExit(1)
