def test_login_success(client, seeded_db):
    resp = client.post(
        "/auth/login?portal=user",
        data={"username": "emp1", "password": "Test@1234"},
        follow_redirects=True,
    )
    assert b"Welcome back, emp1" in resp.data


def test_login_failure(client, seeded_db):
    resp = client.post(
        "/auth/login?portal=user",
        data={"username": "emp1", "password": "WrongPassword"},
        follow_redirects=True,
    )
    assert b"Invalid username or password" in resp.data


def test_role_portal_mismatch(client, seeded_db):
    # Manager trying to log in through employee portal
    resp = client.post(
        "/auth/login?portal=user",
        data={"username": "mgr1", "password": "Test@1234"},
        follow_redirects=True,
    )
    assert b"This portal is for EMPLOYEE accounts. Your role is MANAGER" in resp.data


def test_logout(logged_in_employee):
    resp = logged_in_employee.get("/auth/logout", follow_redirects=True)
    assert b"You have been logged out." in resp.data
