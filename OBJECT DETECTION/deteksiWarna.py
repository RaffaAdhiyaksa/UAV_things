import cv2
import numpy as np

def deteksiWarna(frame):
    hsv =cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

     #merah
    lower_merah1 = np.array([0, 90, 50])
    upper_merah1 = np.array([10, 255, 255])

    lower_merah2 = np.array([170, 90, 50])
    upper_merah2 = np.array([180, 255, 255])

    mask_merah1 = cv2.inRange(hsv, lower_merah1, upper_merah1)
    mask_merah2 = cv2.inRange(hsv, lower_merah2, upper_merah2)
    mask_merah = mask_merah1 + mask_merah2

    #biru
    lower_biru = np.array([100,150,50])
    upper_biru = np.array([130, 255, 255])

    mask_biru = cv2.inRange(hsv, lower_biru, upper_biru)

    contours_merah, _ = cv2.findContours(mask_merah, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for c in contours_merah:
        if cv2.contourArea(c) > 500:
            x, y, w, h = cv2.boundingRect(c)
            if w * h > 1000:
                cv2.rectangle(frame, (x,y), (x+w, y+h), (0,0,255), 2)
                cv2.putText(frame, "Merah", (x,y-5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,0,255), 2)
            
    contours_biru, _ = cv2.findContours(mask_biru, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for c in contours_biru:
        if cv2.contourArea(c) > 500:
            x, y, w, h = cv2.boundingRect(c)
            cv2.rectangle(frame, (x,y), (x+w, y+h), (255,0,0), 2)
            cv2.putText(frame, "Biru", (x,y-5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,0,0), 2)

    return frame

cap = cv2.VideoCapture(0)

while True:
    ret, frame = cap.read()
    if not ret:
        break

    frame = deteksiWarna(frame)
    cv2.imshow("Deteksi Warna Merah & Biru", frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
