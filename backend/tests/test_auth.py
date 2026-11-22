"""
test_auth.py — Integration tests for YojanaMitra authentication endpoints.

Tests:
  - POST /api/auth/register — success, duplicate email, validation errors
  - POST /api/auth/login    — success, wrong password, unknown email
  - GET  /api/auth/me       — authenticated, unauthenticated
  - GET  /api/user/saved-schemes — authenticated
  - POST /api/user/saved-schemes/{id} — save + duplicate
  - DELETE /api/user/saved-schemes/{id} — unsave
  - GET  /api/user/history — authenticated
  - DELETE /api/user/history — clear
"""

import os
import sys
import unittest
from pathlib import Path

# Point to the backend directory so app imports resolve correctly
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("AUTH_SECRET_KEY", "test-secret-key-for-unit-tests-only")

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

TEST_EMAIL = "demo_test_user_ym@example.com"
TEST_NAME  = "Demo User"
TEST_PASS  = "SecurePass123"


def _register(email=TEST_EMAIL, name=TEST_NAME, password=TEST_PASS):
    return client.post("/api/auth/register", json={"name": name, "email": email, "password": password})


def _login(email=TEST_EMAIL, password=TEST_PASS):
    return client.post("/api/auth/login", json={"email": email, "password": password})


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


class AuthRegistrationTests(unittest.TestCase):

    def setUp(self):
        """Remove any existing test user so each test starts clean."""
        from app.auth import _get_conn
        with _get_conn() as conn:
            conn.execute("DELETE FROM users WHERE email = ? COLLATE NOCASE", (TEST_EMAIL,))

    def test_register_success(self):
        r = _register()
        self.assertEqual(r.status_code, 201, r.text)
        body = r.json()
        self.assertIn("access_token", body)
        self.assertEqual(body["user"]["email"], TEST_EMAIL)
        self.assertEqual(body["user"]["name"], TEST_NAME)

    def test_register_duplicate_email(self):
        _register()
        r = _register()
        self.assertEqual(r.status_code, 409)

    def test_register_short_password(self):
        r = _register(password="short")
        self.assertIn(r.status_code, (422,))

    def test_register_invalid_email(self):
        r = _register(email="not-an-email")
        self.assertIn(r.status_code, (422,))

    def test_register_short_name(self):
        r = _register(name="X")
        self.assertIn(r.status_code, (422,))


class AuthLoginTests(unittest.TestCase):

    def setUp(self):
        from app.auth import _get_conn
        with _get_conn() as conn:
            conn.execute("DELETE FROM users WHERE email = ? COLLATE NOCASE", (TEST_EMAIL,))
        _register()

    def tearDown(self):
        from app.auth import _get_conn
        with _get_conn() as conn:
            conn.execute("DELETE FROM users WHERE email = ? COLLATE NOCASE", (TEST_EMAIL,))

    def test_login_success(self):
        r = _login()
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertIn("access_token", body)
        self.assertEqual(body["user"]["email"], TEST_EMAIL)

    def test_login_wrong_password(self):
        r = _login(password="WrongPassword!")
        self.assertEqual(r.status_code, 401)

    def test_login_unknown_email(self):
        r = _login(email="nobody@example.com")
        self.assertEqual(r.status_code, 401)


class AuthMeTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from app.auth import _get_conn
        with _get_conn() as conn:
            conn.execute("DELETE FROM users WHERE email = ? COLLATE NOCASE", (TEST_EMAIL,))
        r = _register()
        cls.token = r.json()["access_token"]

    @classmethod
    def tearDownClass(cls):
        from app.auth import _get_conn
        with _get_conn() as conn:
            conn.execute("DELETE FROM users WHERE email = ? COLLATE NOCASE", (TEST_EMAIL,))

    def test_me_authenticated(self):
        r = client.get("/api/auth/me", headers=_auth_header(self.token))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["email"], TEST_EMAIL)

    def test_me_unauthenticated(self):
        r = client.get("/api/auth/me")
        self.assertEqual(r.status_code, 401)

    def test_me_invalid_token(self):
        r = client.get("/api/auth/me", headers=_auth_header("invalid.token.here"))
        self.assertEqual(r.status_code, 401)


class SavedSchemesTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from app.auth import _get_conn
        with _get_conn() as conn:
            conn.execute("DELETE FROM users WHERE email = ? COLLATE NOCASE", (TEST_EMAIL,))
        r = _register()
        cls.token = r.json()["access_token"]

    @classmethod
    def tearDownClass(cls):
        from app.auth import _get_conn
        with _get_conn() as conn:
            conn.execute("DELETE FROM users WHERE email = ? COLLATE NOCASE", (TEST_EMAIL,))

    def _h(self):
        return _auth_header(self.token)

    def test_list_saved_empty(self):
        r = client.get("/api/user/saved-schemes", headers=self._h())
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["saved"], [])

    def test_save_scheme(self):
        r = client.post("/api/user/saved-schemes/pm-kisan", headers=self._h())
        self.assertEqual(r.status_code, 201)
        self.assertIn("pm-kisan", r.json()["saved"])

    def test_save_duplicate_idempotent(self):
        client.post("/api/user/saved-schemes/pm-kisan", headers=self._h())
        r = client.post("/api/user/saved-schemes/pm-kisan", headers=self._h())
        self.assertEqual(r.status_code, 201)
        # Still only one entry
        saved = r.json()["saved"]
        self.assertEqual(saved.count("pm-kisan"), 1)

    def test_save_nonexistent_scheme(self):
        r = client.post("/api/user/saved-schemes/nonexistent-scheme-id", headers=self._h())
        self.assertEqual(r.status_code, 404)

    def test_unsave_scheme(self):
        client.post("/api/user/saved-schemes/pm-kisan", headers=self._h())
        r = client.delete("/api/user/saved-schemes/pm-kisan", headers=self._h())
        self.assertEqual(r.status_code, 200)
        self.assertNotIn("pm-kisan", r.json()["saved"])

    def test_saved_requires_auth(self):
        r = client.get("/api/user/saved-schemes")
        self.assertEqual(r.status_code, 401)


class ConversationHistoryTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from app.auth import _get_conn, save_conversation_turn
        with _get_conn() as conn:
            conn.execute("DELETE FROM users WHERE email = ? COLLATE NOCASE", (TEST_EMAIL,))
        r = _register()
        cls.token = r.json()["access_token"]
        # Seed a couple of turns via the helper (bypasses HTTP for speed)
        user_id = r.json()["user"]["id"]
        save_conversation_turn(user_id, "user", "What is PM-KISAN?")
        save_conversation_turn(user_id, "model", "PM-KISAN provides ₹6,000/year.")

    @classmethod
    def tearDownClass(cls):
        from app.auth import _get_conn
        with _get_conn() as conn:
            conn.execute("DELETE FROM users WHERE email = ? COLLATE NOCASE", (TEST_EMAIL,))

    def _h(self):
        return _auth_header(self.token)

    def test_get_history(self):
        # Re-seed turns in case clear_history ran first (alphabetical order)
        from app.auth import _get_conn, get_user_by_email, save_conversation_turn
        row = get_user_by_email(TEST_EMAIL)
        if row:
            save_conversation_turn(row["id"], "user", "What is PM-KISAN?")
            save_conversation_turn(row["id"], "model", "PM-KISAN provides ₹6,000/year.")
        r = client.get("/api/user/history", headers=self._h())
        self.assertEqual(r.status_code, 200)
        history = r.json()["history"]
        self.assertGreaterEqual(len(history), 1)

    def test_clear_history(self):
        r = client.delete("/api/user/history", headers=self._h())
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["cleared"])
        # Verify it's empty
        r2 = client.get("/api/user/history", headers=self._h())
        self.assertEqual(r2.json()["history"], [])

    def test_history_requires_auth(self):
        r = client.get("/api/user/history")
        self.assertEqual(r.status_code, 401)


if __name__ == "__main__":
    unittest.main()
