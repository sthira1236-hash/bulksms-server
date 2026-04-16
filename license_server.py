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

    conn.commit()
    conn.close()

init_db()

# ================= HOME =================
@app.route("/")
def home():
    return "License Server Running ✅"

# ================= VERIFY =================
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

    if datetime.now() > expiry_date:
        conn.close()
        return jsonify({"status": "expired"})

    if row[1] != "active":
        conn.close()
        return jsonify({"status": "inactive"})

    # DEVICE LOCK
    if not row[2]:
        cursor.execute("UPDATE licenses SET device_id=? WHERE license_key=?", (device_id, key))
        conn.commit()
        conn.close()
        return jsonify({"status": "valid"})

    if row[2] == device_id:
        conn.close()
        return jsonify({"status": "valid"})

    conn.close()
    return jsonify({"status": "blocked"})

# ================= RESET =================
@app.route("/reset_device/<key>")
def reset_device(key):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("UPDATE licenses SET device_id=NULL WHERE license_key=?", (key,))
    conn.commit()
    conn.close()
    return redirect("/dashboard")

# ================= ACTIVATE =================
@app.route("/activate/<key>")
def activate(key):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("UPDATE licenses SET status='active' WHERE license_key=?", (key,))
    conn.commit()
    conn.close()
    return redirect("/dashboard")

# ================= DEACTIVATE =================
@app.route("/deactivate/<key>")
def deactivate(key):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("UPDATE licenses SET status='inactive' WHERE license_key=?", (key,))
    conn.commit()
    conn.close()
    return redirect("/dashboard")

# ================= EXTEND CUSTOM =================
@app.route("/extend_custom", methods=["POST"])
def extend_custom():
    key = request.form.get("key")
    days = int(request.form.get("days"))

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute("SELECT expiry_date FROM licenses WHERE license_key=?", (key,))
    row = cursor.fetchone()

    if row:
        current_expiry = datetime.strptime(row[0], "%Y-%m-%d")

        if current_expiry < datetime.now():
            new_expiry = datetime.now() + timedelta(days=days)
        else:
            new_expiry = current_expiry + timedelta(days=days)

        cursor.execute(
            "UPDATE licenses SET expiry_date=? WHERE license_key=?",
            (new_expiry.strftime("%Y-%m-%d"), key)
        )

        conn.commit()

    conn.close()
    return redirect("/dashboard")

# ================= ADMIN =================
@app.route("/admin", methods=["GET", "POST"])
def admin():
    if request.method == "POST":
        if request.form.get("password") == ADMIN_PASSWORD:
            session["admin"] = True
            return redirect("/dashboard")
        else:
            return "Wrong Password"

    return """
    <h2>Admin Login</h2>
    <form method="post">
        <input type="password" name="password">
        <button>Login</button>
    </form>
    """

# ================= DASHBOARD =================
@app.route("/dashboard")
def dashboard():
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
            <td>
                <a href="/reset_device/{d[0]}">Reset</a> |
                <a href="/deactivate/{d[0]}">Deactivate</a> |
                <a href="/activate/{d[0]}">Activate</a>
                <form method="post" action="/extend_custom" style="display:inline;">
                    <input type="hidden" name="key" value="{d[0]}">
                    <input type="number" name="days" placeholder="Days" style="width:60px;">
                    <button>Extend</button>
                </form>
            </td>
        </tr>
        """

    return f"""
    <html>
    <body style="background:#111;color:white;padding:20px;">
    <h2>🚀 Dashboard</h2>

    <table border="1" cellpadding="10">
    <tr>
        <th>Key</th>
        <th>Expiry</th>
        <th>Status</th>
        <th>Device</th>
        <th>Action</th>
    </tr>
    {rows}
    </table>

    </body>
    </html>
    """

# ================= RUN =================
if __name__ == "__main__":
    app.run(debug=True)