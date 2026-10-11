<script setup lang="ts">
// A calendar card's settings (firmware 0.56.0, docs/CALENDAR.md): what it shows first, which calendars it puts
// together, which of their events it lets through, how far it looks and where its full screen opens. What the add-on
// keeps is calendar_feed.validate's; a default is never stored. The card as the screen would get it comes from
// api/calendar/preview, asked again a moment after a choice changes: the calendars' own colours for their dots, the
// places their events name for the place filter, and how many events the filters let through.
import { computed, onBeforeUnmount, ref, watch } from "vue";
import { t } from "../../i18n";
import { send } from "../../api";
import rules from "../../model/page-rules.json";
import { CALENDAR_DEFAULTS } from "../../model/tile-options";
import type { Tile } from "../../types";
import type { IconName } from "../../model/ui-icons";
import ChoiceField from "../ChoiceField.vue";
import CheckRow from "../ui/CheckRow.vue";
import Icon from "../ui/Icon.vue";
import PropRow from "../ui/PropRow.vue";
import Section from "../ui/Section.vue";
import SwitchRow from "../ui/SwitchRow.vue";
import TagField from "./TagField.vue";
import { setTileOption, setTileOptions } from "../../editor/tiles";
import { useEntitiesStore } from "../../stores/entities";
import { useInventoryStore } from "../../stores/inventory";
import { useScreenStore } from "../../stores/screen";

const entities = useEntitiesStore();
const inv = useInventoryStore();
const scr = useScreenStore();
const props = defineProps<{ tile: Tile }>();

const current = <T,>(key: string) => (props.tile.options?.[key] ?? CALENDAR_DEFAULTS[key]) as T;
const list = (key: string) => (props.tile.options?.[key] as string[] | undefined) ?? [];
const set = (key: string, value: unknown) => setTileOption(props.tile, key, value);

// ---- What the card shows: two presets, named by what you see on it.
const style = computed(() => current<string>("style"));
const STYLE_ICONS: Record<string, IconName> = { events: "format-list-bulleted", busy_free: "check-circle" };
// Free or busy is about the next booking: it says Starts soon a while before one, a quarter of an hour unless chosen.
function pickStyle(value: string) {
  if (value === style.value) return;
  if (value === "busy_free" && !current<number>("soon")) setTileOptions(props.tile, { style: value, soon: 15 });
  else set("style", value);
}

// ---- The calendars: the tile's own first and always, then every other one Home Assistant has, tapped on or off.
const extra = computed(() => list("calendars"));
const others = computed(() => (inv.inventory.entities || []).filter((item) => item.id.startsWith("calendar.") && item.id !== props.tile.entity).map((item) => item.id));
const calendarsFull = computed(() => extra.value.length >= rules.calendar.calendars);
function toggleCalendar(id: string) {
  if (extra.value.includes(id)) set("calendars", extra.value.filter((item) => item !== id));
  else if (!calendarsFull.value) set("calendars", [...extra.value, id]);
}

// ---- The card as the screen would get it (api/calendar/preview). A failed answer leaves neutral dots and no places.
type Preview = { cal?: { c?: [number, string][]; e?: unknown[]; m?: number }; places?: string[] };
const preview = ref<Preview | null>(null);
let timer: ReturnType<typeof setTimeout> | undefined, asked = 0;
async function load() {
  const ask = ++asked;
  try {
    const answer = await send<Preview>("calendar/preview", "POST", { tile: { entity: props.tile.entity, options: props.tile.options || {} } });
    if (ask === asked) preview.value = answer;
  } catch {
    if (ask === asked) preview.value = null;
  }
}
watch(() => [props.tile.entity, JSON.stringify(props.tile.options || {})], (now, before) => {
  clearTimeout(timer);
  // Another tile in this panel asks at once; a change of choices waits until the typing or tapping settles.
  timer = setTimeout(load, before && now[0] === before[0] ? 450 : 0);
}, { immediate: true });
onBeforeUnmount(() => { clearTimeout(timer); asked++; });
// The calendars of the card in the preview's order: the tile's own, then the ones it adds (calendar_feed.calendars_of).
const colours = computed(() => {
  const order = [props.tile.entity, ...extra.value.filter((id) => id !== props.tile.entity)];
  const out: Record<string, string> = {};
  (preview.value?.cal?.c ?? []).forEach(([colour], index) => {
    if (order[index] && Number.isInteger(colour)) out[order[index]] = `#${colour.toString(16).padStart(6, "0")}`;
  });
  return out;
});
const dot = (id: string) => (colours.value[id] ? { background: colours.value[id] } : undefined);
const places = computed(() => preview.value?.places ?? []);
const found = computed(() => preview.value?.cal?.e ? preview.value.cal.e.length + (preview.value.cal.m ?? 0) : null);

// ---- How far it looks, when an event starts soon, where its full screen opens. A value stored by hand stays in sight.
const withCurrent = (values: number[], now: number) => (values.includes(now) ? values : [...values, now].sort((a, b) => a - b));
const aheadChoices = computed(() => withCurrent([1, 3, 7, 14, 31], current<number>("ahead")).map((days) => [days, t("editor.tile.calendar.days", days)] as [number, string]));
const soonChoices = computed(() => withCurrent([0, 5, 10, 15, 30], current<number>("soon"))
  .map((minutes) => [minutes, minutes ? t("editor.tile.calendar.minutes", minutes) : t("editor.tile.calendar.soon_off")] as [number, string]));
const viewChoices = computed(() => rules.calendar.startViews.map((view) => [view, t(`editor.tile.calendar.view.${view}`)] as [string, string]));
</script>

<template>
  <Section :title="t('editor.tile.calendar.title')">
    <p v-if="!scr.supports(0, 56, 0)" class="hint warn">{{ t("editor.tile.calendar.needs_firmware") }}</p>
    <PropRow :label="t('editor.tile.calendar.show.label')" icon="eye-outline" stack>
      <div class="cal-presets" role="group" :aria-label="t('editor.tile.calendar.show.label')">
        <button v-for="value in rules.calendar.styles" :key="value" type="button" class="cal-preset" :aria-pressed="style === value ? 'true' : 'false'" @click="pickStyle(value)">
          <span class="cal-preset-head"><Icon :name="STYLE_ICONS[value] ?? 'eye-outline'" /><b>{{ t(`editor.tile.calendar.show.${value}`) }}</b></span>
          <small>{{ t(`editor.tile.calendar.show.${value}_hint`) }}</small>
        </button>
      </div>
    </PropRow>
    <PropRow :label="t('editor.tile.calendar.calendars.label')" icon="view-column-outline" :hint="t('editor.tile.calendar.calendars.hint', { n: rules.calendar.calendars + 1 })" stack>
      <template #aside>{{ t("editor.tile.calendar.calendars.count", extra.length + 1) }}</template>
      <div class="cal-list">
        <CheckRow :checked="true" class="cal-own" aria-disabled="true">
          <i class="cal-dot" :style="dot(tile.entity)"></i><span class="cal-name">{{ entities.entityName(tile.entity) }}</span>
          <small>{{ t("editor.tile.calendar.calendars.own") }}</small>
        </CheckRow>
        <CheckRow v-for="id in others" :key="id" :checked="extra.includes(id)" :disabled="!extra.includes(id) && calendarsFull" @toggle="toggleCalendar(id)">
          <i class="cal-dot" :style="dot(id)"></i><span class="cal-name">{{ entities.entityName(id) }}</span>
        </CheckRow>
      </div>
      <small v-if="!others.length" class="hint">{{ t("editor.tile.calendar.calendars.none") }}</small>
    </PropRow>
  </Section>

  <Section :title="t('editor.tile.calendar.filter.title')" :aside="found === null ? undefined : t('editor.tile.calendar.filter.found', found)">
    <PropRow :label="t('editor.tile.calendar.places.label')" icon="map-marker-radius-outline" :hint="t('editor.tile.calendar.places.hint')" stack>
      <TagField :values="list('places')" :suggestions="places" :max="rules.calendar.words" :placeholder="t('editor.tile.calendar.places.add')"
        :label="t('editor.tile.calendar.places.label')" @change="(values) => set('places', values)" />
    </PropRow>
    <PropRow :label="t('editor.tile.calendar.words.label')" icon="format-title" :hint="t('editor.tile.calendar.words.hint')" stack>
      <div class="cal-words">
        <span class="cal-words-label">{{ t("editor.tile.calendar.words.only") }}</span>
        <TagField :values="list('words')" :max="rules.calendar.words" :placeholder="t('editor.tile.calendar.words.add')"
          :label="t('editor.tile.calendar.words.only')" @change="(values) => set('words', values)" />
        <span class="cal-words-label">{{ t("editor.tile.calendar.words.hide") }}</span>
        <TagField :values="list('hide_words')" :max="rules.calendar.words" :placeholder="t('editor.tile.calendar.words.add')"
          :label="t('editor.tile.calendar.words.hide')" @change="(values) => set('hide_words', values)" />
      </div>
    </PropRow>
    <SwitchRow :label="t('editor.tile.calendar.all_day')" :model-value="current<boolean>('all_day')" @update:model-value="(on) => set('all_day', on)" />
    <SwitchRow :label="t('editor.tile.calendar.tentative')" :description="t('editor.tile.calendar.tentative_hint')"
      :model-value="current<boolean>('tentative')" @update:model-value="(on) => set('tentative', on)" />
    <SwitchRow :label="t('editor.tile.calendar.private')" :description="t('editor.tile.calendar.private_hint')"
      :model-value="current<boolean>('private')" @update:model-value="(on) => set('private', on)" />
  </Section>

  <Section :title="t('editor.tile.calendar.time.title')">
    <PropRow :label="t('editor.tile.calendar.ahead')" icon="arrow-right" :hint="t('editor.tile.calendar.ahead_hint')">
      <ChoiceField :choices="aheadChoices" :value="current<number>('ahead')" :aria-label="t('editor.tile.calendar.ahead')" @pick="(v) => set('ahead', Number(v))" />
    </PropRow>
    <PropRow :label="t('editor.tile.calendar.soon')" icon="clock-outline" :hint="t('editor.tile.calendar.soon_hint')">
      <ChoiceField :choices="soonChoices" :value="current<number>('soon')" :aria-label="t('editor.tile.calendar.soon')" @pick="(v) => set('soon', Number(v))" />
    </PropRow>
    <PropRow :label="t('editor.tile.calendar.start_view')" icon="tablet-dashboard" :hint="t('editor.tile.calendar.start_view_hint')">
      <ChoiceField :choices="viewChoices" :value="current<string>('start_view')" :aria-label="t('editor.tile.calendar.start_view')" @pick="(v) => set('start_view', v)" />
    </PropRow>
  </Section>
</template>
