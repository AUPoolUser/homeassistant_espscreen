#pragma once
// Saving power while the glass is dark (standby or Sleep at brightness 0). The backlight is already off then; this
// stops the two things that still run for nobody, and gives up nothing a lit screen needs:
//
// - drawing: LVGL pauses (ESPHome's own lvgl.pause), so nothing is rendered or sent to the panel. The model, the cards
//   and every change from Home Assistant keep being applied; LVGL draws the whole screen once when it resumes.
// - Wi-Fi: the radio dozes between the router's beacons (ESP-IDF's modem sleep, ESPHome's `light`). A lit screen keeps
//   the mode its YAML has, `none` from the core and from the YAML ESP Screens writes, so its messages never wait for a
//   beacon (firmware 0.2.74+); a dark one dozes, and gets its own mode back when it wakes. The connection stays up, so
//   Home Assistant still sees the screen and can wake it. ESPHome's high-performance request can't do this: it only
//   lets go of a `none` the YAML does not have, and every screen's YAML has it.
//
// enter() comes a moment after the screen went dark, once the backlight has faded out (packages/core.yaml,
// screen_power_rest); leave() comes first in every wake, before the backlight comes up. A touch on the dark glass
// resumes drawing at once (touched()), so the touch reaches the wake overlay as it always did. A moment after the
// finger lifted, once LVGL has had the release (settled()), a screen that is still dark had a tap LVGL did not see:
// one of TAP_MS or more wakes it, a shorter one is noise on the glass and the screen rests again. Free of LVGL and
// ESPHome; core.yaml hands it the hooks at boot.
#include <cstdint>
#include <functional>
// In the firmware: ESP-IDF's Wi-Fi, for doze_wifi() and wifi_mode() below (core.yaml keeps no #if of its own: a line
// starting with # is a Jinja statement there).
#if __has_include("esphome/core/defines.h")
#include "esphome/core/defines.h"
#endif
#if defined(USE_ESP32) && defined(USE_WIFI)
#include <esp_wifi.h>
#endif

namespace screen_power {

inline std::function<void(bool)> draw;       // true: LVGL draws; false: paused
inline std::function<void(bool)> fast_wifi;  // true: Wi-Fi in its own mode; false: dozing
inline std::function<void()> wake;           // wakes the screen
inline std::function<void()> rest;           // saves again in a moment (screen_power_rest)
inline std::function<bool()> dark;           // the glass is still dark
inline std::function<void()> settle;         // calls settled() in a moment (screen_power_settle)
inline std::function<void(const char *)> note;  // the log, tag power

// The shortest touch on the dark glass that counts as a tap.
constexpr uint32_t TAP_MS = 30;

inline bool saving = false;
inline bool woken_by_touch = false;
inline uint32_t touch_start = 0;
inline bool was_tap = false;

inline void say(const char *what) {
  if (note) note(what);
}

inline void enter() {
  if (saving) return;
  saving = true;
  say("enter: the glass is dark, saving");
  if (fast_wifi) fast_wifi(false);
  if (draw) draw(false);
}

inline void leave() {
  if (!saving) return;
  saving = false;
  say("leave: awake again");
  if (fast_wifi) fast_wifi(true);
  if (draw) draw(true);
}

// A finger on the glass: drawing resumes before LVGL reads the touch again.
inline void touched(uint32_t now) {
  if (!saving) return;
  woken_by_touch = true;
  touch_start = now;
  say("touch on the dark glass: drawing resumes");
  leave();
}

// The finger lifted: the wake overlay gets its click on LVGL's next round, and settled() looks after that.
inline void released(uint32_t now) {
  if (!woken_by_touch) return;
  woken_by_touch = false;
  was_tap = now - touch_start >= TAP_MS;
  say(was_tap ? "touch lifted: a tap" : "touch lifted: too short for a tap");
  if (settle) settle();
}

inline void settled() {
  if (!dark || !dark()) {
    say("settled: the wake overlay woke the screen");
    return;
  }
  if (was_tap) {
    say("settled: LVGL missed the tap, waking here");
    if (wake) wake();
  } else {
    say("settled: noise, resting again");
    if (rest) rest();
  }
}

// Lets the radio doze (modem sleep) or gives it back the mode it had, which ESPHome set from the YAML. Answers what it
// changed, for the log, or nullptr when nothing changed (the minute's check of a dark screen).
inline const char *doze_wifi(bool doze) {
#if defined(USE_ESP32) && defined(USE_WIFI)
  static bool dozing = false;
  static wifi_ps_type_t own = WIFI_PS_NONE;
  wifi_ps_type_t now;
  if (esp_wifi_get_ps(&now) != ESP_OK) return "not started";
  if (doze) {
    if (!dozing) own = now;
    dozing = true;
    if (now != WIFI_PS_NONE) return nullptr;
    return esp_wifi_set_ps(WIFI_PS_MIN_MODEM) == ESP_OK ? "dozes (min modem)" : "doze FAILED";
  }
  if (!dozing) return nullptr;
  dozing = false;
  if (now == own) return "already in its own mode";
  return esp_wifi_set_ps(own) == ESP_OK ? "back in its own mode" : "wake FAILED";
#else
  (void) doze;
  return nullptr;
#endif
}

// The mode the radio really has.
inline const char *wifi_mode() {
#if defined(USE_ESP32) && defined(USE_WIFI)
  wifi_ps_type_t type;
  if (esp_wifi_get_ps(&type) != ESP_OK) return "unknown";
  return type == WIFI_PS_NONE ? "none (full speed)" : type == WIFI_PS_MIN_MODEM ? "min modem (dozes)" : "max modem (dozes)";
#else
  return "n/a";
#endif
}

}  // namespace screen_power
