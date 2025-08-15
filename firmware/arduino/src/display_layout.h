#pragma once

// Display dimensions
#ifndef EINK_WIDTH
#define EINK_WIDTH 250
#endif
#ifndef EINK_HEIGHT
#define EINK_HEIGHT 122
#endif

// Partial update windows (x, y, w, h) — 2px grid, non-overlapping
static const int HEADER_NAME[4] = {  6,  2, 160, 14};
static const int HEADER_TIME[4] = {172,  2,  72, 14};

static const int INSIDE_TEMP[4] = {  6, 36, 118, 28};
static const int INSIDE_RH[4]   = {  6, 66, 118, 14};
static const int INSIDE_TIME[4] = {  6, 82, 118, 12};

static const int OUT_TEMP[4]    = {131, 36,  90, 28};
static const int OUT_RH[4]      = {131, 78, 113, 12};
static const int OUT_ICON[4]    = {224, 22,  20, 20};
static const int OUT_COND[4]    = {131, 90, 113, 12};
static const int OUT_WIND[4]    = {131, 66, 113, 12};

static const int STATUS_[4]     = {  6, 100, 238, 20};

enum WeatherIconId {
    ICON_CLEAR = 0,
    ICON_PARTLY,
    ICON_CLOUDY,
    ICON_RAIN,
    ICON_STORM,
    ICON_SNOW,
    ICON_FOG,
};


