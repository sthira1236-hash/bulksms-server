import tkinter as tk
from tkinter import messagebox, filedialog
import serial
import serial.tools.list_ports
import requests
import threading
import time
import uuid
import os
import csv

# ================= CONFIG =================
VERIFY_URL = "https://bulksms-server.onrender.com/verify"
API_KEY = "my_super_secret_123"

connected_ports = []
license_valid = False
sent_count = 0
fail_count = 0

# ================= DEVICE ID =================
def get_device_id():
    if os.path.exists("device_id.txt"):
        return open("device_id.txt").read().strip()
    else:
        did = str(uuid.uuid4())
        open("device_id.txt", "w").write(did)
        return did

DEVICE_ID = get_device_id()

# ================= FUNCTIONS =================
def log(msg):
    txt_logs.insert(tk.END, msg + "\n")
    txt_logs.see(tk.END)

def update_counter():
    lbl_counter.config(text=f"Sent: {sent_count} | Failed: {fail_count}")

# ================= CSV IMPORT =================
def import_csv_numbers():
    file_path = filedialog.askopenfilename(filetypes=[("CSV Files", "*.csv")])
    if not file_path:
        return

    numbers = set()

    try:
        with open(file_path, "r") as f:
            reader = csv.reader(f)
            for row in reader:
                if row:
                    num = row[0].strip()
                    if num.isdigit() and 8 <= len(num) <= 15:
                        numbers.add(num)

        txt_numbers.delete("1.0", tk.END)

        for num in sorted(numbers):
            txt_numbers.insert(tk.END, num + "\n")

        log(f"Imported {len(numbers)} valid unique numbers")

    except Exception as e:
        messagebox.showerror("Error", str(e))

# ================= PORTS =================
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
    messagebox.showinfo("Connected", "Ports Connected")

# ================= LICENSE =================
def activate_license():
    global license_valid

    key = entry_license.get()

    try:
        res = requests.post(
            VERIFY_URL,
            json={"license_key": key, "device_id": DEVICE_ID},
            headers={"x-api-key": API_KEY}
        )

        data = res.json()

        if data.get("status") == "valid":
            license_valid = True
            lbl_status.config(text="License Active", fg="green")
            log("License Activated")
        else:
            license_valid = False
            lbl_status.config(text="Invalid License", fg="red")
            log("License Failed")

    except Exception as e:
        messagebox.showerror("Error", str(e))

# ================= SMS SEND =================
def send_worker(port, numbers, message, delay):
    global sent_count, fail_count

    try:
        ser = serial.Serial(port, 115200, timeout=5)
        time.sleep(2)

        for num in numbers:
            try:
                ser.write(b'AT+CMGF=1\r')
                time.sleep(1)

                ser.write(f'AT+CMGS="{num}"\r'.encode())
                time.sleep(1)

                ser.write(message.encode() + b"\x1A")
                time.sleep(delay)

                sent_count += 1
                update_counter()
                log(f"{port} -> Sent: {num}")

            except:
                fail_count += 1
                update_counter()
                log(f"{port} -> Failed: {num}")

        ser.close()

    except Exception as e:
        log(f"{port} error: {str(e)}")

def start_sending():
    if not license_valid:
        messagebox.showerror("Error", "Activate license first")
        return

    if not connected_ports:
        messagebox.showerror("Error", "Connect ports first")
        return

    numbers = txt_numbers.get("1.0", tk.END).strip().split("\n")
    message = txt_message.get("1.0", tk.END).strip()
    delay = int(entry_delay.get() or 2)

    numbers = [n for n in numbers if n]

    if not numbers:
        messagebox.showerror("Error", "No numbers")
        return

    log("Starting sending...")

    # 🔄 Round robin multi-port sending
    for i, port in enumerate(connected_ports):
        part = numbers[i::len(connected_ports)]
        threading.Thread(target=send_worker, args=(port, part, message, delay)).start()

# ================= BALANCE =================
def check_balance():
    if not connected_ports:
        messagebox.showerror("Error", "Connect port first")
        return

    try:
        ser = serial.Serial(connected_ports[0], 115200, timeout=5)
        time.sleep(2)

        ser.write(b'AT+CUSD=1,"*123#"\r')
        time.sleep(5)

        resp = ser.read_all().decode()
        log("Balance:\n" + resp)

        ser.close()

    except Exception as e:
        log("Balance error: " + str(e))

# ================= UI =================
root = tk.Tk()
root.title("Bulk SMS PRO")
root.geometry("420x720")
root.configure(bg="#1e1e2f")

# License
tk.Label(root, text="License Key", fg="white", bg="#1e1e2f").pack()
entry_license = tk.Entry(root, width=40)
entry_license.pack()

tk.Button(root, text="Activate License", bg="green", fg="white",
          command=activate_license).pack(pady=5)

lbl_status = tk.Label(root, text="License Not Active", fg="red", bg="#1e1e2f")
lbl_status.pack()

# Ports
tk.Label(root, text="COM Ports", fg="white", bg="#1e1e2f").pack()
entry_ports = tk.Entry(root, width=40)
entry_ports.pack()

tk.Button(root, text="Auto Detect", command=detect_ports).pack()
tk.Button(root, text="Connect Ports", bg="blue", fg="white",
          command=connect_ports).pack(pady=5)

tk.Button(root, text="Check Balance", bg="purple", fg="white",
          command=check_balance).pack(pady=5)

# Numbers
tk.Label(root, text="Numbers", fg="white", bg="#1e1e2f").pack()
txt_numbers = tk.Text(root, height=5)
txt_numbers.pack()

tk.Button(root, text="Import CSV Numbers", bg="purple", fg="white",
          command=import_csv_numbers).pack(pady=5)

# Message
tk.Label(root, text="Message", fg="white", bg="#1e1e2f").pack()
txt_message = tk.Text(root, height=5)
txt_message.pack()

# Delay
tk.Label(root, text="Delay (sec)", fg="white", bg="#1e1e2f").pack()
entry_delay = tk.Entry(root)
entry_delay.insert(0, "2")
entry_delay.pack()

# Start
tk.Button(root, text="Start Sending", bg="orange",
          command=start_sending).pack(pady=10)

# Counter
lbl_counter = tk.Label(root, text="Sent: 0 | Failed: 0",
                       fg="white", bg="#1e1e2f")
lbl_counter.pack()

# Logs
tk.Label(root, text="Logs", fg="white", bg="#1e1e2f").pack()
txt_logs = tk.Text(root, height=10)
txt_logs.pack()

root.mainloop()