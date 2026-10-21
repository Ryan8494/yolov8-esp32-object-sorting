import cv2
import time
import numpy as np
import serial
import serial.tools.list_ports
from ultralytics import YOLO

# ================== PENGATURAN ==================
# Untuk mencoba sekarang, pakai model bawaan "yolov8n.pt" (otomatis diunduh).
# Setelah dataset sendiri selesai dilatih, ganti ke "models/best.pt".
MODEL_PATH = "models/best_update.pt"

# Nama kelas objek yang ingin diambil robot.
# Bisa satu atau lebih kelas sekaligus.
TARGET = ["coin", "bottle-cap"]

CAMERA_INDEX = 0
CONFIDENCE = 0.55         # ambang keyakinan deteksi (0-1)
STABLE_FRAMES = 10        # objek harus terdeteksi sekian frame berturut-turut
COOLDOWN_DETIK = 5        # jeda minimal antar pengiriman serial (detik)
BATAS_SATURASI_KOIN = 45  # koin logam: saturasi rendah (<45), tutup botol: saturasi tinggi (>60)
PREVIEW_WIDTH = 640       # lebar jendela preview di laptop
PREVIEW_HEIGHT = 480      # tinggi jendela preview di laptop
# ================================================
stream_url = "http://192.168.88.130:8080/video"

# ================== SERIAL / USB ==================
SERIAL_PORT = "COM3"      # ganti sesuai port ESP32 kamu
SERIAL_BAUD = 115200      # harus sama dengan Serial.begin() di ESP32
# ==================================================


def deteksi_port_esp32():
    """Cari port COM yang kemungkinan ESP32 (otomatis)."""
    ports = serial.tools.list_ports.comports()
    for p in ports:
        desc = p.description.lower()
        if any(kata in desc for kata in ["cp210", "ch340", "usb serial", "silicon labs", "uart"]):
            return p.device
    # Tidak ditemukan otomatis, pakai default
    return None


def buat_koneksi_serial():
    """Buka koneksi serial ke ESP32."""
    # Coba deteksi otomatis dulu
    port = deteksi_port_esp32()
    if port:
        print(f"ESP32 terdeteksi otomatis di {port}")
    else:
        port = SERIAL_PORT
        print(f"Menggunakan port manual: {port}")

    try:
        ser = serial.Serial(port, SERIAL_BAUD, timeout=1)
        time.sleep(2)  # tunggu ESP32 reset setelah koneksi serial dibuka
        print(f"Serial tersambung ke {port} @ {SERIAL_BAUD} baud")
        return ser
    except serial.SerialException as e:
        print(f"Gagal buka serial {port}: {e}")
        print("\nPort yang tersedia:")
        for p in serial.tools.list_ports.comports():
            print(f"  {p.device} - {p.description}")
        return None


def koreksi_objek_berdasarkan_warna(roi, label_terdeteksi):
    """
    Koreksi klasifikasi: Jika terdeteksi 'bottle-cap' tetapi objeknya
    berwarna logam/monokrom (saturasi rendah), koreksi menjadi 'coin'.
    Mengembalikan: (label_akhir, rata_saturasi)
    """
    if roi is None or roi.size == 0:
        return label_terdeteksi, 0.0

    h, w = roi.shape[:2]
    if h < 5 or w < 5:
        return label_terdeteksi, 0.0

    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    # Ambil area tengah ROI (50% tengah) agar background meja tidak dominan
    tengah = hsv[h//4 : 3*h//4, w//4 : 3*w//4, 1]  # Channel 1: Saturation (0-255)
    rata_saturasi = float(np.mean(tengah))

    label_akhir = label_terdeteksi
    # Koin logam memiliki saturasi rendah (< BATAS_SATURASI_KOIN)
    # Jika YOLO salah tebak jadi bottle-cap padahal pucat/abu-abu logam, ubah ke coin
    if label_terdeteksi in ["bottle-cap", "tutup_botol"] and rata_saturasi < BATAS_SATURASI_KOIN:
        label_akhir = "coin"

    return label_akhir, rata_saturasi


def kirim_ke_robot(ser, label, cx, cy):
    """
    Kirim jenis objek dan koordinat piksel ke ESP32 lewat Serial USB.
    Format: "STOP,label,cx,cy\n"
    Contoh: "STOP,coin,320,240\n" atau "STOP,bottle-cap,320,240\n"
    """
    pesan = f"STOP,{label},{cx},{cy}\n"
    ser.write(pesan.encode())
    print(f">> TERKIRIM via Serial: STOP [{label}] (piksel {cx}, {cy})")


def main():
    model = YOLO(MODEL_PATH)
    print("Kelas yang dikenali model:", list(model.names.values()))

    cap = cv2.VideoCapture(stream_url)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    if not cap.isOpened():
        print("Kamera tidak terbuka.")
        return

    ser = buat_koneksi_serial()
    if ser is None:
        print("\n=== MODE TESTING (tanpa ESP32) ===")
        print("Deteksi kamera tetap berjalan, pengiriman serial dilewati.\n")

    stabil = 0
    sudah_kirim = False
    waktu_terakhir_kirim = 0  # timestamp terakhir kirim serial

    cv2.namedWindow("Deteksi Objek", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("Deteksi Objek", PREVIEW_WIDTH, PREVIEW_HEIGHT)

    while True:
        ok, frame = cap.read()
        if not ok:
            break

        hasil = model(frame, conf=CONFIDENCE, imgsz=640, verbose=False)[0]
        target_ditemukan = False
        target_label = ""
        cx = cy = 0

        for box in hasil.boxes:
            label = model.names[int(box.cls[0])]
            skor = float(box.conf[0])
            x1, y1, x2, y2 = map(int, box.xyxy[0])

            # Ambil potongan ROI objek untuk analisis warna
            h_frame, w_frame = frame.shape[:2]
            x1_c, y1_c = max(0, x1), max(0, y1)
            x2_c, y2_c = min(w_frame, x2), min(h_frame, y2)
            roi = frame[y1_c:y2_c, x1_c:x2_c]

            # Koreksi otomatis: jika terdeteksi bottle-cap tapi pucat/logam, ubah jadi coin
            label, sat = koreksi_objek_berdasarkan_warna(roi, label)

            is_target = (label in TARGET)

            # Warna kotak: koin = abu-abu, bottle-cap = hijau
            if label in ["coin", "koin"]:
                warna = (180, 180, 180)  # abu-abu untuk koin
            elif label in ["bottle-cap", "tutup_botol"]:
                warna = (0, 255, 0)      # hijau untuk bottle-cap
            else:
                warna = (100, 100, 100)  # non-target

            cv2.rectangle(frame, (x1, y1), (x2, y2), warna, 2)
            cv2.putText(frame, f"{label} {skor:.2f} (S:{int(sat)})", (x1, y1 - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, warna, 2)

            if is_target:
                target_ditemukan = True
                target_label = label
                cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
                cv2.circle(frame, (cx, cy), 6, (0, 0, 255), -1)

        # Filter stabilitas: hindari robot bergerak karena deteksi sesaat
        if target_ditemukan:
            stabil += 1
        else:
            stabil = 0
            sudah_kirim = False

        if stabil >= STABLE_FRAMES and not sudah_kirim:
            sekarang = time.time()
            if sekarang - waktu_terakhir_kirim >= COOLDOWN_DETIK:
                if ser:
                    kirim_ke_robot(ser, target_label, cx, cy)
                else:
                    print(f">> [TEST] STOP [{target_label}] (piksel {cx}, {cy}) — tidak dikirim, ESP32 tidak tersambung")
                sudah_kirim = True
                waktu_terakhir_kirim = sekarang
            else:
                sisa = COOLDOWN_DETIK - (sekarang - waktu_terakhir_kirim)
                print(f"Cooldown... {sisa:.1f}s lagi")

        # Cek apakah ada balasan dari ESP32
        if ser and ser.in_waiting > 0:
            balasan = ser.readline().decode().strip()
            if balasan:
                print(f"<< ESP32: {balasan}")

        target_teks = ", ".join(TARGET) if isinstance(TARGET, list) else TARGET
        cv2.putText(frame, f"Target: {target_teks} | stabil: {stabil}/{STABLE_FRAMES}",
                    (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
        status_serial = f"Serial {ser.port} @ {SERIAL_BAUD} baud" if ser else "MODE TESTING (tanpa ESP32)"
        cv2.putText(frame, status_serial,
                    (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

        cv2.imshow("Deteksi Objek", frame)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()
    if ser:
        ser.close()
        print("Serial ditutup.")


if __name__ == "__main__":
    main()
