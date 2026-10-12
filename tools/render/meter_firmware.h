#pragma once
// Host renders of the meter (firmware 0.56.0): the firmware's own planner and painter (meter_card.h, meter_paint.h) on a
// board's real fonts and sizes, on every span its grid takes, so a look can be checked on every card without a screen.
// No device firmware includes this file (tools/render/meter_firmware.py builds it).
#include "esphome/components/lvgl/lvgl_esphome.h"
#include "../../components/smart_display/meter_paint.h"
#include <cassert>
#include <cstdio>
#include <string>
#include <vector>

namespace meter_firmware {
namespace mc = meter_card;
namespace mp = meter_paint;

struct Board {
  const char *name, *look;
  int width, height, dpi, cols, rows, top, footer, margin, gx, gy, radius, pad;
  std::array<const lv_font_t *, mc::FACES> faces;
};
// A sensor as the tile has it: its words, its range, its colours and its last day.
struct Scene {
  const char *name, *icon, *unit, *state;
  float low, high;
  int segments;
  std::array<uint32_t, 3> colors;
  std::array<float, 2> thresholds;
  uint32_t own;
  std::vector<float> history;
};

inline int cuts = 0, overflows = 0;

inline uint32_t codepoint(const std::string &s, size_t &at) {
  const auto c = static_cast<unsigned char>(s[at]);
  const int n = c < 0x80 ? 1 : c < 0xE0 ? 2 : c < 0xF0 ? 3 : 4;
  uint32_t cp = n == 1 ? c : n == 2 ? c & 0x1F : n == 3 ? c & 0x0F : c & 0x07;
  for (int i = 1; i < n && at + i < s.size(); ++i) cp = cp << 6 | (static_cast<unsigned char>(s[at + i]) & 0x3F);
  at += n;
  return cp;
}
inline int width_of(const std::string &s, const lv_font_t *f) {
  lv_point_t size;
  lv_text_get_size(&size, s.c_str(), f, 0, 0, LV_COORD_MAX, LV_TEXT_FLAG_NONE);
  return size.x;
}
inline mc::Measure measure(const Board &b) {
  mc::Measure m;
  for (int i = 0; i < mc::FACES; ++i) { m.line[i] = lv_font_get_line_height(b.faces[i]); m.base[i] = b.faces[i]->base_line; }
  const auto f = b.faces;
  m.width = [f](mc::Face face, const std::string &s) { return width_of(s, f[face]); };
  m.covers = [f](mc::Face face, const std::string &s) {
    lv_font_glyph_dsc_t g;
    for (size_t at = 0; at < s.size();) { const uint32_t cp = codepoint(s, at); if (cp != ' ' && !lv_font_get_glyph_dsc(f[face], &g, cp, 0)) return false; }
    return true;
  };
  return m;
}
inline std::string ends(float v) {
  char b[24];
  if (std::fabs(v - std::round(v)) < 1e-3f) snprintf(b, sizeof b, "%.0f", double(std::round(v)));
  else snprintf(b, sizeof b, "%.1f", double(v));
  return b;
}

struct Card { mp::Look look; };
inline void draw(lv_event_t *e) {
  auto *o = static_cast<lv_obj_t *>(lv_event_get_current_target(e));
  auto *c = static_cast<Card *>(lv_event_get_user_data(e));
  lv_area_t a;
  lv_obj_get_coords(o, &a);
  mp::paint(lv_event_get_layer(e), c->look, a.x1, a.y1);
}
inline std::vector<Card *> cards;

// One card of `cols` x `rows` cells of the board, with the scene in `style`, at (x, y) of `parent`.
inline void card(lv_obj_t *parent, const Board &b, const Scene &s, mc::Style style, int x, int y, int w, int h, const std::string &where) {
  auto *o = lv_obj_create(parent);
  lv_obj_remove_style_all(o);
  lv_obj_set_pos(o, x, y);
  lv_obj_set_size(o, w, h);
  lv_obj_set_style_bg_color(o, lv_color_hex(theme::hex(theme::CARD)), 0);
  lv_obj_set_style_bg_opa(o, LV_OPA_COVER, 0);
  lv_obj_set_style_radius(o, b.radius, 0);
  lv_obj_set_style_border_width(o, 1, 0);
  lv_obj_set_style_border_color(o, lv_color_hex(theme::hex(theme::LINE)), 0);
  auto *in = lv_obj_create(o);
  lv_obj_remove_style_all(in);
  const int cw = w - 2 * b.pad, ch = h - 2 * b.pad;
  lv_obj_set_pos(in, b.pad, b.pad);
  lv_obj_set_size(in, cw, ch);
  auto *c = new Card();
  cards.push_back(c);
  auto &v = c->look;
  v.faces = b.faces;
  char *end = nullptr;
  const float value = std::strtof(s.state, &end);
  v.value = end && *end == '\0' ? value : NAN;
  v.low = s.low; v.high = s.high;
  v.own = s.own;
  v.ground = theme::hex(theme::CARD);
  v.colours.segments = s.segments;
  v.colours.colors = s.colors;
  v.colours.thresholds = s.thresholds;
  v.icon = s.icon;
  v.history = s.history;
  mc::Data d;
  d.name = s.name; d.icon = s.icon;
  if (std::isfinite(v.value)) {
    d.number = s.state; d.unit = s.unit;
    d.words = d.number + (d.unit.empty() ? "" : d.unit == std::string("%") ? "%" : " " + d.unit);
  } else d.words = d.number = "Unavailable";
  d.percent = d.unit == "%";
  d.low = ends(s.low); d.high = ends(s.high);
  d.graph = v.history.size() >= 2;
  mc::plan(v.plan, measure(b), d, style, cw, ch, s.high - s.low);
  if (v.plan.cut) { cuts += v.plan.cut; fprintf(stdout, "CUT %s %d\n", where.c_str(), v.plan.cut); }
  // Everything inside the card's content: every word, the ring with its caps, the ruler and its pointer, the cells.
  const auto &p = v.plan;
  auto inside = [&](int x0, int y0, int x1, int y1, const char *what) {
    if (x0 < 0 || y0 < 0 || x1 > cw || y1 > ch) { ++overflows; fprintf(stdout, "OVERFLOW %s %s %d,%d..%d,%d in %dx%d\n", where.c_str(), what, x0, y0, x1, y1, cw, ch); }
  };
  for (auto &t : p.texts) {
    const int tw = width_of(t.s, b.faces[t.face]);
    const int tx = t.align == mc::LEFT ? t.x : t.align == mc::CENTRE ? t.x + (t.w - tw) / 2 : t.x + t.w - tw;
    inside(tx, t.y, tx + tw, t.y + lv_font_get_line_height(b.faces[t.face]), t.s.c_str());
  }
  if (p.ring) inside(p.cx - p.d / 2, p.cy - p.d / 2, p.cx + p.d / 2, p.cy + p.d / 4 + p.thick / 2, "ring");  // open at the bottom
  if (p.tape) inside(p.ruler.x - p.pointer / 2 - 1, p.ruler.y - p.over, p.ruler.right() + p.pointer / 2 + 1, p.ruler.bottom(), "ruler");
  if (p.bar) inside(p.cells.x, p.cells.y, p.cells.right(), p.cells.bottom(), "cells");
  if (p.graph) inside(p.line.x, p.line.y, p.line.right(), p.line.bottom(), "graph");
  lv_obj_add_event_cb(in, draw, LV_EVENT_DRAW_MAIN, c);
}

inline void save(lv_obj_t *root, const std::string &path) {
  lv_obj_update_layout(root);
  auto *buf = lv_snapshot_take(root, LV_COLOR_FORMAT_RGB888);
  assert(buf);
  FILE *fp = fopen(path.c_str(), "wb");
  assert(fp);
  fprintf(fp, "P6\n%d %d\n255\n", int(buf->header.w), int(buf->header.h));
  for (int y = 0; y < int(buf->header.h); ++y)
    for (int x = 0; x < int(buf->header.w); ++x) {
      const auto *q = buf->data + y * buf->header.stride + 3 * x;
      const uint8_t rgb[] = {q[2], q[1], q[0]};
      fwrite(rgb, 1, 3, fp);
    }
  fclose(fp);
  lv_draw_buf_destroy(buf);
}
inline void clear() { for (auto *c : cards) delete c; cards.clear(); }

// Every span the board's grid takes, one look, one scene: a sheet of cards at the board's own cell size.
inline void spans(const Board &b, const std::string &out, const Scene &s, const char *scene, mc::Style style, bool dark) {
  ui::configure(b.dpi, b.look);
  theme::set_dark(dark);
  const int cw = (b.width - 2 * b.margin - (b.cols - 1) * b.gx) / b.cols, ch = (b.height - b.top - b.footer - (b.rows - 1) * b.gy) / b.rows;
  const char *names[] = {"ring", "tape", "bar"};
  for (int r = 1; r <= b.rows; ++r)
    for (int c = 1; c <= b.cols; ++c) {
      const int w = c * cw + (c - 1) * b.gx, h = r * ch + (r - 1) * b.gy;
      auto *root = lv_obj_create(lv_screen_active());
      lv_obj_remove_style_all(root);
      lv_obj_set_size(root, w + 16, h + 16);
      lv_obj_set_style_bg_color(root, lv_color_hex(theme::hex(theme::PAGE)), 0);
      lv_obj_set_style_bg_opa(root, LV_OPA_COVER, 0);
      char where[160];
      snprintf(where, sizeof where, "%s-%s-%s-%dx%d%s", b.name, names[style], scene, c, r, dark ? "-dark" : "");
      card(root, b, s, style, 8, 8, w, h, where);
      save(root, out + "/" + where + ".ppm");
      lv_obj_delete(root);
      clear();
    }
}
}  // namespace meter_firmware
