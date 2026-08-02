#pragma once
// Copyright 2026 Justin
//
// Delta-T garage ventilation policy as a pure value type.
//
// The stock iLiving controller only knows the room's own temperature, so in a
// hot climate it happily pulls 110-degree outside air into the garage. This
// policy uses both sides of the wall: it vents only when outside air is cooler
// than inside air, ramps speed with the size of that win, and respects a noise
// cap that is lower than the fan's 12-step maximum.
//
// Pure by the same rule as power_pure.h / system_pure.h: the clock and both
// temperatures are injected, nothing here touches hardware or MQTT, and the
// native test suite exercises the exact code the device runs. The actuation
// layer (UART frame, PWM duty, or button-press emulation -- see
// docs/GARAGE_FAN_CONTROLLER.md) consumes the returned speed.
//
// Temperatures are unit-agnostic: feed both in the same unit and express the
// thresholds in that unit. The defaults below assume Fahrenheit.

#include <cmath>
#include <cstdint>

// Fan hardware's speed range is 0..12 (iLiving ILG8SF12V-DC).
#ifndef FAN_SPEED_MAX_HW
#define FAN_SPEED_MAX_HW 12
#endif

enum class FanState : uint8_t {
  kFailsafe,  // stale or invalid inputs: the fan must never run on frozen data
  kLockout,   // outside hotter than inside: venting makes the garage worse
  kTrickle,   // outside barely cooler: not worth more than a whisper
  kVent,      // outside meaningfully cooler: ramp with the delta
  kTarget,    // inside reached the target temp: done for the day
};

struct FanControlConfig {
  // delta = t_inside - t_outside. Positive means outside is cooler.
  float delta_on = 3.0f;     // enter VENT at this delta
  float delta_full = 10.0f;  // delta at which the ramp reaches max_speed_cap
  float hysteresis = 1.0f;   // exit thresholds are this much easier than entry

  uint8_t min_speed = 1;      // TRICKLE speed and the bottom of the VENT ramp
  uint8_t max_speed_cap = 8;  // noise ceiling; the motor's 12 is not the limit
  uint8_t standby_speed = 0;  // LOCKOUT speed (0, or 1-2 for a minimum stir)
  uint8_t failsafe_speed = 0;

  // Inside temp at or below this parks the fan in TARGET. NAN disables.
  float target_temp = NAN;

  // Minimum time between state changes, so boundary noise cannot flap the
  // fan. FAILSAFE and LOCKOUT entry are exempt: safety does not wait, and a
  // venting fan must stop pulling hot air the moment the delta flips.
  uint32_t dwell_ms = 5UL * 60UL * 1000UL;

  // Speed slews at most one step per this interval (default +-2/minute), so
  // ramps are gradual instead of lurching between quiet and loud.
  uint32_t slew_ms = 30UL * 1000UL;
};

struct FanController {
  FanState state = FanState::kFailsafe;
  uint8_t speed = 0;

  // `have_*` flags are authoritative, per the power_pure.h convention:
  // millis() really does return 0 for the first millisecond after boot, so a
  // "0 means never" shortcut would be a bug.
  bool have_change_ms = false;
  uint32_t last_change_ms = 0;
  bool have_slew_ms = false;
  uint32_t last_slew_ms = 0;

  // One control iteration. `fresh` is the caller's staleness verdict for BOTH
  // temperatures (each newer than its stale_after budget and the broker
  // reachable). Returns the speed to actuate, 0..FAN_SPEED_MAX_HW.
  uint8_t tick(float t_inside, float t_outside, bool fresh, uint32_t now_ms,
               const FanControlConfig& cfg) {
    FanState desired = classify(t_inside, t_outside, fresh, cfg);

    if (desired != state) {
      // FAILSAFE and LOCKOUT enter immediately; everything else waits out the
      // dwell. Exit from either still dwells, so a boundary cannot flap.
      bool dwell_over = !have_change_ms || (now_ms - last_change_ms) >= cfg.dwell_ms;
      if (desired == FanState::kFailsafe || desired == FanState::kLockout || dwell_over) {
        state = desired;
        have_change_ms = true;
        last_change_ms = now_ms;
      }
    }

    uint8_t goal = goal_speed(t_inside, t_outside, cfg);

    if (state == FanState::kFailsafe || state == FanState::kLockout) {
      // Snap: a fan running blind, or pulling hotter air in, gets stopped
      // now, not slewed down.
      speed = goal;
      have_slew_ms = false;
      return speed;
    }

    if (speed == goal)
      return speed;
    if (!have_slew_ms || (now_ms - last_slew_ms) >= cfg.slew_ms) {
      speed = (goal > speed) ? static_cast<uint8_t>(speed + 1) : static_cast<uint8_t>(speed - 1);
      have_slew_ms = true;
      last_slew_ms = now_ms;
    }
    return speed;
  }

 private:
  // Where the inputs say we should be, with exit thresholds loosened by the
  // hysteresis so a reading dancing on a boundary cannot flip the state.
  FanState classify(float t_inside, float t_outside, bool fresh,
                    const FanControlConfig& cfg) const {
    // isfinite, not !isnan: an infinity would sail through the delta math and
    // could park the policy in VENT at the cap on garbage data.
    if (!fresh || !std::isfinite(t_inside) || !std::isfinite(t_outside))
      return FanState::kFailsafe;

    if (!std::isnan(cfg.target_temp)) {
      bool in_target = (state == FanState::kTarget);
      float exit_at = cfg.target_temp + cfg.hysteresis;
      if (in_target ? (t_inside <= exit_at) : (t_inside <= cfg.target_temp))
        return FanState::kTarget;
    }

    float delta = t_inside - t_outside;

    bool in_lockout = (state == FanState::kLockout);
    if (in_lockout ? (delta < cfg.hysteresis) : (delta <= 0.0f))
      return FanState::kLockout;

    bool in_vent = (state == FanState::kVent);
    float vent_at = in_vent ? (cfg.delta_on - cfg.hysteresis) : cfg.delta_on;
    if (delta >= vent_at)
      return FanState::kVent;

    return FanState::kTrickle;
  }

  uint8_t goal_speed(float t_inside, float t_outside, const FanControlConfig& cfg) const {
    uint8_t cap = (cfg.max_speed_cap > FAN_SPEED_MAX_HW) ? FAN_SPEED_MAX_HW : cfg.max_speed_cap;
    switch (state) {
      case FanState::kFailsafe:
        return (cfg.failsafe_speed > cap) ? cap : cfg.failsafe_speed;
      case FanState::kTarget:
        return 0;
      case FanState::kLockout:
        return (cfg.standby_speed > cap) ? cap : cfg.standby_speed;
      case FanState::kTrickle:
        return (cfg.min_speed > cap) ? cap : cfg.min_speed;
      case FanState::kVent:
        break;
    }
    // VENT: proportional ramp min_speed..cap across delta_on..delta_full.
    float delta = t_inside - t_outside;
    float span = cfg.delta_full - cfg.delta_on;
    float frac = (span > 0.0f) ? (delta - cfg.delta_on) / span : 1.0f;
    if (frac < 0.0f)
      frac = 0.0f;
    if (frac > 1.0f)
      frac = 1.0f;
    uint8_t lo = (cfg.min_speed > cap) ? cap : cfg.min_speed;
    return static_cast<uint8_t>(lo + std::lround(frac * (cap - lo)));
  }
};
