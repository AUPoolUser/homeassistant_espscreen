// A sensor's meter (firmware 0.56.0, model/meter.ts): its options as the add-on keeps them (meter.validate), the
// thresholds and range the inspector starts from, and the face on the mockup at every span of every grid.
import { describe, expect, it } from "vitest";
import { canonicalOptions } from "../src/model/tile-options";
import { ems, meterColors, meterLayout, meterThresholds, startThresholds, suggestRange, tapeTicks, zoneColor, type MeterInput, type MeterStyle, type TextBox } from "../src/model/meter";
import { tileFace } from "../src/model/tile-face";
import rules from "../src/model/page-rules.json";

describe("the meter's options (meter.validate)", () => {
  it("keeps no default and nothing of the meter on another display or another domain", () => {
    expect(canonicalOptions("sensor.co2", { display: "meter", meter: "ring", segments: 1, colors: undefined, thresholds: [] })).toEqual({ display: "meter" });
    expect(canonicalOptions("sensor.co2", { display: "meter", segments: 2, colors: ["green", "red"], thresholds: [1360] }))
      .toEqual({ display: "meter", segments: 2, thresholds: [1360] });
    expect(canonicalOptions("sensor.co2", { display: "meter", segments: 3, colors: ["red", "orange", "green"], thresholds: [20, 50], min: 0, max: 100, meter: "bar" }))
      .toEqual({ display: "meter", segments: 3, colors: ["red", "orange", "green"], thresholds: [20, 50], min: 0, max: 100, meter: "bar" });
    // One end of a range is no range; a range the wrong way round neither.
    expect(canonicalOptions("sensor.co2", { display: "meter", min: 400 })).toEqual({ display: "meter" });
    expect(canonicalOptions("sensor.co2", { display: "meter", min: 10, max: 5 })).toEqual({ display: "meter" });
    // One segment keeps a colour of its own and no thresholds.
    expect(canonicalOptions("sensor.co2", { display: "meter", colors: ["blue"], thresholds: [5] })).toEqual({ display: "meter", colors: ["blue"] });
    expect(canonicalOptions("sensor.co2", { display: "graph", meter: "tape", min: 0, max: 5, segments: 2, colors: ["green", "red"], thresholds: [4] })).toEqual({ display: "graph" });
    expect(canonicalOptions("light.a", { display: "meter", meter: "tape" })).toEqual({ display: "meter" });
  });

  it("starts the thresholds at 80 % and 90 % of the range, in round numbers of the sensor's unit", () => {
    expect(startThresholds(400, 1600, 3)).toEqual([1360, 1480]);
    expect(startThresholds(16, 26, 3)).toEqual([24, 25]);
    expect(startThresholds(0, 100, 3)).toEqual([80, 90]);
    expect(startThresholds(0, 3000, 3)).toEqual([2400, 2700]);
    expect(startThresholds(0, 100, 2)).toEqual([80]);
    expect(startThresholds(0, 100, 1)).toEqual([]);
    // Without thresholds of its own the screen puts them there too.
    expect(meterThresholds({ display: "meter", segments: 3, min: 400, max: 1600 })).toEqual([1360, 1480]);
    expect(meterColors({ display: "meter", segments: 3 })).toEqual(rules.meter.defaultColors["3"]);
  });

  it("paints a value in its segment's colour, or the tile's own with one segment", () => {
    const options = { display: "meter", segments: 3, thresholds: [800, 1200], min: 400, max: 1600 };
    expect(zoneColor(600, options, "#123456")).toBe(rules.meter.colors.green);
    expect(zoneColor(800, options, "#123456")).toBe(rules.meter.colors.orange);
    expect(zoneColor(1500, options, "#123456")).toBe(rules.meter.colors.red);
    expect(zoneColor(1500, { display: "meter" }, "#123456")).toBe("#123456");
    expect(zoneColor(1500, { display: "meter", colors: ["blue"] }, "#123456")).toBe(rules.meter.colors.blue);
  });

  it("suggests a range of its own that holds the value", () => {
    expect(suggestRange(840)).toEqual([0, 1000]);
    expect(suggestRange(-12)).toEqual([-20, 0]);
    expect(suggestRange(840, [420, 600, null, 1210])).toEqual([400, 1300]);
    const [low, high] = suggestRange(21.4, [19.2, 20.1, 23.8]);
    expect(low).toBeLessThanOrEqual(19.2); expect(high).toBeGreaterThanOrEqual(23.8);
  });

  it("is a face of its own for a sensor at every size", () => {
    const face = (columns: number, rows: number, full = false) => tileFace({ entity: "sensor.co2", options: { display: "meter" }, shape: { columns, rows }, full, wide: columns > 1,
      live: { state: "840", a: { unit_of_measurement: "ppm" } }, chosen: null, rangeReady: true, bigKeys: true, favorite: false, plugin: false, pluginRow: false, watch: false }).kind;
    for (const [c, r] of [[1, 1], [2, 1], [1, 2], [2, 2], [3, 2]]) expect(face(c, r)).toBe("meter");
    expect(face(4, 3, true)).toBe("meter");
  });
});

describe("the meter on the mockup, at every span (model/meter.ts meterLayout)", () => {
  // Cards as the editor draws them: a cell of 60 to 220 px wide and 40 to 200 px high (the CYD to the ten-inch glass),
  // and every span of a landscape or a standing grid up to the whole page.
  const cells = [[70, 52], [110, 80], [150, 110], [200, 150], [80, 110], [120, 170], [60, 40], [220, 130]];
  const spans = [[1, 1], [2, 1], [1, 2], [2, 2], [3, 1], [3, 2], [2, 3], [4, 2], [4, 3], [3, 4], [1, 3], [5, 4]];
  const styles: MeterStyle[] = ["ring", "tape", "bar"];
  const texts = { valueText: "1,184 ppm", number: "1,184", unit: "ppm", name: "Office CO2" };
  const inside = (box: { x: number; y: number; w: number; h: number }, w: number, h: number) =>
    box.x >= -0.5 && box.y >= -0.5 && box.x + box.w <= w + 0.5 && box.y + box.h <= h + 0.5;
  const textRect = (t: TextBox) => ({ x: t.x, y: t.y, w: t.w, h: t.size * 1.2 });
  const apart = (a: { x: number; y: number; w: number; h: number }, b: { x: number; y: number; w: number; h: number }) =>
    a.x + a.w <= b.x + 0.5 || b.x + b.w <= a.x + 0.5 || a.y + a.h <= b.y + 0.5 || b.y + b.h <= a.y + 0.5;

  for (const style of styles) it(`keeps every part of the ${style} on the card and its words apart`, () => {
    for (const [cw, ch] of cells) for (const [c, r] of spans) for (const history of [false, true]) {
      const width = cw * c, height = ch * r, glass = 0.7;
      const input: MeterInput = { style, width, height, glass, ...texts, ends: ["400", "1,600"], history };
      const layout = meterLayout(input), where = `${style} ${c}x${r} of ${cw}x${ch}`;
      const words: { x: number; y: number; w: number; h: number }[] = [];
      if (layout.kind === "ring") {
        const ring = { x: layout.cx - layout.r - layout.stroke / 2, y: layout.cy - layout.r - layout.stroke / 2, w: 2 * layout.r + layout.stroke, h: 1.5 * layout.r + layout.stroke };
        expect(inside(ring, width, height), where).toBe(true);
        words.push(textRect(layout.value));
        if (layout.name) words.push(textRect(layout.name));
        for (const word of words) expect(inside(word, width, height), where).toBe(true);
        if (layout.line) { expect(inside(layout.line, width, height), where).toBe(true); expect(apart(layout.line, ring), where).toBe(true); }
        // Beside the ring the words keep out of it.
        if (layout.value.align === "left") for (const word of words) expect(apart(word, ring), where).toBe(true);
        expect(layout.value.size, where).toBeGreaterThanOrEqual(6);
      } else if (layout.kind === "tape") {
        if (layout.name) words.push(textRect(layout.name));
        words.push(textRect(layout.value));
        for (const word of words) expect(inside(word, width, height), where).toBe(true);
        const ruler = { x: layout.x0, y: layout.pointer.y1, w: layout.x1 - layout.x0, h: layout.pointer.y2 - layout.pointer.y1 };
        expect(inside(ruler, width, height), where).toBe(true);
        for (const word of words) expect(apart(word, ruler), where).toBe(true);
        if (layout.ends) {
          // Each end's number centred under its tick, inside the card.
          const half = Math.max(ems("400"), ems("1,600")) * layout.ends.size / 2;
          expect(layout.x0 - half, where).toBeGreaterThanOrEqual(-0.5);
          expect(layout.x1 + half, where).toBeLessThanOrEqual(width + 0.5);
          expect(layout.ends.y + layout.ends.size * 1.2, where).toBeLessThanOrEqual(height + 0.5);
        }
      } else {
        words.push(textRect(layout.value));
        if (layout.name) words.push(textRect(layout.name));
        for (const word of words) expect(inside(word, width, height), where).toBe(true);
        const cells = layout.cells;
        expect(inside(cells, width, height), where).toBe(true);
        for (const word of words) expect(apart(word, cells), where).toBe(true);
        // The cells fill all the room under the words (or the right of a standing card) to the card's edge.
        expect(cells.y + cells.h, where).toBeCloseTo(height, 0);
        if (!cells.vertical) expect(cells.w, where).toBeCloseTo(width, 0);
        else expect(cells.x + cells.w, where).toBeCloseTo(width, 0);
      }
      if (words.length > 1) expect(apart(words[0], words[1]), where).toBe(true);
    }
  });

  it("grows the ring with its card and stands the bar up on a standing card", () => {
    const ring = (w: number, h: number) => (meterLayout({ style: "ring", width: w, height: h, glass: 1, ...texts, ends: null, history: false }) as any).r;
    expect(ring(200, 200)).toBeGreaterThan(ring(100, 100));
    expect(ring(400, 400)).toBeGreaterThan(ring(200, 200));
    const bar = (w: number, h: number) => (meterLayout({ style: "bar", width: w, height: h, glass: 1, ...texts, ends: null, history: false }) as any).cells;
    expect(bar(100, 220).vertical).toBe(true);
    expect(bar(100, 220).w).toBeCloseTo(30, 0);
    expect(bar(220, 100).vertical).toBe(false);
    // A roomy wide card gives the right half to the last hours, one cell never.
    const line = (w: number, h: number, glass = 1) => (meterLayout({ style: "ring", width: w, height: h, glass, ...texts, ends: null, history: true }) as any).line;
    expect(line(420, 160)).not.toBeNull();
    expect(line(160, 160)).toBeNull();
    expect(line(420, 160, 1.5)).toBeNull();
  });

  it("rules a still tape of at most five long ticks with its ends among them", () => {
    for (const [low, high] of [[16, 26], [400, 1600], [0, 7], [0, 100], [-20, 40], [0, 3000]]) {
      const ticks = tapeTicks(low, high, 10, 210);
      const longs = ticks.filter((tick) => tick.long);
      expect(longs.length).toBeLessThanOrEqual(5);
      expect(longs[0].x).toBe(10); expect(longs.at(-1)!.x).toBe(210);
      expect(ticks.every((tick) => tick.x >= 10 && tick.x <= 210)).toBe(true);
    }
  });
});
