import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_auth_flow():
    # 1. Register a new user
    username = "testuser_pytest"
    password = "a"
    
    response = client.post(
        "/register",
        json={"username": username, "password": password}
    )
    # Registration might fail with 409 if the user already exists in redis,
    # but let's assume a clean redis or handle both
    if response.status_code == 409:
        pass # Already exists, we can proceed to login
    else:
        assert response.status_code == 200
        assert "User registered successfully" in response.json()["message"]

    # 2. Login
    response = client.post(
        "/login",
        json={"username": username, "password": password}
    )
    assert response.status_code == 200
    assert "session" in response.cookies

    # Extract the session cookie
    session_cookie = response.cookies.get("session")
    
    # 3. Test /me with valid cookie
    response = client.get(
        "/me",
        cookies={"session": session_cookie}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "user_id" in data
    
    # 4. Test /me with invalid cookie
    response = client.get(
        "/me",
        cookies={"session": "invalid_or_expired_cookie_value"}
    )
    assert response.status_code == 401
    
    # 5. Logout
    response = client.post(
        "/logout",
        cookies={"session": session_cookie}
    )
    assert response.status_code == 200
    
    # 6. Test /me after logout (should be blacklisted)
    response = client.get(
        "/me",
        cookies={"session": session_cookie}
    )
    assert response.status_code == 401
