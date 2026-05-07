import cv2
import cv2.aruco as aruco

d = aruco.getPredefinedDictionary(aruco.DICT_4X4_50)
for i in range(3):
    img = aruco.generateImageMarker(d, i, 400)
    cv2.imwrite(f'/home/drone/Downloads/marker_{i}.png', img)
    print(f'Saved marker_{i}.png')

print('Tekan Q buat keluar')

params = aruco.DetectorParameters()
params.adaptiveThreshWinSizeMin = 3
params.adaptiveThreshWinSizeMax = 23
params.adaptiveThreshWinSizeStep = 4
params.adaptiveThreshConstant = 7
params.minMarkerPerimeterRate = 0.03
params.maxMarkerPerimeterRate = 4.0
params.polygonalApproxAccuracyRate = 0.04
params.errorCorrectionRate = 0.8
params.cornerRefinementMethod = aruco.CORNER_REFINE_SUBPIX
params.cornerRefinementWinSize = 5
params.cornerRefinementMaxIterations = 30
params.cornerRefinementMinAccuracy = 0.01

detector = aruco.ArucoDetector(d, params)
cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

while True:
    ret, frame = cap.read()
    if not ret: 
        break 

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
    gray = clahe.apply(gray)

    corners, ids, rejected = detector.detectMarkers(gray)

    if ids is not None:
        aruco.drawDetectedMarkers(frame, corners, ids)
        for i, mid in enumerate(ids.flatten()):
            c = corners[i][0]
            cx = int(c[:,0].mean())
            cy = int(c[:,1].mean())
            offset_x = cx - frame.shape[1]//2
            offset_y = cy - frame.shape[0]//2
            area = cv2.contourArea(c)
            est_dist = round(1e6 / (area + 1), 1)

            print(f'[DETECTED] ID:{mid} | center:({cx},{cy}) | offset:({offset_x},{offset_y}) | est_dist:{est_dist}')

            cv2.putText(frame, f'ID:{mid}', (cx-40, cy-20),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0,255,0), 2)
            cv2.putText(frame, f'off:({offset_x},{offset_y})', (cx-60, cy+30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,255,0), 2)
    else:
        cv2.putText(frame, 'No marker detected', (20,40),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0,0,255), 2)

    cv2.putText(frame, f'Rejected: {len(rejected)}', (20, frame.shape[0]-20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (100,100,255), 1)

    fh, fw = frame.shape[:2]
    cv2.line(frame, (fw//2-20, fh//2), (fw//2+20, fh//2), (255,0,0), 2)
    cv2.line(frame, (fw//2, fh//2-20), (fw//2, fh//2+20), (255,0,0), 2)

    cv2.imshow('ArUco Detection', frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()