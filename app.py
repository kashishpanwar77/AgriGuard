from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash
)

from werkzeug.security import generate_password_hash, check_password_hash

from database import get_db_connection

from functools import wraps

import joblib
import pandas as pd
import os
from dotenv import load_dotenv

load_dotenv()

# ============================================================
# FLASK APP
# ============================================================

app = Flask(__name__)

app.secret_key = os.getenv("FLASK_SECRET_KEY")


# ============================================================
# LOAD ML MODEL
# ============================================================

model = joblib.load("agriguard_boost_model.pkl")
preprocessor = joblib.load("agriguard_preprocessor.pkl")


# ============================================================
# LOAD DATASET
# ============================================================

dataset = pd.read_csv("dataset/Data.csv")

dataset = dataset.drop_duplicates().copy()


countries = sorted(
    dataset["country"]
    .dropna()
    .unique()
    .tolist()
)


crops = sorted(
    dataset["commodity"]
    .dropna()
    .unique()
    .tolist()
)


activities = sorted(
    dataset["activity"]
    .dropna()
    .unique()
    .tolist()
)


stages = sorted(
    dataset["food_supply_stage"]
    .dropna()
    .unique()
    .tolist()
)


# Model was trained using 2000–2022
MIN_YEAR = 2000
MAX_YEAR = 2022


# ============================================================
# LOGIN REQUIRED DECORATOR
# ============================================================

def login_required(function):

    @wraps(function)
    def wrapper(*args, **kwargs):

        if "user_id" not in session:

            flash(
                "Please login to continue.",
                "warning"
            )

            return redirect(
                url_for("login")
            )

        return function(*args, **kwargs)

    return wrapper


# ============================================================
# HOME
# ============================================================

@app.route("/", methods=["GET", "POST"])
@login_required
def home():

    result = None

    if request.method == "POST":

        try:

            country = request.form["country"]
            crop = request.form["crop"]
            year = int(request.form["year"])
            activity = request.form["activity"]
            stage = request.form["stage"]
            quantity = float(request.form["quantity"])

            # ------------------------------------------------
            # YEAR VALIDATION
            # ------------------------------------------------

            if year < MIN_YEAR or year > MAX_YEAR:

                flash(
                    "Prediction year must be between 2000 and 2022.",
                    "danger"
                )

                return redirect(
                    url_for("home")
                )

            # ------------------------------------------------
            # INPUT DATA FOR ML MODEL
            # ------------------------------------------------

            input_data = pd.DataFrame([
                {
                    "country": country,
                    "commodity": crop,
                    "year": year,
                    "activity": activity,
                    "food_supply_stage": stage
                }
            ])

            # ------------------------------------------------
            # PREPROCESS
            # ------------------------------------------------

            input_encoded = preprocessor.transform(
                input_data
            )

            # ------------------------------------------------
            # PREDICTION
            # ------------------------------------------------

            predicted_loss = model.predict(
                input_encoded.toarray()
            )[0]

            # Prevent negative prediction
            predicted_loss = max(
                0,
                predicted_loss
            )

            predicted_loss = round(
                predicted_loss,
                2
            )

            # ------------------------------------------------
            # RISK CLASSIFICATION
            # ------------------------------------------------

            if predicted_loss < 3:

                risk_level = "Low"

                recommendation = (
                    "Loss risk is low. Continue proper handling, "
                    "storage and regular monitoring."
                )

            elif predicted_loss < 6:

                risk_level = "Medium"

                recommendation = (
                    "Moderate loss risk detected. Improve handling, "
                    "storage conditions and transportation practices."
                )

            else:

                risk_level = "High"

                recommendation = (
                    "High loss risk detected. Review storage, "
                    "handling and transportation practices and "
                    "take preventive action."
                )

            # ------------------------------------------------
            # SAVE PREDICTION
            # ------------------------------------------------

            connection = get_db_connection()

            cursor = connection.cursor()

            query = """
            INSERT INTO loss_records
            (
                user_id,
                crop,
                stage,
                quantity,
                loss_percentage,
                region,
                risk_level
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """

            values = (
                session["user_id"],
                crop,
                stage,
                quantity,
                predicted_loss,
                country,
                risk_level
            )

            cursor.execute(
                query,
                values
            )

            connection.commit()

            cursor.close()

            connection.close()

            # ------------------------------------------------
            # RESULT
            # ------------------------------------------------

            result = {

                "country": country,

                "crop": crop,

                "year": year,

                "activity": activity,

                "stage": stage,

                "quantity": quantity,

                "loss_percentage": predicted_loss,

                "risk_level": risk_level,

                "recommendation": recommendation

            }

        except Exception as error:

            flash(
                f"Prediction failed: {error}",
                "danger"
            )

    return render_template(
        "index.html",

        result=result,

        countries=countries,

        crops=crops,

        activities=activities,

        stages=stages,

        min_year=MIN_YEAR,

        max_year=MAX_YEAR,

        user_name=session.get("user_name")
    )


# ============================================================
# REGISTER
# ============================================================

@app.route(
    "/register",
    methods=["GET", "POST"]
)
def register():

    if "user_id" in session:

        return redirect(
            url_for("home")
        )

    if request.method == "POST":

        full_name = request.form["full_name"].strip()

        email = request.form["email"].strip().lower()

        password = request.form["password"]

        confirm_password = request.form["confirm_password"]

        # ------------------------------------------------
        # VALIDATION
        # ------------------------------------------------

        if not full_name:

            flash(
                "Please enter your full name.",
                "danger"
            )

            return redirect(
                url_for("register")
            )

        if password != confirm_password:

            flash(
                "Passwords do not match.",
                "danger"
            )

            return redirect(
                url_for("register")
            )

        if len(password) < 6:

            flash(
                "Password must contain at least 6 characters.",
                "danger"
            )

            return redirect(
                url_for("register")
            )

        # ------------------------------------------------
        # DATABASE
        # ------------------------------------------------

        connection = get_db_connection()

        cursor = connection.cursor(
            dictionary=True
        )

        cursor.execute(
            """
            SELECT id
            FROM users
            WHERE email = %s
            """,
            (email,)
        )

        existing_user = cursor.fetchone()

        if existing_user:

            cursor.close()

            connection.close()

            flash(
                "An account with this email already exists.",
                "warning"
            )

            return redirect(
                url_for("login")
            )

        # ------------------------------------------------
        # HASH PASSWORD
        # ------------------------------------------------

        password_hash = generate_password_hash(
            password
        )

        cursor.execute(
            """
            INSERT INTO users
            (full_name, email, password_hash)
            VALUES (%s, %s, %s)
            """,
            (
                full_name,
                email,
                password_hash
            )
        )

        connection.commit()

        cursor.close()

        connection.close()

        flash(
            "Account created successfully. Please login.",
            "success"
        )

        return redirect(
            url_for("login")
        )

    return render_template(
        "register.html"
    )


# ============================================================
# LOGIN
# ============================================================

@app.route(
    "/login",
    methods=["GET", "POST"]
)
def login():

    if "user_id" in session:

        return redirect(
            url_for("home")
        )

    if request.method == "POST":

        email = request.form["email"].strip().lower()

        password = request.form["password"]

        connection = get_db_connection()

        cursor = connection.cursor(
            dictionary=True
        )

        cursor.execute(
            """
            SELECT *
            FROM users
            WHERE email = %s
            """,
            (email,)
        )

        user = cursor.fetchone()

        cursor.close()

        connection.close()

        if user and check_password_hash(
            user["password_hash"],
            password
        ):

            session["user_id"] = user["id"]

            session["user_name"] = user["full_name"]

            session["user_email"] = user["email"]

            flash(
                f"Welcome back, {user['full_name']}!",
                "success"
            )

            return redirect(
                url_for("home")
            )

        flash(
            "Invalid email or password.",
            "danger"
        )

    return render_template(
        "login.html"
    )


# ============================================================
# LOGOUT
# ============================================================

@app.route("/logout")
def logout():

    session.clear()

    flash(
        "You have been logged out.",
        "success"
    )

    return redirect(
        url_for("login")
    )


# ============================================================
# DASHBOARD
# ============================================================

@app.route("/dashboard")
@login_required
def dashboard():

    connection = get_db_connection()

    cursor = connection.cursor(
        dictionary=True
    )

    user_id = session["user_id"]

    # ------------------------------------------------
    # TOTAL RECORDS
    # ------------------------------------------------

    cursor.execute(
        """
        SELECT COUNT(*) AS total_records
        FROM loss_records
        WHERE user_id = %s
        """,
        (user_id,)
    )

    total_records = cursor.fetchone()["total_records"]

    # ------------------------------------------------
    # AVERAGE LOSS
    # ------------------------------------------------

    cursor.execute(
        """
        SELECT AVG(loss_percentage) AS average_loss
        FROM loss_records
        WHERE user_id = %s
        """,
        (user_id,)
    )

    average_loss = cursor.fetchone()["average_loss"]

    if average_loss is None:

        average_loss = 0

    # ------------------------------------------------
    # RISK COUNTS
    # ------------------------------------------------

    cursor.execute(
        """
        SELECT COUNT(*) AS high_risk
        FROM loss_records
        WHERE user_id = %s
        AND risk_level = 'High'
        """,
        (user_id,)
    )

    high_risk = cursor.fetchone()["high_risk"]

    cursor.execute(
        """
        SELECT COUNT(*) AS medium_risk
        FROM loss_records
        WHERE user_id = %s
        AND risk_level = 'Medium'
        """,
        (user_id,)
    )

    medium_risk = cursor.fetchone()["medium_risk"]

    cursor.execute(
        """
        SELECT COUNT(*) AS low_risk
        FROM loss_records
        WHERE user_id = %s
        AND risk_level = 'Low'
        """,
        (user_id,)
    )

    low_risk = cursor.fetchone()["low_risk"]

    # ------------------------------------------------
    # RECORDS
    # ------------------------------------------------

    cursor.execute(
        """
        SELECT *
        FROM loss_records
        WHERE user_id = %s
        ORDER BY id DESC
        """,
        (user_id,)
    )

    records = cursor.fetchall()

    # ------------------------------------------------
    # CROP ANALYTICS
    # ------------------------------------------------

    cursor.execute(
        """
        SELECT
            crop,
            AVG(loss_percentage) AS average_loss
        FROM loss_records
        WHERE user_id = %s
        GROUP BY crop
        ORDER BY average_loss DESC
        """,
        (user_id,)
    )

    crop_data = cursor.fetchall()

    # ------------------------------------------------
    # STAGE ANALYTICS
    # ------------------------------------------------

    cursor.execute(
        """
        SELECT
            stage,
            AVG(loss_percentage) AS average_loss
        FROM loss_records
        WHERE user_id = %s
        GROUP BY stage
        ORDER BY average_loss DESC
        """,
        (user_id,)
    )

    stage_data = cursor.fetchall()

    cursor.close()

    connection.close()

    # ------------------------------------------------
    # RISK PERCENTAGES
    # ------------------------------------------------

    risk_total = (
        low_risk
        + medium_risk
        + high_risk
    )

    if risk_total > 0:

        low_percent = round(
            low_risk / risk_total * 100,
            2
        )

        medium_percent = round(
            medium_risk / risk_total * 100,
            2
        )

        high_percent = round(
            high_risk / risk_total * 100,
            2
        )

    else:

        low_percent = 0

        medium_percent = 0

        high_percent = 0

    return render_template(

        "dashboard.html",

        total_records=total_records,

        average_loss=round(
            average_loss,
            2
        ),

        high_risk=high_risk,

        medium_risk=medium_risk,

        low_risk=low_risk,

        low_percent=low_percent,

        medium_percent=medium_percent,

        high_percent=high_percent,

        records=records,

        crop_data=crop_data,

        stage_data=stage_data,

        user_name=session.get(
            "user_name"
        )

    )


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    app.run(
        debug=True
    )
