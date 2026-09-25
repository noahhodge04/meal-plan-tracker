from flask import Flask, jsonify, render_template, request
from backend import create_transaction, get_balances, get_transactions
#from database import engine, Base
#from models import Student, Transaction

app = Flask(__name__)


#Base.metadata.create_all(engine)


@app.route("/")
def home():
    return "Meal Plan Tracker is running!"

@app.route("/api/balances", methods=["GET"])
def api_get_balances():
    """API endpoint to retrieve student balances."""
    try:
        balances = get_balances()
        return jsonify({"success": True, "data": balances}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/transactions", methods=["GET"])
def api_get_transactions():
    """API endpoint to retrieve transaction history."""
    try:
        history = get_transactions()
        return jsonify({"success": True, "data": history}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/transactions", methods=["POST"])
def api_create_transaction():
    """API endpoint to submit a new transaction."""
    data = request.get_json() or {}

    transaction_type = data.get("type")
    amount = data.get("amount")
    location = data.get("location", "")
    note = data.get("note", "")

    try:
        if amount is not None:
            amount = float(amount)

        updated_balances = create_transaction(
            transaction_type=transaction_type,
            amount=amount,
            location=location,
            note=note,
        )
        return jsonify({"success": True, "data": updated_balances}), 201
    except ValueError as ve:
        return jsonify({"success": False, "error": str(ve)}), 400
    except Exception as e:
        return jsonify({"success": False, "error":str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True)