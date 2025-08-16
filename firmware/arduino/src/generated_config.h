// Auto-generated from config/device.yaml by scripts/gen_device_header.py
#pragma once

#define ROOM_NAME "Office"
#define WAKE_INTERVAL_SEC 7200
#define FULL_REFRESH_EVERY 12
#define OUTSIDE_SOURCE "mqtt"
#define WIFI_SSID "YOUR_SSID"
#define WIFI_PASS "YOUR_PASS"
#define MQTT_HOST "192.168.1.10"
#define MQTT_PORT 1883
#define MQTT_PUB_BASE "sensors/office"
#define MQTT_SUB_BASE "home/outdoor"
#define MQTT_USER "your_mqtt_user"
#define MQTT_PASS "your_mqtt_password"
#define BATTERY_CAPACITY_MAH 3500
#define SLEEP_CURRENT_MA 0.09
#define ACTIVE_CURRENT_MA 80.0
#define ACTIVE_SECONDS 10
#define VBAT_ADC_PIN -1
#define VBAT_DIVIDER 2.0
#define ADC_MAX_COUNTS 4095
#define ADC_REF_V 3.3
#define THRESH_TEMP_C 0.1
#define THRESH_RH_PCT 1.0
