from flask import Flask, request, jsonify
import sqlite3
import datetime
import hashlib

app = Flask(__name__)

DB_FILE = "licenses.db"

# =========================
# DATABASE INIT
# =========================
def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS licenses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        license_key TEXT UNIQUE,
        created_at TEXT,
        expiry_date TEXT,
        status TEXT
    )
    """)
    conn.commit()
    conn.close()

init_db()

# =========================
# HOME ROUTE (IMPORTANT)
# =========================
@app.route("/")
def home():
    return "License Server Running ✅"

# =========================
# GENERATE LICENSE
# =========================
@app.route("/generate", methods=["POST"])
def generate_license():
    data = request.json
    days = data.get("days", 30)

    # Generate unique license
    raw = str(datetime.datetime.now()) + str(days)
    license_key = hashlib.sha256(raw.encode()).hexdigest()[:16]

    created_at = datetime.datetime.now()
    expiry_date = created_at + datetime.timedelta(days=days)

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO licenses (license_key, created_at, expiry_date, status)
    VALUES (?, ?, ?, ?)
    """, (license_key, created_at, expiry_date, "active"))

    conn.commit()
    conn.close()

    return jsonify({
        "license_key": license_key,
        "expiry_date": str(expiry_date)
    })

# =========================
# VERIFY LICENSE
# =========================
@app.route("/verify", methods=["POST"])
def verify_license():
    data = request.json
    license_key = data.get("license_key")

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute("SELECT expiry_date, status FROM licenses WHERE license_key=?", (license_key,))
    result = cursor.fetchone()

    conn.close()

    if not result:
        return jsonify({"status": "invalid"})

    expiry_date, status = result
    expiry_date = datetime.datetime.fromisoformat(expiry_date)

    if status != "active":
        return jsonify({"status": "blocked"})

    if datetime.datetime.now() > expiry_date:
        return jsonify({"status": "expired"})

    return jsonify({"status": "valid"})

# =========================
# ADMIN LOGIN (BASIC)
# =========================
ADMIN_USER = "admin"
ADMIN_PASS = "1234"  # change later

@app.route("/admin/login", methods=["POST"])
def admin_login():
    data = request.json
    username = data.get("username")
    password = data.get("password")

    if username == ADMIN_USER and password == ADMIN_PASS:
        return jsonify({"status": "success"})
    else:
        return jsonify({"status": "failed"}), 401

# =========================
# LIST LICENSES (ADMIN)
# =========================
@app.route("/admin/licenses", methods=["GET"])
def list_licenses():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute("SELECT license_key, expiry_date, status FROM licenses")
    data = cursor.fetchall()

    conn.close()

    licenses = []
    for row in data:
        licenses.append({
            "license_key": row[0],
            "expiry_date": row[1],
            "status": row[2]
        })

    return jsonify(licenses)

# =========================
# BLOCK LICENSE (ADMIN)
# =========================
@app.route("/admin/block", methods=["POST"])
def block_license():
    data = request.json
    license_key = data.get("license_key")

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute("UPDATE licenses SET status='blocked' WHERE license_key=?", (license_key,))
    conn.commit()
    conn.close()

    return jsonify({"status": "blocked"})

# =========================
# RUN LOCAL (NOT USED IN RENDER)
# =========================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
