#pragma once

#include "icons_generated.h"

// Simple facade to keep includes stable if generation changes later
template<typename GFX>
inline void draw_icon(GFX& d, int16_t x, int16_t y, IconId id, uint16_t color) {
    draw_icon_xbm(d, x, y, id, color);
}


