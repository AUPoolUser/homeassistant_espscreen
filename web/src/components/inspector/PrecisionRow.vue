<script setup lang="ts">
// A sensor's display precision, in the tile's and the top bar item's panel: Home Assistant's own setting of the entity
// (model/display-precision.ts), the same list as its entity settings show. A pick goes to Home Assistant at once, with
// no Save: it is not the page's, and every dashboard, screen and card of the sensor follows it. The mockup asks the
// sensor's value and the top bar's items again, which the add-on now rounds the new way.
import { computed, ref, watch } from "vue";
import { getJson, send } from "../../api";
import { editorNumber, t } from "../../i18n";
import { DEFAULT, precisionChoices, readPrecision, type DisplayPrecision } from "../../model/display-precision";
import ChoiceField from "../ChoiceField.vue";
import PropRow from "../ui/PropRow.vue";
import { useEntitiesStore } from "../../stores/entities";
import { useInventoryStore } from "../../stores/inventory";
import { useTopbarStore } from "../../stores/topbar";

const entities = useEntitiesStore();
const inv = useInventoryStore();
const topbar = useTopbarStore();
// `stack`: the name above the list, as the top bar item's other rows stand.
const props = defineProps<{ entity: string; stack?: boolean }>();

const info = ref<DisplayPrecision | null>(null);
const error = ref("");
const busy = ref(false);
// An answer for the entity the panel showed before (another one chosen meanwhile) is dropped.
let asked = 0;
async function load() {
  const entity = props.entity, mine = ++asked;
  info.value = null; error.value = "";
  try {
    const answer = readPrecision(await getJson(`display-precision?entity=${encodeURIComponent(entity)}`));
    if (mine === asked) info.value = answer;
  } catch (failure) {
    if (mine === asked) error.value = failure instanceof Error ? failure.message : String(failure);
  }
}
watch(() => props.entity, load, { immediate: true });

// Each choice is labelled by the sensor's value as Home Assistant reports it, unrounded: the add-on's, else the one the
// inventory read, else the value on the mockup (already written with the precision of now).
const state = computed(() => {
  const known = info.value?.state ?? inv.entityOf(props.entity)?.state;
  return known !== undefined && known !== "" && Number.isFinite(Number(known)) ? known : entities.liveOf(props.entity)?.state;
});
const choices = computed(() => precisionChoices(info.value?.suggested ?? null, state.value, editorNumber));
const chosen = computed(() => info.value?.own ?? DEFAULT);
async function pick(key: string | number) {
  const precision = key === DEFAULT ? null : Number(key);
  if (!info.value || precision === info.value.own) return;
  const before = info.value, entity = props.entity, mine = asked;
  // The choice shows at once; Home Assistant's answer squares it, and a refusal puts the one before back.
  info.value = { ...before, own: precision };
  error.value = ""; busy.value = true;
  try {
    const answer = readPrecision(await send("display-precision", "PUT", { entity, precision }));
    if (mine === asked) info.value = answer;
    void entities.reloadState(entity);
    topbar.loadTopbarPreview(0);
  } catch (failure) {
    if (mine === asked) { info.value = before; error.value = failure instanceof Error ? failure.message : String(failure); }
  } finally {
    busy.value = false;
  }
}
</script>

<template>
  <PropRow class="precision-row" :label="t('editor.precision.label')" :icon="stack ? undefined : 'crosshairs'" :stack="stack">
    <ChoiceField :choices="choices" :value="chosen" :disabled="!info?.editable || busy" :aria-label="t('editor.precision.label')" @pick="pick" />
    <template #note>
      <small v-if="error" class="help warn">{{ error }}</small>
      <small v-else class="help">{{ t(info && !info.editable ? "editor.precision.unregistered" : "editor.precision.note") }}</small>
    </template>
  </PropRow>
</template>
