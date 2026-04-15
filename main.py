import tkinter as tk
from tkinter import messagebox
import serial
import serial.tools.list_ports
import threading
import time
import json
import os
import requests
import uuid

# ================= CONFIG =================
SERVER_URL = "http://127.0.0.1:5000/verify"
LICENSE_FILE = "license.json"

# ================= GLOBAL =================
connected_ports = []
license_data = {"key": "", "activated": False}


# ================= DEVICE ID =================
def get_device_id():
    return str(uuid.getnode())


# ================= LICENSE =================
def load_license():
    global license_data
    if os.path.exists(LICENSE_FILE):
        with open(LICENSE_FILE, "r") as f:
            license_data = json.load(f)


def save_license():
    with open(LICENSE_FILE, "w") as f:
        json.dump(license_data, f)


def verify_online(key):
    try:
        res = requests.post(SERVER_URL, json={
            "key": key,
            "device": get_device_id()
        }, timeout=5)

        data = res.json()

        if data["status"] == "valid":
            return True, data["expiry"]

        return False, data["status"]

    except:
        return None, "offline"


def activate_license():
    key = license_entry.get().strip()

    ok, info = verify_online(key)

    if ok:
        license_data["key"] = key
        license_data["activated"] = True
        save_license()
        log("✅ License Activated")
        update_status()

    elif ok is None:
        messagebox.showwarning("Warning", "No internet. Try again.")
    else:
        messagebox.showerror("Error", f"License {info}")


def check_license_on_start():
    if not license_data.get("key"):
        return False

    ok, info = verify_online(license_data["key"])

    if ok:
        license_data["activated"] = True
        save_license()
        return True

    elif ok is None:
        # offline fallback
        return license_data.get("activated", False)

    else:
        license_data["activated"] = False
        save_license()
        return False


# ================= PORT =================
def auto_detect():
    ports = [p.device for p in serial.tools.list_ports.comports()]
    port_entry.delete(0, tk.END)
    port_entry.insert(0, ",".join(ports))
    log(f"Detected: {ports}")


def connect_ports():
    global connected_ports
    connected_ports = []

    ports = port_entry.get().split(",")

    for p in ports:
        try:
            ser = serial.Serial(p.strip(), 115200, timeout=5)
            connected_ports.append(ser)
            log(f"Connected: {p}")
        except:
            log(f"Failed: {p}")

    if connected_ports:
        log("All ports connected")
    else:
        log("No ports connected")


# ================= SMS =================
def send_sms_worker():
    if not license_data.get("activated"):
        messagebox.showerror("Error", "License not active")
        return

    numbers = numbers_box.get("1.0", tk.END).strip().split("\n")
    msg = message_box.get("1.0", tk.END).strip()
    delay = int(delay_entry.get())

    def worker():
        for num in numbers:
            num = num.strip()
            if not num:
                continue

            for ser in connected_ports:
                try:
                    log(f"Sending {num} via {ser.port}")

                    ser.write(b'AT\r')
                    time.sleep(1)
                    ser.read_all()

                    ser.write(b'AT+CMGF=1\r')
                    time.sleep(1)
                    ser.read_all()

                    cmd = f'AT+CMGS="{num}"\r'
                    ser.write(cmd.encode())
                    time.sleep(2)

                    ser.write(msg.encode() + b"\x1A")
                    time.sleep(5)

                    resp = ser.read_all().decode(errors="ignore")

                    if "OK" in resp or "+CMGS" in resp:
                        log(f"✔ Sent: {num}")
                    else:
                        log(f"✖ Failed: {num}")

                except Exception as e:
                    log(f"Error: {str(e)}")

            time.sleep(delay)

        log("✅ All Done")

    threading.Thread(target=worker).start()


# ================= LOG =================
def log(msg):
    logs.insert(tk.END, msg + "\n")
    logs.see(tk.END)


# ================= UI =================
def update_status():
    if license_data.get("activated"):
        status_label.config(text="License: Active", fg="green")
    else:
        status_label.config(text="License: Not Active", fg="red")


root = tk.Tk()
root.title("Bulk SMS PRO - Online License")
root.geometry("420x650")
root.configure(bg="#1e1e2f")

# License
tk.Label(root, text="License Key", bg="#1e1e2f", fg="white").pack()
license_entry = tk.Entry(root, width=40)
license_entry.pack(pady=5)

tk.Button(root, text="Activate License", bg="green", fg="white",
          command=activate_license).pack(pady=5)

status_label = tk.Label(root, text="Checking...", bg="#1e1e2f")
status_label.pack()

# Ports
tk.Label(root, text="COM Ports", bg="#1e1e2f", fg="white").pack()
port_entry = tk.Entry(root, width=40)
port_entry.pack()

tk.Button(root, text="Auto Detect", command=auto_detect).pack()
tk.Button(root, text="Connect Ports", bg="blue", fg="white",
          command=connect_ports).pack(pady=5)

# Numbers
tk.Label(root, text="Numbers", bg="#1e1e2f", fg="white").pack()
numbers_box = tk.Text(root, height=5)
numbers_box.pack()

# Message
tk.Label(root, text="Message", bg="#1e1e2f", fg="white").pack()
message_box = tk.Text(root, height=4)
message_box.pack()

# Delay
tk.Label(root, text="Delay (sec)", bg="#1e1e2f", fg="white").pack()
delay_entry = tk.Entry(root)
delay_entry.insert(0, "2")
delay_entry.pack()

# Send
tk.Button(root, text="Start Sending", bg="orange", fg="white",
          command=send_sms_worker).pack(pady=10)

# Logs
tk.Label(root, text="Logs", bg="#1e1e2f", fg="white").pack()
logs = tk.Text(root, height=10)
logs.pack()

# ================= INIT =================
load_license()

if check_license_on_start():
    log("✔ License Valid")
else:
    log("✖ License Required")

update_status()

root.mainloop()