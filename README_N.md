# Meal-Plan Tracker backend update

This update adds one-time starting balance setup, manual swipe restoration, and persistent in-app notifications while leaving templates/UI unchanged.

## Configuration and run

Set `FLASK_SECRET_KEY` to a long, random secret before starting the Flask app. Install the project's dependencies (Flask, SQLAlchemy, and Werkzeug), then run `python main.py` from this directory or integrate these files into the existing project.

bash
```
python -c "import secrets; print(secrets.token_hex(32))"

$env:FLASK_SECRET_KEY = "paste-your-generated-key-here"

python main.py
```

## New endpoints

- `POST /api/setup/balances` — authenticated, one-time initial balance setup. JSON body: `{"swipes": 19, "village_flex": 25.00, "campus_flex": 15.00}`.
- `POST /api/swipes/reset` — authenticated manual reset to the saved `starting_swipes` amount. Body may be empty.
- `GET /api/notifications` — list the authenticated student's notifications.
- `POST /api/notifications/<id>/read` — mark one of that student's notifications as read.

Existing `/api/register`, `/api/login`, `/api/logout`, `/api/balances`, and `/api/transactions` routes remain available. Registration logs the student in automatically; later sign-ins use the chosen unique username and password. Login returns `setup_completed` so a future UI can route appropriately.

## Behavior notes

- Starting balances can only be saved once per account. The reset uses `starting_swipes`, not the current swipe balance.
- Resetting swipes records a `swipe_reset` transaction and creates a notification. Transactions also create notifications.
- Clearing transaction history remains separate from resetting balances.
- Startup creates new tables and includes a small SQLite-only migration for `starting_swipes` and `setup_completed`. Back up any existing `meal_tracker.db` before running this update. If you use a non-SQLite database, apply an equivalent schema migration before running.
- The existing HTML templates are not modified. The new APIs are backend foundations and are not wired into UI controls yet.
