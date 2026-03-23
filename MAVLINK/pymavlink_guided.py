from pymavlink import mavutil
import time
import math

# ==========================================================
# 1. KONEKSI UDP KE SITL
# ==========================================================
print("Menghubungkan ke SITL via UDP...")
master = mavutil.mavlink_connection('udp:127.0.0.1:14551')
master.wait_heartbeat()
print("SITL Terhubung!")

# Fungsi untuk mengirim target posisi lokal (NED)
def goto_position_target_local_ned(north, east, down):
    msg = master.mav.set_position_target_local_ned_encode(
        0, master.target_system, master.target_component,
        mavutil.mavlink.MAV_FRAME_LOCAL_NED, 
        0b0000111111111000, 
        north, east, down,  
        0, 0, 0, 0, 0, 0, 0, 0)
    master.mav.send(msg)

# ==========================================================
# 2. EKSEKUSI TERBANG (TAKEOFF)
# ==========================================================
print("\n--- MULAI PROSES TERBANG ---")
print("Ganti mode ke GUIDED...")
master.mav.set_mode_send(master.target_system, mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED, master.mode_mapping()['GUIDED'])
time.sleep(1)

print("Arming motor, awas baling-baling...")
master.mav.command_long_send(master.target_system, master.target_component,
                             mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM, 0, 1, 0, 0, 0, 0, 0, 0)
master.motors_armed_wait()
print("Drone ARMED!")

target_alt = 15
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
            print("\nUdah di atas! Ketinggian pas.")
            break
    time.sleep(0.1)

# ==========================================================
# 3. MANUVER BINTANG LEBIH EFISIEN (PRE-KALKULASI)
# ==========================================================
radius_m = 20
waktu_tunggu = 10 
print("\nMemulai manuver Bintang secara Real-Time...")

# Menghitung semua titik di awal (List Comprehension)
# Lompat 144 derajat tiap titik. range(6) buat 5 titik + 1 balik ke awal biar tertutup rapat.
# Ditambah offset 90 derajat biar ujung lancip bintang menghadap persis ke Utara.
titik_bintang = [
    (radius_m * math.sin(math.radians(90 + ((i % 5) * 144))), 
     radius_m * math.cos(math.radians(90 + ((i % 5) * 144)))) 
    for i in range(6) 
]

# Eksekusi pergerakan
for i, (north, east) in enumerate(titik_bintang):
    print(f" -> Gerak ke Titik {i+1}: Utara {north:.1f}m, Timur {east:.1f}m")
    goto_position_target_local_ned(north, east, -target_alt)
    time.sleep(waktu_tunggu)

print("\nPola Bintang selesai digambar!")

# ==========================================================
# 4. LANDING
# ==========================================================
print("Balik ke titik tengah (Home)...")
goto_position_target_local_ned(0, 0, -target_alt)
time.sleep(8)

print("Misi Selesai! Ganti mode ke LAND...")
master.mav.set_mode_send(master.target_system, master.target_component, mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED, master.mode_mapping()['LAND'])
print("Drone mendarat otomatis. Kerja bagus!")