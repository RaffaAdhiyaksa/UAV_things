import cv2
import numpy as np

colors = {
    "merah": {
        "ranges": [
            (np.array([165,80,60]),  np.array([180,255,255])),
            (np.array([0,80,60]),    np.array([8,255,255])),
            (np.array([165,40,40]), np.array([180,100,200])),
            (np.array([0,40,40]),    np.array([8,100,200])),
        ],
        "bgr": (0,0,255)
    },
    "oranye": {
        "ranges": [
            (np.array([8,150,150]),  np.array([18,255,255])),
            (np.array([8,80,80]),    np.array([18,150,255])),
            (np.array([6,100,100]),  np.array([10,255,255])),
            (np.array([18,100,100]), np.array([22,255,255])),
        ],
        "bgr": (0,130,255)
    },
    "pink": {
        "ranges": [
            (np.array([148,80,180]), np.array([165,255,255])),
            (np.array([145,40,150]), np.array([165,100,255])),
            (np.array([140,60,180]), np.array([150,180,255])),
            (np.array([155,80,100]), np.array([170,255,255])),
        ],
        "bgr": (180,0,255)
    },
    "ungu": {
        "ranges": [
            (np.array([125,120,60]), np.array([145,255,255])),
            (np.array([120,60,40]),  np.array([138,130,200])),
            (np.array([138,180,80]), np.array([148,255,255])),
            (np.array([120,40,100]), np.array([130,120,255])),
        ],
        "bgr": (255,0,100)
    },
}

COLOR_HUE_CENTER = {
    "merah":  [0, 176],
    "oranye": [14],
    "pink":   [155],
    "ungu":   [133],
}
HUE_PROXIMITY_THRESH = 15
MIN_AREA             = 1500
CONFIRM_FRAMES       = 4
TUNE_COLOR           = None  # ganti ke "merah"/"oranye"/"pink"/"ungu" buat tuning

BRIGHTNESS_NORMAL  = 0
BRIGHTNESS_REDUCED = -40
current_brightness = BRIGHTNESS_NORMAL
target_brightness  = BRIGHTNESS_NORMAL

counters  = {name: 0 for name in colors}
confirmed = {name: False for name in colors}

def nothing(x):
    pass

def build_mask(hsv, ranges):
    combined = np.zeros(hsv.shape[:2], dtype=np.uint8)
    for (lo, hi) in ranges:
        combined = cv2.bitwise_or(combined, cv2.inRange(hsv, lo, hi))
    return combined

def validate(name, hue, sat, val):
    if name == "merah":
        return (hue >= 165 or hue <= 8) and sat >= 40
    if name == "oranye":
        return 6 <= hue <= 22 and sat >= 80 and val >= 60
    if name == "pink":
        return 140 <= hue <= 170 and val >= 100
    if name == "ungu":
        return 120 <= hue <= 148 and sat >= 40
    return False


        hsv amrkmv 
def disambiguate(name, hue, sat, val):
    if name == "pink"   and hue < 145:           return False
    if name == "ungu"   and hue > 148:           return False
    if name == "merah"  and 8 < hue < 165:       return False
    if name == "oranye" and (hue<=6 or hue>=22): return False
    return True

def get_avg_hsv(frame, x, y, w, h):
    roi = frame[y:y+h, x:x+w]
    return cv2.cvtColor(roi, cv2.COLOR_BGR2HSV).mean(axis=(0,1))

def hue_distance(h1, h2):
    diff = abs(int(h1) - int(h2))
    return min(diff, 180 - diff)

def is_near_target_color(hsv_frame):
    hue_ch = hsv_frame[:,:,0]
    sat_ch = hsv_frame[:,:,1]
    sat_mask = sat_ch > 50
    if not np.any(sat_mask):
        return False, None
    hues = hue_ch[sat_mask]
    for name, centers in COLOR_HUE_CENTER.items():
        for center in centers:
            near = np.array([hue_distance(h, center) < HUE_PROXIMITY_THRESH for h in hues])
            if near.sum() / len(hues) > 0.08:
                return True, name
    return False, None

def adjust_brightness(frame, value):
    if value == 0:
        return frame
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV).astype(np.int32)
    hsv[:,:,2] = np.clip(hsv[:,:,2] + value, 0, 255)
    return cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)

def setup_trackbars(win, lower, upper):
    cv2.createTrackbar('HMin', win, int(lower[0]), 179, nothing)
    cv2.createTrackbar('SMin', win, int(lower[1]), 255, nothing)
    cv2.createTrackbar('VMin', win, int(lower[2]), 255, nothing)
    cv2.createTrackbar('HMax', win, int(upper[0]), 179, nothing)
    cv2.createTrackbar('SMax', win, int(upper[1]), 255, nothing)
    cv2.createTrackbar('VMax', win, int(upper[2]), 255, nothing)

def get_trackbar_vals(win):
    lo = np.array([cv2.getTrackbarPos('HMin', win),
                   cv2.getTrackbarPos('SMin', win),
                   cv2.getTrackbarPos('VMin', win)])
    hi = np.array([cv2.getTrackbarPos('HMax', win),
                   cv2.getTrackbarPos('SMax', win),
                   cv2.getTrackbarPos('VMax', win)])
    return lo, hi

cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

if TUNE_COLOR:
    win = f'TUNING: {TUNE_COLOR}'
    cv2.namedWindow(win)
    first_range = colors[TUNE_COLOR]["ranges"][0]
    setup_trackbars(win, first_range[0], first_range[1])
    print(f'MODE TUNING: {TUNE_COLOR} | Tekan Q keluar')
    prev_lo = prev_hi = None
else:
    print('MODE DETEKSI — merah, oranye, pink, ungu | Tekan Q keluar')

while True:
    ret, frame = cap.read()
    if not ret:
        break

    if current_brightness < target_brightness:
        current_brightness = min(current_brightness + 5, target_brightness)
    elif current_brightness > target_brightness:
        current_brightness = max(current_brightness - 5, target_brightness)

    frame = adjust_brightness(frame, current_brightness)
    hsv   = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

    if TUNE_COLOR:
        lo, hi = get_trackbar_vals(win)
        mask   = cv2.inRange(hsv, lo, hi)
        output = cv2.bitwise_and(frame, frame, mask=mask)
        if prev_lo is None or not (np.array_equal(lo, prev_lo) and np.array_equal(hi, prev_hi)):
            print(f'(np.array([{lo[0]},{lo[1]},{lo[2]}]), np.array([{hi[0]},{hi[1]},{hi[2]}]))')
            prev_lo, prev_hi = lo.copy(), hi.copy()
        fh, fw = frame.shape[:2]
        roi_c  = hsv[fh//2-30:fh//2+30, fw//2-30:fw//2+30]
        avg    = roi_c.mean(axis=(0,1))
        cv2.rectangle(output, (fw//2-30,fh//2-30), (fw//2+30,fh//2+30), (255,255,255), 1)
        cv2.putText(output, f'Center H:{avg[0]:.0f} S:{avg[1]:.0f} V:{avg[2]:.0f}',
                    (10,30), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255,255,255), 2)
        cv2.putText(output, f'Range: ({lo[0]},{lo[1]},{lo[2]}) - ({hi[0]},{hi[1]},{hi[2]})',
                    (10,55), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,255,255), 1)
        cv2.imshow(win, output)

    else:
        near, near_name = is_near_target_color(hsv)
        target_brightness = BRIGHTNESS_REDUCED if near else BRIGHTNESS_NORMAL

        detected_this_frame = set()
        detections = []

        for name, profile in colors.items():
            mask = build_mask(hsv, profile["ranges"])
            kernel = np.ones((5,5), np.uint8)
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for cnt in contours:
                area = cv2.contourArea(cnt)
                if area < MIN_AREA:
                    continue
                bx, by, bw, bh = cv2.boundingRect(cnt)
                avg = get_avg_hsv(frame, bx, by, bw, bh)
                hue, sat, val = avg[0], avg[1], avg[2]
                if not validate(name, hue, sat, val):
                    continue
                if not disambiguate(name, hue, sat, val):
                    continue
                detected_this_frame.add(name)
                detections.append({
                    "name": name, "profile": profile,
                    "bx": bx, "by": by, "bw": bw, "bh": bh,
                    "area": area, "hue": hue, "sat": sat, "val": val
                })

        for name in colors:
            if name in detected_this_frame:
                counters[name] = min(counters[name] + 1, CONFIRM_FRAMES)
            else:
                counters[name] = max(counters[name] - 1, 0)
            was = confirmed[name]
            confirmed[name] = counters[name] >= CONFIRM_FRAMES
            if confirmed[name] and not was:
                print(f'[CONFIRMED] {name.upper()} terdeteksi!')
            elif not confirmed[name] and was:
                print(f'[LOST] {name.upper()} hilang')

        for d in detections:
            name    = d["name"]
            profile = d["profile"]
            bx, by, bw, bh = d["bx"], d["by"], d["bw"], d["bh"]
            cx, cy   = bx + bw//2, by + bh//2
            offset_x = cx - frame.shape[1]//2
            offset_y = cy - frame.shape[0]//2
            is_confirmed = confirmed[name]
            color     = profile["bgr"]
            thickness = 3 if is_confirmed else 1
            label     = f'[OK] {name}' if is_confirmed else f'[..] {name} {counters[name]}/{CONFIRM_FRAMES}'
            cv2.rectangle(frame, (bx,by), (bx+bw,by+bh), color, thickness)
            cv2.circle(frame, (cx,cy), 5, color, -1)
            cv2.putText(frame, label, (bx, by-25),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.65, color, 2)
            cv2.putText(frame, f'H:{d["hue"]:.0f} S:{d["sat"]:.0f} V:{d["val"]:.0f}', (bx, by-8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.42, color, 1)
            if is_confirmed:
                print(f'[CONFIRMED] {name.upper()} | center:({cx},{cy}) | offset:({offset_x},{offset_y}) | H:{d["hue"]:.0f} S:{d["sat"]:.0f} V:{d["val"]:.0f}')

        y_hud = 25
        for name in colors:
            c      = (0,255,0) if confirmed[name] else (100,100,255)
            status = "CONFIRMED" if confirmed[name] else f"{counters[name]}/{CONFIRM_FRAMES}"
            cv2.putText(frame, f'{name}: {status}', (10, y_hud),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, c, 1)
            y_hud += 20

        bright_color = (0,200,255) if current_brightness < 0 else (200,200,200)
        cv2.putText(frame, f'Brightness: {current_brightness}', (10, y_hud+5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, bright_color, 1)
        if near:
            cv2.putText(frame, f'NEAR: {near_name} -> dimming', (10, y_hud+25),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,200,255), 1)

        fh, fw = frame.shape[:2]
        cv2.line(frame, (fw//2-20,fh//2), (fw//2+20,fh//2), (255,255,255), 1)
        cv2.line(frame, (fw//2,fh//2-20), (fw//2,fh//2+20), (255,255,255), 1)
        cv2.imshow('Color Detection', frame)

    if cv2.waitKey(33) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()