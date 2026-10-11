<script setup lang="ts">
// A short list of words as chips (a calendar card's places and title words, firmware 0.56.0): the ones chosen are lit,
// the ones offered (`suggestions`, such as the places a calendar's events name) wait beside them to be tapped on, and
// a word of your own goes in with Enter or a comma. A chip tapped again goes off; one of your own then goes away.
import { computed, ref } from "vue";
import Icon from "../ui/Icon.vue";

const props = defineProps<{ values: readonly string[]; suggestions?: readonly string[]; max: number; placeholder: string; label: string }>();
const emit = defineEmits<{ change: [values: string[]] }>();
const typed = ref("");
const same = (a: string, b: string) => a.toLocaleLowerCase() === b.toLocaleLowerCase();
const chosen = (word: string) => props.values.some((value) => same(value, word));
// Your own words first, in the order they were added, then the offered ones where they stand, lit or not.
const chips = computed(() => [
  ...props.values.filter((value) => !(props.suggestions ?? []).some((word) => same(word, value))).map((word) => ({ word, own: true })),
  ...(props.suggestions ?? []).map((word) => ({ word, own: false })),
]);
const full = computed(() => props.values.length >= props.max);
// The add-on keeps a word up to 48 bytes (calendar_feed.validate).
const fits = (word: string) => new TextEncoder().encode(word).length <= 48;
function toggle(word: string) {
  if (chosen(word)) emit("change", props.values.filter((value) => !same(value, word)));
  else if (!full.value) emit("change", [...props.values, word]);
}
function add() {
  const word = typed.value.replace(/,/g, " ").trim();
  typed.value = "";
  if (!word || chosen(word) || full.value || !fits(word)) return;
  emit("change", [...props.values, word]);
}
function key(event: KeyboardEvent) {
  if (event.key === "Enter" || event.key === ",") { event.preventDefault(); add(); }
  else if (event.key === "Backspace" && !typed.value && props.values.length) emit("change", props.values.slice(0, -1));
}
</script>

<template>
  <div class="tag-field" role="group" :aria-label="label">
    <button v-for="chip in chips" :key="chip.word" type="button" class="tag-chip" :aria-pressed="chosen(chip.word) ? 'true' : 'false'"
      :disabled="!chosen(chip.word) && full" @click="toggle(chip.word)">
      <Icon :name="!chosen(chip.word) ? 'plus' : chip.own ? 'close' : 'check'" />{{ chip.word }}
    </button>
    <input v-if="!full" v-model="typed" class="tag-input" type="text" maxlength="48" enterkeyhint="done" :placeholder="placeholder" :aria-label="placeholder"
      @keydown="key" @blur="add" />
  </div>
</template>
