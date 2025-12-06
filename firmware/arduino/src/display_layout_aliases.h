// Legacy aliases file - provides backward compatibility aliases
// Note: display_renderer.h also defines some aliases for legacy code paths
#pragma once

#include "display_layout.h"

// display_layout.h defines the canonical rectangle names with RECT_ prefix
// These aliases remove the RECT_ prefix for backward compatibility
// Use global scope (::) to avoid conflict with ui::RectId enum values

// Main region aliases - map from non-RECT_ names to RECT_ prefixed names (global scope)
#define HEADER_NAME (::RECT_HEADER_NAME)
#define HEADER_VERSION (::RECT_HEADER_VERSION)
#define HEADER_TIME_CENTER (::RECT_HEADER_TIME_CENTER)
#define INSIDE_TEMP (::RECT_INSIDE_TEMP)
#define INSIDE_HUMIDITY (::RECT_INSIDE_HUMIDITY)
#define INSIDE_PRESSURE (::RECT_INSIDE_PRESSURE)
#define OUT_TEMP (::RECT_OUT_TEMP)
#define OUT_PRESSURE (::RECT_OUT_PRESSURE)
#define OUT_HUMIDITY (::RECT_OUT_HUMIDITY)
#define OUT_WIND (::RECT_OUT_WIND)
#define WEATHER_ICON (::RECT_WEATHER_ICON)
#define FOOTER_STATUS (::RECT_FOOTER_IP)  // Legacy alias - RECT_FOOTER_STATUS renamed to RECT_FOOTER_IP
#define FOOTER_WEATHER (::RECT_FOOTER_WEATHER)

