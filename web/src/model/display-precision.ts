// A sensor's display precision: Home Assistant's own setting of the entity, "Display precision" in its entity settings
// (frontend entity-registry-settings-editor.ts), never a choice of a card. Home Assistant has no decimals per card: every
// dashboard writes the sensor with this one setting, and the add-on rounds every value of the sensor it sends a screen,
// a top bar and the editor's mockup with it too. The add-on reads and sets it (api/display-precision).
// Pure: what the add-on answers and the state Home Assistant reports come in; the number marks are the caller's.
import { t } from "../i18n";
import type { Live } from "./tile-text";

/** The precisions Home Assistant offers, in its order. */
export const PRECISIONS = [0, 1, 2, 3, 4, 5, 6] as const;
/** The choice that leaves it to the integration (Home Assistant's "Default"): no precision of the entity's own. */
export const DEFAULT = "default";

/** What the add-on answers: the precision chosen in Home Assistant (`own`, null for Default), the one the integration
 * suggests (`suggested`, what Default writes), and whether Home Assistant keeps settings for the entity at all (only one
 * with a unique ID is in its registry). `state`: the state as Home Assistant reports it, unrounded, where the add-on
 * sends it along. */
export type DisplayPrecision = { own: number | null; suggested: number | null; editable: boolean; state?: string };
const whole = (value: unknown) => (typeof value === "number" && Number.isInteger(value) && value >= 0 && value <= 6 ? value : null);
/** An answer of the add-on, as far as it says something. */
export const readPrecision = (answer: any): DisplayPrecision => ({
  own: whole(answer?.own), suggested: whole(answer?.suggested), editable: answer?.editable === true,
  ...(typeof answer?.state === "string" ? { state: answer.state } : {}),
});

const isNumber = (state: unknown): state is string => typeof state === "string" && state.trim() !== "" && Number.isFinite(Number(state));
/** Whether a sensor has a display precision to choose: Home Assistant offers it for a sensor with a numeric device
 * class, a unit of measurement or a state class; here a sensor whose value is a number counts as well. */
export function precisionOffered(entity: string, live: Live | null | undefined) {
  if (!entity.startsWith("sensor.") || !live) return false;
  return Boolean(live.a?.unit_of_measurement || live.a?.state_class) || isNumber(live.state);
}

/** A state with so many decimals, as Home Assistant's dialog labels each choice (_precisionLabel): rounded half away from
 * zero ("21.456" at 2 is "21.46"); without a precision the value as Home Assistant sent it. A state that is no number
 * reads 0, as there. `write` puts the user's number marks in ("21,46"). */
export function precisionLabel(precision: number | null | undefined, state: string | null | undefined, write: (plain: string) => string) {
  const value = isNumber(state) ? state.trim() : "0";
  if (precision == null) return write(value);
  return write(new Intl.NumberFormat("en-US", { minimumFractionDigits: precision, maximumFractionDigits: precision, useGrouping: false,
    signDisplay: "negative" }).format(Number(value)));
}

/** The choices as Home Assistant's dialog has them: Default, the value at the precision the integration suggests, then
 * 0 to 6 decimals, each labelled by the value written with them. */
export function precisionChoices(suggested: number | null, state: string | null | undefined, write: (plain: string) => string): [string | number, string][] {
  return [[DEFAULT, t("editor.precision.default", { value: precisionLabel(suggested, state, write) })],
    ...PRECISIONS.map((precision) => [precision, precisionLabel(precision, state, write)] as [number, string])];
}
