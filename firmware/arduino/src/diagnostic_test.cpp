// Diagnostic test to validate hardware features
#include <Arduino.h>
#include <Wire.h>
#include "config.h"
#include "display_layout.h"

#ifdef NEOPIXEL_PIN
#include <Adafruit_NeoPixel.h>
Adafruit_NeoPixel status_pixel(1, NEOPIXEL_PIN, NEO_GRB + NEO_KHZ800);
#endif

void diagnostic_test_init() {
  Serial.println("\n=== HARDWARE DIAGNOSTIC TEST ===");
  Serial.flush();
  
  // Test 1: Neopixel
  #ifdef NEOPIXEL_PIN
  Serial.println("[DIAG] Testing NeoPixel...");
  Serial.flush();
  
  #ifdef NEOPIXEL_POWER
  pinMode(NEOPIXEL_POWER, OUTPUT);
  digitalWrite(NEOPIXEL_POWER, HIGH);
  delay(10);
  Serial.println("[DIAG] NeoPixel power enabled");
  #endif
  
  status_pixel.begin();
  status_pixel.setBrightness(50);
  
  // Flash R-G-B pattern
  status_pixel.setPixelColor(0, status_pixel.Color(255, 0, 0)); // Red
  status_pixel.show();
  Serial.println("[DIAG] NeoPixel: RED");
  Serial.flush();
  delay(500);
  
  status_pixel.setPixelColor(0, status_pixel.Color(0, 255, 0)); // Green
  status_pixel.show();
  Serial.println("[DIAG] NeoPixel: GREEN");
  Serial.flush();
  delay(500);
  
  status_pixel.setPixelColor(0, status_pixel.Color(0, 0, 255)); // Blue
  status_pixel.show();
  Serial.println("[DIAG] NeoPixel: BLUE");
  Serial.flush();
  delay(500);
  
  // Leave it dim white
  status_pixel.setPixelColor(0, status_pixel.Color(10, 10, 10));
  status_pixel.show();
  Serial.println("[DIAG] NeoPixel: OK - Set to dim white");
  #else
  Serial.println("[DIAG] NeoPixel: NOT CONFIGURED");
  #endif
  
  // Test 2: Display detection
  #if USE_DISPLAY
  Serial.println("[DIAG] Testing Display...");
  Serial.flush();
  
  // Simple display size check
  Serial.printf("[DIAG] Display configured for %dx%d\n", DISPLAY_WIDTH, DISPLAY_HEIGHT);
  Serial.println("[DIAG] Display: ENABLED in build");
  #else
  Serial.println("[DIAG] Display: DISABLED (USE_DISPLAY=0)");
  #endif
  
  // Test 3: I2C bus scan
  Serial.println("[DIAG] Testing I2C bus...");
  Serial.flush();
  
  Wire.begin();
  delay(100);
  
  int devices_found = 0;
  for (uint8_t addr = 0x08; addr < 0x78; addr++) {
    Wire.beginTransmission(addr);
    uint8_t error = Wire.endTransmission();
    if (error == 0) {
      Serial.printf("[DIAG] I2C device found at 0x%02X\n", addr);
      devices_found++;
      
      // Identify known devices
      if (addr == 0x76 || addr == 0x77) {
        Serial.println("       ^ Likely BME280 sensor");
      } else if (addr == 0x36) {
        Serial.println("       ^ Likely MAX17048 battery gauge");
      } else if (addr == 0x0B) {
        Serial.println("       ^ Likely LC709203F battery gauge");  
      } else if (addr == 0x44) {
        Serial.println("       ^ Likely SHT40 sensor");
      }
    }
  }
  Serial.printf("[DIAG] I2C scan complete: %d devices found\n", devices_found);
  Serial.flush();
  
  // Test 4: Memory check
  Serial.println("[DIAG] Testing Memory...");
  uint32_t free_heap = ESP.getFreeHeap();
  uint32_t heap_size = ESP.getHeapSize();
  uint32_t min_free = ESP.getMinFreeHeap();
  
  Serial.printf("[DIAG] Heap: %u bytes free of %u total\n", free_heap, heap_size);
  Serial.printf("[DIAG] Min free heap: %u bytes\n", min_free);
  Serial.printf("[DIAG] Free PSRAM: %u bytes\n", ESP.getFreePsram());
  
  if (free_heap < 10000) {
    Serial.println("[DIAG] WARNING: Low memory!");
  } else {
    Serial.println("[DIAG] Memory: OK");
  }
  Serial.flush();
  
  // Test 5: Pin states
  Serial.println("[DIAG] Checking pin states...");
  #ifdef SENSOR_POWER_PIN
  Serial.printf("[DIAG] SENSOR_POWER_PIN (%d): %s\n", 
                SENSOR_POWER_PIN, digitalRead(SENSOR_POWER_PIN) ? "HIGH" : "LOW");
  #endif
  #ifdef NEOPIXEL_POWER
  Serial.printf("[DIAG] NEOPIXEL_POWER (%d): %s\n",
                NEOPIXEL_POWER, digitalRead(NEOPIXEL_POWER) ? "HIGH" : "LOW");
  #endif
  
  Serial.println("\n=== DIAGNOSTIC TEST COMPLETE ===");
  Serial.flush();
}

void diagnostic_test_loop() {
  static uint32_t last_test = 0;
  static int cycle = 0;
  
  // Run periodic tests every 10 seconds
  if (millis() - last_test > 10000) {
    last_test = millis();
    cycle++;
    
    Serial.printf("\n[DIAG LOOP %d] Running periodic checks...\n", cycle);
    
    // Pulse neopixel
    #ifdef NEOPIXEL_PIN
    // Cycle through colors
    switch(cycle % 3) {
      case 0:
        status_pixel.setPixelColor(0, status_pixel.Color(20, 0, 0)); // Dim red
        break;
      case 1:
        status_pixel.setPixelColor(0, status_pixel.Color(0, 20, 0)); // Dim green
        break;
      case 2:
        status_pixel.setPixelColor(0, status_pixel.Color(0, 0, 20)); // Dim blue
        break;
    }
    status_pixel.show();
    #endif
    
    // Check memory
    Serial.printf("[DIAG LOOP] Free heap: %u bytes\n", ESP.getFreeHeap());
    
    // Check uptime
    Serial.printf("[DIAG LOOP] Uptime: %lu seconds\n", millis() / 1000);
    
    Serial.flush();
  }
}