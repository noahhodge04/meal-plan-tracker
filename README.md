# Meal Plan Tracker

A web app built for Grace College students for tracking meal-plan swipes, village flex, and campus flex. It includes account registration and login, transaction history, balance setup, swipe resets, in-app notifications, and optional per-account low-balance alerts.

## Requirements

- Python 3.10 or newer
- Windows, macOS, or Linux

## Install

Open a terminal in the project directory, then create a virtual environment.

### Windows (PowerShell)

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

If PowerShell blocks virtual-environment activation, use the environment's Python executable directly instead:

```powershell
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### macOS or Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Configure

The application requires `FLASK_SECRET_KEY` to sign session cookies. Generate a strong random value:

```console
python -c "import secrets; print(secrets.token_hex(32))"
```

Set the value in the terminal session where you will run Flask.

### Windows (PowerShell)

```powershell
$env:FLASK_SECRET_KEY = "paste-the-generated-value-here"
```

### macOS or Linux

```bash
export FLASK_SECRET_KEY="paste-the-generated-value-here"
```

Keep this value private, do not commit it, and use the same value while the app is running. Changing it invalidates existing login sessions. For a deployed app, configure it through the hosting provider's secret/environment-variable settings rather than hard-coding it.

Each account must have a unique username. If an existing database contains students with duplicate names, update those names to unique usernames before starting this version; the database enforces username uniqueness.

## Run

With the virtual environment active and `FLASK_SECRET_KEY` set, start the development server:

```console
python main.py
```

On Windows, `run.bat` starts the same Flask command. Open <http://127.0.0.1:5000> in your browser. Stop the server with `Ctrl+C`.

The built-in Flask server is for local development. Use a production WSGI server and secure deployment configuration when hosting the app publicly.

## Using the app

1. Register with a unique username. You are logged in automatically; use that username and your password for future sign-ins.
2. Set starting swipe and flex balances during initial setup. Setup can only be completed once per account.
3. Record transactions from **New Transaction**. Transactions update balances and create in-app notifications.
4. Visit **Settings** to set optional low-balance thresholds for swipes, village flex, and campus flex. Leave a field blank to disable that alert. An alert is created when a transaction takes the balance from above its threshold to at or below it; another alert is possible after the balance rises above the threshold and crosses it again.
5. Review unread notifications on the home page and mark them as read to remove them from the unread list.

## Tests

Install the requirements, configure `FLASK_SECRET_KEY`, and run:

```console
pytest
```
