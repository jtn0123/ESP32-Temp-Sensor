#!/usr/bin/env python3
import serial
import time
import sys

# Open serial port
try:
    ser = serial.Serial('/dev/cu.usbmodem101', 115200, timeout=1)
    print("Connected to /dev/cu.usbmodem101")
    
    # Reset the device by toggling DTR
    print("Resetting device...")
    ser.dtr = False
    time.sleep(0.5)
    ser.dtr = True
    time.sleep(0.5)
    
    print("Reading serial output for 15 seconds...")
    print("-" * 50)
    
    start_time = time.time()
    while time.time() - start_time < 15:
        if ser.in_waiting:
            line = ser.readline()
            try:
                decoded = line.decode('utf-8').rstrip()
                # Highlight important boot messages
                if '[BOOT' in decoded or 'Serial initialized' in decoded or '12:34' in decoded:
                    print(f">>> {decoded}")
                else:
                    print(decoded)
            except:
                print(f"[Raw bytes]: {line}")
    
    ser.close()
    print("-" * 50)
    print("Done reading serial output")
    
except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)