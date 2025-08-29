// Display management implementation - extracted from main.cpp
#include "display_manager.h"

#if USE_DISPLAY

#include <Arduino.h>
#include <GxEPD2_BW.h>
#include "display_layout.h"
#include "icons.h"
#include "power.h"
#include "net.h"
#include "generated_config.h"

// Check panel configuration
#ifndef EINK_PANEL_DEPG0213BN
#define EINK_PANEL_DEPG0213BN 0
#endif

// Display object - will be moved here from main.cpp later
// For now, we'll access it via extern from main.cpp
#if EINK_PANEL_DEPG0213BN
extern GxEPD2_BW<GxEPD2_213_DEPG0213BN, GxEPD2_213_DEPG0213BN::HEIGHT> display;
#else
extern GxEPD2_BW<GxEPD2_213_GDEY0213B74, GxEPD2_213_GDEY0213B74::HEIGHT> display;
#endif

// Constants needed for display operations
#define TOP_Y_OFFSET 4
#define HEADER_NAME_Y_ADJ -8

// Note: Layout variables are generated without RECT_ prefix
// Variables are defined in display_layout.h as HEADER_TIME_CENTER, FOOTER_STATUS_, etc.

// Forward declaration for status pixel (if enabled)
#if USE_STATUS_PIXEL
extern void status_pixel_tick();
#endif

// Forward declaration for draw_in_region template from main.cpp
// We'll declare it properly to avoid link issues
void draw_in_region_lambda(const int rect[4], void(*fn)(int16_t, int16_t, int16_t, int16_t, void*), void* ctx);

// Placeholder implementations - will be filled with actual code from main.cpp
void display_manager_init() {
    Serial.println("[DISPLAY] Initializing display...");
    
    // Initialize display hardware
    display.init(115200, true, 2, false);  // Serial speed, initial, pulldown_dis_time, use RST
    display.setRotation(3);  // Landscape orientation
    display.setTextColor(GxEPD_BLACK);
    display.setFullWindow();
    
    // Clear display with white background
    display.firstPage();
    do {
        display.fillScreen(GxEPD_WHITE);
    } while (display.nextPage());
    
    #ifdef BOOT_DEBUG
    // Show test pattern during boot
    Serial.println("[DISPLAY] Showing boot test pattern");
    display.firstPage();
    do {
        display.fillScreen(GxEPD_WHITE);
        
        // Draw test time "12:34"
        display.setTextSize(2);
        display.setCursor(HEADER_TIME_CENTER[0], HEADER_TIME_CENTER[1] + 4);
        display.print("12:34");
        
        // Draw version in top right if available
        display.setTextSize(1);
        display.setCursor(HEADER_VERSION[0], HEADER_VERSION[1]);
        display.print("v4.0");
        
        // Draw "BOOT TEST" in center
        display.setTextSize(2);
        const char* test_msg = "BOOT TEST";
        int16_t x1, y1;
        uint16_t w, h;
        display.getTextBounds(test_msg, 0, 0, &x1, &y1, &w, &h);
        display.setCursor((EINK_WIDTH - w) / 2, (EINK_HEIGHT - h) / 2);
        display.print(test_msg);
        
    } while (display.nextPage());
    
    delay(2000);  // Show test pattern for 2 seconds
    #endif
    
    Serial.println("[DISPLAY] Display initialized");
}

// Text width calculation
int16_t text_width_default_font(const char* s, uint8_t size) {
    // Default 5x7 font is 6 px advance per char at size 1
    int16_t count = 0;
    for (const char* p = s; *p; ++p) count++;
    return count * 6 * size;
}

// Make a shortened condition string from weather text
void make_short_condition_cstr(const char* weather, char* out, size_t out_size) {
    if (!out || out_size == 0)
        return;
    out[0] = '\0';
    if (!weather)
        return;
    // Skip leading spaces
    const char* p = weather;
    while (*p == ' ' || *p == '\t') p++;
    // Copy until next separator or end
    size_t i = 0;
    while (*p && i < out_size - 1) {
        char c = *p;
        // Treat common separators and hyphen as delimiters so HA values like
        // "clear-night" or "snowy-rainy" shorten to a single word.
        if (c == ' ' || c == '\t' || c == ',' || c == ';' || c == ':' || c == '/' || c == '-')
            break;
        out[i++] = c;
        p++;
    }
    out[i] = '\0';
}

// Draw static chrome (borders, labels, etc.)
void draw_static_chrome() {
    // Frame and header linework
    display.fillScreen(GxEPD_WHITE);
    // Draw outer border flush to panel extents
    display.drawRect(0, 0, EINK_WIDTH, EINK_HEIGHT, GxEPD_BLACK);
    // Header underline aligned with simulator and other draw paths
    display.drawLine(1, 22 + TOP_Y_OFFSET, EINK_WIDTH - 2, 22 + TOP_Y_OFFSET, GxEPD_BLACK);
    // Extend the center divider to the bottom frame to match the simulator
    display.drawLine(125, 18 + TOP_Y_OFFSET, 125, EINK_HEIGHT - 2, GxEPD_BLACK);
    // Single header underline between header and content
    display.drawLine(1, 16 + TOP_Y_OFFSET, EINK_WIDTH - 2, 16 + TOP_Y_OFFSET, GxEPD_BLACK);
    // Horizontal rule for footer region (drawn at top edge of footer)
    display.drawLine(1, FOOTER_STATUS[1], EINK_WIDTH - 2, FOOTER_STATUS[1], GxEPD_BLACK);

    // Header: room name left, time will be drawn separately
    display.setTextColor(GxEPD_BLACK);
    display.setTextSize(1);
    display.setCursor(6, 13 + TOP_Y_OFFSET + HEADER_NAME_Y_ADJ);
    display.print(ROOM_NAME);

    // Section labels: left 'INSIDE', right 'OUTSIDE'; top-right also shows version
    display.setCursor(6, 22 + TOP_Y_OFFSET);
    display.print(F("INSIDE"));
    display.setCursor(131, 22 + TOP_Y_OFFSET);
    display.print(F("OUTSIDE"));
    // Top-right version string within HEADER_TIME box
    String version_str = String("v") + FW_VERSION;
    display.setCursor(
        HEADER_TIME_CENTER[0] + HEADER_TIME_CENTER[2] - 2 - text_width_default_font(version_str.c_str(), 1),
        HEADER_TIME_CENTER[1] + TOP_Y_OFFSET + HEADER_TIME_CENTER[3] - 8);
    display.print(F("v"));
    display.print(FW_VERSION);
    // Center time will be drawn later in draw_header_time(_direct)
}

// These functions use draw_in_region template which is complex to move
// They remain in main.cpp for now

void draw_header_time_direct(const char* time_str) {
    int16_t tw = text_width_default_font(time_str, 1);
    int16_t rx = static_cast<int16_t>(HEADER_TIME_CENTER[0] + (HEADER_TIME_CENTER[2] - tw) / 2);
    int16_t by = static_cast<int16_t>(HEADER_TIME_CENTER[1] + TOP_Y_OFFSET + HEADER_TIME_CENTER[3] - 6);
    display.setTextColor(GxEPD_BLACK);
    display.setTextSize(1);
    display.setCursor(rx, by);
    display.print(time_str);
}

// draw_status_line uses draw_in_region - remains in main.cpp

void draw_status_line_direct(const BatteryStatus& bs, const char* ip_cstr) {
    #define STATUS_Y_ADJ 0  // Temporary until we refactor this properly
    int16_t xx = FOOTER_STATUS[0];
    int16_t yy = static_cast<int16_t>(FOOTER_STATUS[1] + STATUS_Y_ADJ);
    int16_t ww = FOOTER_STATUS[2];
    int16_t hh = FOOTER_STATUS[3];
    display.setTextColor(GxEPD_BLACK);
    display.setTextSize(1);
    int16_t cx = static_cast<int16_t>(xx + 2);
    int16_t cy = static_cast<int16_t>(yy + hh - 4);
    if (bs.percent >= 0) {
        int16_t bx = cx;
        int16_t by = static_cast<int16_t>(yy + 1);
        int16_t bw2 = 13;
        int16_t bh2 = 7;
        display.drawRect(bx, by, bw2, bh2, GxEPD_BLACK);
        display.fillRect(static_cast<int16_t>(bx + bw2), static_cast<int16_t>(by + 2), 2, 3,
                       GxEPD_BLACK);
        int16_t fillw = static_cast<int16_t>(((bw2 - 2) * (bs.percent / 100.0f) + 0.5f));
        if (fillw > 0)
            display.fillRect(static_cast<int16_t>(bx + 1), static_cast<int16_t>(by + 1), fillw,
                           static_cast<int16_t>(bh2 - 2), GxEPD_BLACK);
        cx = static_cast<int16_t>(cx + bw2 + 6);
    }
    char right[48];
    snprintf(right, sizeof(right), "IP %s", ip_cstr);
    int16_t bx, by2;
    uint16_t bw3, bh3;
    display.getTextBounds(right, 0, 0, &bx, &by2, &bw3, &bh3);
    int16_t rx = static_cast<int16_t>(xx + ww - 2 - static_cast<int16_t>(bw3));
    char left_full[64];
    char left_nobatt[64];
    char left_tail[32];
    snprintf(left_full, sizeof(left_full), "Batt %.2fV %d%% | ~%dd", bs.voltage, bs.percent,
             bs.estimatedDays);
    snprintf(left_nobatt, sizeof(left_nobatt), "%.2fV %d%% | ~%dd", bs.voltage, bs.percent,
             bs.estimatedDays);
    snprintf(left_tail, sizeof(left_tail), "%d%% | ~%dd", bs.percent, bs.estimatedDays);
    int16_t available = static_cast<int16_t>(rx - cx - 2);
    const char* to_print = left_full;
    display.getTextBounds(to_print, 0, 0, &bx, &by2, &bw3, &bh3);
    if (static_cast<int16_t>(bw3) > available) {
        to_print = left_nobatt;
        display.getTextBounds(to_print, 0, 0, &bx, &by2, &bw3, &bh3);
    }
    if (static_cast<int16_t>(bw3) > available) {
        display.getTextBounds(left_tail, 0, 0, &bx, &by2, &bw3, &bh3);
        if (static_cast<int16_t>(bw3) <= available) {
            to_print = left_tail;
        } else {
            to_print = "";
        }
    }
    display.setCursor(cx, cy);
    display.print(to_print);
    display.setCursor(rx, cy);
    display.print(right);
}

#endif // USE_DISPLAY