from flask import Flask, request, jsonify, redirect, session
import sqlite3
import uuid
from datetime import datetime, timedelta

app = Flask(__name__)

# ================= CONFIG =================
DB_FILE = "licenses.db"
SECRET_KEY = "my_super_secret_123"
ADMIN_PASSWORD = "admin123"

app.secret_key = "session_secret_456"

# ================= DB INIT (FIXED) =================
def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # Create table if not exists
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS licenses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        license_key TEXT UNIQUE,
        created_at TEXT,
        expiry_date TEXT,
        status TEXT
    )
    """)

    # 🔥 AUTO FIX OLD DB (IMPORTANT)
    cursor.execute("PRAGMA table_info(licenses)")
    columns = [col[1] for col in cursor.fetchall()]

    if "license_key" not in columns:
        cursor.execute("DROP TABLE licenses")

        cursor.execute("""
        CREATE TABLE licenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            license_key TEXT UNIQUE,
            created_at TEXT,
            expiry_date TEXT,
            status TEXT
        )
        """)

    conn.commit()
    conn.close()

# 👇 MUST CALL
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
    INSERT INTO licenses (license_key, created_at, expiry_date, status)
    VALUES (?, ?, ?, ?)
    """, (
        license_key,
        created.strftime("%Y-%m-%d"),
        expiry.strftime("%Y-%m-%d"),
        "active"
    ))

    conn.commit()
    conn.close()

    return jsonify({
        "license_key": license_key,
        "expiry_date": expiry.strftime("%Y-%m-%d")
    })

# ================= VERIFY =================
@app.route("/verify", methods=["POST"])
def verify():

    if request.headers.get("x-api-key") != SECRET_KEY:
        return jsonify({"error": "Unauthorized"}), 403

    data = request.get_json() or {}
    key = data.get("license_key")

    if not key:
        return jsonify({"status": "invalid"})

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute("SELECT expiry_date, status FROM licenses WHERE license_key=?", (key,))
    row = cursor.fetchone()

    conn.close()

    if not row:
        return jsonify({"status": "invalid"})

    expiry_date = datetime.strptime(row[0], "%Y-%m-%d")

    if row[1] != "active":
        return jsonify({"status": "invalid"})

    if datetime.now() > expiry_date:
        return jsonify({"status": "expired"})

    return jsonify({
        "status": "valid",
        "expiry_date": row[0]
    })

# ================= ADMIN LOGIN =================
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
    <body style="text-align:center;margin-top:150px;font-family:Arial;">
        <h2>🔐 Admin Login</h2>
        <form method="post">
            <input type="password" name="password" placeholder="Password"><br><br>
            <button>Login</button>
        </form>
    </body>
    </html>
    """

# ================= LOGOUT =================
@app.route("/logout")
def logout():
    session.pop("admin", None)
    return redirect("/admin")

# ================= DASHBOARD =================
@app.route("/dashboard")
def dashboard():

    if not session.get("admin"):
        return redirect("/admin")

    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()

        cursor.execute("SELECT license_key, expiry_date, status FROM licenses")
        data = cursor.fetchall()

        conn.close()

    except Exception as e:
        return f"<h2>Database Error:</h2><pre>{str(e)}</pre>"

    rows = ""

    if not data:
        rows = "<tr><td colspan='4'>No licenses found</td></tr>"
    else:
        for d in data:
            color = "green" if d[2] == "active" else "red"

            rows += f"""
            <tr>
                <td>{d[0]}</td>
                <td>{d[1]}</td>
                <td style='color:{color}'>{d[2]}</td>
                <td><button onclick="copyKey('{d[0]}')">Copy</button></td>
            </tr>
            """

    return f"""
    <html>
    <body style="background:#111;color:white;padding:20px;font-family:Arial;">

    <h2>🚀 Dashboard</h2>
    <a href="/logout">Logout</a>

    <h3>Create License</h3>
    <form method="post" action="/create_license_ui">
        <input name="days" placeholder="Days (default 30)">
        <button>Generate</button>
    </form>

    <h3>Licenses</h3>
    <table border="1" cellpadding="10">
        <tr>
            <th>Key</th>
            <th>Expiry</th>
            <th>Status</th>
            <th>Action</th>
        </tr>
        {rows}
    </table>

    <script>
    function copyKey(key){{
        navigator.clipboard.writeText(key);
        alert("Copied: "+key);
    }}
    </script>

    </body>
    </html>
    """

# ================= CREATE LICENSE UI =================
@app.route("/create_license_ui", methods=["POST"])
def create_license_ui():

    if not session.get("admin"):
        return redirect("/admin")

    days = int(request.form.get("days") or 30)

    license_key = str(uuid.uuid4()).upper()
    created = datetime.now()
    expiry = created + timedelta(days=days)

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO licenses (license_key, created_at, expiry_date, status)
    VALUES (?, ?, ?, ?)
    """, (
        license_key,
        created.strftime("%Y-%m-%d"),
        expiry.strftime("%Y-%m-%d"),
        "active"
    ))

    conn.commit()
    conn.close()

    return f"""
    <html>
    <body style="text-align:center;margin-top:100px;">
        <h2>✅ License Created</h2>
        <h3>{license_key}</h3>
        <a href="/dashboard">Back</a>
    </body>
    </html>
    """

# ================= RUN =================
if __name__ == "__main__":
    app.run(debug=True)