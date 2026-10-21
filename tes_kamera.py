import cv2

# 0 = kamera default. Coba 1 atau 2 untuk kamera eksternal / USB.
# cv2.CAP_DSHOW mempercepat pembukaan kamera di Windows.
cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)

if not cap.isOpened():
    print("Kamera tidak terbuka. Coba ganti indeks kamera (0, 1, 2).")
    raise SystemExit

print("Kamera berjalan. Tekan 'q' untuk keluar.")

while True:
    ok, frame = cap.read()
    if not ok:
        print("Gagal membaca frame dari kamera.")
        break

    cv2.imshow("Tes Kamera", frame)

    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

cap.release()
cv2.destroyAllWindows()
