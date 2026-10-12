<script setup lang="ts">
// A sensor's meter (firmware 0.56.0, docs/METER.md) on the mockup: where its value stands in its range, as a 240° ring
// with the tile's icon, a still ruler with one pointer, or a bar of cells filling the card. Drawn in the room the card
// has on the page (measured), with its parts placed by model/meter.ts so nothing overflows at any size; its colours
// are the tile's own or its segments', Home Assistant's.
import { computedAsync, useResizeObserver } from "@vueuse/core";
import { computed, ref } from "vue";
import theme from "virtual:esp-screens-theme";
import { glyph } from "../../model/topbar";
import { numberText } from "../../i18n";
import { ownWords } from "../../model/tile-text";
import { arcPath, ems, meterLayout, meterRange, meterSegments, meterStyle, POINTER, share, tapeTicks, tint, zoneColor, type TextBox } from "../../model/meter";
import type { TileCardView } from "../../composables/useTileCard";
import { useEntitiesStore } from "../../stores/entities";
import { useRegionStore } from "../../stores/region";

const props = defineProps<{ card: TileCardView }>();
const card = props.card;
const entities = useEntitiesStore();
const region = useRegionStore();

const hex = (role: string) => `#${theme.roles[role].light.toString(16).padStart(6, "0")}`;
const CARD = hex("CARD"), TRACK = hex("TRACK"), TICK = hex("TICK"), MUTED = hex("MUTED"), INK = hex("INK");

const root = ref<HTMLElement | null>(null);
const room = ref({ width: 0, height: 0 });
useResizeObserver(root, ([entry]) => { room.value = { width: entry.contentRect.width, height: entry.contentRect.height }; });

const options = computed(() => card.tile.options);
const style = computed(() => meterStyle(options.value));
const range = computed(() => meterRange(options.value));
const value = computed(() => (card.gone ? NaN : Number(card.current?.state)));
const known = computed(() => Number.isFinite(value.value));
// A duration's own words carry their units (tile-text ownWords).
const unit = computed(() => (ownWords("sensor", card.current) ? "" : String(card.current?.a?.unit_of_measurement ?? "")));
const percent = computed(() => unit.value === "%");
const glass = computed(() => card.glassScale || 1);
// The colour of the value: its segment's, or the tile's own; a tape's pointer is deep orange unless the tile has colours.
const own = computed(() => card.palette.accent);
const color = computed(() => (known.value ? zoneColor(value.value, options.value, own.value) : hex("OFF")));
const pointer = computed(() => (known.value && (meterSegments(options.value) > 1 || Array.isArray(options.value?.colors)) ? color.value : POINTER));
const fraction = computed(() => (known.value ? share(value.value, range.value) : 0));
const end = (n: number) => numberText(String(n), region.numberMarks);

// The last 24 hours beside a ring on a roomy wide card: asked only for such a card (and kept a minute by the store).
const wantsLine = computed(() => style.value === "ring" && room.value.width / glass.value >= 360 && room.value.width > 1.3 * room.value.height);
const history = computedAsync(async () => {
  if (!wantsLine.value) return null;
  try { return await entities.loadHistory(card.tile.entity, 24); } catch { return null; }
}, null);
const values = computed(() => (history.value?.values ?? []).filter((v): v is number => v !== null && Number.isFinite(v)));

// The browser's own widths of the words, in the card's letters at the value's weight: a hidden word of the face is
// measured (the estimate where nothing is drawn, as in the tests).
const ruler = ref<HTMLElement | null>(null);
function measure(text: string) {
  const el = ruler.value;
  if (!el) return ems(text);
  el.textContent = text;
  const width = el.getBoundingClientRect().width;
  return width > 0 ? (width / 100) * 1.03 : ems(text);
}
const layout = computed(() => room.value.width > 0 && room.value.height > 0 ? meterLayout({
  style: style.value, width: room.value.width, height: room.value.height, glass: glass.value,
  valueText: card.texts.status, number: card.texts.value, unit: card.gone ? "" : unit.value, name: card.texts.name,
  ends: percent.value ? null : [end(range.value[0]), end(range.value[1])], history: values.value.length > 1, measure,
}) : null);

const box = (b: TextBox) => ({ left: `${b.x}px`, top: `${b.y}px`, width: `${b.w}px`, fontSize: `${b.size}px`, textAlign: b.align });

// ---- The ring ----
const ring = computed(() => (layout.value?.kind === "ring" ? layout.value : null));
const line = computed(() => {
  const l = ring.value?.line, list = history.value?.values ?? [];
  if (!l || values.value.length < 2) return null;
  const low = Math.min(...values.value), high = Math.max(...values.value), pad = 2;
  const x = (i: number) => l.x + (i / Math.max(1, list.length - 1)) * l.w;
  const y = (v: number) => l.y + l.h - pad - (high > low ? (v - low) / (high - low) : 0.5) * (l.h - 2 * pad - 4);
  const points = list.map((v, i) => (v !== null && Number.isFinite(v) ? [x(i), y(v)] : null)).filter((p): p is number[] => !!p);
  const path = points.map(([px, py], i) => `${i ? "L" : "M"}${px.toFixed(1)} ${py.toFixed(1)}`).join(" ");
  const fill = `${path} L${points.at(-1)![0].toFixed(1)} ${l.y + l.h} L${points[0][0].toFixed(1)} ${l.y + l.h} Z`;
  return { path, fill };
});

// ---- The tape ----
const tape = computed(() => (layout.value?.kind === "tape" ? layout.value : null));
const ticks = computed(() => (tape.value ? tapeTicks(range.value[0], range.value[1], tape.value.x0, tape.value.x1, 5 * glass.value) : []));
const pointerX = computed(() => (tape.value ? tape.value.x0 + fraction.value * (tape.value.x1 - tape.value.x0) : 0));

// ---- The bar: lit cells in the colour of their place, unlit ones a dimmed tint of it ----
const bar = computed(() => (layout.value?.kind === "bar" ? layout.value : null));
const cells = computed(() => {
  const b = bar.value?.cells;
  if (!b) return [];
  const [low, high] = range.value, out: { x: number; y: number; w: number; h: number; fill: string }[] = [];
  const length = b.vertical ? b.h : b.w, pitch = (length + b.gap) / b.count, size = pitch - b.gap;
  for (let i = 0; i < b.count; i++) {
    const middle = (i + 0.5) / b.count, paint = known.value ? zoneColor(low + middle * (high - low), options.value, own.value) : hex("OFF");
    const fill = known.value && middle <= fraction.value ? paint : tint(paint, CARD, 0.22);
    out.push(b.vertical ? { x: b.x, y: b.y + b.h - (i + 1) * pitch + b.gap, w: b.w, h: size, fill } : { x: b.x + i * pitch, y: b.y, w: size, h: b.h, fill });
  }
  return out;
});
</script>

<template>
  <div ref="root" class="meter-face" :class="`meter-${style}`">
    <i ref="ruler" class="meter-ruler" aria-hidden="true"></i>
    <template v-if="ring">
      <svg class="meter-svg" aria-hidden="true">
        <path :d="arcPath(ring.cx, ring.cy, ring.r, 0, 1)" :stroke="TRACK" :stroke-width="ring.stroke" fill="none" stroke-linecap="round" />
        <path v-if="fraction > 0" :d="arcPath(ring.cx, ring.cy, ring.r, 0, Math.max(fraction, 0.005))" :stroke="color" :stroke-width="ring.stroke" fill="none" stroke-linecap="round" />
        <circle :cx="ring.cx" :cy="ring.cy" :r="ring.circle" :fill="tint(color, CARD, 0.2)" />
        <text class="mdi" :x="ring.cx" :y="ring.cy" :font-size="ring.icon" :fill="color" text-anchor="middle" dominant-baseline="central">{{ glyph(card.icon) }}</text>
        <template v-if="line">
          <path :d="line.fill" :fill="tint(color, CARD, 0.2)" stroke="none" />
          <path :d="line.path" :stroke="color" stroke-width="1.5" fill="none" stroke-linejoin="round" />
        </template>
      </svg>
      <span class="mv" :style="box(ring.value)">{{ card.texts.status }}</span>
      <span v-if="ring.name" class="mn nm" :style="box(ring.name)">{{ card.texts.name }}</span>
    </template>
    <template v-else-if="tape">
      <span v-if="tape.name" class="mn caps" :style="box(tape.name)">{{ card.texts.name }}</span>
      <span class="mv tape-value" :style="box(tape.value)">{{ card.texts.value }}<small v-if="unit && !card.gone" :style="{ fontSize: `${tape.unitSize}px` }">{{ unit }}</small></span>
      <svg class="meter-svg" aria-hidden="true">
        <line :x1="tape.x0" :x2="tape.x1" :y1="tape.base" :y2="tape.base" :stroke="TICK" :stroke-width="tape.hair" />
        <line v-for="(tick, i) in ticks" :key="i" :x1="tick.x" :x2="tick.x" :y1="tape.base" :y2="tape.base - (tick.long ? tape.long : tape.short)"
          :stroke="tick.long ? MUTED : TICK" :stroke-width="tape.hair" />
        <line v-if="known" :x1="pointerX" :x2="pointerX" :y1="tape.pointer.y1" :y2="tape.pointer.y2" :stroke="CARD" :stroke-width="tape.pointer.width + 2 * tape.hair" stroke-linecap="round" />
        <line v-if="known" :x1="pointerX" :x2="pointerX" :y1="tape.pointer.y1" :y2="tape.pointer.y2" :stroke="pointer" :stroke-width="tape.pointer.width" stroke-linecap="round" />
      </svg>
      <template v-if="tape.ends">
        <span class="mn end" :style="{ left: `${tape.x0}px`, top: `${tape.ends.y}px`, fontSize: `${tape.ends.size}px` }">{{ end(range[0]) }}</span>
        <span class="mn end" :style="{ left: `${tape.x1}px`, top: `${tape.ends.y}px`, fontSize: `${tape.ends.size}px` }">{{ end(range[1]) }}</span>
      </template>
    </template>
    <template v-else-if="bar">
      <span class="mv" :style="box(bar.value)">{{ card.texts.status }}</span>
      <span v-if="bar.name" class="mn nm" :style="box(bar.name)">{{ card.texts.name }}</span>
      <svg class="meter-svg" aria-hidden="true">
        <rect v-for="(c, i) in cells" :key="i" :x="c.x" :y="c.y" :width="c.w" :height="c.h" :fill="c.fill" />
      </svg>
    </template>
  </div>
</template>

<style scoped>
.meter-face { position: relative; flex: 1 1 auto; align-self: stretch; min-width: 0; min-height: 0; width: 100%; }
.meter-ruler { position: absolute; left: 0; top: 0; visibility: hidden; white-space: nowrap; font-size: 100px; font-weight: 600; font-style: normal; line-height: 1; pointer-events: none; }
.meter-svg { position: absolute; inset: 0; width: 100%; height: 100%; overflow: visible; }
.meter-face > span { position: absolute; line-height: 1.2; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.mv { font-weight: 600; color: v-bind(INK); letter-spacing: -0.01em; }
.mn { font-weight: 500; color: v-bind(MUTED); }
.meter-face .nm { font-size: inherit; }
.caps { text-transform: uppercase; letter-spacing: 0.04em; font-weight: 400; }
.tape-value { font-weight: 400; }
.tape-value small { display: inline; margin-left: 0.15em; font-weight: 400; color: v-bind(MUTED); }
.end { transform: translateX(-50%); overflow: visible !important; }
</style>
