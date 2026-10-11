#include "components/smart_display/screen_power.h"
#include <cassert>
#include <cstdio>
#include <string>
using namespace screen_power;

static std::string calls;
static bool lvgl_on = true, wifi_fast = true, dark_now = false;
static int wakes = 0, rests = 0, settles = 0;

int main() {
  draw = [](bool on) { lvgl_on = on; calls += on ? "D" : "d"; };
  fast_wifi = [](bool fast) { wifi_fast = fast; calls += fast ? "W" : "w"; };
  wake = [] { wakes++; dark_now = false; leave(); };
  rest = [] { rests++; };
  dark = [] { return dark_now; };
  settle = [] { settles++; };

  // Going dark: Wi-Fi lets go before drawing pauses; twice is once.
  dark_now = true;
  enter();
  enter();
  assert(saving && !lvgl_on && !wifi_fast && calls == "wd");
  // Waking: Wi-Fi and drawing back; twice is once; leave() without saving does nothing.
  leave();
  leave();
  assert(!saving && lvgl_on && wifi_fast && calls == "wdWD");

  // A touch on the dark glass resumes drawing at once; the overlay woke the screen before settled().
  enter();
  touched(1000);
  assert(!saving && lvgl_on);
  released(1080);
  assert(settles == 1 && was_tap);
  dark_now = false;
  settled();
  assert(wakes == 0 && rests == 0);

  // A tap LVGL did not see wakes the screen here.
  dark_now = true;
  enter();
  touched(2000);
  released(2000 + TAP_MS);
  settled();
  assert(wakes == 1 && rests == 0 && !dark_now);

  // Noise shorter than a tap rests again.
  dark_now = true;
  enter();
  touched(3000);
  released(3000 + TAP_MS - 1);
  settled();
  assert(wakes == 1 && rests == 1);

  // A touch while awake changes nothing.
  touched(4000);
  released(4100);
  assert(settles == 3 && !woken_by_touch);

  std::puts("screen_power OK");
}
