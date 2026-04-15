from flask import Flask, request, jsonify
import sqlite3
import uuid
from datetime import datetime, timedelta

app = Flask(__name__)

# ==============================
# DATABASE INIT (FIXED VERSION)
# ==============================
def init_db():
    conn = sqlite3.connect("licenses.db")
    cursor = conn.cursor()

    # Drop old table (fix structure issue)
    cursor.execute("DROP TABLE IF EXISTS licenses")

    # Create new table
    cursor.execute("""
    CREATE TABLE licenses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        license_key TEXT,
        created_at TEXT,
        expiry_date TEXT,
        status TEXT
    )
    """)

    conn.commit()
    conn.close()

# Run DB setup on start
init_db()

# ==============================
# GENERATE LICENSE API
# ==============================
@app.route('/generate', methods=['POST'])
def generate_license():
    data = request.get_json()

    days = data.get("days", 30)

    license_key = str(uuid.uuid4()).upper()
    created_at = datetime.now()
    expiry_date = created_at + timedelta(days=days)

    conn = sqlite3.connect("licenses.db")
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO licenses (license_key, created_at, expiry_date, status)
        VALUES (?, ?, ?, ?)
    """, (
        license_key,
        created_at.strftime("%Y-%m-%d %H:%M:%S"),
        expiry_date.strftime("%Y-%m-%d %H:%M:%S"),
        "active"
    ))

    conn.commit()
    conn.close()

    return jsonify({
        "license_key": license_key,
        "expiry_date": expiry_date.strftime("%Y-%m-%d")
    })


# ==============================
# VERIFY LICENSE API
# ==============================
@app.route('/verify', methods=['POST'])
def verify_license():
    data = request.get_json()
    license_key = data.get("license_key")

    conn = sqlite3.connect("licenses.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT expiry_date, status FROM licenses WHERE license_key=?
    """, (license_key,))

    result = cursor.fetchone()
    conn.close()

    if not result:
        return jsonify({"status": "invalid"})

    expiry_date_str, status = result
    expiry_date = datetime.strptime(expiry_date_str, "%Y-%m-%d %H:%M:%S")

    if status != "active":
        return jsonify({"status": "inactive"})

    if datetime.now() > expiry_date:
        return jsonify({"status": "expired"})

    return jsonify({
        "status": "valid",
        "expiry_date": expiry_date.strftime("%Y-%m-%d")
    })


# ==============================
# ADMIN VIEW (OPTIONAL)
# ==============================
@app.route('/admin/licenses', methods=['GET'])
def get_licenses():
    conn = sqlite3.connect("licenses.db")
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM licenses")
    rows = cursor.fetchall()

    conn.close()

    return jsonify(rows)


# ==============================
# ROOT CHECK
# ==============================
@app.route('/')
def home():
    return "License Server Running ✅"


# ==============================
# RUN (LOCAL ONLY)
# ==============================
if __name__ == '__main__':
    app.run(debug=True)
