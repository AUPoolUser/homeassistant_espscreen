<script setup lang="ts">
// A sensor's meter (firmware 0.56.0, docs/METER.md): its look (a ring, a tape or a bar of cells), its range (Home
// Assistant's, or one of the tile's own) and its colour (one, or two or three segments that change at thresholds in the
// sensor's own unit). What the add-on keeps is meter.validate's; a default is never stored (model/meter.ts).
import { computed, ref } from "vue";
import { PopoverContent, PopoverPortal, PopoverRoot, PopoverTrigger } from "reka-ui";
import { editorLanguage, editorNumber, languageMarks, t } from "../../i18n";
import { haRange, METER, meterColors, meterHex, meterColorNames, meterRange, meterSegments, meterStyle, meterThresholds, ownRange,
  startThresholds, suggestRange, type MeterStyle } from "../../model/meter";
import { unitSuffix } from "../../model/tile-text";
import { tilePalette } from "../../model/tile-palette";
import type { Tile } from "../../types";
import PropRow from "../ui/PropRow.vue";
import Section from "../ui/Section.vue";
import { setTileOption, setTileOptions } from "../../editor/tiles";
import { useEntitiesStore } from "../../stores/entities";
import { useInspectorStore } from "../../stores/inspector";

const entities = useEntitiesStore();
const insp = useInspectorStore();
const props = defineProps<{ tile: Tile }>();
const options = computed(() => props.tile.options);
const set = (changes: Record<string, unknown>) => setTileOptions(props.tile, changes);

const live = computed(() => entities.liveOf(props.tile.entity));
const unit = computed(() => String(live.value?.a?.unit_of_measurement ?? ""));
const value = computed(() => Number(live.value?.state));
const known = computed(() => live.value?.state !== undefined && live.value.state !== "" && Number.isFinite(value.value));
const shown = (n: number) => `${editorNumber(String(n))}${unitSuffix(unit.value)}`;

// ---- The look: drawn on the tile while the pointer rests on one, as the other choices of a tile are ----
const style = computed(() => meterStyle(options.value));
function preview(key: MeterStyle | null) {
  if (key && props.tile.id && key !== style.value) insp.optionPreview = { tileId: props.tile.id, key: "meter", value: key };
  else if (insp.optionPreview?.key === "meter") insp.optionPreview = null;
}
function pickStyle(key: MeterStyle) { preview(null); setTileOption(props.tile, "meter", key); }

// ---- The range: Home Assistant's (0 to 100, as its gauge card has it) or the tile's own ----
const own = computed(() => ownRange(options.value));
const range = computed(() => meterRange(options.value));
const outside = computed(() => !own.value && known.value && (value.value < haRange()[0] || value.value > haRange()[1]));
const drafts = ref<{ min?: string; max?: string }>({});
const rangeWrong = ref(false);
async function pickRange(kind: string) {
  if (kind === "ha") { drafts.value = {}; rangeWrong.value = false; set({ min: undefined, max: undefined }); return; }
  if (own.value) return;
  // A sensible start: the last day's low and high where Home Assistant has them, else 0 to a round number above the value.
  let history: (number | null)[] | null = null;
  if (unit.value !== "%") {
    try { history = (await entities.loadHistory(props.tile.entity, 24))?.values ?? null; } catch { history = null; }
  }
  const [min, max] = unit.value === "%" || !known.value ? haRange() : suggestRange(value.value, history);
  set({ min, max });
}
const parse = (text: string) => {
  const n = Number(text.replace(/\s/g, "").replace(",", "."));
  return text.trim() !== "" && Number.isFinite(n) ? n : null;
};
function commitRange() {
  const min = parse(drafts.value.min ?? String(range.value[0])), max = parse(drafts.value.max ?? String(range.value[1]));
  rangeWrong.value = min === null || max === null || !(min < max);
  if (rangeWrong.value) return;
  drafts.value = {};
  if (min !== range.value[0] || max !== range.value[1]) set({ min, max });
}
// A number to type over: the editor's decimal mark, no grouping, so what is read back is what was shown.
const fieldText = (n: number) => String(n).replace(".", languageMarks(editorLanguage()).decimal);

// ---- The colour: one segment (the tile's own colour unless chosen), or two or three with their thresholds ----
const segments = computed(() => meterSegments(options.value));
const colors = computed(() => meterColors(options.value));
const thresholds = computed(() => meterThresholds(options.value));
const tileColor = computed(() => tilePalette(props.tile.entity, live.value).accent);
const swatch = (name: string | null) => (name ? meterHex(name) : tileColor.value);
// Two or three segments start from the default colours and thresholds at 80 % and 90 % of the range, in round numbers.
function pickSegments(n: number) {
  if (n === segments.value) return;
  thresholdDrafts.value = {}; thresholdsWrong.value = false;
  set({ segments: n, colors: undefined, thresholds: n > 1 ? startThresholds(range.value[0], range.value[1], n) : undefined });
}
const open = ref(-1);
function pickColor(index: number, name: string | null) {
  open.value = -1;
  if (name === null) { set({ colors: undefined }); return; }
  const list = colors.value.map((color) => color ?? name);
  list[index] = name;
  set({ colors: list });
}
const thresholdDrafts = ref<Record<number, string>>({});
const thresholdsWrong = ref(false);
function commitThreshold(index: number) {
  const draft = thresholdDrafts.value[index];
  if (draft === undefined) return;
  const n = parse(draft), list = [...thresholds.value];
  if (n === null) { thresholdsWrong.value = true; return; }
  list[index] = n;
  thresholdsWrong.value = list.some((v, i) => i > 0 && list[i - 1] >= v);
  if (thresholdsWrong.value) return;
  delete thresholdDrafts.value[index];
  set({ thresholds: list });
}
const defaults = computed(() => !options.value?.colors && (segments.value === 1 ||
  JSON.stringify(thresholds.value) === JSON.stringify(startThresholds(range.value[0], range.value[1], segments.value))));
function reset() {
  thresholdDrafts.value = {}; thresholdsWrong.value = false; open.value = -1;
  set({ colors: undefined, thresholds: segments.value > 1 ? startThresholds(range.value[0], range.value[1], segments.value) : undefined });
}
const colorName = (name: string | null) => (name ? t(`editor.tile.meter.colors.${name}`) : t("editor.tile.meter.own_color"));
</script>

<template>
  <Section :title="t('editor.tile.meter.title')">
    <PropRow :label="t('editor.tile.meter.look')" icon="eye-outline" stack>
      <div class="seg meter-looks" role="group" :aria-label="t('editor.tile.meter.look')" @pointerleave="preview(null)">
        <button v-for="key in (METER.styles as MeterStyle[])" :key="key" type="button" :class="`look-${key}`" :aria-pressed="style === key ? 'true' : 'false'"
          @pointerenter="preview(key)" @focus="preview(key)" @blur="preview(null)" @click="pickStyle(key)">
          <svg viewBox="0 0 40 30" aria-hidden="true">
            <template v-if="key === 'ring'">
              <path d="M8.5 24.5a13.5 13.5 0 1 1 23 0" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" opacity=".25" />
              <path d="M8.5 24.5a13.5 13.5 0 0 1 6-19" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" />
              <circle cx="20" cy="15" r="4.5" fill="currentColor" opacity=".45" />
            </template>
            <template v-else-if="key === 'tape'">
              <g stroke="currentColor" stroke-width="1"><line x1="5" y1="24" x2="5" y2="17" /><line x1="10" y1="24" x2="10" y2="20" /><line x1="15" y1="24" x2="15" y2="20" />
                <line x1="25" y1="24" x2="25" y2="20" /><line x1="30" y1="24" x2="30" y2="17" /><line x1="35" y1="24" x2="35" y2="20" /></g>
              <line x1="20" y1="10" x2="20" y2="25" stroke="currentColor" stroke-width="3" stroke-linecap="round" />
            </template>
            <template v-else>
              <rect v-for="i in 10" :key="i" :x="4 + (i - 1) * 3.2" y="10" width="2" height="12" fill="currentColor" :opacity="i <= 6 ? 1 : 0.25" />
            </template>
          </svg>
          <span>{{ t(`editor.tile.meter.styles.${key}`) }}</span>
        </button>
      </div>
    </PropRow>
    <PropRow :label="t('editor.tile.meter.range')" icon="resize" :hint="t('editor.tile.meter.range_hint')" stack>
      <div class="seg meter-range" role="group" :aria-label="t('editor.tile.meter.range')">
        <button type="button" :aria-pressed="own ? 'false' : 'true'" @click="pickRange('ha')">{{ t("editor.tile.meter.range_ha") }}</button>
        <button type="button" :aria-pressed="own ? 'true' : 'false'" @click="pickRange('own')">{{ t("editor.tile.meter.range_own") }}</button>
      </div>
      <template #note>
        <div class="meter-minmax">
          <label>{{ t("editor.tile.meter.min") }}<input class="meter-min" inputmode="decimal" :disabled="!own" :value="drafts.min ?? fieldText(range[0])"
            @input="drafts.min = ($event.target as HTMLInputElement).value" @blur="commitRange" @keydown.enter="($event.target as HTMLInputElement).blur()" /></label>
          <label>{{ t("editor.tile.meter.max") }}<input class="meter-max" inputmode="decimal" :disabled="!own" :value="drafts.max ?? fieldText(range[1])"
            @input="drafts.max = ($event.target as HTMLInputElement).value" @blur="commitRange" @keydown.enter="($event.target as HTMLInputElement).blur()" /></label>
          <span v-if="unit" class="meter-unit">{{ unit }}</span>
        </div>
        <small v-if="own && rangeWrong" class="help warn">{{ t("editor.tile.meter.range_wrong") }}</small>
        <p v-if="outside" class="help warn meter-outside">{{ t("editor.tile.meter.outside", { value: shown(value), min: editorNumber(String(haRange()[0])), max: editorNumber(String(haRange()[1])) }) }}
          <button type="button" class="meter-link meter-own" @click="pickRange('own')">{{ t("editor.tile.meter.set_own") }}</button></p>
      </template>
    </PropRow>
  </Section>

  <Section :title="t('editor.tile.meter.color')">
    <PropRow :label="t('editor.tile.meter.segments')" icon="palette-outline" :hint="t('editor.tile.meter.segments_hint')">
      <div class="seg meter-segments" role="group" :aria-label="t('editor.tile.meter.segments')">
        <button v-for="n in METER.segments" :key="n" type="button" :aria-pressed="segments === n ? 'true' : 'false'" @click="pickSegments(n)">{{ n }}</button>
      </div>
    </PropRow>
    <div class="meter-rows">
      <div v-for="(name, index) in colors" :key="`${segments}-${index}`" class="meter-row">
        <PopoverRoot :open="open === index" @update:open="(on) => (open = on ? index : -1)">
          <PopoverTrigger as-child>
            <button type="button" class="meter-swatch" :style="{ background: swatch(name) }" :title="colorName(name)"
              :aria-label="t('editor.tile.meter.swatch_aria', { n: index + 1, color: colorName(name) })"></button>
          </PopoverTrigger>
          <PopoverPortal>
            <PopoverContent class="ui-popover meter-palette" align="start" :side-offset="6" :collision-padding="10">
              <div class="sw">
                <button v-if="segments === 1" type="button" :aria-pressed="name === null ? 'true' : 'false'" :title="colorName(null)" :aria-label="colorName(null)"
                  @click="pickColor(index, null)"><i :style="{ background: tileColor }"></i></button>
                <button v-for="choice in meterColorNames" :key="choice" type="button" :aria-pressed="name === choice ? 'true' : 'false'" :title="colorName(choice)"
                  :aria-label="colorName(choice)" @click="pickColor(index, choice)"><i :style="{ background: meterHex(choice) }"></i></button>
              </div>
            </PopoverContent>
          </PopoverPortal>
        </PopoverRoot>
        <span v-if="segments === 1" class="meter-words">{{ t("editor.tile.meter.whole") }}</span>
        <span v-else-if="index === segments - 1" class="meter-words">{{ t("editor.tile.meter.above") }}</span>
        <template v-else>
          <span class="meter-words">{{ t("editor.tile.meter.up_to") }}</span>
          <input class="meter-threshold" inputmode="decimal" :aria-label="t('editor.tile.meter.threshold_aria', { n: index + 1 })"
            :value="thresholdDrafts[index] ?? fieldText(thresholds[index])" @input="thresholdDrafts[index] = ($event.target as HTMLInputElement).value"
            @blur="commitThreshold(index)" @keydown.enter="($event.target as HTMLInputElement).blur()" />
          <span v-if="unit" class="meter-unit">{{ unit }}</span>
        </template>
      </div>
      <small v-if="thresholdsWrong" class="help warn">{{ t("editor.tile.meter.thresholds_wrong") }}</small>
      <button v-if="!defaults" type="button" class="meter-link meter-reset" @click="reset">{{ t("editor.tile.meter.reset") }}</button>
    </div>
  </Section>
</template>

<style scoped>
.meter-looks button { flex-direction: column; gap: 2px; padding: 6px 4px; }
.meter-looks svg { width: 34px; height: 24px; }
.meter-minmax { display: flex; align-items: center; gap: 8px; min-width: 0; }
.meter-minmax label { display: flex; align-items: center; gap: 6px; flex: 1; min-width: 0; font-size: 12px; color: var(--muted); }
.meter-minmax input { flex: 1; min-width: 0; width: 100%; height: 30px; padding: 4px 8px; font-size: 13px; border-radius: 7px; }
.meter-unit { font-size: 12px; color: var(--muted); white-space: nowrap; }
.meter-outside { margin: 0; }
.meter-link { display: inline; padding: 0; margin-left: 4px; font: inherit; font-weight: 600; color: var(--accent); text-decoration: underline; text-underline-offset: 2px; }
.meter-rows { display: grid; gap: 8px; padding: 4px 0 6px; }
.meter-row { display: flex; align-items: center; gap: 8px; min-width: 0; }
.meter-swatch { width: 26px; height: 26px; flex: none; border-radius: 50%; border: 1px solid rgba(0, 0, 0, 0.12); padding: 0; }
.meter-swatch:focus-visible { box-shadow: 0 0 0 2px var(--surface), 0 0 0 4px var(--accent); }
.meter-words { font-size: 12.5px; color: var(--ink-2); white-space: nowrap; }
.meter-threshold { width: 0; flex: 1 1 70px; min-width: 50px; max-width: 120px; height: 30px; padding: 4px 8px; font-size: 13px; border-radius: 7px; }
.meter-reset { justify-self: start; margin-left: 0; font-size: 12px; }
.meter-palette .sw { max-width: 236px; }
</style>
