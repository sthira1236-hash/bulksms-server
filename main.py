import tkinter as tk
from tkinter import messagebox
import serial.tools.list_ports
import requests
from multi_sender import send_sms

# ================= CONFIG =================
VERIFY_URL = "https://bulksms-server.onrender.com/verify"
API_KEY = "my_super_secret_123"

connected_ports = []

# ================= FUNCTIONS =================

def detect_ports():
    ports = serial.tools.list_ports.comports()
    port_list = [p.device for p in ports]

    entry_ports.delete(0, tk.END)
    entry_ports.insert(0, ",".join(port_list))

    log("Detected ports: " + ", ".join(port_list))


def connect_ports():
    global connected_ports
    ports = entry_ports.get().split(",")

    if not ports or ports == [""]:
        messagebox.showerror("Error", "No ports found")
        return

    connected_ports = ports
    log("Connected ports: " + ", ".join(ports))
    messagebox.showinfo("Success", "Ports Connected")


def activate_license():
    key = entry_license.get()

    if not key:
        messagebox.showerror("Error", "Enter license key")
        return

    try:
        res = requests.post(
            VERIFY_URL,
            json={"license_key": key},
            headers={"x-api-key": API_KEY}
        )

        data = res.json()

        if data.get("status") == "valid":
            lbl_status.config(text="License Active", fg="green")
            log("License Activated")
        else:
            lbl_status.config(text="Invalid License", fg="red")
            log("License Failed")

    except Exception as e:
        messagebox.showerror("Error", str(e))


def start_sending():
    if lbl_status.cget("text") != "License Active":
        messagebox.showerror("Error", "Activate license first")
        return

    numbers = txt_numbers.get("1.0", tk.END).strip().split("\n")
    message = txt_message.get("1.0", tk.END).strip()
    delay = int(entry_delay.get() or 2)

    if not connected_ports:
        messagebox.showerror("Error", "Connect ports first")
        return

    if not numbers or numbers == [""]:
        messagebox.showerror("Error", "Enter numbers")
        return

    if not message:
        messagebox.showerror("Error", "Enter message")
        return

    log("Starting SMS sending...")

    send_sms(connected_ports, numbers, message, delay, log)

    log("Finished sending")


def log(text):
    txt_logs.insert(tk.END, text + "\n")
    txt_logs.see(tk.END)


# ================= UI =================
root = tk.Tk()
root.title("Bulk SMS PRO - Online License")
root.geometry("400x650")
root.configure(bg="#1e1e2f")

# License
tk.Label(root, text="License Key", fg="white", bg="#1e1e2f").pack()
entry_license = tk.Entry(root, width=40)
entry_license.pack(pady=5)

tk.Button(root, text="Activate License", bg="green", fg="white", command=activate_license).pack()

lbl_status = tk.Label(root, text="License Not Active", fg="red", bg="#1e1e2f")
lbl_status.pack(pady=5)

# Ports
tk.Label(root, text="COM Ports", fg="white", bg="#1e1e2f").pack()

entry_ports = tk.Entry(root, width=40)
entry_ports.pack(pady=5)

tk.Button(root, text="Auto Detect", command=detect_ports).pack(pady=2)
tk.Button(root, text="Connect Ports", bg="blue", fg="white", command=connect_ports).pack(pady=2)

# Numbers
tk.Label(root, text="Numbers", fg="white", bg="#1e1e2f").pack()
txt_numbers = tk.Text(root, height=5)
txt_numbers.pack(pady=5)

# Message
tk.Label(root, text="Message", fg="white", bg="#1e1e2f").pack()
txt_message = tk.Text(root, height=5)
txt_message.pack(pady=5)

# Delay
tk.Label(root, text="Delay (sec)", fg="white", bg="#1e1e2f").pack()
entry_delay = tk.Entry(root)
entry_delay.insert(0, "2")
entry_delay.pack(pady=5)

# Start
tk.Button(root, text="Start Sending", bg="orange", command=start_sending).pack(pady=10)

# Logs
tk.Label(root, text="Logs", fg="white", bg="#1e1e2f").pack()
txt_logs = tk.Text(root, height=8)
txt_logs.pack(pady=5)

root.mainloop()
