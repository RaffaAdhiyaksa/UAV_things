from ultralytics import YOLO
import cv2

model = YOLO("yolov8n.pt")
cap = cv2.VideoCapture(0)

while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break

    for r in model(frame, conf=0.5, verbose=False):
        for b in r.boxes or []:
            x1, y1, x2, y2 = map(int, b.xyxy[0])
            if (x2-x1)*(y2-y1) > 15000 and model.names[int(b.cls[0])] in ("bed", "couch"):
                cv2.rectangle(frame, (x1,y1), (x2,y2), (0,255,0), 2)
                cv2.putText(frame, "BANTAL", (x1,y1-8),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0,255,0), 2)

    cv2.imshow("YOLO Bantal", frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
