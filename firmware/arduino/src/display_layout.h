#pragma once

// Display dimensions
#ifndef EINK_WIDTH
#define EINK_WIDTH 250
#endif
#ifndef EINK_HEIGHT
#define EINK_HEIGHT 122
#endif

// Partial update windows (x, y, w, h) — 2px grid, non-overlapping
static constexpr int HEADER_NAME[4] = {  6,  2, 160, 14};
static constexpr int HEADER_TIME[4] = {172,  2,  72, 14};

static constexpr int INSIDE_TEMP[4] = {  6, 36, 118, 28};
static constexpr int INSIDE_RH[4]   = {  6, 66, 118, 14};
static constexpr int INSIDE_TIME[4] = {  6, 82, 118, 12};

static constexpr int OUT_TEMP[4]    = {131, 36,  90, 28};
static constexpr int OUT_ICON[4]    = {224, 22,  24, 24};

// Two small columns at bottom right
// moved up by 12 px to close space
static constexpr int OUT_ROW1_L[4]  = {131, 74,  44, 12}; // e.g., condition
static constexpr int OUT_ROW1_R[4]  = {177, 74,  44, 12}; // e.g., RH
static constexpr int OUT_ROW2_L[4]  = {131, 86,  44, 12}; // e.g., wind
static constexpr int OUT_ROW2_R[4]  = {177, 86,  44, 12}; // e.g., H/L

static constexpr int STATUS_[4]     = {  6, 112, 238, 10};

enum WeatherIconId {
    ICON_CLEAR = 0,
    ICON_PARTLY,
    ICON_CLOUDY,
    ICON_RAIN,
    ICON_STORM,
    ICON_SNOW,
    ICON_FOG,
};

// Compile-time layout sanity checks (widths/heights within bounds)
static_assert(HEADER_NAME[0] >= 0 && HEADER_NAME[1] >= 0, "HEADER_NAME origin");
static_assert(HEADER_NAME[0] + HEADER_NAME[2] <= EINK_WIDTH, "HEADER_NAME width");
static_assert(HEADER_NAME[1] + HEADER_NAME[3] <= EINK_HEIGHT, "HEADER_NAME height");
static_assert(HEADER_TIME[0] + HEADER_TIME[2] <= EINK_WIDTH, "HEADER_TIME width");
static_assert(INSIDE_TEMP[0] + INSIDE_TEMP[2] <= EINK_WIDTH, "INSIDE_TEMP width");
static_assert(OUT_TEMP[0] + OUT_TEMP[2] <= EINK_WIDTH, "OUT_TEMP width");
static_assert(STATUS_[0] + STATUS_[2] <= EINK_WIDTH, "STATUS_ width");


