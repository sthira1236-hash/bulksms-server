from flask import Flask, request, jsonify, redirect
import sqlite3
import uuid
from datetime import datetime, timedelta

app = Flask(__name__)

# ================= CONFIG =================
DB_FILE = "licenses.db"
SECRET_KEY = "my_super_secret_123"
ADMIN_PASSWORD = "admin123"   # change this!

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
        status TEXT
    )
    """)

    conn.commit()
    conn.close()

init_db()

# ================= API =================

@app.route("/")
def home():
    return "License Server Running ✅"


@app.route("/generate", methods=["POST"])
def generate_license():

    # 🔒 PROTECTION
    if request.headers.get("x-api-key") != SECRET_KEY:
        return jsonify({"error": "Unauthorized"}), 403

    data = request.get_json()
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


@app.route("/verify", methods=["POST"])
def verify():

    # 🔒 PROTECTION
    if request.headers.get("x-api-key") != SECRET_KEY:
        return jsonify({"error": "Unauthorized"}), 403

    data = request.get_json()
    key = data.get("license_key")

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute("""
    SELECT expiry_date, status FROM licenses WHERE license_key=?
    """, (key,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        return jsonify({"status": "invalid"})

    expiry_date = datetime.strptime(row[0], "%Y-%m-%d")
    status = row[1]

    if status != "active":
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
            return redirect("/dashboard")
        else:
            return "<h3 style='color:red;text-align:center;'>Wrong Password</h3>"

    return """
    <html>
    <head>
        <title>Admin Login</title>
        <style>
            body {
                background: linear-gradient(135deg, #667eea, #764ba2);
                font-family: Arial;
                color: white;
                text-align: center;
                margin-top: 150px;
            }
            input, button {
                padding: 10px;
                margin: 10px;
                border: none;
                border-radius: 5px;
            }
            button {
                background: #00ffcc;
                cursor: pointer;
            }
        </style>
    </head>
    <body>
        <h1>🔐 Admin Login</h1>
        <form method="post">
            <input type="password" name="password" placeholder="Enter Password"><br>
            <button type="submit">Login</button>
        </form>
    </body>
    </html>
    """


# ================= DASHBOARD =================

@app.route("/dashboard")
def dashboard():

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT license_key, expiry_date, status FROM licenses")
    data = cursor.fetchall()
    conn.close()

    rows = ""
    for d in data:
        color = "#00ff88" if d[2] == "active" else "#ff4d4d"

        rows += f"""
        <tr>
            <td>{d[0]}</td>
            <td>{d[1]}</td>
            <td style='color:{color};font-weight:bold;'>{d[2]}</td>
            <td><button onclick="copyKey('{d[0]}')">Copy</button></td>
        </tr>
        """

    return f"""
    <html>
    <head>
        <title>Dashboard</title>
        <style>
            body {{
                background: #0f172a;
                color: white;
                font-family: Arial;
                padding: 20px;
            }}
            h1 {{ color: #00ffcc; }}
            table {{
                width: 100%;
                border-collapse: collapse;
                margin-top: 20px;
            }}
            th, td {{
                padding: 12px;
                border-bottom: 1px solid #333;
            }}
            th {{ background: #1e293b; }}
            tr:hover {{ background: #1e293b; }}
            button {{
                padding: 6px 12px;
                border-radius: 5px;
                border: none;
                background: #00ffcc;
                cursor: pointer;
            }}
            .card {{
                background: #1e293b;
                padding: 20px;
                border-radius: 10px;
                margin-top: 20px;
            }}
            input {{
                padding: 8px;
                border-radius: 5px;
                border: none;
                margin-right: 10px;
            }}
        </style>

        <script>
            function copyKey(key) {{
                navigator.clipboard.writeText(key);
                alert("Copied: " + key);
            }}
        </script>
    </head>

    <body>

    <h1>🚀 License Dashboard</h1>

    <div class="card">
        <h3>Create License</h3>
        <form method="post" action="/create_license_ui">
            <input name="days" placeholder="Days (30)">
            <button type="submit">Generate</button>
        </form>
    </div>

    <div class="card">
        <h3>All Licenses</h3>
        <table>
            <tr>
                <th>License Key</th>
                <th>Expiry</th>
                <th>Status</th>
                <th>Action</th>
            </tr>
            {rows}
        </table>
    </div>

    </body>
    </html>
    """


# ================= CREATE LICENSE UI =================

@app.route("/create_license_ui", methods=["POST"])
def create_license_ui():

    days = int(request.form.get("days"))

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
    <body style="background:#0f172a;color:white;text-align:center;padding-top:100px;">
        <h2>✅ License Generated</h2>
        <h3 style="color:#00ffcc;">{license_key}</h3>
        <a href="/dashboard" style="color:white;">⬅ Back</a>
    </body>
    </html>
    """


# ================= RUN =================

if __name__ == "__main__":
    app.run(debug=True)
