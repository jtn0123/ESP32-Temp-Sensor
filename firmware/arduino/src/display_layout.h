#pragma once

// Display dimensions
#ifndef EINK_WIDTH
#define EINK_WIDTH 250
#endif
#ifndef EINK_HEIGHT
#define EINK_HEIGHT 122
#endif

// Partial update windows (x0, y0, x1, y1)
static const int INSIDE_TEMP[4] = {6, 38, 124, 64};
static const int INSIDE_RH[4]   = {6, 64, 124, 80};
static const int INSIDE_TIME[4] = {6, 78, 124, 92};
static const int OUT_TEMP[4]    = {131, 38, 220, 64};
static const int OUT_RH[4]      = {131, 64, 220, 80};
static const int OUT_ICON[4]    = {218, 22, 242, 46}; // 24x24
static const int STATUS_[4]     = {6, 96, 244, 118};

enum WeatherIconId {
    ICON_CLEAR = 0,
    ICON_PARTLY,
    ICON_CLOUDY,
    ICON_RAIN,
    ICON_STORM,
    ICON_SNOW,
    ICON_FOG,
};


