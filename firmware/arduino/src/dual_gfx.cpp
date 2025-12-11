#include "dual_gfx.h"

#if USE_DISPLAY

static DualGFX* g_dual_gfx_context = nullptr;

void set_dual_gfx_context(DualGFX* ctx) {
    g_dual_gfx_context = ctx;
}

DualGFX* get_dual_gfx_context() {
    return g_dual_gfx_context;
}

#endif // USE_DISPLAY


