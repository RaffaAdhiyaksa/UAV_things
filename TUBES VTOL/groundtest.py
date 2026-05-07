import cv2
import cv2.aruco as aruco
import numpy as np
from pymavlink import mavutil
import time
import threading

# =============================================================================
# KONFIGURASI
# =============================================================================
SERIAL_PORT  = '/dev/ttyACM0'
BAUD_RATE    = 115200

SERVO_CHANNEL   = 7      # channel servo drop (sesuaikan di MP)
SERVO_OPEN_PWM  = 1900   # PWM saat servo buka
SERVO_CLOSE_PWM = 1100   # PWM saat servo tutup

FRAME_W, FRAME_H = 640, 480
CENTER_THRESH    = 40
MIN_AREA         = 800

ARUCO_TO_COLOR = {0: "merah", 1: "ungu", 2: "pink"}

COLORS = {
    "merah": {
        "lower": [np.array([0, 100, 100]), np.array([160, 100, 100])],
        "upper": [np.array([10, 255, 255]), np.array([180, 255, 255])],
        "bgr": (0, 0, 255)
    },
    "ungu": {
        "lower": [np.array([125, 120, 60])],
        "upper": [np.array([145, 255, 255])],
        "bgr": (255, 0, 100)
    },
    "pink": {
        "lower": [np.array([148, 80, 180])],
        "upper": [np.array([165, 255, 255])],
        "bgr": (180, 0, 255)
    },
    "orange": {
        "lower": [np.array([10, 100, 100])],
        "upper": [np.array([25, 255, 255])],
        "bgr": (0, 165, 255)
    }
}

# =============================================================================
# GLOBALS
# =============================================================================
lock         = threading.Lock()
g_running    = True
g_state      = "INIT"         # INIT → SCAN_ARUCO → SCAN_COLOR → DONE
g_aruco_id   = None
g_target_color = None
g_detection  = None

# =============================================================================
# MAVLINK UTILS
# =============================================================================
def mavlink_connect():
    print(f"[MAV] Connecting {SERIAL_PORT} @ {BAUD_RATE}...")
    mav = mavutil.mavlink_connection(SERIAL_PORT, baud=BAUD_RATE)
    mav.wait_heartbeat()
    print(f"[MAV] Heartbeat! sys={mav.target_system} comp={mav.target_component}")
    return mav

def disable_all_checks(mav):
    """Disable semua pre-arm check via MAVLink param"""
    params = {
        'ARMING_CHECK': 0,
        'FS_GCS_ENABLE': 0,
        'FS_THR_ENABLE': 0,
        'GPS_TYPE': 0,
    }
    for name, val in params.items():
        mav.mav.param_set_send(
            mav.target_system, mav.target_component,
            name.encode('utf-8'),
            float(val),
            mavutil.mavlink.MAV_PARAM_TYPE_REAL32
        )
        print(f"[MAV] PARAM SET: {name} = {val}")
        time.sleep(0.3)

def force_arm(mav):
    """Force arm pakai magic number, bypass semua"""
    print("[MAV] Force ARM...")
    mav.mav.command_long_send(
        mav.target_system, mav.target_component,
        mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
        0,
        1,       # arm
        21196,   # magic bypass
        0, 0, 0, 0, 0
    )
    t0 = time.time()
    while time.time() - t0 < 10:
        msg = mav.recv_match(type='HEARTBEAT', blocking=True, timeout=1)
        if msg and (msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED):
            print("[MAV] ARMED!")
            return True
    print("[MAV] ARM timeout!")
    return False

def disarm(mav):
    print("[MAV] Disarming...")
    mav.mav.command_long_send(
        mav.target_system, mav.target_component,
        mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
        0, 0, 0, 0, 0, 0, 0, 0
    )

def set_servo(mav, channel, pwm):
    """Kirim perintah servo via DO_SET_SERVO"""
    print(f"[SERVO] CH{channel} = {pwm} PWM")
    mav.mav.command_long_send(
        mav.target_system, mav.target_component,
        mavutil.mavlink.MAV_CMD_DO_SET_SERVO,
        0,
        float(channel),
        float(pwm),
        0, 0, 0, 0, 0
    )

# =============================================================================
# VISION
# =============================================================================
aruco_dict     = aruco.getPredefinedDictionary(aruco.DICT_4X4_50)
aruco_params   = aruco.DetectorParameters()
aruco_detector = aruco.ArucoDetector(aruco_dict, aruco_params)

def detect_aruco(frame):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    corners, ids, _ = aruco_detector.detectMarkers(gray)
    if ids is not None:
        aruco.drawDetectedMarkers(frame, corners, ids)
        for i, mid in enumerate(ids.flatten()):
            if mid in ARUCO_TO_COLOR:
                c = corners[i][0]
                cx = int(c[:, 0].mean())
                cy = int(c[:, 1].mean())
                return mid, (cx, cy), frame
    return None, None, frame

def detect_color(frame, color_name):
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    profile = COLORS[color_name]
    mask = np.zeros(hsv.shape[:2], dtype=np.uint8)
    for lo, hi in zip(profile["lower"], profile["upper"]):
        mask = cv2.bitwise_or(mask, cv2.inRange(hsv, lo, hi))
    kernel = np.ones((5, 5), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None, frame
    largest = max(contours, key=cv2.contourArea)
    area = cv2.contourArea(largest)
    if area < MIN_AREA:
        return None, frame
    x, y, w, h = cv2.boundingRect(largest)
    cx, cy = x + w // 2, y + h // 2
    bgr = profile["bgr"]
    cv2.rectangle(frame, (x, y), (x + w, y + h), bgr, 2)
    cv2.putText(frame, f"{color_name.upper()} area={int(area)}", (x, y - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, bgr, 2)
    cv2.circle(frame, (cx, cy), 6, bgr, -1)
    return (cx, cy, area), frame

def vision_thread():
    global g_running, g_state, g_aruco_id, g_target_color, g_detection

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        # coba index 1 kalau 0 gagal
        cap = cv2.VideoCapture(1)
    if not cap.isOpened():
        print("[VISION] ERROR: Kamera tidak terbuka! Cek /dev/video0")
        g_running = False
        return

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_W)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_H)
    print("[VISION] Kamera OK.")

    while g_running:
        ret, frame = cap.read()
        if not ret:
            time.sleep(0.01)
            continue

        det = None
        state_now = g_state

        if state_now == "SCAN_ARUCO":
            ar_id, pos, frame = detect_aruco(frame)
            if ar_id is not None:
                color = ARUCO_TO_COLOR[ar_id]
                with lock:
                    g_aruco_id     = ar_id
                    g_target_color = color
                det = ("aruco", ar_id, pos[0], pos[1])
                print(f"[VISION] ArUco ID={ar_id} -> Target warna: {color}")

        elif state_now == "SCAN_COLOR":
            with lock:
                tc = g_target_color
            if tc:
                res, frame = detect_color(frame, tc)
                if res:
                    cx, cy, area = res
                    det = ("color", tc, cx, cy, area)

        with lock:
            g_detection = det

        # overlay state di frame
        cv2.putText(frame, f"STATE: {state_now}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        cv2.line(frame, (FRAME_W//2-25, FRAME_H//2), (FRAME_W//2+25, FRAME_H//2), (200,200,200), 1)
        cv2.line(frame, (FRAME_W//2, FRAME_H//2-25), (FRAME_W//2, FRAME_H//2+25), (200,200,200), 1)

        # save frame ke file biar bisa dicek dari laptop via scp
        cv2.imwrite("/tmp/gt_frame.jpg", frame)

        time.sleep(0.033)

    cap.release()
    print("[VISION] Thread selesai.")

# =============================================================================
# MAIN GROUND TEST
# =============================================================================
def main():
    global g_state, g_running

    print("=" * 50)
    print("  GROUND TEST MODE — NO PROP REQUIRED")
    print("=" * 50)

    # 1. Connect MAVLink
    mav = mavlink_connect()

    # 2. Disable semua safety check via param
    print("\n[GT] Disabling pre-arm checks...")
    disable_all_checks(mav)
    time.sleep(1)

    # 3. Start vision thread
    print("[GT] Starting camera thread...")
    vt = threading.Thread(target=vision_thread, daemon=True)
    vt.start()
    time.sleep(1.5)

    if not g_running:
        print("[GT] Kamera gagal, abort.")
        return

    # 4. Servo ke posisi tutup dulu
    set_servo(mav, SERVO_CHANNEL, SERVO_CLOSE_PWM)
    time.sleep(0.5)

    # 5. ARM
    if not force_arm(mav):
        print("[GT] Gagal ARM, cek koneksi Pixhawk.")
        g_running = False
        vt.join(timeout=2)
        return

    try:
        # =====================================================================
        # SCAN ARUCO
        # =====================================================================
        g_state = "SCAN_ARUCO"
        print("\n[GT] === SCAN ARUCO — tunjukin marker ke kamera ===")
        aruco_timeout = time.time() + 30  # 30 detik nunggu aruco

        while g_running and g_state == "SCAN_ARUCO":
            if time.time() > aruco_timeout:
                print("[GT] ArUco timeout 30s, skip ke SCAN_COLOR manual")
                with lock:
                    g_target_color = "merah"  # default fallback
                g_state = "SCAN_COLOR"
                break

            with lock:
                found_id = g_aruco_id
                target   = g_target_color

            if found_id is not None:
                print(f"[GT] ArUco ID={found_id} terdeteksi! Target: {target}")
                time.sleep(0.5)
                g_state = "SCAN_COLOR"
                break

            time.sleep(0.1)

        # =====================================================================
        # SCAN COLOR + SERVO TEST
        # =====================================================================
        print(f"\n[GT] === SCAN COLOR ({g_target_color}) — tunjukin warna ke kamera ===")
        centered_cnt  = 0
        servo_opened  = False
        color_timeout = time.time() + 30  # 30 detik nunggu warna

        while g_running and g_state == "SCAN_COLOR":
            if time.time() > color_timeout:
                print("[GT] Color timeout 30s.")
                break

            with lock:
                det = g_detection

            if det is None:
                centered_cnt = 0
                time.sleep(0.1)
                continue

            _, color_name, cx, cy, area = det
            off_x = cx - FRAME_W // 2
            off_y = cy - FRAME_H // 2
            dist  = (off_x**2 + off_y**2) ** 0.5

            print(f"[GT] {color_name.upper()} terdeteksi | cx={cx} cy={cy} dist={dist:.0f} area={int(area)}")

            if dist < CENTER_THRESH:
                centered_cnt += 1
                print(f"[GT] Centered {centered_cnt}/3")
            else:
                centered_cnt = 0

            if centered_cnt >= 3 and not servo_opened:
                print("[GT] TARGET LOCK! Buka servo...")
                set_servo(mav, SERVO_CHANNEL, SERVO_OPEN_PWM)
                servo_opened = True
                print("[GT] Servo BUKA. Tunggu 3 detik...")
                time.sleep(3)
                print("[GT] Tutup servo...")
                set_servo(mav, SERVO_CHANNEL, SERVO_CLOSE_PWM)
                print("[GT] Servo TUTUP.")
                g_state = "DONE"
                break

            time.sleep(0.1)

        # =====================================================================
        # DONE
        # =====================================================================
        print("\n" + "=" * 50)
        if g_state == "DONE":
            print("  GROUND TEST SELESAI — SEMUA OK!")
        else:
            print("  GROUND TEST SELESAI — timeout/interrupt")
        print("=" * 50)

    except KeyboardInterrupt:
        print("\n[GT] Manual interrupt (Ctrl+C)")

    finally:
        g_running = False
        print("[GT] Disarming...")
        disarm(mav)
        vt.join(timeout=3)
        print("[GT] Program selesai.")

if __name__ == "__main__":
    main()