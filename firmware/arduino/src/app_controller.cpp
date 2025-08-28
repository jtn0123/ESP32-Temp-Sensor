// Application controller implementation
#include "app_controller.h"
#include "config.h"
#include "generated_config.h"
#include "sensors.h"
#include "power.h"
#include "wifi_manager.h"
#include "mqtt_client.h"
#include "net.h"
#include "system_manager.h"
#include "state_manager.h"
#include "metrics_diagnostics.h"
#include "display_manager.h"

// Diagnostic test functions (from diagnostic_test.cpp)
extern void diagnostic_test_init();
extern void diagnostic_test_loop();
extern void show_boot_stage(int stage);

// Track wake time for phase management  
static uint32_t g_wake_time_ms = 0;

// Diagnostic mode tracking
static uint32_t g_diagnostic_last_publish_ms = 0;
#define DIAGNOSTIC_PUBLISH_INTERVAL_MS 30000

uint32_t get_wake_time_ms() {
  return g_wake_time_ms;
}

bool is_first_boot() {
  return esp_reset_reason() == ESP_RST_POWERON;
}

// Main application setup orchestration
void app_setup() {
  g_wake_time_ms = millis();
  
  // Initialize serial FIRST with longer delay
  Serial.begin(115200);
  delay(500);  // Longer delay for serial stability
  
  // Immediate debug output
  Serial.println("\n\n=== ESP32 BOOT SEQUENCE ===");
  Serial.printf("FW Version: %s\n", FW_VERSION);
  #ifdef BOOT_DEBUG
  Serial.println("Build: dev_display");
  Serial.println("Flags: DEV_NO_SLEEP, FORCE_FULL_ONLY, BOOT_DEBUG");
  #endif
  Serial.flush();
  delay(10);
  Serial.println("[BOOT-1] Serial initialized");
  Serial.flush();
  show_boot_stage(1);  // Red for boot/serial
  
  // Show we're alive with neopixel if available
  #ifdef NEOPIXEL_PIN
  pinMode(NEOPIXEL_PIN, OUTPUT);
  #ifdef NEOPIXEL_POWER
  pinMode(NEOPIXEL_POWER, OUTPUT);
  digitalWrite(NEOPIXEL_POWER, HIGH);
  #endif
  // Quick red flash to show boot
  analogWrite(NEOPIXEL_PIN, 10);
  delay(100);
  analogWrite(NEOPIXEL_PIN, 0);
  #endif
  
  Serial.println("[2] Starting initialization");
  Serial.flush();
  
  // Run diagnostic tests in DEV_NO_SLEEP mode
  #ifdef DEV_NO_SLEEP
  Serial.println("[BOOT-2a] Running hardware diagnostics...");
  diagnostic_test_init();
  Serial.println("[BOOT-2b] Diagnostics complete, continuing boot...");
  Serial.flush();
  #endif
  
  #ifdef BOOT_DEBUG
  show_boot_stage(2);  // Yellow for display init
  #ifdef USE_DISPLAY
  Serial.println("[BOOT-2c] Display test will occur during init...");
  // Note: Display will be initialized later in normal flow
  // The clock test happens in display_manager initialization
  #endif
  #endif
  
  // Initialize state management with error checking
  Serial.println("[3] Initializing NVS cache...");
  Serial.flush();
  nvs_begin_cache();
  nvs_load_cache_if_unset();
  Serial.println("[3] NVS cache OK");
  Serial.flush();
  
  // Initialize power management with error checking
  Serial.println("[4] Initializing power management...");
  Serial.flush();
  power_init();
  power_wake_from_sleep();
  Serial.println("[4] Power management OK");
  Serial.flush();
  
  // Initialize sensors with error checking
  Serial.println("[5] Initializing sensors...");
  Serial.flush();
  sensors_init_all();
  // Note: We continue even if some sensors fail
  // The sensors module will handle individual failures
  Serial.println("[5] Sensors initialized (check logs for any failures)");
  Serial.flush();
  
  #ifdef BOOT_DEBUG
  // In debug mode, show memory status after sensor init
  Serial.printf("[MEMORY] After sensors - Free heap: %u, Min free: %u\n", 
                ESP.getFreeHeap(), ESP.getMinFreeHeap());
  #endif
  
  // Initialize network (but don't block on it)
  Serial.println("[BOOT-3] Attempting WiFi connection...");
  Serial.flush();
  show_boot_stage(3);  // Blue for WiFi
  if (!wifi_connect_with_timeout(5000)) {
    Serial.println("[BOOT-3] WiFi connection failed - continuing anyway");
    Serial.flush();
    show_boot_stage(5);  // Purple for error
  } else {
    Serial.println("[BOOT-4] WiFi connected");
    Serial.flush();
    show_boot_stage(4);  // Green for ready
  }
  
  // Initialize MQTT
  if (wifi_is_connected()) {
    mqtt_begin();
    ensure_mqtt_connected();
  }
  
  // Run main phases
  run_sensor_phase();
  run_network_phase();
  
  #if USE_DISPLAY
  run_display_phase();
  #endif
  
  run_sleep_phase();
}

// Main application loop (for diagnostic mode)
void app_loop() {
  #ifdef DEV_NO_SLEEP
  // In always-on mode, just print alive message periodically
  static uint32_t last_print = 0;
  if (millis() - last_print > 5000) {
    last_print = millis();
    Serial.print("[ALIVE] Uptime: ");
    Serial.print(millis() / 1000);
    Serial.println(" seconds");
    Serial.flush();
  }
  delay(100);  // Small delay to prevent watchdog issues
  return;  // Don't run diagnostic mode logic in DEV_NO_SLEEP
  #endif
  
  // Check for MQTT diagnostic mode commands
  bool diag_mode_value;
  if (net_check_diagnostic_mode_request(diag_mode_value)) {
    set_diagnostic_mode(diag_mode_value);
    mqtt_publish_diagnostic_mode(diag_mode_value);
    Serial.printf("DIAG: Mode changed to %s via MQTT\n", diag_mode_value ? "active" : "inactive");
  }
  
  // In diagnostic mode, stay awake and publish diagnostics periodically
  if (is_diagnostic_mode_active()) {
    // Keep network alive
    net_loop();
    
    // Publish diagnostics every interval
    if (millis() - g_diagnostic_last_publish_ms >= DIAGNOSTIC_PUBLISH_INTERVAL_MS) {
      g_diagnostic_last_publish_ms = millis();
      
      if (mqtt_is_connected()) {
        Serial.println("DIAG: Publishing diagnostic data");
        
        // Update and publish memory diagnostics
        MemoryDiagnostics mem_diag = get_memory_diagnostics();
        net_publish_memory_diagnostics(mem_diag.free_heap, mem_diag.min_free_heap,
                                       mem_diag.largest_free_block, mem_diag.fragmentation_pct);
        
        // Update uptime
        uint32_t current_uptime = get_cumulative_uptime_sec() + (millis() / 1000);
        net_publish_uptime(current_uptime);
        
        // Publish other diagnostic info
        net_publish_wake_count(get_wake_count());
        net_publish_wifi_rssi(WiFi.RSSI());
        
        // Publish detailed diagnostic JSON
        char diag_json[512];
        snprintf(diag_json, sizeof(diag_json),
                 "{\"diag_mode\":true,\"free_heap\":%u,\"min_heap\":%u,"
                 "\"fragmentation\":%.1f,\"rssi\":%d,\"uptime\":%u,"
                 "\"boot_count\":%u,\"crash_count\":%u,\"wake_count\":%u}",
                 mem_diag.free_heap, mem_diag.min_free_heap, mem_diag.fragmentation_pct,
                 WiFi.RSSI(), current_uptime, get_boot_count(), get_crash_count(), get_wake_count());
        net_publish_debug_json(diag_json, false);
        
        // Log to serial
        Serial.printf("DIAG: Heap: free=%u min=%u frag=%.1f%%\n",
                      mem_diag.free_heap, mem_diag.min_free_heap, mem_diag.fragmentation_pct);
      }
    }
    
    // Handle serial commands for diagnostic mode
    if (Serial.available()) {
      String cmd = Serial.readStringUntil('\n');
      cmd.trim();
      
      if (cmd == "normal" || cmd == "exit") {
        Serial.println("DIAG: Exiting diagnostic mode");
        set_diagnostic_mode(false);
        mqtt_publish_diagnostic_mode(false);
      } else if (cmd == "memtest") {
        Serial.println("DIAG: Running memory test");
        MemoryDiagnostics mem = get_memory_diagnostics();
        Serial.printf("  Free: %u bytes\n", mem.free_heap);
        Serial.printf("  Min:  %u bytes\n", mem.min_free_heap);
        Serial.printf("  Largest block: %u bytes\n", mem.largest_free_block);
        Serial.printf("  Fragmentation: %.1f%%\n", mem.fragmentation_pct);
      } else if (cmd == "sensortest") {
        Serial.println("DIAG: Testing sensors");
        InsideReadings ir = read_inside_sensors();
        Serial.printf("  Temp: %.2f°C\n", ir.temperatureC);
        Serial.printf("  Humidity: %.1f%%\n", ir.humidityPct);
        Serial.printf("  Pressure: %.1f hPa\n", ir.pressureHPa);
      } else if (cmd == "wifitest") {
        Serial.println("DIAG: WiFi scan");
        int n = WiFi.scanNetworks();
        Serial.printf("  Found %d networks\n", n);
        for (int i = 0; i < n && i < 10; i++) {
          Serial.printf("  %d: %s (%d dBm)\n", i+1, WiFi.SSID(i).c_str(), WiFi.RSSI(i));
        }
      }
    }
    
    delay(100);
  } else {
    // Normal mode: deep sleep from setup, shouldn't reach here
    delay(1000);
  }
}

// Sensor reading phase
void run_sensor_phase() {
  Serial.println("=== Sensor Phase ===");
  uint32_t phase_start = millis();
  
  InsideReadings readings = read_sensors_with_timeout(SENSOR_PHASE_TIMEOUT_MS);
  
  if (isfinite(readings.temperatureC)) {
    Serial.printf("Sensors: %.1f°C, %.1f%% RH, %.1f hPa\n",
                  readings.temperatureC, readings.humidityPct, readings.pressureHPa);
    
    // Store for publishing
    set_last_published_inside_tempC(readings.temperatureC);
    set_last_published_inside_rh(readings.humidityPct);
    set_last_published_inside_pressureHPa(readings.pressureHPa);
  }
  
  Serial.printf("Sensor phase took %lu ms\n", millis() - phase_start);
}

// Network and MQTT publishing phase
void run_network_phase() {
  Serial.println("=== Network Phase ===");
  uint32_t phase_start = millis();
  
  if (!mqtt_is_connected()) {
    Serial.println("MQTT not connected, skipping publish");
    return;
  }
  
  // Publish sensor readings
  float tempC = get_last_published_inside_tempC();
  float rhPct = get_last_published_inside_rh();
  float pressHPa = get_last_published_inside_pressureHPa();
  
  if (isfinite(tempC)) {
    mqtt_publish_inside(tempC, rhPct);
    net_publish_pressure(pressHPa);
  }
  
  // Publish battery status
  BatteryStatus bs = read_battery_status();
  if (bs.percent >= 0) {
    net_publish_battery(bs.voltage, bs.percent);
  }
  
  // Publish diagnostics
  publish_boot_diagnostics();
  
  // Fetch any retained outside data
  pump_network_ms(FETCH_RETAINED_TIMEOUT_MS);
  
  Serial.printf("Network phase took %lu ms\n", millis() - phase_start);
}

#if USE_DISPLAY
// Display update phase
void run_display_phase() {
  Serial.println("=== Display Phase ===");
  uint32_t phase_start = millis();
  
  // This would contain display update logic
  // Currently in main.cpp but would be moved here
  
  Serial.printf("Display phase took %lu ms\n", millis() - phase_start);
}
#endif

// Deep sleep phase
void run_sleep_phase() {
  Serial.println("=== Sleep Phase ===");
  
  #ifdef DEV_NO_SLEEP
  Serial.println("DEV_NO_SLEEP: Staying awake in loop()");
  Serial.println("Device will print [ALIVE] message every 5 seconds");
  Serial.flush();
  return;  // Return to setup(), then loop() will run continuously
  #endif
  
  // Calculate wake interval based on mode
  uint32_t wake_interval_sec = WAKE_INTERVAL_SEC;
  
  // Update cumulative uptime before sleep
  add_to_cumulative_uptime(millis() / 1000);
  
  // Prepare for sleep
  power_prepare_sleep();
  net_prepare_for_sleep();
  
  // Store state to NVS
  nvs_end_cache();
  
  Serial.printf("Entering deep sleep for %u seconds\n", wake_interval_sec);
  go_deep_sleep_with_tracking(wake_interval_sec);
}