// Builds (docs/PLUGINS.md, "A plugin on a screen"): the add-on says per screen what is being built for it, whoever asked
// (Manager.builds), and the store is the editor's one source for it. The screen list, the progress and the build log all
// read it, so a plugin build shows the same way as a firmware update.
import { mount } from "@vue/test-utils";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { nextTick } from "vue";
import BuildLog from "../src/components/BuildLog.vue";
import type { Screen } from "../src/types";
import { useBuildsStore } from "../src/stores/builds";
import { useScreenStore } from "../src/stores/screen";
import { useInventoryStore } from "../src/stores/inventory";

const screen = (id: string, more: Partial<Screen> = {}) =>
  ({ id: `text.${id}`, name: id, node: id, online: true, board: "guition", firmware: "0.52.0", pictures: true, layout: {},
     update: { profile: `${id}.yaml`, host: "10.0.0.1", state: "idle" }, ...more }) as unknown as Screen;
const hall = screen("hall"), desk = screen("desk");

// The add-on's answers: api/firmware with the build line, and a build's own log (kept once it ended).
let kept: Record<number, string[]> = {};
beforeEach(() => {
  kept = {};
  vi.stubGlobal("fetch", vi.fn(async (url: string) => {
    const log = /firmware\/builds\/(\d+)\/log$/.exec(String(url));
    const body = log ? { build: useBuildsStore().lineBuild(Number(log[1])), logs: kept[Number(log[1])] || [] } : useBuildsStore().answer || {};
    return new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
  }));
  useInventoryStore().inventory.screens = [hall, desk];
  useInventoryStore().inventory.builds = {};
});
afterEach(() => vi.unstubAllGlobals());

describe("builds", () => {
  it("knows nothing builds until the add-on says so", () => {
    expect(useBuildsStore().buildOf(hall)).toBeNull();
    expect(useBuildsStore().anyBuilding).toBe(false);
    expect(useScreenStore().updateState(hall)?.kind).not.toBe("running");
  });

  it("shows a plugin build the way an update shows: running, with its ESPHome stage as progress", () => {
    useInventoryStore().inventory.builds = { [hall.id]: { by: "plugins", state: "running", plugins: ["bus"], file: "hall.yaml", stage: "compile" },
                               [desk.id]: { by: "plugins", state: "queued", plugins: ["waste"], file: "desk.yaml" } };
    expect(useBuildsStore().anyBuilding).toBe(true);
    expect(useScreenStore().updateState(hall)).toEqual({ kind: "running", text: "Building with its plugins" });
    expect(useScreenStore().updateState(desk)?.kind).toBe("queued");
    expect(useBuildsStore().buildProgress(hall)).toEqual({ percent: 40, text: expect.any(String) });
    expect(useBuildsStore().buildProgress(desk)).toBeNull();
    expect(useBuildsStore().buildingScreens.map((s) => s.name)).toEqual(["hall", "desk"]);
  });

  it("reads an update's phase from the same record", () => {
    useInventoryStore().inventory.builds = { [hall.id]: { by: "update", state: "running", phase: "verify", file: "hall.yaml" } };
    expect(useBuildsStore().buildProgress(hall)?.percent).toBe(78);
  });

  it("a build log shows the progress, and the lines of this screen's build when opened", async () => {
    useInventoryStore().inventory.builds = { [hall.id]: { id: 4, by: "plugins", state: "running", plugins: ["bus"], file: "hall.yaml", stage: "upload" } };
    useInventoryStore().inventory.line = [{ id: 4, by: "plugins", file: "hall.yaml", action: "install", state: "running", asked: 9, started: 10, finished: null, stage: "upload" }];
    useBuildsStore().answer = { job: { file: "hall.yaml", state: "running", stage: "upload", started: 11 }, logs: ["Compiling", "Uploading"] };
    const view = mount(BuildLog, { props: { screen: hall, name: true } });
    await nextTick();
    expect(view.text()).toContain("hall · 66 %");
    expect(view.find("pre").text()).toContain("Uploading");
  });

  it("keeps the log of a build that failed, and says so, until the next build: also when another screen builds now", async () => {
    // The next build of the line (desk's) started at once, so ESPHome's log is desk's: hall's own is the add-on's to keep.
    kept[4] = ["error: plugin ov_departures"];
    useInventoryStore().inventory.builds = { [desk.id]: { id: 5, by: "update", state: "running", file: "desk.yaml" } };
    useInventoryStore().inventory.line = [{ id: 5, by: "update", file: "desk.yaml", action: "install", state: "running", asked: 19, started: 20, finished: null },
      { id: 4, by: "plugins", file: "hall.yaml", action: "install", state: "failed", asked: 9, started: 10, finished: 18 }];
    useBuildsStore().answer = { job: { file: "desk.yaml", state: "running", started: 21 }, logs: ["Compiling desk"] };
    const view = mount(BuildLog, { props: { screen: hall } });
    await vi.waitFor(() => expect(view.find("pre").exists()).toBe(true));
    expect(view.text()).toContain("The last build of hall failed");
    expect(view.find("pre").text()).toContain("error: plugin ov_departures");
    expect(view.find("pre").text()).not.toContain("Compiling desk");
    useInventoryStore().inventory.builds = {};
    useInventoryStore().inventory.line = useInventoryStore().inventory.line!.slice(1);
    const other = mount(BuildLog, { props: { screen: desk } });
    await nextTick();
    expect(other.find(".build-log").exists()).toBe(false);
    // The next build of hall: what failed before is no longer said.
    useInventoryStore().inventory.builds = { [hall.id]: { id: 6, by: "update", state: "queued", place: 1, file: "hall.yaml" } };
    await nextTick();
    expect(view.text()).not.toContain("The last build of hall failed");
  });
});
