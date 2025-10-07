// Stubs for diagnostic and boot-stage functions when diagnostic_test.cpp is excluded
#include <Arduino.h>

void diagnostic_test_init() {}
void diagnostic_test_loop() {}

void show_boot_stage(int stage) {
  // No-op in headless build
  (void)stage;
}


