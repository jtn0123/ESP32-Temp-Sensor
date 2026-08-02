// Unit tests for the delta-T ventilation policy (src/fan_control_pure.h).
// Compiled from the real header on platform = native — no hand-copied logic.

#include <unity.h>

#include <cmath>

#include "../../src/fan_control_pure.h"

void setUp(void) {}
void tearDown(void) {}

static FanControlConfig fast_cfg() {
  // Real dwell/slew are minutes; tests use small values and step now_ms.
  FanControlConfig cfg;
  cfg.dwell_ms = 100;
  cfg.slew_ms = 10;
  return cfg;
}

// Hot afternoon: outside hotter than inside must hold the fan off.
void test_lockout_when_outside_hotter(void) {
  FanController c;
  FanControlConfig cfg = fast_cfg();
  uint8_t s = c.tick(95.0f, 108.0f, true, 1000, cfg);
  TEST_ASSERT_EQUAL(static_cast<int>(FanState::kLockout), static_cast<int>(c.state));
  TEST_ASSERT_EQUAL_UINT8(0, s);
}

// Evening flip: outside drops well below inside; fan ramps one step per slew
// interval and levels off at the noise cap, not the motor's 12.
void test_vent_ramps_to_cap_not_hw_max(void) {
  FanController c;
  FanControlConfig cfg = fast_cfg();
  uint32_t now = 0;
  // delta = 15 >= delta_full, so the goal is the cap (8).
  for (int i = 0; i < 40; i++) {
    now += cfg.slew_ms;
    c.tick(95.0f, 80.0f, true, now, cfg);
  }
  TEST_ASSERT_EQUAL(static_cast<int>(FanState::kVent), static_cast<int>(c.state));
  TEST_ASSERT_EQUAL_UINT8(cfg.max_speed_cap, c.speed);
}

// The ramp is proportional: halfway between delta_on and delta_full lands
// halfway between min_speed and the cap.
void test_vent_ramp_is_proportional(void) {
  FanController c;
  FanControlConfig cfg = fast_cfg();  // delta_on=3, delta_full=10, min=1, cap=8
  uint32_t now = 0;
  // delta = 6.5 = midpoint of [3, 10] -> goal = 1 + round(0.5 * 7) = 5 (rounds up).
  for (int i = 0; i < 40; i++) {
    now += cfg.slew_ms;
    c.tick(90.0f, 83.5f, true, now, cfg);
  }
  TEST_ASSERT_EQUAL_UINT8(5, c.speed);
}

// Slew: speed moves at most one step per slew interval, so a big delta does
// not slam the fan from 0 to 8 in one tick.
void test_speed_slews_one_step_per_interval(void) {
  FanController c;
  FanControlConfig cfg = fast_cfg();
  c.tick(95.0f, 80.0f, true, 0, cfg);
  TEST_ASSERT_EQUAL_UINT8(1, c.speed);  // first step only
  c.tick(95.0f, 80.0f, true, 1, cfg);   // same interval: no further movement
  TEST_ASSERT_EQUAL_UINT8(1, c.speed);
  c.tick(95.0f, 80.0f, true, cfg.slew_ms, cfg);
  TEST_ASSERT_EQUAL_UINT8(2, c.speed);
}

// A delta dancing on the VENT threshold must not flap the state: entry needs
// delta_on, exit tolerates down to delta_on - hysteresis.
void test_vent_hysteresis_holds_state(void) {
  FanController c;
  FanControlConfig cfg = fast_cfg();
  uint32_t now = 0;
  for (int i = 0; i < 40; i++) {
    now += cfg.slew_ms;
    c.tick(90.0f, 86.0f, true, now, cfg);  // delta 4: VENT
  }
  TEST_ASSERT_EQUAL(static_cast<int>(FanState::kVent), static_cast<int>(c.state));
  // delta drops to 2.5: below entry (3) but above exit (3 - 1 = 2) -> stays.
  now += cfg.dwell_ms + 1;
  c.tick(90.0f, 87.5f, true, now, cfg);
  TEST_ASSERT_EQUAL(static_cast<int>(FanState::kVent), static_cast<int>(c.state));
  // delta drops to 1.5: below exit -> leaves VENT once dwell allows.
  now += cfg.dwell_ms + 1;
  c.tick(90.0f, 88.5f, true, now, cfg);
  TEST_ASSERT_EQUAL(static_cast<int>(FanState::kTrickle), static_cast<int>(c.state));
}

// Dwell: a state change within the dwell window is deferred, not taken.
void test_dwell_defers_state_change(void) {
  FanController c;
  FanControlConfig cfg = fast_cfg();
  c.tick(90.0f, 95.0f, true, 0, cfg);  // LOCKOUT at t=0
  TEST_ASSERT_EQUAL(static_cast<int>(FanState::kLockout), static_cast<int>(c.state));
  // Conditions now say VENT, but the dwell window is still open.
  c.tick(90.0f, 80.0f, true, 50, cfg);
  TEST_ASSERT_EQUAL(static_cast<int>(FanState::kLockout), static_cast<int>(c.state));
  // After the window closes the change goes through.
  c.tick(90.0f, 80.0f, true, cfg.dwell_ms + 1, cfg);
  TEST_ASSERT_EQUAL(static_cast<int>(FanState::kVent), static_cast<int>(c.state));
}

// Stale data stops the fan immediately: no dwell, no slew-down.
void test_stale_data_snaps_to_failsafe(void) {
  FanController c;
  FanControlConfig cfg = fast_cfg();
  uint32_t now = 0;
  for (int i = 0; i < 40; i++) {
    now += cfg.slew_ms;
    c.tick(95.0f, 80.0f, true, now, cfg);
  }
  TEST_ASSERT_EQUAL_UINT8(cfg.max_speed_cap, c.speed);
  // Broker went quiet 1ms after the last good tick: full stop, this tick.
  uint8_t s = c.tick(95.0f, 80.0f, false, now + 1, cfg);
  TEST_ASSERT_EQUAL(static_cast<int>(FanState::kFailsafe), static_cast<int>(c.state));
  TEST_ASSERT_EQUAL_UINT8(0, s);
}

// NAN from a sensor is as bad as no data at all.
void test_nan_input_is_failsafe(void) {
  FanController c;
  FanControlConfig cfg = fast_cfg();
  c.tick(NAN, 80.0f, true, 0, cfg);
  TEST_ASSERT_EQUAL(static_cast<int>(FanState::kFailsafe), static_cast<int>(c.state));
  TEST_ASSERT_EQUAL_UINT8(0, c.speed);
}

// Target reached: inside is cool enough, stop running the fan for sport.
// Exit needs target + hysteresis so the boundary cannot flap.
void test_target_parks_fan_until_warmed_past_hysteresis(void) {
  FanController c;
  FanControlConfig cfg = fast_cfg();
  cfg.target_temp = 75.0f;
  uint32_t now = 0;
  c.tick(74.0f, 70.0f, true, now, cfg);
  TEST_ASSERT_EQUAL(static_cast<int>(FanState::kTarget), static_cast<int>(c.state));
  TEST_ASSERT_EQUAL_UINT8(0, c.speed);
  // 75.5 is above target but inside the hysteresis band: stays parked.
  now += cfg.dwell_ms + 1;
  c.tick(75.5f, 70.0f, true, now, cfg);
  TEST_ASSERT_EQUAL(static_cast<int>(FanState::kTarget), static_cast<int>(c.state));
  // 76.5 clears target + hysteresis: back to work (delta 6.5 -> VENT).
  now += cfg.dwell_ms + 1;
  c.tick(76.5f, 70.0f, true, now, cfg);
  TEST_ASSERT_EQUAL(static_cast<int>(FanState::kVent), static_cast<int>(c.state));
}

// A standby speed keeps a low stir during LOCKOUT when configured.
void test_lockout_standby_speed(void) {
  FanController c;
  FanControlConfig cfg = fast_cfg();
  cfg.standby_speed = 2;
  uint32_t now = 0;
  for (int i = 0; i < 10; i++) {
    now += cfg.slew_ms;
    c.tick(95.0f, 108.0f, true, now, cfg);
  }
  TEST_ASSERT_EQUAL(static_cast<int>(FanState::kLockout), static_cast<int>(c.state));
  TEST_ASSERT_EQUAL_UINT8(2, c.speed);
}

// A cap above the hardware's 12 is clamped to 12.
void test_cap_clamped_to_hardware_max(void) {
  FanController c;
  FanControlConfig cfg = fast_cfg();
  cfg.max_speed_cap = 20;
  uint32_t now = 0;
  for (int i = 0; i < 60; i++) {
    now += cfg.slew_ms;
    c.tick(95.0f, 70.0f, true, now, cfg);
  }
  TEST_ASSERT_EQUAL_UINT8(FAN_SPEED_MAX_HW, c.speed);
}

// Recovery from FAILSAFE: fresh data resumes normal control (after dwell).
void test_failsafe_recovers_when_data_returns(void) {
  FanController c;
  FanControlConfig cfg = fast_cfg();
  c.tick(95.0f, 80.0f, false, 0, cfg);
  TEST_ASSERT_EQUAL(static_cast<int>(FanState::kFailsafe), static_cast<int>(c.state));
  uint32_t now = cfg.dwell_ms + 1;
  c.tick(95.0f, 80.0f, true, now, cfg);
  TEST_ASSERT_EQUAL(static_cast<int>(FanState::kVent), static_cast<int>(c.state));
  TEST_ASSERT_EQUAL_UINT8(1, c.speed);  // slews up from 0, no snap to 8
}

int main(int argc, char** argv) {
  UNITY_BEGIN();
  RUN_TEST(test_lockout_when_outside_hotter);
  RUN_TEST(test_vent_ramps_to_cap_not_hw_max);
  RUN_TEST(test_vent_ramp_is_proportional);
  RUN_TEST(test_speed_slews_one_step_per_interval);
  RUN_TEST(test_vent_hysteresis_holds_state);
  RUN_TEST(test_dwell_defers_state_change);
  RUN_TEST(test_stale_data_snaps_to_failsafe);
  RUN_TEST(test_nan_input_is_failsafe);
  RUN_TEST(test_target_parks_fan_until_warmed_past_hysteresis);
  RUN_TEST(test_lockout_standby_speed);
  RUN_TEST(test_cap_clamped_to_hardware_max);
  RUN_TEST(test_failsafe_recovers_when_data_returns);
  return UNITY_END();
}
