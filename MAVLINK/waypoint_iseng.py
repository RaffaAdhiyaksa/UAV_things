from pymavlink import mavutil
import time

# ==========================================================
# 1. INISIALISASI KONEKSI UDP KE SITL
# ==========================================================
print("Menghubungkan ke SITL via UDP...")
master = mavutil.mavlink_connection('udp:127.0.0.1:14551')
master.wait_heartbeat()
print("SITL Terhubung!")

print("Menunggu GPS lock di Iran (Bisa agak lama, sabar ya bos)...")
while True:
    msg = master.recv_match(type='GLOBAL_POSITION_INT', blocking=True)
    if msg:
        home_lat = msg.lat 
        home_lon = msg.lon 
        break
print(f"GPS Terkunci! Posisi saat ini: Lat {home_lat/1e7}, Lon {home_lon/1e7}")

# ==========================================================
# 2. UPLOAD RUTE KE ISRAEL
# ==========================================================
# Koordinat Tel Aviv, Israel (Latitude: 32.0853, Longitude: 34.7818)
target_lat = int(32.0853 * 1e7)
target_lon = int(34.7818 * 1e7)
target_alt = 500 # Terbang tinggi di 500 meter 

waypoints = [
    # Waypoint 0 (Home / Titik Awal)
    {'cmd': mavutil.mavlink.MAV_CMD_NAV_WAYPOINT, 'x': home_lat, 'y': home_lon, 'z': 0},
    # Waypoint 1 (Takeoff tegak lurus dulu)
    {'cmd': mavutil.mavlink.MAV_CMD_NAV_TAKEOFF, 'x': home_lat, 'y': home_lon, 'z': target_alt},
    # Waypoint 2 (Terbang Lurus ke koordinat Israel)
    {'cmd': mavutil.mavlink.MAV_CMD_NAV_WAYPOINT, 'x': target_lat, 'y': target_lon, 'z': target_alt},
]

print("Mengupload target kordinat Israel...")
master.mav.mission_count_send(master.target_system, master.target_component, len(waypoints))

for i in range(len(waypoints)):
    msg = master.recv_match(type=['MISSION_REQUEST_INT', 'MISSION_REQUEST'], blocking=True, timeout=5)
    if not msg:
        print("Gagal dapat request dari SITL! Coba restart SITL-nya.")
        exit()
    
    seq = msg.seq
    wp = waypoints[seq]
    
    master.mav.mission_item_int_send(
        master.target_system, master.target_component, seq,                                               
        mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT, 
        wp['cmd'], 0, 1, 0, 0, 0, 0,                                       
        wp['x'], wp['y'], wp['z']                          
    )
    print(f" -> Titik rute {seq} terkirim!")

ack = master.recv_match(type='MISSION_ACK', blocking=True, timeout=5)
print("Upload Rute Selesai!")

# ==========================================================
# 3. TAKEOFF & AUTO MODE
# ==========================================================
print("\n--- MULAI MISI JARAK JAUH ---")
print("Ganti mode ke GUIDED...")
master.mav.set_mode_send(master.target_system, mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED, master.mode_mapping()['GUIDED'])
time.sleep(2) # Kasih napas bentar ke sistem

print("Arming motor, awas baling-baling...")
master.mav.command_long_send(master.target_system, master.target_component,
                             mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM, 0, 1, 0, 0, 0, 0, 0, 0)
master.motors_armed_wait()
print("Drone ARMED!")

print(f"Takeoff ke {target_alt} meter...")
master.mav.command_long_send(master.target_system, master.target_component,
                             mavutil.mavlink.MAV_CMD_NAV_TAKEOFF, 0, 0, 0, 0, 0, 0, 0, target_alt)

print("Nunggu nyampe ketinggian target...")
while True:
    msg = master.recv_match(type='GLOBAL_POSITION_INT', blocking=True)
    if msg:
        alt = msg.relative_alt / 1000.0 
        print(f"  -> Ketinggian sekarang: {alt:.1f} m", end='\r') 
        if alt >= (target_alt * 0.95): 
            print("\nUdah di atas! Siap meluncur.")
            break
    time.sleep(0.1)

# Ganti kecepatan biar makin ngebut (Kecepatan di-set ke 50 m/s)
print("Mengaktifkan mode NOS! Kecepatan di-set ke 50 m/s...")
master.mav.command_long_send(
    master.target_system, master.target_component,
    mavutil.mavlink.MAV_CMD_DO_CHANGE_SPEED, 0, 1, 50, -1, 0, 0, 0, 0
)
time.sleep(1)

print("Ganti mode ke AUTO. Drone sedang meluncur melintasi Timur Tengah!")
master.set_mode('AUTO')

print("\n=== BUKA MISSION PLANNER SEKARANG! ===")
print("Liat garis kuningnya, dronenya lagi ngacir ke target!")