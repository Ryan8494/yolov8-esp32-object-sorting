import cv2
import os
from datetime import datetime

# ================== PENGATURAN ==================
# Sesuaikan dengan stream kamera kamu
stream_url = "http://192.168.1.14:8080/video"
output_dir = "dataset_kamera"
# ================================================

os.makedirs(f"{output_dir}/images", exist_ok=True)

cap = cv2.VideoCapture(stream_url)
if not cap.isOpened():
    print("Kamera tidak terbuka. Cek stream URL.")
    raise SystemExit

count = 0

print("=" * 50)
print("  CAPTURE DATASET DARI KAMERA")
print("=" * 50)
print()
print("  Letakkan objek (koin / tutup botol) di depan kamera,")
print("  lalu tekan tombol untuk menyimpan frame:")
print()
print("  [s] = Simpan frame")
print("  [q] = Keluar")
print()
print("  Tips: ambil dari berbagai sudut, jarak, dan posisi.")
print("  Target minimal: 100 foto koin + 100 foto tutup botol")
print("=" * 50)

while True:
    ok, frame = cap.read()
    if not ok:
        print("Gagal membaca frame.")
        break

    # Tampilkan info di layar
    cv2.putText(frame, f"Tersimpan: {count} | [s] Simpan  [q] Keluar",
                (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)

    cv2.imshow("Capture Dataset", frame)
    key = cv2.waitKey(1) & 0xFF

    if key == ord('s'):
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        filename = f"{output_dir}/images/frame_{timestamp}.jpg"
        cv2.imwrite(filename, frame)
        count += 1
        print(f"[{count}] Tersimpan: {filename}")

    elif key == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
print(f"\nSelesai! Total frame tersimpan: {count}")
print(f"Lokasi: {os.path.abspath(output_dir)}/images/")
print()
print("Langkah selanjutnya:")
print("1. Upload folder images/ ke Roboflow")
print("2. Anotasi (beri label koin & tutup botol)")
print("3. Train ulang model")
print("4. Download best.pt baru, taruh di models/")
