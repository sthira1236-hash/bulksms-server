from flask import Flask, request, jsonify, redirect, session
import sqlite3
import uuid
from datetime import datetime, timedelta
import os

app = Flask(__name__)

# ================= CONFIG =================
DB_FILE = "licenses.db"
SECRET_KEY = os.getenv("SECRET_KEY", "fallback_secret")
ADMIN_PASSWORD = "admin123"

app.secret_key = "session_secret_456"

# ================= DB INIT =================
def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS licenses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        license_key TEXT UNIQUE,
        created_at TEXT,
        expiry_date TEXT,
        status TEXT,
        device_id TEXT
    )
    """)

    # 🔥 AUTO FIX OLD DB
    cursor.execute("PRAGMA table_info(licenses)")
    columns = [col[1] for col in cursor.fetchall()]

    if "device_id" not in columns:
        cursor.execute("DROP TABLE licenses")

        cursor.execute("""
        CREATE TABLE licenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            license_key TEXT UNIQUE,
            created_at TEXT,
            expiry_date TEXT,
            status TEXT,
            device_id TEXT
        )
        """)

    conn.commit()
    conn.close()

init_db()

# ================= HOME =================
@app.route("/")
def home():
    return "License Server Running ✅"

# ================= GENERATE =================
@app.route("/generate", methods=["POST"])
def generate_license():

    if request.headers.get("x-api-key") != SECRET_KEY:
        return jsonify({"error": "Unauthorized"}), 403

    data = request.get_json() or {}
    days = int(data.get("days", 30))

    license_key = str(uuid.uuid4()).upper()
    created = datetime.now()
    expiry = created + timedelta(days=days)

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO licenses (license_key, created_at, expiry_date, status, device_id)
    VALUES (?, ?, ?, ?, ?)
    """, (
        license_key,
        created.strftime("%Y-%m-%d"),
        expiry.strftime("%Y-%m-%d"),
        "active",
        None
    ))

    conn.commit()
    conn.close()

    return jsonify({
        "license_key": license_key,
        "expiry_date": expiry.strftime("%Y-%m-%d")
    })

# ================= VERIFY (DEVICE LOCK) =================
@app.route("/verify", methods=["POST"])
def verify():

    if request.headers.get("x-api-key") != SECRET_KEY:
        return jsonify({"error": "Unauthorized"}), 403

    data = request.get_json() or {}
    key = data.get("license_key")
    device_id = data.get("device_id")

    if not key or not device_id:
        return jsonify({"status": "invalid"})

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute("SELECT expiry_date, status, device_id FROM licenses WHERE license_key=?", (key,))
    row = cursor.fetchone()

    if not row:
        conn.close()
        return jsonify({"status": "invalid"})

    expiry_date = datetime.strptime(row[0], "%Y-%m-%d")
    status = row[1]
    saved_device = row[2]

    # ❌ expired
    if datetime.now() > expiry_date:
        conn.close()
        return jsonify({"status": "expired"})

    # ❌ inactive
    if status != "active":
        conn.close()
        return jsonify({"status": "invalid"})

    # 🔒 FIRST TIME → SAVE DEVICE
    if not saved_device:
        cursor.execute("UPDATE licenses SET device_id=? WHERE license_key=?", (device_id, key))
        conn.commit()
        conn.close()

        return jsonify({
            "status": "valid",
            "expiry_date": row[0],
            "message": "Device registered"
        })

    # 🔒 SAME DEVICE → OK
    if saved_device == device_id:
        conn.close()
        return jsonify({
            "status": "valid",
            "expiry_date": row[0]
        })

    # ❌ DIFFERENT DEVICE → BLOCK
    conn.close()
    return jsonify({
        "status": "blocked",
        "message": "License already used on another device"
    })

# ================= ADMIN =================
@app.route("/admin", methods=["GET", "POST"])
def admin_login():

    if request.method == "POST":
        if request.form.get("password") == ADMIN_PASSWORD:
            session["admin"] = True
            return redirect("/dashboard")
        else:
            return "<h3 style='color:red;text-align:center;'>Wrong Password</h3>"

    return """
    <html>
    <body style="text-align:center;margin-top:150px;">
        <h2>Admin Login</h2>
        <form method="post">
            <input type="password" name="password">
            <button>Login</button>
        </form>
    </body>
    </html>
    """

# ================= DASHBOARD =================
@app.route("/dashboard")
def dashboard():

    if not session.get("admin"):
        return redirect("/admin")

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute("SELECT license_key, expiry_date, status, device_id FROM licenses")
    data = cursor.fetchall()

    conn.close()

    rows = ""
    for d in data:
        rows += f"""
        <tr>
            <td>{d[0]}</td>
            <td>{d[1]}</td>
            <td>{d[2]}</td>
            <td>{d[3]}</td>
        </tr>
        """

    return f"""
    <html>
    <body style="background:#111;color:white;padding:20px;">
    <h2>Dashboard</h2>
    <table border="1" cellpadding="10">
    <tr>
        <th>Key</th>
        <th>Expiry</th>
        <th>Status</th>
        <th>Device</th>
    </tr>
    {rows}
    </table>
    </body>
    </html>
    """

# ================= RUN =================
if __name__ == "__main__":
    app.run(debug=True)