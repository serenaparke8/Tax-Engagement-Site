from app import create_app


TEST_DEMO_ACCOUNTS = (
    ("demo-serena", "test-only-serena-password", "Demo Serena"),
    ("demo-professor", "test-only-professor-password", "Demo Professor"),
)


def create_test_app(database):
    return create_app({
        "TESTING": True,
        "SECRET_KEY": "unit-test-only-signing-key",
        "DATABASE": database,
        "DEMO_ACCOUNTS": TEST_DEMO_ACCOUNTS,
    })


def login_with_csrf(client, username, password):
    token_response = client.get("/api/auth/csrf")
    token = token_response.get_json()["csrf_token"]
    response = client.post(
        "/api/auth/login",
        json={"username": username, "password": password},
        headers={"X-CSRF-Token": token},
    )
    if response.status_code == 200:
        client.environ_base["HTTP_X_CSRF_TOKEN"] = response.get_json()["csrf_token"]
    return response
