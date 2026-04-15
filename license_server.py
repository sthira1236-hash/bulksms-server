import sqlite3
import uuid
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, redirect

app = Flask(__name__)

# ==============================
# 🔐 SECURITY CONFIG
# ==============================
SECRET_KEY = "my_super_secret_123"
ADMIN_PASSWORD = "admin123"

# ==============================
# 🗄️ DATABASE INIT
# ==============================
def init_db():
    conn = sqlite3.connect("licenses.db")
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

# ==============================
# 🔑 GENERATE LICENSE (API)
# ==============================
@app.route("/generate", methods=["POST"])
def generate_license():

    if request.headers.get("x-api-key") != SECRET_KEY:
        return jsonify({"error": "Unauthorized"}), 403

    data = request.get_json()

    if not data or "days" not in data:
        return jsonify({"error": "Days required"}), 400

    days = int(data["days"])

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
        created_at.strftime("%Y-%m-%d"),
        expiry_date.strftime("%Y-%m-%d"),
        "active"
    ))

    conn.commit()
    conn.close()

    return jsonify({
        "license_key": license_key,
        "expiry_date": expiry_date.strftime("%Y-%m-%d")
    })


# ==============================
# ✅ VERIFY LICENSE (API)
# ==============================
@app.route("/verify", methods=["POST"])
def verify_license():

    if request.headers.get("x-api-key") != SECRET_KEY:
        return jsonify({"error": "Unauthorized"}), 403

    data = request.get_json()

    if not data or "license_key" not in data:
        return jsonify({"error": "License key required"}), 400

    license_key = data["license_key"]

    conn = sqlite3.connect("licenses.db")
    cursor = conn.cursor()

    cursor.execute("""
    SELECT expiry_date, status FROM licenses WHERE license_key = ?
    """, (license_key,))

    row = cursor.fetchone()
    conn.close()

    if not row:
        return jsonify({"status": "invalid"})

    expiry_date, status = row

    if status != "active":
        return jsonify({"status": "inactive"})

    if datetime.strptime(expiry_date, "%Y-%m-%d") < datetime.now():
        return jsonify({"status": "expired"})

    return jsonify({
        "status": "valid",
        "expiry_date": expiry_date
    })


# ==============================
# 🔐 ADMIN LOGIN
# ==============================
@app.route("/admin", methods=["GET", "POST"])
def admin_login():

    if request.method == "POST":
        if request.form.get("password") == ADMIN_PASSWORD:
            return redirect("/dashboard")
        else:
            return "❌ Wrong Password"

    return """
    <html>
    <body style="text-align:center;margin-top:100px;font-family:Arial;">
        <h2>🔐 Admin Login</h2>
        <form method="post">
            <input type="password" name="password" placeholder="Enter Password"><br><br>
            <button type="submit">Login</button>
        </form>
    </body>
    </html>
    """


# ==============================
# 📊 DASHBOARD
# ==============================
@app.route("/dashboard")
def dashboard():

    conn = sqlite3.connect("licenses.db")
    cursor = conn.cursor()
    cursor.execute("SELECT license_key, expiry_date, status FROM licenses")
    data = cursor.fetchall()
    conn.close()

    rows = ""
    for d in data:
        rows += f"""
        <tr>
            <td>{d[0]}</td>
            <td>{d[1]}</td>
            <td>{d[2]}</td>
        </tr>
        """

    return f"""
    <html>
    <body style="font-family:Arial;padding:20px;">
    
    <h2>🚀 License Dashboard</h2>

    <h3>Create License</h3>
    <form method="post" action="/create_license_ui">
        Days: <input name="days" value="30"><br><br>
        <button type="submit">Generate</button>
    </form>

    <hr>

    <h3>All Licenses</h3>
    <table border="1" cellpadding="10">
        <tr>
            <th>License Key</th>
            <th>Expiry</th>
            <th>Status</th>
        </tr>
        {rows}
    </table>

    </body>
    </html>
    """


# ==============================
# 🧾 CREATE LICENSE FROM UI
# ==============================
@app.route("/create_license_ui", methods=["POST"])
def create_license_ui():

    days = int(request.form.get("days"))

    license_key = str(uuid.uuid4()).upper()
    created = datetime.now()
    expiry = created + timedelta(days=days)

    conn = sqlite3.connect("licenses.db")
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
    <h3>✅ License Created</h3>
    <p><b>{license_key}</b></p>
    <a href="/dashboard">Back</a>
    """


# ==============================
# 🟢 HOME
# ==============================
@app.route("/")
def home():
    return "License Server Running ✅"


# ==============================
# 🚀 RUN
# ==============================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
