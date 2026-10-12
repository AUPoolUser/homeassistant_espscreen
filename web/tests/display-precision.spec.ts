import { appendTiles, current, loadLayout, screenFixture } from "./helpers/fixtures";
// A sensor's display precision: Home Assistant's own setting of the entity (its entity settings' "Display precision"),
// offered in the tile's and the top bar item's panel with the same list as there, each choice labelled by the sensor's
// value with that many decimals, and sent to Home Assistant at once by the add-on (api/display-precision).
import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import PrecisionRow from "../src/components/inspector/PrecisionRow.vue";
import TileInspector from "../src/components/TileInspector.vue";
import TopbarInspector from "../src/components/TopbarInspector.vue";
import { i18n, languageMarks, loadLanguage, numberText } from "../src/i18n";
import { precisionChoices, precisionLabel, precisionOffered, readPrecision } from "../src/model/display-precision";
import type { Inventory } from "../src/types";
import { useEntitiesStore } from "../src/stores/entities";
import { useInspectorStore } from "../src/stores/inspector";
import { useInventoryStore } from "../src/stores/inventory";
import { useScreenStore } from "../src/stores/screen";
import { useTopbarStore } from "../src/stores/topbar";
import { failure, fakeApi } from "./helpers/fake-api";

const plain = (text: string) => text;
const dutch = (text: string) => numberText(text, languageMarks("nl"));

describe("the choices (Home Assistant's _precisionLabel)", () => {
  it("labels each precision by the value with that many decimals, rounded half away from zero", () => {
    expect([0, 1, 2, 3, 4, 5, 6].map((p) => precisionLabel(p, "21.456", plain))).toEqual(["21", "21.5", "21.46", "21.456", "21.4560", "21.45600", "21.456000"]);
    // The decimal Home Assistant sends, not the float nearest it: 1.005 is 1.01, as Intl and the add-on's Decimal round it.
    expect(precisionLabel(2, "1.005", plain)).toBe("1.01");
    expect(precisionLabel(0, "2.5", plain)).toBe("3");
    expect(precisionLabel(0, "-2.5", plain)).toBe("-3");
    // A value that rounds to nothing is no negative zero, as the screens write it.
    expect(precisionLabel(2, "-0.001", plain)).toBe("0.00");
  });

  it("writes Default with the precision the integration suggests, else the value as Home Assistant sent it", () => {
    expect(precisionLabel(1, "21.456", plain)).toBe("21.5");
    expect(precisionLabel(null, "21.4560", plain)).toBe("21.4560");
    expect(precisionLabel(undefined, "1250", plain)).toBe("1250");
    const choices = precisionChoices(1, "21.456", plain);
    expect(choices.map(([key]) => key)).toEqual(["default", 0, 1, 2, 3, 4, 5, 6]);
    expect(choices[0][1]).toBe("Default (21.5)");
    expect(precisionChoices(null, "21.456", plain)[0][1]).toBe("Default (21.456)");
  });

  it("writes them in the user's number format, and a state that is no number as 0, as Home Assistant does", async () => {
    await loadLanguage("nl");
    expect(precisionLabel(2, "21.456", dutch)).toBe("21,46");
    expect(precisionLabel(1, "1234.56", dutch)).toBe("1.234,6");
    expect(precisionLabel(null, "1234.5", dutch)).toBe("1.234,5");
    expect(precisionLabel(1, "unavailable", plain)).toBe("0.0");
    expect(precisionLabel(null, undefined, plain)).toBe("0");
  });

  it("is offered for a sensor with a unit, a state class or a number for its value", () => {
    expect(precisionOffered("sensor.t", { state: "21.5", a: {} })).toBe(true);
    expect(precisionOffered("sensor.t", { state: "unavailable", a: { unit_of_measurement: "°C" } })).toBe(true);
    expect(precisionOffered("sensor.energy", { state: "unknown", a: { state_class: "total_increasing" } })).toBe(true);
    expect(precisionOffered("sensor.phase", { state: "Waxing crescent", a: {} })).toBe(false);
    expect(precisionOffered("sensor.t", null)).toBe(false);
    // Only a sensor: Home Assistant keeps a display precision for no other domain.
    expect(precisionOffered("number.volume", { state: "3", a: { unit_of_measurement: "%" } })).toBe(false);
  });

  it("reads the add-on's answer as far as it says something", () => {
    expect(readPrecision({ own: 2, suggested: 1, editable: true })).toEqual({ own: 2, suggested: 1, editable: true });
    expect(readPrecision({ own: 9, suggested: "1", editable: 1 })).toEqual({ own: null, suggested: null, editable: false });
    expect(readPrecision(null)).toEqual({ own: null, suggested: null, editable: false });
  });
});

function inventory(): Inventory {
  return {
    csrf: "t", connected: true,
    screens: [screenFixture({ id: "living", name: "Living room", online: true, firmware: "0.56.0", board: "guition",
      shape: { width: 480, height: 480, columns: 2, rows: 3 }, layout: { title: "Living room", tiles: [] } } as any)],
    entities: [
      { id: "sensor.t", name: "Temperature", state: "21.456", area: "" }, { id: "sensor.phase", name: "Moon", state: "Full moon", area: "" },
      { id: "light.a", name: "Lamp", state: "on", area: "" },
    ],
    builtin: [],
    icons: { groups: [], weather: {}, sun: {}, defaults: {}, fallback: "F0335", builtin: {}, controls: {} },
    backgrounds: { auto: { label: "Default" } },
    header: { max_items: 6, builtin: [], contents: [{ key: "state", label: "State" }, { key: "icon", label: "Icon" }], shows: [] },
  } as unknown as Inventory;
}
beforeEach(() => {
  useInventoryStore().inventory = inventory();
  useScreenStore().selected = "living";
  loadLayout({ title: "Living room", tiles: [] });
});
// The precision row's choices (ChoiceField is drawn as a row of buttons in the tests, tests/setup.ts).
const buttons = (view: ReturnType<typeof mount>) => view.get(".precision-row").findAll(".seg button");
const pressed = (view: ReturnType<typeof mount>) => buttons(view).find((b) => b.attributes("aria-pressed") === "true")?.text();

describe("the Display precision row", () => {
  const answer = (own: number | null, editable = true) => ({ own, suggested: 1, editable });
  it("shows Home Assistant's choice and list, and sends a pick to Home Assistant at once", async () => {
    let own: number | null = null;
    const api = fakeApi({
      "GET display-precision": () => answer(own),
      "PUT display-precision": ({ body }) => { own = body.precision; return answer(own); },
      "GET states": { states: { "sensor.t": { state: "21.46", a: { unit_of_measurement: "°C" } } } },
    });
    const preview = vi.spyOn(useTopbarStore(), "loadTopbarPreview");
    const view = mount(PrecisionRow, { props: { entity: "sensor.t" } });
    await flushPromises();
    expect(api.asked("GET display-precision")[0].query.get("entity")).toBe("sensor.t");
    expect(buttons(view).map((b) => b.text())).toEqual(["Default (21.5)", "21", "21.5", "21.46", "21.456", "21.4560", "21.45600", "21.456000"]);
    expect(pressed(view)).toBe("Default (21.5)");
    expect(view.text()).toContain("Home Assistant's own setting for this sensor");

    await buttons(view).find((b) => b.text() === "21.46")!.trigger("click");
    // The choice shows while Home Assistant saves it.
    expect(pressed(view)).toBe("21.46");
    await flushPromises();
    expect(api.asked("PUT display-precision").map((call) => call.body)).toEqual([{ entity: "sensor.t", precision: 2 }]);
    expect(pressed(view)).toBe("21.46");
    // The mockup asks the sensor's value and the top bar again, which the add-on now rounds the new way.
    expect(api.asked("GET states")[0].query.getAll("entity")).toEqual(["sensor.t"]);
    expect(useEntitiesStore().liveStates["sensor.t"].state).toBe("21.46");
    expect(preview).toHaveBeenCalledWith(0);

    await buttons(view).find((b) => b.text() === "Default (21.5)")!.trigger("click");
    await flushPromises();
    expect(api.asked("PUT display-precision")[1].body).toEqual({ entity: "sensor.t", precision: null });
    expect(pressed(view)).toBe("Default (21.5)");
  });

  it("puts the choice before back and says why when Home Assistant refuses it", async () => {
    const api = fakeApi({ "GET display-precision": answer(1), "PUT display-precision": failure(400, "Home Assistant refused it") });
    const view = mount(PrecisionRow, { props: { entity: "sensor.t" } });
    await flushPromises();
    expect(pressed(view)).toBe("21.5");
    await buttons(view).find((b) => b.text() === "21")!.trigger("click");
    await flushPromises();
    expect(api.count("PUT display-precision")).toBe(1);
    expect(pressed(view)).toBe("21.5");
    expect(view.get(".precision-row small.warn").text()).toBe("Home Assistant refused it");
  });

  it("speaks the editor's language and writes its numbers", async () => {
    fakeApi({ "GET display-precision": answer(null) });
    await loadLanguage("nl");
    i18n.global.locale.value = "nl";
    const view = mount(PrecisionRow, { props: { entity: "sensor.t" } });
    await flushPromises();
    expect(view.text()).toContain("Precisie weergeven");
    expect(buttons(view).map((b) => b.text()).slice(0, 4)).toEqual(["Standaard ( 21,5 )", "21", "21,5", "21,46"]);
  });

  it("is shown but can't be changed for a sensor Home Assistant keeps no settings for", async () => {
    const api = fakeApi({ "GET display-precision": answer(null, false) });
    const view = mount(PrecisionRow, { props: { entity: "sensor.t" } });
    await flushPromises();
    expect(buttons(view).every((b) => b.attributes("disabled") !== undefined)).toBe(true);
    expect(view.text()).toContain("has no unique ID");
    await buttons(view)[3].trigger("click");
    expect(api.count("PUT display-precision")).toBe(0);
  });
});

describe("where the row stands", () => {
  beforeEach(() => { fakeApi({ "GET display-precision": { own: null, suggested: 1, editable: true } }); });

  it("is in the panel of a sensor's tile on every face, and not on a lamp's or a sensor of words", async () => {
    for (const display of ["standard", "watch", "graph", "meter"]) {
      const tile = { entity: "sensor.t", name: "", slot: 0, options: { display } };
      appendTiles(tile);
      const panel = mount(TileInspector, { props: { tile: current(tile)! } });
      expect(panel.find(".precision-row").exists(), display).toBe(true);
      panel.unmount();
    }
    const lamp = { entity: "light.a", name: "", slot: 1 };
    const words = { entity: "sensor.phase", name: "", slot: 2 };
    appendTiles(lamp, words);
    expect(mount(TileInspector, { props: { tile: current(lamp)! } }).find(".precision-row").exists()).toBe(false);
    expect(mount(TileInspector, { props: { tile: current(words)! } }).find(".precision-row").exists()).toBe(false);
  });

  it("is in the top bar item's panel while the item writes the sensor's value", async () => {
    loadLayout({ title: "Living room", tiles: [], header: { items: [{ type: "entity", entity: "sensor.t", content: "state", show: "always" },
      { type: "entity", entity: "sensor.t", content: "icon", show: "always" }, { type: "entity", entity: "light.a", content: "state", show: "always" }] } } as any);
    const insp = useInspectorStore();
    const shown = (index: number) => { insp.openBar(index); return mount(TopbarInspector, { props: { index } }).find(".precision-row").exists(); };
    expect(shown(0)).toBe(true);
    expect(shown(1)).toBe(false);
    expect(shown(2)).toBe(false);
  });
});
