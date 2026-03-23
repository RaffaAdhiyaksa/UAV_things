from pymavlink import mavutil
import time
import math # Diperlukan untuk perhitungan trigonometri (sin/cos) pada pola sudut

# ==========================================================
# 1. INISIALISASI KONEKSI UDP KE SITL
# ==========================================================
print("Menghubungkan ke SITL via UDP...")
# Menggunakan localhost dan port 14551 sesuai pembagian routing di WSL
master = mavutil.mavlink_connection('udp:127.0.0.1:14551')
master.wait_heartbeat()
print("SITL Terhubung!")

# ==========================================================
# 2. MENDAPATKAN KOORDINAT HOME (TITIK ACUAN)
# ==========================================================
print("Menunggu GPS lock (Bisa agak lama, sabar ya)...")
while True:
    # Membaca pesan GLOBAL_POSITION_INT untuk mendapatkan koordinat awal
    msg = master.recv_match(type='GLOBAL_POSITION_INT', blocking=True)
    if msg:
        home_lat = msg.lat # Koordinat latitude dalam format 1e7
        home_lon = msg.lon # Koordinat longitude dalam format 1e7
        break
print(f"Home terkunci di Lat: {home_lat}, Lon: {home_lon}")

# ==========================================================
# 3. KALKULASI TITIK WAYPOINT (POLA BINTANG / PENTAGRAM)
# ==========================================================
# Konversi meter ke format MAVLink 1e7 (1 meter ~ 89.8 satuan di 1e7)
meter_to_1e7 = 1e7 / 111320.0
radius_m = 20 # Radius jarak bintang sejauh 20 meter dari titik tengah
target_alt = 15 # Ketinggian terbang 15 meter

waypoints = [
    # Sequence 0: Titik Dummy Home (Wajib ada pada protokol ArduPilot)
    {'cmd': mavutil.mavlink.MAV_CMD_NAV_WAYPOINT, 'x': home_lat, 'y': home_lon, 'z': 0},
    # Sequence 1: Perintah Takeoff tegak lurus ke ketinggian target
    {'cmd': mavutil.mavlink.MAV_CMD_NAV_TAKEOFF, 'x': home_lat, 'y': home_lon, 'z': target_alt},
]

# Looping untuk membuat 5 titik sudut Bintang (Pentagram)
for i in range(5):
    # Logika Matematika Bintang: Melompat sejauh 144 derajat tiap iterasi.
    # Dimulai dari offset 90 derajat agar ujung puncak bintang menghadap tepat ke Utara.
    angle_deg = 90 + (i * 144)
    angle_rad = math.radians(angle_deg) # Konversi derajat ke radian
    
    # Menghitung offset X (Longitude/Timur-Barat) dan Y (Latitude/Utara-Selatan)
    # Cosinus untuk sumbu X (Timur), Sinus untuk sumbu Y (Utara)
    dy = radius_m * math.cos(angle_rad) # Offset Longitude
    dx = radius_m * math.sin(angle_rad) # Offset Latitude
    
    # Menerapkan offset ke koordinat home awal
    wp_lat = int(home_lat + (dx * meter_to_1e7))
    wp_lon = int(home_lon + (dy * meter_to_1e7))
    
    # Memasukkan titik yang sudah dihitung ke dalam list waypoint
    waypoints.append({'cmd': mavutil.mavlink.MAV_CMD_NAV_WAYPOINT, 'x': wp_lat, 'y': wp_lon, 'z': target_alt})

# Sequence 7: Mengunci pola dengan mengulangi titik ujung bintang pertama (agar garis menyilang tertutup)
waypoints.append(waypoints[2]) 

# Sequence 8: Perintah RTL (Return To Launch) untuk pendaratan otomatis setelah misi selesai
waypoints.append({'cmd': mavutil.mavlink.MAV_CMD_NAV_RETURN_TO_LAUNCH, 'x': 0, 'y': 0, 'z': 0})

# ==========================================================
# 4. PROTOKOL UPLOAD MISI (MAVLINK HANDSHAKE)
# ==========================================================
print(f"Memulai upload {len(waypoints)} titik misi ke SITL...")
# Mengirim jumlah total waypoint ke sistem drone
master.mav.mission_count_send(master.target_system, master.target_component, len(waypoints))

for i in range(len(waypoints)):
    # Menunggu request dari drone untuk setiap urutan (sequence) waypoint
    msg = master.recv_match(type=['MISSION_REQUEST_INT', 'MISSION_REQUEST'], blocking=True, timeout=5)
    if not msg:
        print("Gagal dapat request dari SITL! Coba jalanin ulang scriptnya.")
        exit()
    
    seq = msg.seq
    wp = waypoints[seq]
    
    # Mengirim detail koordinat untuk sequence yang direquest
    master.mav.mission_item_int_send(
        master.target_system, master.target_component,
        seq,                                               
        mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT, # Menggunakan frame altitude relatif terhadap daratan
        wp['cmd'],                                         
        0, 1, # Current (0) & Autocontinue (1)                                             
        0, 0, 0, 0, # Parameter 1-4 tidak digunakan untuk waypoint standar                                       
        wp['x'], wp['y'], wp['z']                          
    )
    print(f" -> Titik {seq} berhasil dikirim!")

# Menunggu konfirmasi bahwa seluruh rute berhasil diterima oleh sistem (ACK 0)
ack = master.recv_match(type='MISSION_ACK', blocking=True, timeout=5)
print(f"Upload selesai! Status ACK: {ack.type if ack else 'No ACK'}")

# ==========================================================
# 5. EKSEKUSI PENERBANGAN OTOMATIS
# ==========================================================
print("\n--- MULAI PROSES TERBANG ---")

# Mengubah mode ke GUIDED sebagai syarat sebelum Arming di ArduPilot
print("Ganti mode ke GUIDED...")
mode_id_guided = master.mode_mapping()['GUIDED']
master.mav.set_mode_send(master.target_system, mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED, mode_id_guided)
time.sleep(1)

# Mengirim perintah ARM untuk menyalakan motor baling-baling
print("Arming motor, awas baling-baling...")
master.mav.command_long_send(master.target_system, master.target_component,
                             mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM, 0, 1, 0, 0, 0, 0, 0, 0)

# Memastikan motor benar-benar menyala sebelum melanjutkan
master.motors_armed_wait()
print("Drone ARMED! Siap ngacir...")

# Mengirim perintah Takeoff sesuai target altitude
print(f"Takeoff ke {target_alt} meter...")
master.mav.command_long_send(master.target_system, master.target_component,
                             mavutil.mavlink.MAV_CMD_NAV_TAKEOFF, 0, 0, 0, 0, 0, 0, 0, target_alt)

# Loop untuk memantau ketinggian secara real-time
print("Nunggu nyampe ketinggian target...")
while True:
    msg = master.recv_match(type='GLOBAL_POSITION_INT', blocking=True)
    if msg:
        alt = msg.relative_alt / 1000.0 # Konversi milimeter ke meter
        print(f"  -> Ketinggian sekarang: {alt:.1f} m", end='\r') 
        # Jika ketinggian sudah mencapai 95% dari target, proses dilanjutkan
        if alt >= (target_alt * 0.95): 
            print("\nUdah di atas! Ketinggian pas.")
            break
    time.sleep(0.1)

# Mengubah mode ke AUTO agar drone bergerak menyusuri titik-titik misi
print("Ganti mode ke AUTO biar ngikutin pola BINTANG...")
master.set_mode('AUTO')

print("\n=== DRONE SEDANG MENJALANKAN MISI BINTANG! ===")
print("Cek Mission Planner, terus klik 'Read' di tab PLAN untuk memperbarui visualisasi garis.")
print("Tekan Ctrl+C di terminal ini untuk menghentikan program.")

# Loop agar program tetap berjalan dan drone menyelesaikan misinya
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("\nProgram dihentikan secara manual.")