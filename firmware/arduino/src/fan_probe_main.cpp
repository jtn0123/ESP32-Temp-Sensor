// Copyright 2026 Justin
//
// Standalone Phase-0 sniffer for the iLiving fan's USB control link -- the
// ESP32 as its own logic analyzer (docs/GARAGE_FAN_CONTROLLER.md).
//
// Wiring: pass the fan-to-controller cable through a breakout, tap the two
// data conductors to PROBE_PIN_A / PROBE_PIN_B and share ground. MEASURE THE
// LINES WITH A MULTIMETER FIRST: these GPIOs are not 5 V tolerant, so a line
// that idles above 3.3 V needs a divider (10k series / 15k to ground) on each
// tap. Leave the stock controller connected and working -- this sketch only
// listens.
//
// Every 2 seconds it prints, per channel: the edge count, min/max pulse
// widths, the classifier's verdict (UART baud / PWM period+duty / quiet /
// unknown), and the idle DC level in millivolts. Step the stock controller
// through speeds 0-12 and write down what changes; that table becomes the
// actuator implementation.
//
// Build/flash: pio run -e feather_esp32s2_fan_probe -t upload && pio device monitor
// This file is excluded from every other env's build_src_filter.

#include <Arduino.h>

#include "fan_link_probe.h"

#ifndef PROBE_PIN_A
#define PROBE_PIN_A 18  // A0 on the Feather ESP32-S2: tap for one data line
#endif
#ifndef PROBE_PIN_B
#define PROBE_PIN_B 17  // A1: tap for the other data line
#endif
#ifndef PROBE_REPORT_MS
#define PROBE_REPORT_MS 2000
#endif

// Per-channel edge capture, filled by ISR, drained by loop(). 512 edges per
// window is ~50 UART bytes -- plenty to classify, small enough for stack copies.
static constexpr size_t kMaxEdges = 512;

struct ProbeChannel {
  volatile uint32_t t_us[kMaxEdges];
  volatile uint8_t level[kMaxEdges];
  volatile size_t count = 0;
  uint8_t pin = 0;
};

static ProbeChannel g_ch_a, g_ch_b;

static void IRAM_ATTR capture(ProbeChannel* ch) {
  size_t i = ch->count;
  if (i >= kMaxEdges)
    return;  // window full; loop() will drain and reset
  ch->t_us[i] = micros();
  ch->level[i] = static_cast<uint8_t>(digitalRead(ch->pin));
  ch->count = i + 1;
}

static void IRAM_ATTR isr_a() { capture(&g_ch_a); }
static void IRAM_ATTR isr_b() { capture(&g_ch_b); }

// Copy out and reset a channel with its interrupt held off, then classify.
static LinkProbeReport drain_and_analyze(ProbeChannel* ch) {
  static LinkEdge edges[kMaxEdges];  // static: too big for the loop task stack
  detachInterrupt(digitalPinToInterrupt(ch->pin));
  size_t n = ch->count;
  for (size_t i = 0; i < n; i++) {
    edges[i].t_us = ch->t_us[i];
    edges[i].level = ch->level[i];
  }
  ch->count = 0;
  attachInterrupt(digitalPinToInterrupt(ch->pin), (ch == &g_ch_a) ? isr_a : isr_b, CHANGE);
  return link_probe_analyze(edges, n);
}

static void print_report(const char* name, uint8_t pin, const LinkProbeReport& r) {
  Serial.printf("[%s pin %u] edges=%lu", name, pin, static_cast<unsigned long>(r.edge_count));
  switch (r.signal) {
    case LinkSignal::kQuiet:
      // ADC2 pins are free for analogRead here because WiFi is never started.
      Serial.printf(" QUIET idle=%lumV", static_cast<unsigned long>(analogReadMilliVolts(pin)));
      break;
    case LinkSignal::kUart:
      Serial.printf(" UART? baud~%lu pulse=%lu..%luus", static_cast<unsigned long>(r.baud_guess),
                    static_cast<unsigned long>(r.min_pulse_us),
                    static_cast<unsigned long>(r.max_pulse_us));
      break;
    case LinkSignal::kPwm:
      Serial.printf(" PWM? period=%luus duty=%u%%", static_cast<unsigned long>(r.period_us),
                    r.duty_pct);
      break;
    case LinkSignal::kUnknown:
      Serial.printf(" UNKNOWN pulse=%lu..%luus", static_cast<unsigned long>(r.min_pulse_us),
                    static_cast<unsigned long>(r.max_pulse_us));
      break;
  }
  Serial.println();
}

void setup() {
  Serial.begin(115200);
  delay(2000);  // let the USB CDC console attach
  Serial.println("fan link probe: tap D+/D- of the fan control cable, share GND.");
  Serial.println("Lines above 3.3V need a divider. Step the stock controller 0-12");
  Serial.println("and note what changes per speed.");

  g_ch_a.pin = PROBE_PIN_A;
  g_ch_b.pin = PROBE_PIN_B;
  pinMode(PROBE_PIN_A, INPUT);
  pinMode(PROBE_PIN_B, INPUT);
  attachInterrupt(digitalPinToInterrupt(PROBE_PIN_A), isr_a, CHANGE);
  attachInterrupt(digitalPinToInterrupt(PROBE_PIN_B), isr_b, CHANGE);
}

void loop() {
  delay(PROBE_REPORT_MS);
  LinkProbeReport a = drain_and_analyze(&g_ch_a);
  LinkProbeReport b = drain_and_analyze(&g_ch_b);
  print_report("A", PROBE_PIN_A, a);
  print_report("B", PROBE_PIN_B, b);
}
