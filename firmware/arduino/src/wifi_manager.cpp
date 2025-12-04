// WiFi management implementation - extracted from net.h
#include "wifi_manager.h"
#include "generated_config.h"
#include "config.h"
#include "profiling.h"

// Static storage for provisioning
static Preferences g_wifi_prefs;

// WiFi connection state tracking
static WiFiConnectionState g_wifi_state = WIFI_STATE_IDLE;

bool parse_bssid(const char* str, uint8_t out[6]) {
  if (!str)
    return false;
  int vals[6];
  int n = sscanf(str, "%x:%x:%x:%x:%x:%x", &vals[0], &vals[1], &vals[2], &vals[3], &vals[4], &vals[5]);
  if (n != 6)
    return false;
  for (int i = 0; i < 6; ++i)
    out[i] = static_cast<uint8_t>(vals[i]);
  return true;
}

bool is_all_zero_bssid(const uint8_t b[6]) {
  for (int i = 0; i < 6; ++i)
    if (b[i] != 0)
      return false;
  return true;
}

bool wifi_connect_with_timeout(uint32_t timeout_ms) {
  g_wifi_state = WIFI_STATE_CONNECTING;
  
  // Try to connect with configured credentials
  WiFi.mode(WIFI_STA);
  
  // Parse BSSID if configured
  uint8_t bssid_bytes[6] = {0};
  bool has_bssid = false;
  
#ifdef WIFI_BSSID
  has_bssid = parse_bssid(WIFI_BSSID, bssid_bytes);
  if (!has_bssid || is_all_zero_bssid(bssid_bytes)) {
    has_bssid = false;
  }
#endif

  // Set hostname before connecting
  WiFi.setHostname(ROOM_NAME);
  
  // Connect with or without BSSID
  if (has_bssid) {
    Serial.printf("[WiFi] Connecting to %s with BSSID\n", WIFI_SSID);
    WiFi.begin(WIFI_SSID, WIFI_PASS, 0, bssid_bytes);
  } else {
    Serial.printf("[WiFi] Connecting to %s\n", WIFI_SSID);
    WiFi.begin(WIFI_SSID, WIFI_PASS);
  }
  
  // Wait for connection with timeout
  uint32_t start = millis();
  while (!WiFi.isConnected() && (millis() - start < timeout_ms)) {
    delay(100);
  }
  
  if (WiFi.isConnected()) {
    g_wifi_state = WIFI_STATE_CONNECTED;
    Serial.printf("[WiFi] Connected! IP: %s, RSSI: %d\n", 
                  WiFi.localIP().toString().c_str(), WiFi.RSSI());
    return true;
  } else {
    g_wifi_state = WIFI_STATE_FAILED;
    Serial.printf("[WiFi] Connection failed after %dms\n", timeout_ms);
    return false;
  }
}

bool wifi_connect_with_exponential_backoff(uint32_t max_attempts, uint32_t initial_delay_ms) {
  PROFILE_SCOPE("wifi_connect_backoff");
  uint32_t retry_delay_ms = initial_delay_ms;

  for (uint32_t attempt = 0; attempt < max_attempts; attempt++) {
    Serial.printf("[WiFi] Connection attempt %d/%d\n", attempt + 1, max_attempts);
    
    if (wifi_connect_with_timeout(WIFI_CONNECT_TIMEOUT_MS)) {
      return true;
    }
    
    // Don't delay after the last attempt
    if (attempt < max_attempts - 1) {
      Serial.printf("[WiFi] Waiting %dms before retry...\n", retry_delay_ms);
      delay(retry_delay_ms);
      
      // Exponential backoff with cap at 16 seconds
      retry_delay_ms = min(retry_delay_ms * 2, (uint32_t)16000);
    }
  }
  
  Serial.printf("[WiFi] Failed to connect after %d attempts\n", max_attempts);
  g_wifi_state = WIFI_STATE_FAILED;
  return false;
}

bool wifi_is_connected() {
  return WiFi.isConnected();
}

String wifi_get_ip() {
  if (!WiFi.isConnected()) {
    return String("0.0.0.0");
  }
  return WiFi.localIP().toString();
}

void wifi_get_ip_cstr(char* out, size_t out_size) {
  if (!out || out_size == 0)
    return;
  
  if (!WiFi.isConnected()) {
    snprintf(out, out_size, "0.0.0.0");
    return;
  }
  
  IPAddress ip = WiFi.localIP();
  snprintf(out, out_size, "%d.%d.%d.%d", ip[0], ip[1], ip[2], ip[3]);
}

int wifi_get_rssi() {
  if (!WiFi.isConnected()) {
    return -100;
  }
  return WiFi.RSSI();
}

void wifi_set_hostname(const char* hostname) {
  WiFi.setHostname(hostname);
}

void wifi_configure_power_save(bool enable) {
  if (enable) {
    WiFi.setSleep(WIFI_PS_MIN_MODEM);
  } else {
    WiFi.setSleep(WIFI_PS_NONE);
  }
}

WiFiConnectionState wifi_get_state() {
  // Update state based on actual connection status
  if (WiFi.isConnected() && g_wifi_state != WIFI_STATE_CONNECTED) {
    g_wifi_state = WIFI_STATE_CONNECTED;
  } else if (!WiFi.isConnected() && g_wifi_state == WIFI_STATE_CONNECTED) {
    g_wifi_state = WIFI_STATE_DISCONNECTED;
  }
  return g_wifi_state;
}

const char* wifi_state_to_string(WiFiConnectionState state) {
  switch (state) {
    case WIFI_STATE_IDLE: return "IDLE";
    case WIFI_STATE_CONNECTING: return "CONNECTING";
    case WIFI_STATE_CONNECTED: return "CONNECTED";
    case WIFI_STATE_FAILED: return "FAILED";
    case WIFI_STATE_DISCONNECTED: return "DISCONNECTED";
    default: return "UNKNOWN";
  }
}

#if USE_WIFI_PROVISIONING
bool wifi_clear_provisioning() {
  g_wifi_prefs.begin("wifi", false);
  g_wifi_prefs.clear();
  g_wifi_prefs.end();
  
  wifi_prov_mgr_deinit();
  WiFi.disconnect(true, true);
  delay(100);
  
  return true;
}

void wifi_begin_provisioning() {
  // Implementation would go here - complex provisioning logic
  // For now, just a stub
}

bool wifi_is_provisioning_active() {
  // Check if provisioning manager is active
  return false;  // Stub for now
}
#else
bool wifi_clear_provisioning() {
  return false;  // Not supported without provisioning
}

void wifi_begin_provisioning() {
  // No-op without provisioning support
}

bool wifi_is_provisioning_active() {
  return false;
}
#endif