// Unit tests for the fan link signal classifier (src/fan_link_probe.h).
// Compiled from the real header on platform = native — no hand-copied logic.

#include <unity.h>

#include <cstddef>

#include "../../src/fan_link_probe.h"

void setUp(void) {}
void tearDown(void) {}

// Test helper: append a level held for `dur_us`, emitting the edge that
// starts it. `t` advances; the first call sets the initial edge at t.
struct EdgeBuilder {
  LinkEdge edges[256];
  size_t n = 0;
  uint32_t t = 1000;  // arbitrary nonzero start

  void hold(uint8_t level, uint32_t dur_us) {
    edges[n].t_us = t;
    edges[n].level = level;
    n++;
    t += dur_us;
  }
};

// A dead line (or one edge of noise) is quiet, not a false UART hit.
void test_quiet_line(void) {
  LinkProbeReport r = link_probe_analyze(nullptr, 0);
  TEST_ASSERT_EQUAL(static_cast<int>(LinkSignal::kQuiet), static_cast<int>(r.signal));
  LinkEdge one[] = {{1000, 1}, {2000, 0}, {3000, 1}};
  r = link_probe_analyze(one, 3);
  TEST_ASSERT_EQUAL(static_cast<int>(LinkSignal::kQuiet), static_cast<int>(r.signal));
  TEST_ASSERT_EQUAL_UINT32(3, r.edge_count);
}

// A steady 1 kHz 30% wave is PWM with the right period and duty.
void test_pwm_classified_with_period_and_duty(void) {
  EdgeBuilder b;
  for (int i = 0; i < 10; i++) {
    b.hold(1, 300);
    b.hold(0, 700);
  }
  LinkProbeReport r = link_probe_analyze(b.edges, b.n);
  TEST_ASSERT_EQUAL(static_cast<int>(LinkSignal::kPwm), static_cast<int>(r.signal));
  TEST_ASSERT_UINT32_WITHIN(20, 1000, r.period_us);
  TEST_ASSERT_UINT8_WITHIN(3, 30, r.duty_pct);
}

// A 9600-baud byte burst (0xA5, LSB first, start/stop framing) is UART with
// the right baud guess, and its irregular rises must not read as PWM.
void test_uart_9600_burst(void) {
  EdgeBuilder b;
  const uint32_t bit = 104;  // ~1e6 / 9600
  for (int frames = 0; frames < 3; frames++) {
    b.hold(0, bit);            // start
    b.hold(1, bit);            // bit0 = 1
    b.hold(0, bit);            // bit1 = 0
    b.hold(1, bit);            // bit2 = 1
    b.hold(0, 2 * bit);        // bits 3,4 = 0
    b.hold(1, bit);            // bit5 = 1
    b.hold(0, bit);            // bit6 = 0
    b.hold(1, 2 * bit + 500);  // bit7 = 1, stop, idle gap
  }
  LinkProbeReport r = link_probe_analyze(b.edges, b.n);
  TEST_ASSERT_EQUAL(static_cast<int>(LinkSignal::kUart), static_cast<int>(r.signal));
  TEST_ASSERT_EQUAL_UINT32(9600, r.baud_guess);
  TEST_ASSERT_UINT32_WITHIN(4, bit, r.min_pulse_us);
}

// 115200 is also in the candidate table.
void test_baud_from_pulse_table(void) {
  TEST_ASSERT_EQUAL_UINT32(115200, link_probe_baud_from_pulse(9));
  TEST_ASSERT_EQUAL_UINT32(9600, link_probe_baud_from_pulse(104));
  TEST_ASSERT_EQUAL_UINT32(1200, link_probe_baud_from_pulse(833));
  // 300us is between the 4800 (208us) and 2400 (417us) bit times, outside
  // 20% of both: no guess.
  TEST_ASSERT_EQUAL_UINT32(0, link_probe_baud_from_pulse(300));
}

// Active but aperiodic pulses that match no baud land in kUnknown, with the
// raw pulse range preserved for the human.
void test_unknown_keeps_raw_numbers(void) {
  EdgeBuilder b;
  b.hold(0, 300);
  b.hold(1, 900);
  b.hold(0, 350);
  b.hold(1, 2000);
  b.hold(0, 320);
  b.hold(1, 5000);
  LinkProbeReport r = link_probe_analyze(b.edges, b.n);
  TEST_ASSERT_EQUAL(static_cast<int>(LinkSignal::kUnknown), static_cast<int>(r.signal));
  // The final 5000us hold has no closing edge, so the max measured width is
  // the 2000us pulse before it.
  TEST_ASSERT_EQUAL_UINT32(300, r.min_pulse_us);
  TEST_ASSERT_EQUAL_UINT32(2000, r.max_pulse_us);
}

// 50% PWM is the classifier's trap: its pulse width can sit within 20% of a
// bit time, so periodicity must win and call it PWM, not UART.
void test_fifty_percent_pwm_beats_uart_guess(void) {
  EdgeBuilder b;
  for (int i = 0; i < 10; i++) {
    b.hold(1, 500);  // 500us pulses: within 20% of the 2400-baud bit (417us)
    b.hold(0, 500);
  }
  LinkProbeReport r = link_probe_analyze(b.edges, b.n);
  TEST_ASSERT_EQUAL(static_cast<int>(LinkSignal::kPwm), static_cast<int>(r.signal));
  TEST_ASSERT_UINT8_WITHIN(3, 50, r.duty_pct);
}

int main(int argc, char** argv) {
  UNITY_BEGIN();
  RUN_TEST(test_quiet_line);
  RUN_TEST(test_pwm_classified_with_period_and_duty);
  RUN_TEST(test_uart_9600_burst);
  RUN_TEST(test_baud_from_pulse_table);
  RUN_TEST(test_unknown_keeps_raw_numbers);
  RUN_TEST(test_fifty_percent_pwm_beats_uart_guess);
  UNITY_END();
  return 0;
}
