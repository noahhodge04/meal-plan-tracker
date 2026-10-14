import os

from flask import Flask, jsonify, render_template, request, session
from sqlalchemy import inspect, text
from werkzeug.security import check_password_hash

from database import SessionLocal, engine, Base
from models import Student, Notification
from student import (
    create_student,
    get_balances,
    get_notification_settings,
    reset_swipes_to_starting_balance,
    set_notification_settings,
    set_starting_balances,
)
from transaction import create_transaction, get_transactions


app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("FLASK_SECRET_KEY")
if not app.config["SECRET_KEY"]:
    raise RuntimeError("FLASK_SECRET_KEY environment variable is required.")


Base.metadata.create_all(engine)


def get_authenticated_student_id():
    return session.get("student_id")


def request_data():
    """Accept JSON requests and standard form submissions."""
    return request.get_json(silent=True) or request.form


def error_response(message, status):
    return jsonify({"success": False, "error": message}), status


@app.route("/api/register", methods=["POST"])
def api_register():
    data = request_data()
    try:
        new_student = create_student(data.get("name", ""), data.get("password", ""))
        api_login()
        
        return jsonify({
            "success": True,
            "data": new_student,
        }), 201
    
    except ValueError as e:
        return error_response(str(e), 400)
    except Exception:
        app.logger.exception("Failed to register student")
        return error_response("An internal error occurred.", 500)


@app.route("/api/login", methods=["POST"])
def api_login():
    data = request_data()

    name = data.get("name", "")
    password = data.get("password", "")

    if not isinstance(name, str) or not name.strip() or not isinstance(password, str) or not password:
        return error_response("Login ID and password are required.", 400)

    db = SessionLocal()
    try:
        student = (
            db.query(Student)
            .filter_by(name=name.strip())
            .first()
        )
        if (
            student is None
            or not student.password_hash
            or not check_password_hash(
                student.password_hash,
                password,
            )
        ):
            return error_response("Invalid login ID or password.", 401)

        session.clear()
        session["student_id"] = student.id
        return jsonify({
            "success": True,
            "data": {
                "student_id": student.id,
                "login_id": student.login_id,
                "name": student.name,
                "setup_completed": student.setup_completed,
            },
        }), 200
    finally:
        db.close()


@app.route("/api/logout", methods=["POST"])
def api_logout():
    session.clear()
    return jsonify({
        "success": True,
        "message": "Logged out successfully.",
    }), 200


@app.route("/")
def home():
    if get_authenticated_student_id() is None:
        return render_template("./login_form.html"), 401
    return render_template("./balance.html")


@app.route("/new")
def transaction_page():
    if get_authenticated_student_id() is None:
        return render_template("./login_form.html"), 401
    return render_template("./transaction_form.html")


@app.route("/settings")
def settings_page():
    if get_authenticated_student_id() is None:
        return render_template("./login_form.html"), 401
    return render_template("./settings.html")


@app.route("/login")
def login_page():
    return render_template("./login_form.html")

@app.route("/register")
def register_page():
    return render_template("./register_form.html")

@app.route("/setup")
def balance_setup_page():
    if get_authenticated_student_id() is None:
            return render_template("./login_form.html"), 401
    return render_template("./balance_form.html")


@app.route("/api/balances", methods=["GET"])
def api_get_balances():
    student_id = get_authenticated_student_id()
    if student_id is None:
        return error_response("Authentication required.", 401)
    try:
        return jsonify({"success": True, "data": get_balances(student_id)}), 200
    except LookupError as e:
        session.clear()
        return error_response(str(e), 404)


@app.route("/api/setup/balances", methods=["POST"])
def api_set_starting_balances():
    student_id = get_authenticated_student_id()
    if student_id is None:
        return error_response("Authentication required.", 401)

    data = request_data()
    try:
        if any(key not in data for key in ("swipes", "village_flex", "campus_flex")):
            raise ValueError("swipes, village_flex, and campus_flex are all required.")
        raw_swipes = data.get("swipes")
        if isinstance(raw_swipes, bool):
            raise ValueError("Starting swipes must be a nonnegative whole number.")
        try:
            swipes = int(raw_swipes)
        except (TypeError, ValueError):
            raise ValueError("Starting swipes must be a nonnegative whole number.")
        if str(raw_swipes).strip() not in (str(swipes), f"{swipes}.0") or swipes < 0:
            raise ValueError("Starting swipes must be a nonnegative whole number.")
        balances = set_starting_balances(
            student_id=student_id,
            swipes=swipes,
            village_flex=data.get("village_flex"),
            campus_flex=data.get("campus_flex"),
        )
        return jsonify({"success": True, "data": balances}), 200
    except ValueError as e:
        return error_response(str(e), 400)
    except LookupError as e:
        session.clear()
        return error_response(str(e), 404)
    except Exception:
        app.logger.exception("Failed to save starting balances")
        return error_response("An internal error occurred.", 500)


@app.route("/api/swipes/reset", methods=["POST"])
def api_reset_swipes():
    student_id = get_authenticated_student_id()
    if student_id is None:
        return error_response("Authentication required.", 401)
    try:
        result = reset_swipes_to_starting_balance(student_id)
        return jsonify({"success": True, "data": result}), 200
    except ValueError as e:
        return error_response(str(e), 400)
    except LookupError as e:
        session.clear()
        return error_response(str(e), 404)
    except Exception:
        app.logger.exception("Failed to reset swipes")
        return error_response("An internal error occurred.", 500)


@app.route("/api/transactions", methods=["GET"])
def api_get_transactions():
    student_id = get_authenticated_student_id()
    if student_id is None:
        return error_response("Authentication required.", 401)
    try:
        return jsonify({
            "success": True,
            "data": get_transactions(student_id),
        }), 200
    except LookupError as e:
        session.clear()
        return error_response(str(e), 404)


@app.route("/api/transactions", methods=["POST"])
def api_create_transaction():
    student_id = get_authenticated_student_id()
    if student_id is None:
        return error_response("Authentication required.", 401)
    data = request_data()
    amount = data.get("amount")
    try:
        if amount is not None:
            amount = float(amount)
        updated_balances = create_transaction(
            student_id=student_id,
            type=data.get("type"),
            amount=amount,
            location=data.get("location", ""),
            note=data.get("note", ""),
        )
        return jsonify({
            "success": True,
            "data": updated_balances,
        }), 201
    except ValueError as e:
        return error_response(str(e), 400)
    except LookupError as e:
        session.clear()
        return error_response(str(e), 404)
    except Exception:
        app.logger.exception("Failed to create transaction")
        return error_response("An internal error occurred.", 500)


@app.route("/api/notifications", methods=["GET"])
def api_get_notifications():
    student_id = get_authenticated_student_id()
    if student_id is None:
        return error_response("Authentication required.", 401)

    db = SessionLocal()
    try:
        notifications = (
            db.query(Notification)
            .filter_by(student_id=student_id)
            .order_by(Notification.id.desc())
            .all()
        )
        return jsonify({
            "success": True,
            "data": [{
                "id": item.id,
                "title": item.title,
                "message": item.message,
                "is_read": item.is_read,
                "created_at": item.created_at.isoformat() if item.created_at else None,
            } for item in notifications],
        }), 200
    finally:
        db.close()


@app.route("/api/notification-settings", methods=["GET", "POST"])
def api_notification_settings():
    student_id = get_authenticated_student_id()
    if student_id is None:
        return error_response("Authentication required.", 401)

    if request.method == "GET":
        try:
            return jsonify({
                "success": True,
                "data": get_notification_settings(student_id),
            }), 200
        except LookupError as e:
            session.clear()
            return error_response(str(e), 404)
        except Exception:
            app.logger.exception("Failed to get notification settings")
            return error_response("An internal error occurred.", 500)

    data = request_data()
    fields = (
        "swipe_alert_threshold",
        "village_flex_alert_threshold",
        "campus_flex_alert_threshold",
    )
    if any(field not in data for field in fields):
        return error_response(f"{', '.join(fields)} are all required.", 400)
    try:
        settings = set_notification_settings(
            student_id=student_id,
            **{field: data.get(field) for field in fields},
        )
        return jsonify({"success": True, "data": settings}), 200
    except ValueError as e:
        return error_response(str(e), 400)
    except LookupError as e:
        session.clear()
        return error_response(str(e), 404)
    except Exception:
        app.logger.exception("Failed to save notification settings")
        return error_response("An internal error occurred.", 500)


@app.route("/api/notifications/<int:notification_id>/read", methods=["POST"])
def api_mark_notification_read(notification_id):
    student_id = get_authenticated_student_id()
    if student_id is None:
        return error_response("Authentication required.", 401)

    db = SessionLocal()
    try:
        notification = db.query(Notification).filter_by(
            id=notification_id,
            student_id=student_id,
        ).first()
        if notification is None:
            return error_response("Notification not found.", 404)
        notification.is_read = True
        db.commit()
        return jsonify({"success": True, "data": {"id": notification.id, "is_read": True}}), 200
    except Exception:
        db.rollback()
        app.logger.exception("Failed to mark notification as read")
        return error_response("An internal error occurred.", 500)
    finally:
        db.close()


if __name__ == "__main__":
    app.run(debug=True)