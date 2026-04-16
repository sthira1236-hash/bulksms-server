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

    cursor.execute("PRAGMA table_info(licenses)")
    cols = [c[1] for c in cursor.fetchall()]

    if "device_id" not in cols:
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

    days = int((request.get_json() or {}).get("days", 30))

    key = str(uuid.uuid4()).upper()
    created = datetime.now()
    expiry = created + timedelta(days=days)

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO licenses (license_key, created_at, expiry_date, status, device_id)
    VALUES (?, ?, ?, ?, ?)
    """, (
        key,
        created.strftime("%Y-%m-%d"),
        expiry.strftime("%Y-%m-%d"),
        "active",
        None
    ))

    conn.commit()
    conn.close()

    return jsonify({
        "license_key": key,
        "expiry_date": expiry.strftime("%Y-%m-%d")
    })

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
    status = row[1]
    saved_device = row[2]

    if datetime.now() > expiry_date:
        conn.close()
        return jsonify({"status": "expired"})

    if status != "active":
        conn.close()
        return jsonify({"status": "inactive"})

    if not saved_device:
        cursor.execute("UPDATE licenses SET device_id=? WHERE license_key=?", (device_id, key))
        conn.commit()
        conn.close()
        return jsonify({"status": "valid"})

    if saved_device == device_id:
        conn.close()
        return jsonify({"status": "valid"})

    conn.close()
    return jsonify({"status": "blocked"})

# ================= RESET DEVICE =================
@app.route("/reset_device/<key>")
def reset_device(key):
    if not session.get("admin"):
        return redirect("/admin")

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("UPDATE licenses SET device_id=NULL WHERE license_key=?", (key,))
    conn.commit()
    conn.close()

    return redirect("/dashboard")

# ================= DEACTIVATE =================
@app.route("/deactivate/<key>")
def deactivate(key):
    if not session.get("admin"):
        return redirect("/admin")

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("UPDATE licenses SET status='inactive' WHERE license_key=?", (key,))
    conn.commit()
    conn.close()

    return redirect("/dashboard")

# ================= ACTIVATE =================
@app.route("/activate/<key>")
def activate(key):
    if not session.get("admin"):
        return redirect("/admin")

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("UPDATE licenses SET status='active' WHERE license_key=?", (key,))
    conn.commit()
    conn.close()

    return redirect("/dashboard")

# ================= EXTEND +30 DAYS =================
@app.route("/extend/<key>")
def extend(key):
    if not session.get("admin"):
        return redirect("/admin")

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute("SELECT expiry_date FROM licenses WHERE license_key=?", (key,))
    row = cursor.fetchone()

    if row:
        current_expiry = datetime.strptime(row[0], "%Y-%m-%d")

        # If expired → start from today
        if current_expiry < datetime.now():
            new_expiry = datetime.now() + timedelta(days=30)
        else:
            new_expiry = current_expiry + timedelta(days=30)

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
            <td>
                <a href="/reset_device/{d[0]}">Reset</a> |
                <a href="/deactivate/{d[0]}">Deactivate</a> |
                <a href="/activate/{d[0]}">Activate</a> |
                <a href="/extend/{d[0]}">Extend +30d</a>
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