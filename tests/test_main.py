"""Flask API tests.

Route tests mock the logic layer with *autospec*, so they fail if main.py calls a
function with arguments its real signature doesn't accept. The end-to-end tests
use no mocks (real logic, in-memory DB).
"""
import os
import subprocess
import sys
from pathlib import Path
from unittest import mock

import pytest

import main
import student
import transaction
from models import Notification, Student


# --------------------------------------------------------------------------
# Fixtures / helpers
# --------------------------------------------------------------------------
@pytest.fixture
def client(db):
    main.app.config["TESTING"] = True
    with main.app.test_client() as c:
        yield c


@pytest.fixture
def login_as(client):
    """Put a student id straight into the session (skips the login route)."""
    def _login(student_id=1):
        with client.session_transaction() as sess:
            sess["student_id"] = student_id
    return _login


def session_contents(client):
    with client.session_transaction() as sess:
        return dict(sess)


@pytest.fixture
def new_account(db):
    """A real registered student who has NOT done initial setup."""
    created = student.create_student("Alice", "password123")
    return {"student_id": created["student_id"],
            "username": created["name"],
            "password": "password123"}


@pytest.fixture
def account(new_account):
    """A real registered student with setup done: 10 swipes, $25 village, $15 campus."""
    student.set_starting_balances(new_account["student_id"], 10, 25.00, 15.00)
    return new_account


def log_in(client, acct):
    resp = client.post("/api/login", json={"username": acct["username"],
                                           "password": acct["password"]})
    assert resp.status_code == 200
    return resp


def patch_autospec(monkeypatch, name, target, **kwargs):
    fake = mock.create_autospec(target, **kwargs)
    monkeypatch.setattr(main, name, fake)
    return fake


@pytest.fixture
def fake_create(monkeypatch):
    return patch_autospec(
        monkeypatch, "create_transaction", transaction.create_transaction,
        return_value={"status": "success", "swipes": 9,
                      "village_flex": 25.0, "campus_flex": 15.0},
    )


@pytest.fixture
def fake_setup(monkeypatch):
    return patch_autospec(
        monkeypatch, "set_starting_balances", student.set_starting_balances,
        return_value={"student_id": 5, "swipes": 14, "starting_swipes": 14,
                      "village_flex": 100.0, "campus_flex": 50.0, "setup_completed": True},
    )


@pytest.fixture
def fake_reset(monkeypatch):
    return patch_autospec(
        monkeypatch, "reset_swipes_to_starting_balance",
        student.reset_swipes_to_starting_balance,
        return_value={"student_id": 5, "previous_swipes": 3, "swipes": 14,
                      "starting_swipes": 14},
    )


# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------
def test_secret_key_is_configured():
    assert main.app.config["SECRET_KEY"] == os.environ["FLASK_SECRET_KEY"]


def test_main_refuses_to_start_without_secret_key():
    root = Path(main.__file__).resolve().parent
    env = {k: v for k, v in os.environ.items() if k != "FLASK_SECRET_KEY"}
    # Use an in-memory engine so importing main can't touch meal_tracker.db
    code = ("import database, sqlalchemy; "
            "database.engine = sqlalchemy.create_engine('sqlite://'); "
            "import main")

    proc = subprocess.run([sys.executable, "-c", code], cwd=root, env=env,
                          capture_output=True, text=True)

    assert proc.returncode != 0
    assert "FLASK_SECRET_KEY" in proc.stderr


# --------------------------------------------------------------------------
# POST /api/register
# --------------------------------------------------------------------------
def test_register_success_json(client, session):
    resp = client.post("/api/register", json={"username": "Alice", "password": "password123"})

    assert resp.status_code == 201
    body = resp.get_json()
    assert body["success"] is True
    assert body["data"]["username"] == "Alice"
    assert body["data"]["name"] == "Alice"
    assert "login_id" not in body["data"]
    assert body["data"]["swipes"] == 0
    assert body["data"]["setup_completed"] is False
    assert session.query(Student).count() == 1
    assert session_contents(client)["student_id"] == body["data"]["student_id"]


def test_register_success_form(client):
    resp = client.post("/api/register", data={"username": "Alice", "password": "password123"})

    assert resp.status_code == 201
    assert resp.get_json()["data"]["username"] == "Alice"


def test_register_rejects_duplicate_username(client):
    first = client.post("/api/register", json={"username": "Alice", "password": "password123"})
    second = client.post("/api/register", json={"username": "Alice", "password": "password456"})

    assert first.status_code == 201
    assert second.status_code == 400
    assert second.get_json()["error"] == "That username is already taken."


def test_register_does_not_expose_password_data(client):
    resp = client.post("/api/register", json={"username": "Alice", "password": "password123"})

    text = resp.get_data(as_text=True)
    assert "password123" not in text
    assert "password_hash" not in text


@pytest.mark.parametrize("payload, message", [
    ({"username": "", "password": "password123"}, "Username is required"),
    ({"password": "password123"}, "Username is required"),
    ({"username": "Alice", "password": "short"}, "at least 8 characters"),
    ({"username": "Alice"}, "at least 8 characters"),
])
def test_register_validation_errors(client, session, payload, message):
    resp = client.post("/api/register", json=payload)

    assert resp.status_code == 400
    assert resp.get_json()["success"] is False
    assert message in resp.get_json()["error"]
    assert session.query(Student).count() == 0


def test_register_unexpected_error_is_generic_500(client, monkeypatch):
    def boom(name, password):
        raise RuntimeError("secret internal detail")
    monkeypatch.setattr(main, "create_student", boom)

    resp = client.post("/api/register", json={"username": "Alice", "password": "password123"})

    assert resp.status_code == 500
    assert resp.get_json() == {"success": False, "error": "An internal error occurred."}
    assert "secret internal detail" not in resp.get_data(as_text=True)


# --------------------------------------------------------------------------
# POST /api/login
# --------------------------------------------------------------------------
def test_login_success_for_unconfigured_student(client, new_account):
    resp = client.post("/api/login", json={"username": new_account["username"],
                                           "password": new_account["password"]})

    assert resp.status_code == 200
    assert resp.get_json()["data"] == {"student_id": new_account["student_id"],
                                       "username": "Alice",
                                       "name": "Alice",
                                       "setup_completed": False}
    assert session_contents(client)["student_id"] == new_account["student_id"]


def test_login_reports_setup_completed(client, account):
    resp = log_in(client, account)
    assert resp.get_json()["data"]["setup_completed"] is True


def test_login_accepts_form_data(client, account):
    resp = client.post("/api/login", data={"username": account["username"],
                                           "password": account["password"]})
    assert resp.status_code == 200


def test_login_trims_username(client, account):
    resp = client.post("/api/login", json={"username": f"  {account['username']}  ",
                                           "password": account["password"]})
    assert resp.status_code == 200


def test_login_wrong_password(client, account):
    resp = client.post("/api/login", json={"username": account["username"],
                                           "password": "wrong-password"})

    assert resp.status_code == 401
    assert resp.get_json() == {"success": False, "error": "Invalid username or password."}
    assert "student_id" not in session_contents(client)


def test_login_unknown_username_gives_same_error_as_wrong_password(client, account):
    """Don't reveal which usernames exist."""
    unknown = client.post("/api/login", json={"username": "UnknownUser",
                                              "password": "password123"})
    wrong_pw = client.post("/api/login", json={"username": account["username"],
                                               "password": "wrong-password"})

    assert unknown.status_code == wrong_pw.status_code == 401
    assert unknown.get_json() == wrong_pw.get_json()


def test_login_rejected_for_empty_password_hash(client, session):
    session.add(Student(name="Broken", login_id="MP-BROKEN01", password_hash=""))
    session.commit()

    resp = client.post("/api/login", json={"username": "Broken", "password": "anything1"})

    assert resp.status_code == 401


@pytest.mark.parametrize("payload", [
    {},
    {"username": "Alice"},
    {"password": "password123"},
    {"username": "   ", "password": "password123"},
    {"username": 123, "password": "password123"},        # non-string username
    {"username": "Alice", "password": 12345678},         # non-string password
    {"username": None, "password": "password123"},
    {"login_id": "MP-1", "password": "password123"},    # Login ID is no longer accepted
])
def test_login_requires_both_fields_as_strings(client, payload):
    resp = client.post("/api/login", json=payload)

    assert resp.status_code == 400
    assert resp.get_json()["error"] == "Username and password are required."


def test_login_replaces_existing_session(client, account, login_as):
    login_as(999)
    with client.session_transaction() as sess:
        sess["leftover"] = "stale"

    log_in(client, account)

    contents = session_contents(client)
    assert contents["student_id"] == account["student_id"]
    assert "leftover" not in contents


# --------------------------------------------------------------------------
# POST /api/logout
# --------------------------------------------------------------------------
def test_logout_clears_session_and_blocks_api(client, login_as):
    login_as(1)

    resp = client.post("/api/logout")

    assert resp.status_code == 200
    assert resp.get_json()["success"] is True
    assert session_contents(client) == {}
    assert client.get("/api/balances").status_code == 401


def test_logout_when_not_logged_in_is_ok(client):
    assert client.post("/api/logout").status_code == 200


# --------------------------------------------------------------------------
# Auth guards
# --------------------------------------------------------------------------
@pytest.mark.parametrize("method, url", [
    ("get", "/api/balances"),
    ("get", "/api/transactions"),
    ("post", "/api/transactions"),
    ("post", "/api/setup/balances"),
    ("post", "/api/swipes/reset"),
    ("get", "/api/notifications"),
    ("post", "/api/notifications/1/read"),
])
def test_api_requires_authentication(client, method, url):
    resp = getattr(client, method)(url)

    assert resp.status_code == 401
    assert resp.get_json() == {"success": False, "error": "Authentication required."}


@pytest.mark.parametrize("url", ["/", "/new", "/settings"])
def test_pages_require_authentication(client, url):
    assert client.get(url).status_code == 401


@pytest.mark.parametrize("url, template", [
    ("/", "balance.html"),
    ("/new", "transaction_form.html"),
    ("/settings", "settings.html"),
])
def test_pages_render_when_authenticated(client, login_as, monkeypatch, url, template):
    monkeypatch.setattr(main, "render_template", lambda name, **kw: f"rendered {name}")
    login_as(1)

    resp = client.get(url)

    assert resp.status_code == 200
    assert template in resp.get_data(as_text=True)


# --------------------------------------------------------------------------
# GET /api/balances
# --------------------------------------------------------------------------
def test_get_balances_uses_session_student(client, login_as, monkeypatch):
    data = {"student_id": 4, "login_id": "MP-X", "name": "Test", "swipes": 10,
            "starting_swipes": 10, "village_flex": 25.0, "campus_flex": 15.0,
            "setup_completed": True}
    fake = patch_autospec(monkeypatch, "get_balances", student.get_balances, return_value=data)
    login_as(4)

    resp = client.get("/api/balances")

    assert resp.status_code == 200
    assert resp.get_json() == {"success": True, "data": data}
    fake.assert_called_once_with(4)


def test_get_balances_lookup_error_is_404_and_clears_session(client, login_as, monkeypatch):
    patch_autospec(monkeypatch, "get_balances", student.get_balances,
                   side_effect=LookupError("gone"))
    login_as(4)

    resp = client.get("/api/balances")

    assert resp.status_code == 404
    assert resp.get_json() == {"success": False, "error": "gone"}
    assert "student_id" not in session_contents(client)


# --------------------------------------------------------------------------
# POST /api/setup/balances
# --------------------------------------------------------------------------
def test_setup_balances_success_json(client, login_as, fake_setup):
    login_as(5)

    resp = client.post("/api/setup/balances",
                       json={"swipes": 14, "village_flex": 100.0, "campus_flex": 50})

    assert resp.status_code == 200
    assert resp.get_json()["success"] is True
    assert resp.get_json()["data"]["setup_completed"] is True
    fake_setup.assert_called_once_with(student_id=5, swipes=14,
                                       village_flex=100.0, campus_flex=50)


def test_setup_balances_success_form_passes_strings_for_money(client, login_as, fake_setup):
    login_as(5)

    resp = client.post("/api/setup/balances",
                       data={"swipes": "14", "village_flex": "100.5", "campus_flex": "50"})

    assert resp.status_code == 200
    fake_setup.assert_called_once_with(student_id=5, swipes=14,
                                       village_flex="100.5", campus_flex="50")


@pytest.mark.parametrize("raw, expected", [(5.0, 5), ("5", 5), (5.0, 5), (0, 0)])
def test_setup_balances_normalizes_whole_number_swipes(client, login_as, fake_setup, raw, expected):
    login_as(5)

    resp = client.post("/api/setup/balances",
                       json={"swipes": raw, "village_flex": 1, "campus_flex": 1})

    assert resp.status_code == 200
    swipes = fake_setup.call_args.kwargs["swipes"]
    assert swipes == expected and isinstance(swipes, int)


@pytest.mark.parametrize("bad_swipes", [True, "abc", "", 5.5, "5.5", -1, "-1", None])
def test_setup_balances_rejects_bad_swipes(client, login_as, fake_setup, bad_swipes):
    login_as(5)

    resp = client.post("/api/setup/balances",
                       json={"swipes": bad_swipes, "village_flex": 1, "campus_flex": 1})

    assert resp.status_code == 400
    assert resp.get_json()["error"] == "Starting swipes must be a nonnegative whole number."
    fake_setup.assert_not_called()


@pytest.mark.parametrize("payload", [
    {"village_flex": 1, "campus_flex": 1},
    {"swipes": 1, "campus_flex": 1},
    {"swipes": 1, "village_flex": 1},
    {},
])
def test_setup_balances_requires_all_fields(client, login_as, fake_setup, payload):
    login_as(5)

    resp = client.post("/api/setup/balances", json=payload)

    assert resp.status_code == 400
    assert "all required" in resp.get_json()["error"]
    fake_setup.assert_not_called()


def test_setup_balances_validation_error_is_400(client, login_as, fake_setup):
    fake_setup.side_effect = ValueError("Starting balances have already been configured and cannot be changed.")
    login_as(5)

    resp = client.post("/api/setup/balances",
                       json={"swipes": 1, "village_flex": 1, "campus_flex": 1})

    assert resp.status_code == 400
    assert "already been configured" in resp.get_json()["error"]


def test_setup_balances_lookup_error_is_404_and_clears_session(client, login_as, fake_setup):
    fake_setup.side_effect = LookupError("gone")
    login_as(5)

    resp = client.post("/api/setup/balances",
                       json={"swipes": 1, "village_flex": 1, "campus_flex": 1})

    assert resp.status_code == 404
    assert "student_id" not in session_contents(client)


def test_setup_balances_unexpected_error_is_generic_500(client, login_as, fake_setup):
    fake_setup.side_effect = RuntimeError("secret internal detail")
    login_as(5)

    resp = client.post("/api/setup/balances",
                       json={"swipes": 1, "village_flex": 1, "campus_flex": 1})

    assert resp.status_code == 500
    assert resp.get_json()["error"] == "An internal error occurred."
    assert "secret internal detail" not in resp.get_data(as_text=True)


# --------------------------------------------------------------------------
# POST /api/swipes/reset
# --------------------------------------------------------------------------
def test_reset_swipes_success(client, login_as, fake_reset):
    login_as(5)

    resp = client.post("/api/swipes/reset")

    assert resp.status_code == 200
    assert resp.get_json() == {"success": True, "data": fake_reset.return_value}
    fake_reset.assert_called_once_with(5)


def test_reset_swipes_validation_error_is_400(client, login_as, fake_reset):
    fake_reset.side_effect = ValueError("Complete initial balance setup before resetting swipes.")
    login_as(5)

    resp = client.post("/api/swipes/reset")

    assert resp.status_code == 400
    assert "Complete initial balance setup" in resp.get_json()["error"]


def test_reset_swipes_lookup_error_is_404_and_clears_session(client, login_as, fake_reset):
    fake_reset.side_effect = LookupError("gone")
    login_as(5)

    resp = client.post("/api/swipes/reset")

    assert resp.status_code == 404
    assert "student_id" not in session_contents(client)


def test_reset_swipes_unexpected_error_is_generic_500(client, login_as, fake_reset):
    fake_reset.side_effect = RuntimeError("secret internal detail")
    login_as(5)

    resp = client.post("/api/swipes/reset")

    assert resp.status_code == 500
    assert resp.get_json()["error"] == "An internal error occurred."


# --------------------------------------------------------------------------
# GET /api/transactions
# --------------------------------------------------------------------------
def test_get_transactions_uses_session_student(client, login_as, monkeypatch):
    history = [{"id": 1, "type": "swipe", "amount": 1.0, "location": "Hall", "note": "n"}]
    fake = patch_autospec(monkeypatch, "get_transactions", transaction.get_transactions,
                          return_value=history)
    login_as(4)

    resp = client.get("/api/transactions")

    assert resp.status_code == 200
    assert resp.get_json() == {"success": True, "data": history}
    fake.assert_called_once_with(4)


def test_get_transactions_lookup_error_is_404_and_clears_session(client, login_as, monkeypatch):
    patch_autospec(monkeypatch, "get_transactions", transaction.get_transactions,
                   side_effect=LookupError("gone"))
    login_as(4)

    resp = client.get("/api/transactions")

    assert resp.status_code == 404
    assert "student_id" not in session_contents(client)


# --------------------------------------------------------------------------
# POST /api/transactions
# --------------------------------------------------------------------------
def test_post_transaction_success_form(client, login_as, fake_create):
    login_as(5)

    resp = client.post("/api/transactions", data={
        "type": "swipe", "amount": "1", "location": "Dining Hall", "note": "Lunch",
    })

    assert resp.status_code == 201
    assert resp.get_json()["success"] is True
    assert resp.get_json()["data"]["swipes"] == 9
    fake_create.assert_called_once_with(
        student_id=5, type="swipe", amount=1.0, location="Dining Hall", note="Lunch"
    )


def test_post_transaction_success_json(client, login_as, fake_create):
    login_as(5)

    resp = client.post("/api/transactions", json={
        "type": "campus_flex", "amount": 4.5, "location": "Store", "note": "Pens",
    })

    assert resp.status_code == 201
    fake_create.assert_called_once_with(
        student_id=5, type="campus_flex", amount=4.5, location="Store", note="Pens"
    )


def test_post_transaction_ignores_student_id_in_body(client, login_as, fake_create):
    """A client must not be able to act as another student."""
    login_as(5)

    client.post("/api/transactions", json={"type": "swipe", "amount": 1, "student_id": 99})

    assert fake_create.call_args.kwargs["student_id"] == 5


def test_post_transaction_missing_optional_fields_become_empty_strings(client, login_as, fake_create):
    login_as(5)

    client.post("/api/transactions", data={"type": "swipe", "amount": "1"})

    kwargs = fake_create.call_args.kwargs
    assert kwargs["location"] == ""
    assert kwargs["note"] == ""


def test_post_transaction_non_numeric_amount_is_400(client, login_as, fake_create):
    login_as(5)

    resp = client.post("/api/transactions", data={"type": "swipe", "amount": "abc"})

    assert resp.status_code == 400
    assert resp.get_json()["success"] is False
    fake_create.assert_not_called()


def test_post_transaction_validation_error_is_400(client, login_as, fake_create):
    fake_create.side_effect = ValueError("Insufficient Campus Flex balance.")
    login_as(5)

    resp = client.post("/api/transactions", data={"type": "campus_flex", "amount": "999"})

    assert resp.status_code == 400
    assert resp.get_json() == {"success": False, "error": "Insufficient Campus Flex balance."}


def test_post_transaction_lookup_error_is_404_and_clears_session(client, login_as, fake_create):
    fake_create.side_effect = LookupError("Student with ID 5 was not found.")
    login_as(5)

    resp = client.post("/api/transactions", data={"type": "swipe", "amount": "1"})

    assert resp.status_code == 404
    assert "student_id" not in session_contents(client)


def test_post_transaction_unexpected_error_is_generic_500(client, login_as, fake_create):
    fake_create.side_effect = RuntimeError("secret internal detail")
    login_as(5)

    resp = client.post("/api/transactions", data={"type": "swipe", "amount": "1"})

    assert resp.status_code == 500
    assert resp.get_json() == {"success": False, "error": "An internal error occurred."}
    assert "secret internal detail" not in resp.get_data(as_text=True)


# --------------------------------------------------------------------------
# Notifications
# --------------------------------------------------------------------------
def test_get_notification_settings_requires_authentication(client):
    resp = client.get("/api/notification-settings")

    assert resp.status_code == 401
    assert resp.get_json() == {"success": False, "error": "Authentication required."}


def test_get_notification_settings_returns_own_defaults(client, login_as, seeded):
    login_as(3)

    resp = client.get("/api/notification-settings")

    assert resp.status_code == 200
    assert resp.get_json() == {
        "success": True,
        "data": {
            "swipe_alert_threshold": None,
            "village_flex_alert_threshold": None,
            "campus_flex_alert_threshold": None,
        },
    }


def test_save_notification_settings(client, login_as, seeded):
    login_as(3)

    resp = client.post("/api/notification-settings", json={
        "swipe_alert_threshold": "5",
        "village_flex_alert_threshold": "10.50",
        "campus_flex_alert_threshold": "",
    })

    assert resp.status_code == 200
    assert resp.get_json() == {
        "success": True,
        "data": {
            "swipe_alert_threshold": 5,
            "village_flex_alert_threshold": 10.5,
            "campus_flex_alert_threshold": None,
        },
    }
    assert client.get("/api/notification-settings").get_json()["data"] == resp.get_json()["data"]


def test_save_notification_settings_requires_every_field(client, login_as, seeded):
    login_as(3)

    resp = client.post("/api/notification-settings", json={"swipe_alert_threshold": 5})

    assert resp.status_code == 400
    assert "are all required" in resp.get_json()["error"]


def test_save_notification_settings_rejects_invalid_value(client, login_as, seeded):
    login_as(3)

    resp = client.post("/api/notification-settings", json={
        "swipe_alert_threshold": 1.5,
        "village_flex_alert_threshold": None,
        "campus_flex_alert_threshold": None,
    })

    assert resp.status_code == 400
    assert "Swipe alert threshold" in resp.get_json()["error"]
    assert client.get("/api/notification-settings").get_json()["data"]["swipe_alert_threshold"] is None


@pytest.fixture
def notes(seeded):
    """Notifications: two for student 1 (First, Second), one for student 2 (Other)."""
    s = seeded()
    s.add_all([
        Notification(student_id=1, title="First", message="m1"),
        Notification(student_id=1, title="Second", message="m2"),
        Notification(student_id=2, title="Other", message="theirs"),
    ])
    s.commit()
    ids = [n.id for n in s.query(Notification).order_by(Notification.id)]
    s.close()
    return ids


def is_read(db, notification_id):
    s = db()
    try:
        return s.get(Notification, notification_id).is_read
    finally:
        s.close()


def test_get_notifications_returns_only_own_newest_first(client, login_as, notes):
    login_as(1)

    resp = client.get("/api/notifications")

    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert [n["title"] for n in data] == ["Second", "First"]
    assert data[0].keys() == {"id", "title", "message", "is_read", "created_at"}
    assert data[0]["message"] == "m2"
    assert data[0]["is_read"] is False
    assert isinstance(data[0]["created_at"], str)


def test_get_notifications_empty(client, login_as, seeded):
    login_as(3)

    assert client.get("/api/notifications").get_json() == {"success": True, "data": []}


def test_mark_notification_read_removes_it_from_unread_notifications(
    client, login_as, notes, db
):
    login_as(1)
    notification_id = notes[0]

    response = client.post(f"/api/notifications/{notification_id}/read")

    assert response.status_code == 200
    assert is_read(db, notification_id) is True


def test_mark_notification_read(client, login_as, notes, db):
    login_as(1)

    resp = client.post(f"/api/notifications/{notes[0]}/read")

    assert resp.status_code == 200
    assert resp.get_json() == {"success": True, "data": {"id": notes[0], "is_read": True}}
    assert is_read(db, notes[0]) is True
    assert is_read(db, notes[1]) is False        # others untouched


def test_cannot_mark_another_students_notification_read(client, login_as, notes, db):
    login_as(1)

    resp = client.post(f"/api/notifications/{notes[2]}/read")      # belongs to student 2

    assert resp.status_code == 404
    assert resp.get_json() == {"success": False, "error": "Notification not found."}
    assert is_read(db, notes[2]) is False


def test_mark_missing_notification_read_is_404(client, login_as, notes):
    login_as(1)

    assert client.post("/api/notifications/9999/read").status_code == 404


def test_mark_notification_read_rolls_back_on_error(client, login_as, monkeypatch, make_session):
    from types import SimpleNamespace
    note = SimpleNamespace(id=1, student_id=5, is_read=False)
    fake = make_session(transactions=[note], commit_error=RuntimeError("disk full"))
    monkeypatch.setattr(main, "SessionLocal", lambda: fake)
    login_as(5)

    resp = client.post("/api/notifications/1/read")

    assert resp.status_code == 500
    assert resp.get_json()["error"] == "An internal error occurred."
    assert fake.rolled_back is True
    assert fake.closed is True


# --------------------------------------------------------------------------
# End to end (no mocks)
# --------------------------------------------------------------------------
def test_e2e_new_student_must_complete_setup_before_spending(client, new_account):
    log_in(client, new_account)

    balances = client.get("/api/balances").get_json()["data"]
    assert balances["setup_completed"] is False
    assert (balances["swipes"], balances["village_flex"], balances["campus_flex"]) == (0, 0.0, 0.0)

    resp = client.post("/api/transactions", data={"type": "swipe", "amount": "1"})
    assert resp.status_code == 400
    assert "initial balance setup" in resp.get_json()["error"]

    resp = client.post("/api/swipes/reset")
    assert resp.status_code == 400


def test_e2e_register_then_setup_then_spend_then_reset(client):
    reg = client.post("/api/register", json={"username": "Alice", "password": "password123"})
    username = reg.get_json()["data"]["username"]
    assert session_contents(client)["student_id"] == reg.get_json()["data"]["student_id"]
    client.post("/api/logout")
    client.post("/api/login", json={"username": username, "password": "password123"})

    setup = client.post("/api/setup/balances",
                        json={"swipes": 14, "village_flex": 100, "campus_flex": 50.5})
    assert setup.status_code == 200
    assert setup.get_json()["data"]["starting_swipes"] == 14

    again = client.post("/api/setup/balances",
                        json={"swipes": 1, "village_flex": 1, "campus_flex": 1})
    assert again.status_code == 400
    assert "already been configured" in again.get_json()["error"]

    spend = client.post("/api/transactions", json={"type": "swipe", "amount": 4,
                                                   "location": "Hall", "note": "Dinner"})
    assert spend.status_code == 201
    assert spend.get_json()["data"]["swipes"] == 10

    reset = client.post("/api/swipes/reset")
    assert reset.status_code == 200
    assert reset.get_json()["data"]["previous_swipes"] == 10
    assert reset.get_json()["data"]["swipes"] == 14

    assert client.get("/api/balances").get_json()["data"]["swipes"] == 14
    history = client.get("/api/transactions").get_json()["data"]
    assert [t["type"] for t in history] == ["swipe_reset", "swipe"]


def test_e2e_setup_via_form_data(client, new_account):
    log_in(client, new_account)

    resp = client.post("/api/setup/balances",
                       data={"swipes": "14", "village_flex": "100", "campus_flex": "50.5"})

    assert resp.status_code == 200
    assert resp.get_json()["data"]["campus_flex"] == 50.5


def test_e2e_setup_rejects_negative_money(client, new_account):
    log_in(client, new_account)

    resp = client.post("/api/setup/balances",
                       json={"swipes": 1, "village_flex": -5, "campus_flex": 0})

    assert resp.status_code == 400
    assert client.get("/api/balances").get_json()["data"]["setup_completed"] is False


def test_e2e_spend_and_review(client, account):
    log_in(client, account)

    spend = client.post("/api/transactions", data={
        "type": "village_flex", "amount": "30", "location": "Market", "note": "Food",
    })
    assert spend.status_code == 201
    assert spend.get_json()["data"]["village_flex"] == 0.0
    assert spend.get_json()["data"]["campus_flex"] == pytest.approx(10.0)

    balances = client.get("/api/balances").get_json()["data"]
    assert balances["swipes"] == 10
    assert balances["campus_flex"] == pytest.approx(10.0)

    history = client.get("/api/transactions").get_json()["data"]
    assert [(t["type"], t["amount"], t["note"]) for t in history] == [("village_flex", 30.0, "Food")]


def test_e2e_notifications_flow(client, account):
    log_in(client, account)
    client.post("/api/transactions", data={"type": "swipe", "amount": "1"})

    data = client.get("/api/notifications").get_json()["data"]
    assert [n["title"] for n in data] == ["Meal-plan transaction recorded",
                                          "Starting balances saved"]
    assert all(n["is_read"] is False for n in data)

    resp = client.post(f"/api/notifications/{data[0]['id']}/read")
    assert resp.status_code == 200

    after = client.get("/api/notifications").get_json()["data"]
    assert [n["is_read"] for n in after] == [True, False]


def test_e2e_insufficient_funds_changes_nothing(client, account):
    log_in(client, account)

    resp = client.post("/api/transactions", data={"type": "campus_flex", "amount": "999"})

    assert resp.status_code == 400
    assert client.get("/api/balances").get_json()["data"]["campus_flex"] == 15.0
    assert client.get("/api/transactions").get_json()["data"] == []


@pytest.mark.parametrize("payload, message", [
    ({"type": "swipe"}, "greater than zero"),
    ({"type": "swipe", "amount": "1.5"}, "whole numbers"),
    ({"type": "bogus", "amount": "1"}, "Invalid transaction type"),
    ({"type": "swipe", "amount": "1", "note": "x" * 256}, "Note must be"),
])
def test_e2e_transaction_validation_errors(client, login_as, payload, message):
    login_as(1)

    resp = client.post("/api/transactions", json=payload)

    assert resp.status_code == 400
    assert message in resp.get_json()["error"]


def test_e2e_students_cannot_see_each_others_data(client, account):
    other = student.create_student("Bob", "password456")

    log_in(client, account)
    client.post("/api/transactions", data={"type": "swipe", "amount": "1",
                                           "location": "Hall", "note": "alice only"})

    bob = main.app.test_client()
    bob.post("/api/login", json={"username": other["name"], "password": "password456"})

    assert bob.get("/api/transactions").get_json()["data"] == []
    assert bob.get("/api/notifications").get_json()["data"] == []
    assert bob.get("/api/balances").get_json()["data"]["name"] == "Bob"


def test_e2e_session_for_deleted_student_is_404_and_cleared(client, login_as):
    login_as(999)       # no such student in the DB

    resp = client.get("/api/balances")

    assert resp.status_code == 404
    assert "student_id" not in session_contents(client)
