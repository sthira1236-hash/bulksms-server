from flask import Flask, request, jsonify, render_template_string, session, redirect
import hashlib
import sqlite3
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = "SUPER_SECRET_SESSION_KEY"

SECRET = "MY_SECRET_KEY"
ADMIN_USER = "admin"
ADMIN_PASS = "1234"

DB_NAME = "licenses.db"

# ================= DATABASE =================
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS licenses (
        key TEXT PRIMARY KEY,
        user TEXT,
        expiry TEXT,
        active INTEGER,
        device TEXT
    )
    """)

    conn.commit()
    conn.close()

init_db()

# ================= HELPER =================
def generate_key(name):
    raw = name + SECRET + str(datetime.now())
    return hashlib.sha256(raw.encode()).hexdigest()

def check_login():
    return session.get("logged_in")

# ================= LOGIN =================
LOGIN_HTML = """
<h2>🔐 Admin Login</h2>
<form method="post">
<input name="user" placeholder="Username"><br><br>
<input name="pass" type="password" placeholder="Password"><br><br>
<button>Login</button>
</form>
"""

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        user = request.form.get("user")
        password = request.form.get("pass")

        if user == ADMIN_USER and password == ADMIN_PASS:
            session["logged_in"] = True
            return redirect("/admin")

    return LOGIN_HTML

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

# ================= CREATE =================
@app.route("/create", methods=["POST"])
def create():
    if not check_login():
        return jsonify({"error":"unauthorized"})

    data = request.json
    name = data.get("name", "USER")
    days = int(data.get("days", 30))

    key = generate_key(name)
    expiry = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    c.execute("""
    INSERT INTO licenses (key,user,expiry,active,device)
    VALUES (?,?,?,?,?)
    """, (key, name, expiry, 1, ""))

    conn.commit()
    conn.close()

    return jsonify({"license": key})

# ================= VERIFY =================
@app.route("/verify", methods=["POST"])
def verify():
    data = request.json
    key = data.get("key")
    device = data.get("device", "PC")

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT user,expiry,active,device FROM licenses WHERE key=?", (key,))
    row = c.fetchone()
    conn.close()

    if not row:
        return jsonify({"status": "invalid"})

    user, expiry, active, saved_device = row

    if active == 0:
        return jsonify({"status": "blocked"})

    if datetime.now() > datetime.strptime(expiry, "%Y-%m-%d"):
        return jsonify({"status": "expired"})

    if saved_device == "":
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("UPDATE licenses SET device=? WHERE key=?", (device, key))
        conn.commit()
        conn.close()

    elif saved_device != device:
        return jsonify({"status": "device_mismatch"})

    return jsonify({"status": "valid"})

# ================= ACTIONS =================
@app.route("/disable", methods=["POST"])
def disable():
    if not check_login():
        return jsonify({"error":"unauthorized"})

    key = request.json.get("key")
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE licenses SET active=0 WHERE key=?", (key,))
    conn.commit()
    conn.close()
    return jsonify({"status":"disabled"})

@app.route("/enable", methods=["POST"])
def enable():
    if not check_login():
        return jsonify({"error":"unauthorized"})

    key = request.json.get("key")
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE licenses SET active=1 WHERE key=?", (key,))
    conn.commit()
    conn.close()
    return jsonify({"status":"enabled"})

@app.route("/delete", methods=["POST"])
def delete():
    if not check_login():
        return jsonify({"error":"unauthorized"})

    key = request.json.get("key")
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("DELETE FROM licenses WHERE key=?", (key,))
    conn.commit()
    conn.close()
    return jsonify({"status":"deleted"})

@app.route("/reset_device", methods=["POST"])
def reset():
    if not check_login():
        return jsonify({"error":"unauthorized"})

    key = request.json.get("key")
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE licenses SET device='' WHERE key=?", (key,))
    conn.commit()
    conn.close()
    return jsonify({"status":"reset_done"})

# ================= LIST =================
@app.route("/list")
def list_all():
    if not check_login():
        return jsonify([])

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT key,user,expiry,active FROM licenses")
    rows = c.fetchall()
    conn.close()

    return jsonify([
        {"key":r[0],"user":r[1],"expiry":r[2],"active":r[3]}
        for r in rows
    ])

# ================= ADMIN PANEL =================
ADMIN_HTML = """
<h2>🔐 License Admin Panel</h2>
<a href="/logout">Logout</a><br><br>

<input id="name" placeholder="Customer">
<input id="days" placeholder="Days">
<button onclick="create()">Create</button>

<table id="tbl"></table>

<script>
function load(){
fetch('/list')
.then(r=>r.json())
.then(data=>{
let t=document.getElementById('tbl');
t.innerHTML="<tr><th>User</th><th>Expiry</th><th>Status</th><th>Action</th></tr>";

data.forEach(d=>{
t.innerHTML+=`
<tr>
<td>${d.user}</td>
<td>${d.expiry}</td>
<td>${d.active ? "Active":"Blocked"}</td>
<td>
<button onclick="disable('${d.key}')">Disable</button>
<button onclick="enable('${d.key}')">Enable</button>
<button onclick="del('${d.key}')">Delete</button>
</td>
</tr>`;
});
});
}

function create(){
fetch('/create',{
method:'POST',
headers:{'Content-Type':'application/json'},
body:JSON.stringify({
name:document.getElementById('name').value,
days:document.getElementById('days').value
})
}).then(load);
}

function disable(k){fetch('/disable',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({key:k})}).then(load);}
function enable(k){fetch('/enable',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({key:k})}).then(load);}
function del(k){fetch('/delete',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({key:k})}).then(load);}

load();
</script>
"""

@app.route("/admin")
def admin():
    if not check_login():
        return redirect("/login")
    return render_template_string(ADMIN_HTML)

# ================= RUN =================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)