#!/usr/bin/env python3
import serial
import time

try:
    ser = serial.Serial('/dev/cu.usbmodem101', 115200, timeout=0.5)
    print("Monitoring device for 10 seconds...")
    print("-" * 50)
    
    start = time.time()
    while time.time() - start < 10:
        if ser.in_waiting:
            try:
                line = ser.readline().decode('utf-8', errors='ignore').rstrip()
                if line:
                    print(line)
            except:
                pass
    
    ser.close()
    print("-" * 50)
    print("Done")
    
except Exception as e:
    print(f"Error: {e}")