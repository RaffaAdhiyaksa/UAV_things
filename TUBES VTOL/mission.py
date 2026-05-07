import cv2
import cv2.aruco as aruco
import numpy as np
from pymavlink import mavutil
import time
import threading

# =============================================================================
# KONFIGURASI
# =============================================================================
SERIAL_PORT   = '/dev/ttyACM0'          # USB ke CubeBlack
BAUD_RATE     = 115200                   # baud CubeBlack default
TAKEOFF_ALT   = 2.0
SCAN_ALT      = 3.5
DROP_ALT      = 1.5
TRANSIT_ALT   = 2.5
LAND_DETECT_ALT = 0.5

KP_XY         = 0.003
CENTER_THRESH = 35
MIN_AREA      = 800
CLIMB_VZ      = -0.6   # m/s (negatif = naik di NED)
DESCEND_VZ    = 0.4    # m/s (positif = turun di NED)

SITL_MODE     = False  # REAL HARDWARE
HEADLESS      = True   # True = no display (SSH), False = ada monitor/X11

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

FRAME_W, FRAME_H = 640, 480

# =============================================================================
# GLOBALS
# =============================================================================
lock = threading.Lock()
g_target_color = None
g_aruco_id     = None
g_detection    = None
g_altitude     = 0.0
g_running      = True
g_state        = "INIT"

# =============================================================================
# MAVLINK
# =============================================================================
def mavlink_connect():
    print(f"[MAV] Connecting to {SERIAL_PORT} baud={BAUD_RATE}...")
    mav = mavutil.mavlink_connection(SERIAL_PORT, baud=BAUD_RATE)
    mav.wait_heartbeat()
    print(f"[MAV] Heartbeat OK! sys={mav.target_system} comp={mav.target_component}")
    return mav

def set_mode(mav, mode_name):
    if mode_name not in mav.mode_mapping():
        print(f"[MAV] Mode {mode_name} tidak tersedia!")
        return
    mode_id = mav.mode_mapping()[mode_name]
    mav.mav.set_mode_send(
        mav.target_system,
        mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
        mode_id
    )
    print(f"[MAV] Mode -> {mode_name}")
    time.sleep(1)

def arm(mav):
    print("[MAV] Arming...")
    mav.mav.command_long_send(
        mav.target_system, mav.target_component,
        mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
        0, 1, 21196, 0, 0, 0, 0, 0
    )
    t0 = time.time()
    while time.time() - t0 < 10:
        msg = mav.recv_match(type='HEARTBEAT', blocking=True, timeout=1)
        if msg and (msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED):
            print("[MAV] ARMED!")
            return True
    print("[MAV] ARM timeout!")
    return False

def takeoff(mav, alt):
    print(f"[MAV] Takeoff -> {alt}m")
    mav.mav.command_long_send(
        mav.target_system, mav.target_component,
        mavutil.mavlink.MAV_CMD_NAV_TAKEOFF,
        0, 0, 0, 0, 0, 0, 0, alt
    )

def send_velocity(mav, vx, vy, vz=0):
    mav.mav.set_position_target_local_ned_send(
        0, mav.target_system, mav.target_component,
        mavutil.mavlink.MAV_FRAME_BODY_NED,
        0b0000111111000111,
        0, 0, 0, vx, vy, vz, 0, 0, 0, 0, 0
    )

def get_altitude(mav):
    msg = mav.recv_match(type='GLOBAL_POSITION_INT', blocking=False)
    if msg:
        return msg.relative_alt / 1000.0
    return None

def wait_alt(mav, target, timeout=20, tol=0.3):
    print(f"[MAV] Wait alt {target}m...")
    t0 = time.time()
    while time.time() - t0 < timeout:
        alt = get_altitude(mav)
        if alt is not None and abs(alt - target) < tol:
            print(f"[MAV] Alt reached: {alt:.1f}m")
            return True
        time.sleep(0.2)
    print("[MAV] Alt timeout!")
    return False

def land(mav):
    print("[MAV] Landing...")
    set_mode(mav, 'LAND')

# =============================================================================
# TIME-BASED CLIMB/DESCEND
# =============================================================================
def move_vertical(mav, duration_sec, vz):
    print(f"[MAV] Vertical move: {vz} m/s for {duration_sec}s")
    t0 = time.time()
    while time.time() - t0 < duration_sec and g_running:
        if check_takeover(mav):
            send_velocity(mav, 0, 0, 0)
            return False
        send_velocity(mav, 0, 0, vz)
        time.sleep(0.1)
    send_velocity(mav, 0, 0, 0)
    return True

def check_takeover(mav):
    msg = mav.recv_match(type='HEARTBEAT', blocking=False)
    if msg:
        try:
            current_mode = mavutil.mode_string_v10(msg)
            if current_mode not in ['GUIDED', 'LAND']:
                print(f"[SAFETY] Mode={current_mode} | System takeover! Hovering...")
                return True
        except:
            pass
    return False

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
        flat = ids.flatten()
        for i, mid in enumerate(flat):
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
    cv2.putText(frame, color_name.upper(), (x, y - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, bgr, 2)
    cv2.circle(frame, (cx, cy), 5, bgr, -1)
    return (cx, cy, area), frame

def vision_camera():
    global g_detection, g_aruco_id, g_target_color, g_running, g_state
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("[VISION] Kamera tidak terbuka! Cek /dev/video0")
        g_running = False
        return
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_W)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_H)
    print("[VISION] Kamera aktif.")

    while g_running:
        ret, frame = cap.read()
        if not ret:
            time.sleep(0.01)
            continue

        det = None

        if g_state == "SCAN_ARUCO":
            ar_id, pos, frame = detect_aruco(frame)
            if ar_id is not None:
                with lock:
                    g_aruco_id = ar_id
                    g_target_color = ARUCO_TO_COLOR[ar_id]
                print(f"[VISION] ArUco ID={ar_id} -> Target: {g_target_color}")
                det = ("aruco", f"id_{ar_id}", pos[0], pos[1], 0)

        elif g_state == "SCAN_COLOR" and g_target_color is not None:
            res, frame = detect_color(frame, g_target_color)
            if res:
                cx, cy, area = res
                det = ("color", g_target_color, cx, cy, area)
                print(f"[VISION] Color lock: {g_target_color} cx={cx} cy={cy} area={area}")

        elif g_state == "SCAN_LAND":
            res, frame = detect_color(frame, "orange")
            if res:
                cx, cy, area = res
                det = ("color", "orange", cx, cy, area)
                print(f"[VISION] Landing lock: orange cx={cx} cy={cy}")

        with lock:
            g_detection = det

        if not HEADLESS:
            cv2.putText(frame, f"STATE: {g_state}", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            cv2.putText(frame, f"ALT: {g_altitude:.1f}m", (10, FRAME_H - 15),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
            cv2.line(frame, (FRAME_W//2-20, FRAME_H//2), (FRAME_W//2+20, FRAME_H//2), (200,200,200), 1)
            cv2.line(frame, (FRAME_W//2, FRAME_H//2-20), (FRAME_W//2, FRAME_H//2+20), (200,200,200), 1)
            cv2.imshow("GCS Monitor", frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                g_running = False
        else:
            time.sleep(0.033)  # ~30fps tanpa display

    cap.release()
    if not HEADLESS:
        cv2.destroyAllWindows()
    print("[VISION] Thread selesai.")

# =============================================================================
# MAIN
# =============================================================================
def main():
    global g_state, g_altitude, g_running, g_detection, g_target_color, g_aruco_id

    mav = mavlink_connect()

    vt = threading.Thread(target=vision_camera, daemon=True)
    vt.start()
    time.sleep(1)

    centered_cnt = 0

    try:
        while g_running:
            alt = get_altitude(mav)
            if alt is not None:
                g_altitude = alt

            if check_takeover(mav):
                send_velocity(mav, 0, 0, 0)
                time.sleep(0.5)
                continue

            # =================================================================
            # INIT
            # =================================================================
            if g_state == "INIT":
                set_mode(mav, 'GUIDED')
                if arm(mav):
                    takeoff(mav, TAKEOFF_ALT)
                    wait_alt(mav, TAKEOFF_ALT)
                    with lock:
                        g_aruco_id  = None
                        g_detection = None
                    g_state = "SCAN_ARUCO"
                    print("[STATE] === SCAN_ARUCO ===")
                else:
                    time.sleep(2)

            # =================================================================
            # SCAN_ARUCO
            # =================================================================
            elif g_state == "SCAN_ARUCO":
                send_velocity(mav, 0.5, 0, 0)
                with lock:
                    found_id = g_aruco_id
                if found_id is not None:
                    send_velocity(mav, 0, 0, 0)
                    print(f"[STATE] ArUco ID={found_id}! Naik ke {SCAN_ALT}m...")
                    move_vertical(mav, 3.0, CLIMB_VZ)
                    with lock:
                        g_detection = None
                    g_state = "SCAN_COLOR"
                    centered_cnt = 0
                    print("[STATE] === SCAN_COLOR ===")

            # =================================================================
            # SCAN_COLOR
            # =================================================================
            elif g_state == "SCAN_COLOR":
                with lock:
                    det = g_detection
                if det is None:
                    send_velocity(mav, 0.3, 0, 0)
                    centered_cnt = 0
                else:
                    _, name, cx, cy, area = det
                    off_x = cx - FRAME_W // 2
                    off_y = cy - FRAME_H // 2
                    dist  = (off_x**2 + off_y**2) ** 0.5
                    vx = off_y * KP_XY
                    vy = off_x * KP_XY
                    if dist < CENTER_THRESH:
                        centered_cnt += 1
                        send_velocity(mav, 0, 0, 0)
                        print(f"[STATE] Centered {centered_cnt}/3 | dist={dist:.1f}")
                    else:
                        centered_cnt = 0
                        send_velocity(mav, vx, vy, 0)
                    if centered_cnt >= 3:
                        print(f"[STATE] Centered! Turun ke {DROP_ALT}m...")
                        move_vertical(mav, 5.0, DESCEND_VZ)
                        print(">>> DROP EXECUTED! <<<")
                        time.sleep(1)
                        print(f"[STATE] Naik ke {TRANSIT_ALT}m...")
                        move_vertical(mav, 2.0, CLIMB_VZ)
                        with lock:
                            g_detection = None
                        g_state = "SCAN_LAND"
                        centered_cnt = 0
                        print("[STATE] === SCAN_LAND ===")

            # =================================================================
            # SCAN_LAND
            # =================================================================
            elif g_state == "SCAN_LAND":
                with lock:
                    det = g_detection
                if det is None:
                    send_velocity(mav, 0.4, 0, 0)
                    centered_cnt = 0
                else:
                    _, name, cx, cy, area = det
                    off_x = cx - FRAME_W // 2
                    off_y = cy - FRAME_H // 2
                    dist  = (off_x**2 + off_y**2) ** 0.5
                    vx = off_y * KP_XY
                    vy = off_x * KP_XY
                    if dist < CENTER_THRESH:
                        centered_cnt += 1
                        send_velocity(mav, 0, 0, 0)
                        print(f"[STATE] Landing centered {centered_cnt}/3 | dist={dist:.1f}")
                    else:
                        centered_cnt = 0
                        send_velocity(mav, vx, vy, 0)
                    if centered_cnt >= 3:
                        print("[STATE] Landing zone centered! Descent...")
                        move_vertical(mav, 9.0, 0.3)
                        land(mav)
                        g_state = "LANDED"

            # =================================================================
            # LANDED
            # =================================================================
            elif g_state == "LANDED":
                print("=" * 40)
                print("  MISI SELESAI!")
                print("=" * 40)
                g_running = False

            time.sleep(0.05)

    except KeyboardInterrupt:
        print("\n[SYSTEM] Manual interrupt!")
        send_velocity(mav, 0, 0, 0)
        land(mav)
        g_running = False

    vt.join(timeout=2)
    print("[SYSTEM] Program selesai.")

if __name__ == "__main__":
    main()