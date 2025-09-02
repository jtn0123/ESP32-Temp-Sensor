// Error tracking implementation
#include "error_codes.h"

// Global error tracking variables
ErrorContext g_last_error = {ERR_NONE, nullptr, nullptr, 0, 0, 0};
uint32_t g_error_count = 0;