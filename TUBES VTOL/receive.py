# viewer.py
import cv2

RASPI_IP = "172.20.171.190"  # ganti sesuai IP raspi lu
stream_url = f"http://{RASPI_IP}:5000/video"

cap = cv2.VideoCapture(stream_url)

print("Tekan 'q' untuk keluar")

while True:
    ret, frame = cap.read()
    if not ret:
        print("Gagal konek, cek IP atau server raspi")
        break

    cv2.imshow("Drone Cam", frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()