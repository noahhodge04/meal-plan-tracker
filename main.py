import os

from flask import Flask, jsonify, render_template, request, session

from werkzeug.security import check_password_hash

from database import SessionLocal, engine, Base
from models import Student
from student import get_balances, create_student
from transaction import create_transaction, get_transactions


Base.metadata.create_all(engine)

app = Flask(__name__)

app.config["SECRET_KEY"] = os.environ.get("FLASK_SECRET_KEY")

if not app.config["SECRET_KEY"]:
    raise RuntimeError("FLASK_SECRET_KEY environment variable is required.")


@app.route("/api/register", methods=["POST"])
def api_register():
    data = request.get_json(silent=True) or request.form

    name = data.get("name", "")
    password = data.get("password", "")

    try:
        new_student = create_student(name, password)

        return jsonify({
            "success": True,
            "data": new_student,
        }), 201

    except ValueError as e:
        return jsonify({
            "success": False,
            "error": str(e),
        }), 400


@app.route("/api/login", methods=["POST"])
def api_login():
    data = request.get_json(silent=True) or request.form

    login_id = data.get("login_id", "").strip()
    password = data.get("password", "")

    if not login_id or not password:
        return jsonify({
            "success": False,
            "error": "Login ID and password are required.",
        }), 400

    db = SessionLocal()

    try:
        student = (
            db.query(Student)
            .filter_by(login_id=login_id)
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
            return jsonify({
                "success": False,
                "error": "Invalid login ID or password.",
            }), 401

        # Start a fresh authenticated session.
        session.clear()
        session["student_id"] = student.id

        return jsonify({
            "success": True,
            "data": {
                "student_id": student.id,
                "login_id": student.login_id,
                "name": student.name,
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

def get_authenticated_student_id():
    return session.get("student_id")

@app.route("/")
def home():
    if get_authenticated_student_id() is None:
        return "Authentication required", 401

    return render_template("./balance.html")


@app.route("/new")
def transaction_page():
    if get_authenticated_student_id() is None:
        return "Authentication required", 401

    return render_template("./transaction_form.html")


@app.route("/api/balances", methods=["GET"])
def api_get_balances():
    student_id = get_authenticated_student_id()

    if student_id is None:
        return jsonify({
            "success": False,
            "error": "Authentication required.",
        }), 401

    try:
        balances = get_balances(student_id)

        return jsonify({
            "success": True,
            "data": balances,
        }), 200

    except LookupError as e:
        session.clear()
        return jsonify({
            "success": False,
            "error": str(e),
        }), 404

    
@app.route("/api/transactions", methods=["GET"])
def api_get_transactions():
    student_id = get_authenticated_student_id()

    if student_id is None:
        return jsonify({
            "success": False,
            "error": "Authentication required.",
        }), 401

    try:
        history = get_transactions(student_id)
        return jsonify({
            "success": True,
            "data": history,
        }), 200

    except LookupError as e:
        session.clear()
        return jsonify({
            "success": False,
            "error": str(e),
        }), 404

@app.route("/api/transactions", methods=["POST"])
def api_create_transaction():
    student_id = get_authenticated_student_id()

    if student_id is None:
        return jsonify({
            "success": False,
            "error": "Authentication required.",
        }), 401

    data = request.get_json(silent=True) or request.form

    transaction_type = data.get("type")
    amount = data.get("amount")
    location = data.get("location", "")
    note = data.get("note", "")

    try:
        if amount is not None:
            amount = float(amount)

        updated_balances = create_transaction(
            student_id=student_id,
            type=transaction_type,
            amount=amount,
            location=location,
            note=note,
        )

        return jsonify({
            "success": True,
            "data": updated_balances,
        }), 201

    except ValueError as e:
        return jsonify({
            "success": False,
            "error": str(e),
        }), 400

    except LookupError as e:
        session.clear()
        return jsonify({
            "success": False,
            "error": str(e),
        }), 404

    except Exception:
        app.logger.exception("Failed to create transaction")
        return jsonify({
            "success": False,
            "error": "An internal error occurred.",
        }), 500


if __name__ == "__main__":
    app.run(debug=True)