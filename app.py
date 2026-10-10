"""
Smart Car Parking Management System
Flask + SQLite full-stack college project (MCA/BCA)
Run: python app.py
"""

import os
import sqlite3
import random
import string
from datetime import datetime, date, time as dtime

from flask import (
    Flask, render_template, request, redirect, url_for,
    session, flash, g, jsonify
)
from werkzeug.security import generate_password_hash, check_password_hash

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATABASE = os.path.join(BASE_DIR, "parking.db")

app = Flask(__name__)
app.secret_key = "smart-parking-secret-key-2026-change-in-production"

# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def get_db():
    db = getattr(g, "_database", None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
    return db


@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, "_database", None)
    if db is not None:
        db.close()


def init_db():
    """Create tables if they do not exist, and seed sample data."""
    first_time = not os.path.exists(DATABASE)
    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    cur = db.cursor()

    cur.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            phone TEXT,
            password TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS parking_slots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            slot_number TEXT UNIQUE NOT NULL,
            floor TEXT NOT NULL,
            slot_type TEXT NOT NULL DEFAULT 'Car',
            status TEXT NOT NULL DEFAULT 'available',
            price_per_hour REAL NOT NULL DEFAULT 50
        );

        CREATE TABLE IF NOT EXISTS vehicles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            vehicle_number TEXT NOT NULL,
            vehicle_type TEXT NOT NULL,
            vehicle_model TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id)
        );

        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            booking_id TEXT UNIQUE NOT NULL,
            user_id INTEGER NOT NULL,
            slot_id INTEGER NOT NULL,
            vehicle_id INTEGER NOT NULL,
            booking_date TEXT NOT NULL,
            entry_time TEXT NOT NULL,
            exit_time TEXT NOT NULL,
            duration REAL NOT NULL,
            amount REAL NOT NULL,
            status TEXT NOT NULL DEFAULT 'confirmed',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (slot_id) REFERENCES parking_slots (id),
            FOREIGN KEY (vehicle_id) REFERENCES vehicles (id)
        );
        """
    )
    db.commit()

    # Seed default admin
    cur.execute("SELECT id FROM users WHERE email = ?", ("admin@parking.com",))
    if cur.fetchone() is None:
        cur.execute(
            "INSERT INTO users (name, email, phone, password, role) VALUES (?,?,?,?,?)",
            ("Administrator", "admin@parking.com", "9999999999",
             generate_password_hash("admin123"), "admin"),
        )

    # Seed sample user
    cur.execute("SELECT id FROM users WHERE email = ?", ("user@parking.com",))
    if cur.fetchone() is None:
        cur.execute(
            "INSERT INTO users (name, email, phone, password, role) VALUES (?,?,?,?,?)",
            ("Sample User", "user@parking.com", "9876543210",
             generate_password_hash("user123"), "user"),
        )

    # Seed parking slots (3 rows A/B/C x 5 = 15 slots) if empty
    cur.execute("SELECT COUNT(*) AS c FROM parking_slots")
    if cur.fetchone()["c"] == 0:
        floors = {"A": "Ground Floor", "B": "First Floor", "C": "Second Floor"}
        slot_types = ["Car", "Car", "Car", "SUV", "Bike"]
        for row_letter, floor_name in floors.items():
            for i in range(1, 6):
                slot_number = f"{row_letter}{i}"
                slot_type = random.choice(slot_types)
                price = 30 if slot_type == "Bike" else (70 if slot_type == "SUV" else 50)
                status = "available"
                cur.execute(
                    "INSERT INTO parking_slots (slot_number, floor, slot_type, status, price_per_hour) "
                    "VALUES (?,?,?,?,?)",
                    (slot_number, floor_name, slot_type, status, price),
                )

    db.commit()
    db.close()
    if first_time:
        print("Database initialized with sample data.")


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------

def generate_booking_id():
    year = datetime.now().year
    suffix = "".join(random.choices(string.digits, k=5))
    return f"SP-{year}-{suffix}"


def login_required(view_func):
    from functools import wraps

    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login"))
        return view_func(*args, **kwargs)

    return wrapped


def admin_required(view_func):
    from functools import wraps

    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if session.get("role") != "admin":
            flash("Admin access required.", "danger")
            return redirect(url_for("login"))
        return view_func(*args, **kwargs)

    return wrapped


def parse_time_to_minutes(t_str):
    """Accepts 'HH:MM' 24h format and returns minutes since midnight."""
    h, m = t_str.split(":")
    return int(h) * 60 + int(m)


def compute_duration_hours(entry_str, exit_str):
    entry_min = parse_time_to_minutes(entry_str)
    exit_min = parse_time_to_minutes(exit_str)
    diff = exit_min - entry_min
    if diff <= 0:
        diff += 24 * 60  # crosses midnight
    return round(diff / 60, 2)


# ---------------------------------------------------------------------------
# Public routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    db = get_db()
    total_slots = db.execute("SELECT COUNT(*) c FROM parking_slots").fetchone()["c"]
    available_slots = db.execute(
        "SELECT COUNT(*) c FROM parking_slots WHERE status = 'available'"
    ).fetchone()["c"]
    total_users = db.execute("SELECT COUNT(*) c FROM users WHERE role='user'").fetchone()["c"]
    total_bookings = db.execute("SELECT COUNT(*) c FROM bookings").fetchone()["c"]
    return render_template(
        "index.html",
        total_slots=total_slots,
        available_slots=available_slots,
        total_users=total_users,
        total_bookings=total_bookings,
    )


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        phone = request.form.get("phone", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")

        if not name or not email or not password:
            flash("Please fill all required fields.", "danger")
            return redirect(url_for("register"))

        if password != confirm:
            flash("Passwords do not match.", "danger")
            return redirect(url_for("register"))

        db = get_db()
        existing = db.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        if existing:
            flash("An account with this email already exists.", "danger")
            return redirect(url_for("register"))

        db.execute(
            "INSERT INTO users (name, email, phone, password, role) VALUES (?,?,?,?,?)",
            (name, email, phone, generate_password_hash(password), "user"),
        )
        db.commit()
        flash("Registration successful. Please log in.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        db = get_db()
        user = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()

        if user is None or not check_password_hash(user["password"], password):
            flash("Invalid email or password.", "danger")
            return redirect(url_for("login"))

        session["user_id"] = user["id"]
        session["name"] = user["name"]
        session["role"] = user["role"]

        flash(f"Welcome back, {user['name']}!", "success")
        if user["role"] == "admin":
            return redirect(url_for("admin_dashboard"))
        return redirect(url_for("dashboard"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("index"))


# ---------------------------------------------------------------------------
# User routes
# ---------------------------------------------------------------------------

@app.route("/dashboard")
@login_required
def dashboard():
    db = get_db()
    user_id = session["user_id"]

    available_slots = db.execute(
        "SELECT COUNT(*) c FROM parking_slots WHERE status='available'"
    ).fetchone()["c"]

    my_bookings = db.execute(
        "SELECT COUNT(*) c FROM bookings WHERE user_id=?", (user_id,)
    ).fetchone()["c"]

    active_booking = db.execute(
        "SELECT COUNT(*) c FROM bookings WHERE user_id=? AND status='confirmed'", (user_id,)
    ).fetchone()["c"]

    total_spent = db.execute(
        "SELECT COALESCE(SUM(amount),0) s FROM bookings WHERE user_id=? AND status != 'cancelled'",
        (user_id,),
    ).fetchone()["s"]

    recent_bookings = db.execute(
        """SELECT b.*, s.slot_number, v.vehicle_number
           FROM bookings b
           JOIN parking_slots s ON b.slot_id = s.id
           JOIN vehicles v ON b.vehicle_id = v.id
           WHERE b.user_id = ?
           ORDER BY b.created_at DESC LIMIT 5""",
        (user_id,),
    ).fetchall()

    return render_template(
        "dashboard.html",
        available_slots=available_slots,
        my_bookings=my_bookings,
        active_booking=active_booking,
        total_spent=total_spent,
        recent_bookings=recent_bookings,
    )


@app.route("/parking")
@login_required
def parking():
    db = get_db()
    search = request.args.get("search", "").strip()

    if search:
        slots = db.execute(
            "SELECT * FROM parking_slots WHERE slot_number LIKE ? OR floor LIKE ? "
            "ORDER BY slot_number",
            (f"%{search}%", f"%{search}%"),
        ).fetchall()
    else:
        slots = db.execute("SELECT * FROM parking_slots ORDER BY slot_number").fetchall()

    return render_template("parking.html", slots=slots, search=search)


@app.route("/booking/<int:slot_id>", methods=["GET", "POST"])
@login_required
def booking(slot_id):
    db = get_db()
    user_id = session["user_id"]

    slot = db.execute("SELECT * FROM parking_slots WHERE id = ?", (slot_id,)).fetchone()
    if slot is None:
        flash("Parking slot not found.", "danger")
        return redirect(url_for("parking"))

    if slot["status"] != "available" and request.method == "GET":
        flash("This slot is not available for booking.", "warning")
        return redirect(url_for("parking"))

    if request.method == "POST":
        vehicle_number = request.form.get("vehicle_number", "").strip().upper()
        vehicle_type = request.form.get("vehicle_type", "").strip()
        vehicle_model = request.form.get("vehicle_model", "").strip()
        booking_date = request.form.get("booking_date", "").strip()
        entry_time = request.form.get("entry_time", "").strip()
        exit_time = request.form.get("exit_time", "").strip()

        if not all([vehicle_number, vehicle_type, booking_date, entry_time, exit_time]):
            flash("Please fill all booking details.", "danger")
            return redirect(url_for("booking", slot_id=slot_id))

        # re-check slot availability (prevent double booking / race condition)
        fresh_slot = db.execute(
            "SELECT * FROM parking_slots WHERE id = ?", (slot_id,)
        ).fetchone()
        if fresh_slot["status"] != "available":
            flash("Sorry, this slot was just booked by someone else.", "danger")
            return redirect(url_for("parking"))

        duration = compute_duration_hours(entry_time, exit_time)
        amount = round(duration * fresh_slot["price_per_hour"], 2)

        cur = db.execute(
            "INSERT INTO vehicles (user_id, vehicle_number, vehicle_type, vehicle_model) "
            "VALUES (?,?,?,?)",
            (user_id, vehicle_number, vehicle_type, vehicle_model),
        )
        vehicle_id = cur.lastrowid

        booking_id = generate_booking_id()
        db.execute(
            """INSERT INTO bookings
               (booking_id, user_id, slot_id, vehicle_id, booking_date,
                entry_time, exit_time, duration, amount, status)
               VALUES (?,?,?,?,?,?,?,?,?, 'confirmed')""",
            (booking_id, user_id, slot_id, vehicle_id, booking_date,
             entry_time, exit_time, duration, amount),
        )
        db.execute(
            "UPDATE parking_slots SET status = 'occupied' WHERE id = ?", (slot_id,)
        )
        db.commit()

        flash("Booking confirmed successfully!", "success")
        return redirect(url_for("booking_confirmation", booking_id=booking_id))

    return render_template("booking.html", slot=slot)


@app.route("/booking-confirmation/<booking_id>")
@login_required
def booking_confirmation(booking_id):
    db = get_db()
    b = db.execute(
        """SELECT b.*, s.slot_number, s.floor, v.vehicle_number, v.vehicle_type
           FROM bookings b
           JOIN parking_slots s ON b.slot_id = s.id
           JOIN vehicles v ON b.vehicle_id = v.id
           WHERE b.booking_id = ? AND b.user_id = ?""",
        (booking_id, session["user_id"]),
    ).fetchone()

    if b is None:
        flash("Booking not found.", "danger")
        return redirect(url_for("dashboard"))

    return render_template("confirmation.html", b=b)


@app.route("/my-bookings")
@login_required
def my_bookings():
    db = get_db()
    bookings = db.execute(
        """SELECT b.*, s.slot_number, s.floor, v.vehicle_number, v.vehicle_type
           FROM bookings b
           JOIN parking_slots s ON b.slot_id = s.id
           JOIN vehicles v ON b.vehicle_id = v.id
           WHERE b.user_id = ?
           ORDER BY b.created_at DESC""",
        (session["user_id"],),
    ).fetchall()
    return render_template("bookings.html", bookings=bookings)


@app.route("/cancel-booking/<int:booking_pk>", methods=["POST"])
@login_required
def cancel_booking(booking_pk):
    db = get_db()
    b = db.execute(
        "SELECT * FROM bookings WHERE id = ? AND user_id = ?",
        (booking_pk, session["user_id"]),
    ).fetchone()

    if b is None:
        flash("Booking not found.", "danger")
        return redirect(url_for("my_bookings"))

    if b["status"] == "cancelled":
        flash("Booking is already cancelled.", "warning")
        return redirect(url_for("my_bookings"))

    db.execute("UPDATE bookings SET status = 'cancelled' WHERE id = ?", (booking_pk,))
    db.execute(
        "UPDATE parking_slots SET status = 'available' WHERE id = ?", (b["slot_id"],)
    )
    db.commit()
    flash("Booking cancelled and slot released.", "success")
    return redirect(url_for("my_bookings"))


@app.route("/profile")
@login_required
def profile():
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id = ?", (session["user_id"],)).fetchone()
    vehicles = db.execute(
        "SELECT DISTINCT vehicle_number, vehicle_type, vehicle_model FROM vehicles WHERE user_id=?",
        (session["user_id"],),
    ).fetchall()
    return render_template("profile.html", user=user, vehicles=vehicles)


# ---------------------------------------------------------------------------
# Admin routes
# ---------------------------------------------------------------------------

@app.route("/admin")
@admin_required
def admin_dashboard():
    db = get_db()
    total_slots = db.execute("SELECT COUNT(*) c FROM parking_slots").fetchone()["c"]
    available_slots = db.execute(
        "SELECT COUNT(*) c FROM parking_slots WHERE status='available'"
    ).fetchone()["c"]
    occupied_slots = db.execute(
        "SELECT COUNT(*) c FROM parking_slots WHERE status='occupied'"
    ).fetchone()["c"]
    total_bookings = db.execute("SELECT COUNT(*) c FROM bookings").fetchone()["c"]
    total_users = db.execute("SELECT COUNT(*) c FROM users WHERE role='user'").fetchone()["c"]
    revenue = db.execute(
        "SELECT COALESCE(SUM(amount),0) s FROM bookings WHERE status != 'cancelled'"
    ).fetchone()["s"]

    daily_rows = db.execute(
        """SELECT booking_date, COUNT(*) cnt FROM bookings
           GROUP BY booking_date ORDER BY booking_date DESC LIMIT 7"""
    ).fetchall()
    daily_labels = [r["booking_date"] for r in reversed(daily_rows)]
    daily_counts = [r["cnt"] for r in reversed(daily_rows)]

    vtype_rows = db.execute(
        """SELECT v.vehicle_type, COUNT(*) cnt FROM bookings b
           JOIN vehicles v ON b.vehicle_id = v.id
           GROUP BY v.vehicle_type"""
    ).fetchall()

    recent_bookings = db.execute(
        """SELECT b.*, s.slot_number, u.name AS user_name, v.vehicle_number
           FROM bookings b
           JOIN parking_slots s ON b.slot_id = s.id
           JOIN users u ON b.user_id = u.id
           JOIN vehicles v ON b.vehicle_id = v.id
           ORDER BY b.created_at DESC LIMIT 8"""
    ).fetchall()

    return render_template(
        "admin/dashboard.html",
        total_slots=total_slots,
        available_slots=available_slots,
        occupied_slots=occupied_slots,
        total_bookings=total_bookings,
        total_users=total_users,
        revenue=revenue,
        daily_labels=daily_labels,
        daily_counts=daily_counts,
        vtype_rows=vtype_rows,
        recent_bookings=recent_bookings,
    )


@app.route("/admin/slots")
@admin_required
def admin_slots():
    db = get_db()
    slots = db.execute("SELECT * FROM parking_slots ORDER BY slot_number").fetchall()
    return render_template("admin/slots.html", slots=slots)


@app.route("/admin/slots/add", methods=["GET", "POST"])
@admin_required
def admin_add_slot():
    if request.method == "POST":
        slot_number = request.form.get("slot_number", "").strip().upper()
        floor = request.form.get("floor", "").strip()
        slot_type = request.form.get("slot_type", "").strip()
        price = request.form.get("price_per_hour", "0").strip()

        if not all([slot_number, floor, slot_type, price]):
            flash("Please fill all fields.", "danger")
            return redirect(url_for("admin_add_slot"))

        db = get_db()
        existing = db.execute(
            "SELECT id FROM parking_slots WHERE slot_number = ?", (slot_number,)
        ).fetchone()
        if existing:
            flash("A slot with this number already exists.", "danger")
            return redirect(url_for("admin_add_slot"))

        db.execute(
            "INSERT INTO parking_slots (slot_number, floor, slot_type, status, price_per_hour) "
            "VALUES (?,?,?, 'available', ?)",
            (slot_number, floor, slot_type, float(price)),
        )
        db.commit()
        flash("Parking slot added successfully.", "success")
        return redirect(url_for("admin_slots"))

    return render_template("admin/add_slot.html")


@app.route("/admin/slots/edit/<int:slot_id>", methods=["POST"])
@admin_required
def admin_edit_slot(slot_id):
    db = get_db()
    slot_number = request.form.get("slot_number", "").strip().upper()
    floor = request.form.get("floor", "").strip()
    slot_type = request.form.get("slot_type", "").strip()
    price = request.form.get("price_per_hour", "0").strip()

    db.execute(
        "UPDATE parking_slots SET slot_number=?, floor=?, slot_type=?, price_per_hour=? WHERE id=?",
        (slot_number, floor, slot_type, float(price), slot_id),
    )
    db.commit()
    flash("Parking slot updated.", "success")
    return redirect(url_for("admin_slots"))


@app.route("/admin/slots/status/<int:slot_id>", methods=["POST"])
@admin_required
def admin_change_slot_status(slot_id):
    new_status = request.form.get("status", "available")
    if new_status not in ("available", "occupied", "reserved"):
        new_status = "available"
    db = get_db()
    db.execute("UPDATE parking_slots SET status=? WHERE id=?", (new_status, slot_id))
    db.commit()
    flash("Slot status updated.", "success")
    return redirect(url_for("admin_slots"))


@app.route("/admin/slots/delete/<int:slot_id>", methods=["POST"])
@admin_required
def admin_delete_slot(slot_id):
    db = get_db()
    active = db.execute(
        "SELECT COUNT(*) c FROM bookings WHERE slot_id=? AND status='confirmed'", (slot_id,)
    ).fetchone()["c"]
    if active > 0:
        flash("Cannot delete a slot with an active booking.", "danger")
        return redirect(url_for("admin_slots"))

    db.execute("DELETE FROM parking_slots WHERE id=?", (slot_id,))
    db.commit()
    flash("Parking slot deleted.", "success")
    return redirect(url_for("admin_slots"))


@app.route("/admin/bookings")
@admin_required
def admin_bookings():
    db = get_db()
    search = request.args.get("search", "").strip()

    query = """SELECT b.*, s.slot_number, u.name AS user_name, u.email AS user_email,
                      v.vehicle_number, v.vehicle_type
               FROM bookings b
               JOIN parking_slots s ON b.slot_id = s.id
               JOIN users u ON b.user_id = u.id
               JOIN vehicles v ON b.vehicle_id = v.id"""
    params = ()
    if search:
        query += """ WHERE b.booking_id LIKE ? OR u.name LIKE ? OR v.vehicle_number LIKE ?
                      OR s.slot_number LIKE ?"""
        like = f"%{search}%"
        params = (like, like, like, like)
    query += " ORDER BY b.created_at DESC"

    bookings = db.execute(query, params).fetchall()
    return render_template("admin/bookings.html", bookings=bookings, search=search)


@app.route("/admin/bookings/status/<int:booking_pk>", methods=["POST"])
@admin_required
def admin_update_booking_status(booking_pk):
    new_status = request.form.get("status", "confirmed")
    db = get_db()
    b = db.execute("SELECT * FROM bookings WHERE id=?", (booking_pk,)).fetchone()
    if b is None:
        flash("Booking not found.", "danger")
        return redirect(url_for("admin_bookings"))

    db.execute("UPDATE bookings SET status=? WHERE id=?", (new_status, booking_pk))

    if new_status in ("cancelled", "completed"):
        db.execute(
            "UPDATE parking_slots SET status='available' WHERE id=?", (b["slot_id"],)
        )
    elif new_status == "confirmed":
        db.execute(
            "UPDATE parking_slots SET status='occupied' WHERE id=?", (b["slot_id"],)
        )

    db.commit()
    flash("Booking status updated.", "success")
    return redirect(url_for("admin_bookings"))


@app.route("/admin/users")
@admin_required
def admin_users():
    db = get_db()
    users = db.execute(
        "SELECT * FROM users WHERE role='user' ORDER BY created_at DESC"
    ).fetchall()
    return render_template("admin/users.html", users=users)


@app.route("/admin/vehicles")
@admin_required
def admin_vehicles():
    db = get_db()
    vehicles = db.execute(
        """SELECT v.*, u.name AS owner_name FROM vehicles v
           JOIN users u ON v.user_id = u.id
           ORDER BY v.id DESC"""
    ).fetchall()
    return render_template("admin/vehicles.html", vehicles=vehicles)


@app.route("/admin/revenue")
@admin_required
def admin_revenue():
    db = get_db()
    total_revenue = db.execute(
        "SELECT COALESCE(SUM(amount),0) s FROM bookings WHERE status != 'cancelled'"
    ).fetchone()["s"]

    monthly = db.execute(
        """SELECT strftime('%Y-%m', booking_date) AS month, COALESCE(SUM(amount),0) AS total
           FROM bookings WHERE status != 'cancelled'
           GROUP BY month ORDER BY month DESC LIMIT 12"""
    ).fetchall()

    by_slot_type = db.execute(
        """SELECT s.slot_type, COALESCE(SUM(b.amount),0) AS total
           FROM bookings b JOIN parking_slots s ON b.slot_id = s.id
           WHERE b.status != 'cancelled'
           GROUP BY s.slot_type"""
    ).fetchall()

    return render_template(
        "admin/revenue.html",
        total_revenue=total_revenue,
        monthly=monthly,
        by_slot_type=by_slot_type,
    )


# ---------------------------------------------------------------------------
# API endpoint (used by JS for live fee calculation)
# ---------------------------------------------------------------------------

@app.route("/api/calc-fee")
@login_required
def api_calc_fee():
    slot_id = request.args.get("slot_id", type=int)
    entry_time = request.args.get("entry_time", "")
    exit_time = request.args.get("exit_time", "")

    if not slot_id or not entry_time or not exit_time:
        return jsonify({"error": "missing parameters"}), 400

    db = get_db()
    slot = db.execute("SELECT * FROM parking_slots WHERE id=?", (slot_id,)).fetchone()
    if slot is None:
        return jsonify({"error": "slot not found"}), 404

    try:
        duration = compute_duration_hours(entry_time, exit_time)
    except Exception:
        return jsonify({"error": "invalid time"}), 400

    amount = round(duration * slot["price_per_hour"], 2)
    return jsonify({
        "duration": duration,
        "rate": slot["price_per_hour"],
        "amount": amount,
    })


# ---------------------------------------------------------------------------
# Error handlers
# ---------------------------------------------------------------------------

@app.errorhandler(404)
def not_found(e):
    return render_template("404.html"), 404


@app.errorhandler(500)
def server_error(e):
    return render_template("500.html"), 500


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    init_db()
    app.run(debug=True, host="127.0.0.1", port=5000)
