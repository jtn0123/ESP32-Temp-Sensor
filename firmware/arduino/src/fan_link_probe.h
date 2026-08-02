#pragma once
// Copyright 2026 Justin
//
// Signal classifier for the iLiving fan's USB control link (Phase 0 of
// docs/GARAGE_FAN_CONTROLLER.md), so the ESP32 can be its own logic analyzer.
//
// The probe sketch (fan_probe_main.cpp) timestamps every edge on the tapped
// D+/D- lines; this header turns a batch of those edges into a verdict: quiet
// line, UART (with a baud guess), PWM (with period and duty), or unknown. Pure
// by the same rule as fan_control_pure.h -- no hardware, no clock, natively
// unit-tested -- because edge math full of off-by-ones is exactly the code
// that should not be debugged over a serial cable at the garage wall.
//
// Heuristics, not proof: the report always carries the raw pulse-width numbers
// so a human can overrule the verdict.

#include <cstddef>
#include <cstdint>

// One line transition. `level` is the line state AFTER the edge.
struct LinkEdge {
  uint32_t t_us;
  uint8_t level;
};

enum class LinkSignal : uint8_t {
  kQuiet,    // too few edges to say anything; read the DC level instead
  kUart,     // aperiodic bursts whose shortest pulse matches a standard baud
  kPwm,      // steady period; speed would be encoded in the duty cycle
  kUnknown,  // active line that fits neither pattern -- look at the raw numbers
};

struct LinkProbeReport {
  LinkSignal signal = LinkSignal::kQuiet;
  uint32_t edge_count = 0;
  uint32_t min_pulse_us = 0;
  uint32_t max_pulse_us = 0;
  uint32_t baud_guess = 0;  // nonzero only for kUart
  uint32_t period_us = 0;   // nonzero only for kPwm
  uint8_t duty_pct = 0;     // valid only for kPwm
};

// Bit times for the bauds a fan MCU vendor would plausibly ship.
inline uint32_t link_probe_baud_from_pulse(uint32_t pulse_us) {
  static const uint32_t kBauds[] = {1200, 2400, 4800, 9600, 19200, 38400, 57600, 115200};
  for (uint32_t baud : kBauds) {
    uint32_t bit_us = 1000000UL / baud;
    // Within 20% of one bit time. Integer math: |pulse - bit| * 5 <= bit.
    uint32_t diff = (pulse_us > bit_us) ? (pulse_us - bit_us) : (bit_us - pulse_us);
    if (diff * 5 <= bit_us)
      return baud;
  }
  return 0;
}

// Classify one channel's capture. Edges must be time-ordered.
inline LinkProbeReport link_probe_analyze(const LinkEdge* edges, size_t n) {
  LinkProbeReport r;
  r.edge_count = static_cast<uint32_t>(n);
  if (n < 4)
    return r;  // kQuiet: nothing meaningful to measure

  // Pulse widths between consecutive edges.
  uint32_t min_pulse = UINT32_MAX, max_pulse = 0;
  for (size_t i = 0; i + 1 < n; i++) {
    uint32_t w = edges[i + 1].t_us - edges[i].t_us;
    if (w < min_pulse)
      min_pulse = w;
    if (w > max_pulse)
      max_pulse = w;
  }
  r.min_pulse_us = min_pulse;
  r.max_pulse_us = max_pulse;

  // PWM first: a repeating rising-to-rising period. PWM at 50% duty has pulse
  // widths that also resemble a bit time, so periodicity must win the tie.
  uint32_t periods = 0, highs = 0, period_min = UINT32_MAX, period_max = 0;
  uint64_t period_sum = 0, high_sum = 0;
  uint32_t last_rise = 0;
  bool have_rise = false;
  for (size_t i = 0; i + 1 < n; i++) {
    if (edges[i].level == 1) {  // line high after this edge: a rising edge
      high_sum += edges[i + 1].t_us - edges[i].t_us;
      highs++;
      if (have_rise) {
        uint32_t p = edges[i].t_us - last_rise;
        periods++;
        period_sum += p;
        if (p < period_min)
          period_min = p;
        if (p > period_max)
          period_max = p;
      }
      have_rise = true;
      last_rise = edges[i].t_us;
    }
  }
  if (periods >= 3) {
    uint32_t mean = static_cast<uint32_t>(period_sum / periods);
    // Steady within 1/8 of the mean period counts as periodic.
    if (mean > 0 && (period_max - period_min) <= mean / 8) {
      r.signal = LinkSignal::kPwm;
      r.period_us = mean;
      // Mean high width over mean period; both are means so the one-extra
      // high pulse at the window edge cannot skew the ratio.
      uint32_t mean_high = static_cast<uint32_t>(high_sum / (highs ? highs : 1));
      r.duty_pct = static_cast<uint8_t>((static_cast<uint64_t>(mean_high) * 100) / mean);
      return r;
    }
  }

  uint32_t baud = link_probe_baud_from_pulse(min_pulse);
  if (baud != 0) {
    r.signal = LinkSignal::kUart;
    r.baud_guess = baud;
    return r;
  }

  r.signal = LinkSignal::kUnknown;
  return r;
}
