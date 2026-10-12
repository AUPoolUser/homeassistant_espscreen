#include "components/smart_display/screen_power.h"
#include <cassert>
#include <cstdio>
using namespace screen_power;

static bool paused = false, dark_now = false;
static int pauses = 0, wakes = 0;
static uint32_t waited = 0;

int main() {
  freeze = [](bool on) { paused = on; pauses++; };
  later = [](uint32_t ms) { waited = ms; };
  dark = [] { return dark_now; };
  wake = [] { wakes++; dark_now = false; leave(); };

  // Going dark: a wait, then saving; twice is once.
  dark_now = true;
  rest();
  assert(waited == REST_MS && !saving);
  due();
  due();
  assert(saving && paused && pauses == 1);
  // A wake before the wait ran: nothing saves.
  leave();
  leave();
  assert(!saving && !paused && pauses == 2);
  dark_now = false;
  due();
  assert(!saving);

  // A touch on the dark glass resumes drawing at once; the overlay woke the screen before due().
  dark_now = true;
  due();
  touched(1000);
  assert(!saving && !paused);
  released(1080);
  assert(waited == SETTLE_MS && settling && was_tap);
  rest();  // the minute's check while settling waits for the settling
  assert(waited == SETTLE_MS);
  dark_now = false;
  due();
  assert(wakes == 0 && !settling && !saving);

  // A tap LVGL did not see wakes the screen here.
  dark_now = true;
  due();
  touched(2000);
  released(2000 + TAP_MS);
  due();
  assert(wakes == 1 && !dark_now && !saving);

  // Noise shorter than a tap rests again.
  dark_now = true;
  due();
  touched(3000);
  released(3000 + TAP_MS - 1);
  waited = 0;
  due();
  assert(wakes == 1 && waited == REST_MS && !saving);
  due();
  assert(saving);

  // A touch while awake changes nothing.
  leave();
  dark_now = false;
  touched(4000);
  released(4100);
  assert(!touching && !settling);

  std::puts("screen_power OK");
}
