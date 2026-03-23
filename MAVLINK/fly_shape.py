from pymavlink import mavutil
import time
import math


master = mavutil.mavlink_connection('udpin:127.0.0.1:14551')
master.wait_heartbeat()
print("DRONE KONEK! Mode GUIDED Terdeteksi.")


def send_ned_velocity_and_position(master, vn, ve, vd, x, y, z):
    master.mav.set_position_target_local_ned_send(
        0, master.target_system, master.target_component,
        mavutil.mavlink.MAV_FRAME_LOCAL_NED,
        0b110111000111, 
        x, y, z,        
        vn, ve, vd,     
        0, 0, 0, 0, 0)


master.mav.command_long_send(
    master.target_system, master.target_component,
    mavutil.mavlink.MAV_CMD_DO_CHANGE_SPEED, 0, 1, 5, 0, 0, 0, 0, 0) # 5 m/s
print("Speed Set: 5m/s")


sisi = 20
altitude = -10 

for i in range(7):
    sudut = math.radians(i * 60)
    target_x = sisi * math.cos(sudut)
    target_y = sisi * math.sin(sudut)
    
    print(f"Menuju Titik {i+1}/6: X={target_x:.1f}, Y={target_y:.1f}")
    
    
    vn = 2 * math.cos(sudut)
    ve = 2 * math.sin(sudut)
    
    send_ned_velocity_and_position(master, vn, ve, 0, target_x, target_y, altitude)
    
    
    time.sleep(10)

print("MISI SELESAI! Cek peta Mission Planner kamu.")