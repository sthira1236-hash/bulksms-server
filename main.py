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
from datetime import datetime

# ================= CONFIG =================
VERIFY_URL = "https://bulksms-server.onrender.com/verify"
API_KEY = "my_super_secret_123"

connected_ports = []
license_valid = False

sent_count = 0
fail_count = 0
delivered_count = 0

DEVICE_ID_FILE = "device_id.txt"
DLR_FILE = "delivery_report.csv"

# ================= DEVICE ID =================
def get_device_id():
    if os.path.exists(DEVICE_ID_FILE):
        return open(DEVICE_ID_FILE).read().strip()
    did = str(uuid.uuid4())
    open(DEVICE_ID_FILE, "w").write(did)
    return did

DEVICE_ID = get_device_id()

# ================= LOG =================
def log(msg):
    txt_logs.insert(tk.END, msg + "\n")
    txt_logs.see(tk.END)

def update_counter():
    lbl_counter.config(
        text=f"Sent: {sent_count} | Failed: {fail_count} | Delivered: {delivered_count}"
    )

# ================= CSV IMPORT =================
def import_csv_numbers():
    path = filedialog.askopenfilename(filetypes=[("CSV Files", "*.csv")])
    if not path:
        return

    numbers = set()
    try:
        with open(path, "r") as f:
            reader = csv.reader(f)
            for row in reader:
                if row:
                    num = row[0].strip()
                    if num.isdigit() and 8 <= len(num) <= 15:
                        numbers.add(num)

        txt_numbers.delete("1.0", tk.END)
        for n in sorted(numbers):
            txt_numbers.insert(tk.END, n + "\n")

        log(f"Imported {len(numbers)} valid numbers")
    except Exception as e:
        messagebox.showerror("Error", str(e))

# ================= PORTS =================
def detect_ports():
    ports = serial.tools.list_ports.comports()
    lst = [p.device for p in ports]
    entry_ports.delete(0, tk.END)
    entry_ports.insert(0, ",".join(lst))
    log("Detected: " + ", ".join(lst))

def connect_ports():
    global connected_ports
    ports = [p.strip() for p in entry_ports.get().split(",") if p.strip()]
    if not ports:
        messagebox.showerror("Error", "No ports")
        return
    connected_ports = ports
    log("Connected: " + ", ".join(ports))
    messagebox.showinfo("OK", "Ports connected")

# ================= LICENSE =================
def activate_license():
    global license_valid
    key = entry_license.get().strip()

    try:
        res = requests.post(
            VERIFY_URL,
            json={"license_key": key, "device_id": DEVICE_ID},
            headers={"x-api-key": API_KEY},
            timeout=10
        )
        data = res.json()

        if data.get("status") == "valid":
            license_valid = True
            lbl_status.config(text="License Active", fg="green")
            log("License OK")
        else:
            license_valid = False
            lbl_status.config(text=f"{data.get('status','Invalid')}", fg="red")
            log("License failed")

    except Exception as e:
        messagebox.showerror("Error", str(e))

# ================= DLR SAVE =================
def save_dlr(number, status):
    file_exists = os.path.exists(DLR_FILE)

    with open(DLR_FILE, "a", newline="") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["Number", "Status", "Time"])
        writer.writerow([number, status, datetime.now().strftime("%Y-%m-%d %H:%M:%S")])

# ================= DELIVERY PARSE =================
def read_delivery_report(ser, port, number):
    global delivered_count
    try:
        time.sleep(3)
        resp = ser.read_all().decode(errors="ignore")

        if "+CDS" in resp:
            delivered_count += 1
            update_counter()
            log(f"{port} -> ✅ Delivered: {number}")
            save_dlr(number, "Delivered")

        elif "ERROR" in resp:
            log(f"{port} -> ❌ Delivery Failed: {number}")
            save_dlr(number, "Failed")

        else:
            log(f"{port} -> ⏳ No DLR: {number}")
            save_dlr(number, "Unknown")

    except Exception as e:
        log(f"{port} DLR error: {str(e)}")

# ================= SMS SEND =================
def send_worker(port, numbers, message, delay):
    global sent_count, fail_count

    try:
        ser = serial.Serial(port, 115200, timeout=5)
        time.sleep(2)

        # Text mode + DLR enable
        ser.write(b'AT+CMGF=1\r')
        time.sleep(1)
        ser.write(b'AT+CSMP=49,167,0,0\r')
        time.sleep(1)

        for num in numbers:
            try:
                ser.write(f'AT+CMGS="{num}"\r'.encode())
                time.sleep(1)

                ser.write(message.encode() + b"\x1A")
                time.sleep(delay)

                sent_count += 1
                update_counter()
                log(f"{port} -> Sent: {num}")

                read_delivery_report(ser, port, num)

            except Exception as e:
                fail_count += 1
                update_counter()
                log(f"{port} -> Failed: {num}")
                save_dlr(num, "Failed")

        ser.close()

    except Exception as e:
        log(f"{port} error: {str(e)}")

# ================= START =================
def start_sending():
    if not license_valid:
        messagebox.showerror("Error", "Activate license")
        return

    if not connected_ports:
        messagebox.showerror("Error", "Connect ports")
        return

    numbers = txt_numbers.get("1.0", tk.END).strip().split("\n")
    numbers = [n for n in numbers if n]

    message = txt_message.get("1.0", tk.END).strip()
    delay = int(entry_delay.get() or 2)

    if not numbers:
        messagebox.showerror("Error", "No numbers")
        return

    log("Starting...")

    for i, port in enumerate(connected_ports):
        part = numbers[i::len(connected_ports)]
        threading.Thread(target=send_worker,
                         args=(port, part, message, delay),
                         daemon=True).start()

# ================= BALANCE =================
def check_balance():
    if not connected_ports:
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
        log(str(e))

# ================= UI =================
root = tk.Tk()
root.title("Bulk SMS PRO - DLR")
root.geometry("430x750")
root.configure(bg="#1e1e2f")

tk.Label(root, text="License Key", fg="white", bg="#1e1e2f").pack()
entry_license = tk.Entry(root, width=40)
entry_license.pack()

tk.Button(root, text="Activate License", bg="green", fg="white",
          command=activate_license).pack(pady=5)

lbl_status = tk.Label(root, text="Not Active", fg="red", bg="#1e1e2f")
lbl_status.pack()

tk.Label(root, text="Ports", fg="white", bg="#1e1e2f").pack()
entry_ports = tk.Entry(root, width=40)
entry_ports.pack()

tk.Button(root, text="Auto Detect", command=detect_ports).pack()
tk.Button(root, text="Connect", command=connect_ports).pack()

tk.Button(root, text="Check Balance", bg="purple", fg="white",
          command=check_balance).pack(pady=5)

tk.Label(root, text="Numbers", fg="white", bg="#1e1e2f").pack()
txt_numbers = tk.Text(root, height=5)
txt_numbers.pack()

tk.Button(root, text="Import CSV", bg="purple", fg="white",
          command=import_csv_numbers).pack()

tk.Label(root, text="Message", fg="white", bg="#1e1e2f").pack()
txt_message = tk.Text(root, height=5)
txt_message.pack()

tk.Label(root, text="Delay", fg="white", bg="#1e1e2f").pack()
entry_delay = tk.Entry(root)
entry_delay.insert(0, "2")
entry_delay.pack()

tk.Button(root, text="Start Sending", bg="orange",
          command=start_sending).pack(pady=10)

lbl_counter = tk.Label(root, text="Sent:0 Failed:0 Delivered:0",
                       fg="white", bg="#1e1e2f")
lbl_counter.pack()

tk.Label(root, text="Logs", fg="white", bg="#1e1e2f").pack()
txt_logs = tk.Text(root, height=12)
txt_logs.pack()

root.mainloop()