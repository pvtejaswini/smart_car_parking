# Smart Car Parking Management System

A full-stack **Smart Car Parking Management System** built with Flask, SQLite,
Bootstrap 5 and Chart.js — designed as an MCA/BCA final-year college project.

## Features

**User side:** registration, login, live parking-slot map (available / occupied /
reserved / selected), search, multi-step booking (vehicle details → date & time →
auto fee calculation → confirmation), unique booking-ID generation, booking
history, cancellation, profile page.

**Admin side:** dashboard with live stats and Chart.js graphs (daily bookings,
booking status, vehicle-type split), full slot CRUD (add / edit / change status /
delete), booking management with status updates, user list, vehicle list, and a
revenue report broken down by month and slot type.

The database and two demo accounts (one admin, one user) are created
automatically the first time the app runs — no manual setup required.

## Requirements

- Python 3.9+
- pip

## Setup (VS Code / any terminal)

1. Open this folder in VS Code (`File → Open Folder…`).
2. Open a terminal in VS Code (`` Ctrl+` ``) and create a virtual environment
   (recommended but optional):

   ```bash
   python -m venv venv
   # Windows
   venv\Scripts\activate
   # macOS / Linux
   source venv/bin/activate
   ```

3. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

4. Run the application:

   ```bash
   python app.py
   ```

5. Open your browser at:

   ```
   http://127.0.0.1:5000
   ```

`parking.db` (SQLite) is created automatically on first run, complete with
sample parking slots, a default admin account and a sample user account.

## Default Login Credentials

| Role  | Email               | Password  |
|-------|----------------------|-----------|
| Admin | admin@parking.com    | admin123  |
| User  | user@parking.com     | user123   |

## Project Structure

```text
smart_car_parking/
│
├── app.py                  # Flask application (routes, DB logic, auth)
├── requirements.txt
├── README.md
├── parking.db               # created automatically on first run
│
├── static/
│   ├── css/style.css        # dark automotive theme (glassmorphism, cards)
│   └── js/script.js
│
└── templates/
    ├── base.html
    ├── index.html            # landing page
    ├── login.html
    ├── register.html
    ├── dashboard.html         # user dashboard
    ├── parking.html            # slot map + search
    ├── booking.html             # booking form + live fee calc
    ├── confirmation.html        # booking confirmation
    ├── bookings.html             # booking history
    ├── profile.html
    ├── 404.html / 500.html
    │
    └── admin/
        ├── base_admin.html      # sidebar layout
        ├── dashboard.html         # stats + charts
        ├── slots.html              # slot CRUD
        ├── add_slot.html
        ├── bookings.html
        ├── users.html
        ├── vehicles.html
        └── revenue.html
```

## Database Schema

- **users** — id, name, email, phone, password (hashed), role, created_at
- **parking_slots** — id, slot_number, floor, slot_type, status, price_per_hour
- **vehicles** — id, user_id, vehicle_number, vehicle_type, vehicle_model
- **bookings** — id, booking_id, user_id, slot_id, vehicle_id, booking_date,
  entry_time, exit_time, duration, amount, status, created_at

## Notes

- Passwords are hashed with Werkzeug's `generate_password_hash` — never stored
  in plain text.
- Slot status is updated automatically on booking, cancellation, and admin
  status changes, so the visual map always reflects real availability.
- Parking fee = duration (hours) × the slot's hourly rate, calculated both
  live in the browser (via `/api/calc-fee`) and re-verified server-side on
  submit.
- All backgrounds/illustrations are built with CSS (gradients, dashed
  "parking-bay" borders) rather than external image files, so the project
  runs immediately with no missing-asset errors.
