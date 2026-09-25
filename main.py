from flask import Flask
from database import engine, Base
from models import Student, Transaction

app = Flask(__name__)


Base.metadata.create_all(engine)


@app.route("/")
def home():
    return "Meal Plan Tracker is running!"

if __name__ == "__main__":
    app.run(debug=True)