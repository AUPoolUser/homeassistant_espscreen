#pragma once
// A sensor's meter on the glass (firmware 0.56.0): meter_card.h plans it, this file paints the plan in one object per
// card, in that object's draw event.
#include "lvgl.h"

namespace runtime_tiles {
struct Widgets;
struct Tile;
}

namespace meter_view {
struct View;  // a card's plan and what it shows
// Draws the meter into the slot's extra layer, `width` x `height` (the card's content).
void render(runtime_tiles::Widgets &w, const runtime_tiles::Tile &t, int width, int height);
// The slot shows another card: its plan goes.
void release(runtime_tiles::Widgets &w);
}  // namespace meter_view
