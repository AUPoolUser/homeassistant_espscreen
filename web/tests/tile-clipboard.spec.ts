// Tiles chosen together, copied, cut and pasted (model/tile-clipboard.ts, editor/clipboard.ts, the inspector store's
// selection): every setting goes along, on the same screen and to another one; a group keeps its arrangement where it
// fits, else fills the page and goes on to new pages right after it; a tile too large for a smaller grid takes the
// largest size it has there; a paste is one step of undo and leaves the pasted tiles chosen.
import { describe, expect, it } from "vitest";
import { nextTick } from "vue";
import { copyChosen, copiedTiles, cutChosen, forgetCopied, pasteCopied, removeTiles, selectPage } from "../src/editor/clipboard";
import { emptyLayout, emptyPage, entityOf, instanceId } from "../src/model/pages";
import { copyTiles, fitTile, pasteTiles, type PasteRules } from "../src/model/tile-clipboard";
import { useDocumentStore } from "../src/stores/document";
import { useInspectorStore } from "../src/stores/inspector";
import { useInventoryStore } from "../src/stores/inventory";
import { touches } from "../src/composables/useBandSelect";
import type { Inventory, PageGrid, PageLayout, PageTile, Screen, Tile } from "../src/types";
import { fakeApi } from "./helpers/fake-api";
import { openScreen, screenFixture } from "./helpers/fixtures";

const tile = (entity: string, row: number, column: number, columns = 1, rows = 1, extra: Partial<PageTile["appearance"]> = {}): PageTile => ({
  id: instanceId(), content: { kind: "entity", entityId: entity }, appearance: { label: "", ...extra }, interaction: {},
  placement: { row, column, columns, rows },
});
const rules = (over: Partial<PasteRules> = {}): PasteRules => ({
  allowed: () => true, sizes: () => ["single", "wide", "tall", "square", "full", "3x2", "2x3", "3x1", "4x1"], entityOf, room: 64, pages: 8, ...over,
});
const layoutOf = (...pages: PageTile[][]) => {
  const layout = emptyLayout("Home");
  while (layout.pages.length < pages.length) layout.pages.push(emptyPage());
  pages.forEach((tiles, index) => { layout.pages[index].tiles = tiles; });
  return layout;
};
const places = (layout: PageLayout, page: number) => layout.pages[page].tiles.map((item) =>
  [item.content.kind === "entity" ? item.content.entityId : item.content.kind, item.placement.row, item.placement.column, item.placement.columns, item.placement.rows]);

describe("pasting copied tiles", () => {
  const grid: PageGrid = { columns: 2, rows: 3 };
  it("keeps every setting and the arrangement, with new ids, where the group fits", () => {
    const a = tile("light.a", 1, 0, 1, 1, { icon: "account" }), b = tile("light.b", 2, 1);
    const layout = layoutOf([a, b], []);
    const copied = copyTiles(layout, grid, [b.id, a.id]);
    expect(copied.tiles.map((item) => item.tile.id)).toEqual([a.id, b.id]);
    const pasted = pasteTiles(layout, grid, copied, 1, rules());
    expect(places(pasted.layout, 1)).toEqual([["light.a", 1, 0, 1, 1], ["light.b", 2, 1, 1, 1]]);
    expect(pasted.layout.pages[1].tiles[0].appearance).toEqual({ label: "", icon: "account" });
    expect(pasted.layout.pages[1].tiles[0].interaction).toEqual({});
    expect(pasted.added).toHaveLength(2);
    expect(pasted.added).not.toContain(a.id);
    // A marked cell is where the group's top left corner goes.
    expect(places(pasteTiles(layout, grid, copied, 1, rules(), { row: 0, column: 0 }).layout, 1)).toEqual([["light.a", 0, 0, 1, 1], ["light.b", 1, 1, 1, 1]]);
  });
  it("on its own page, where the places are taken, goes where the group fits, then tile by tile, then on a new page after it", () => {
    const a = tile("light.a", 0, 0), b = tile("light.b", 0, 1);
    const layout = layoutOf([a, b, tile("light.c", 1, 0)], [tile("light.z", 0, 0)]);
    const twice = pasteTiles(layout, grid, copyTiles(layout, grid, [a.id, b.id]), 0, rules());
    expect(places(twice.layout, 0).slice(3)).toEqual([["light.a", 2, 0, 1, 1], ["light.b", 2, 1, 1, 1]]);
    // Six tiles on a page with one free cell: one there, five on a new page right after it, before the page that was second.
    const six = layoutOf([tile("x.1", 0, 0), tile("x.2", 0, 1), tile("x.3", 1, 0), tile("x.4", 1, 1), tile("x.5", 2, 0)], [tile("light.z", 0, 0)]);
    const copied = copyTiles(six, grid, six.pages[0].tiles.map((item) => item.id));
    copied.tiles.push({ ...copied.tiles[0], tile: { ...copied.tiles[0].tile, id: instanceId() } });
    const spread = pasteTiles(six, grid, copied, 0, rules());
    expect(spread.newPages).toBe(1);
    expect(places(spread.layout, 0).at(-1)).toEqual(["x.1", 2, 1, 1, 1]);
    expect(places(spread.layout, 1).map(([entity]) => entity)).toEqual(["x.2", "x.3", "x.4", "x.5", "x.1"]);
    expect(places(spread.layout, 2)).toEqual([["light.z", 0, 0, 1, 1]]);
  });
  it("spreads tiles from a larger screen over new pages of a smaller one, each in the largest size it has there", () => {
    const big: PageGrid = { columns: 4, rows: 4 };
    const source = layoutOf([tile("camera.door", 0, 0, 3, 2, { presentation: "3x2" }), tile("light.a", 0, 3), tile("sensor.t", 2, 0, 4, 1, { presentation: "4x1" }),
      tile("light.b", 3, 0), tile("light.c", 3, 1), tile("light.d", 3, 2), tile("light.e", 3, 3), tile("media_player.tv", 0, 0, 4, 4, { presentation: "full" })]);
    source.pages[0].tiles.pop();
    source.pages.push(emptyPage()); source.pages[1].tiles = [tile("media_player.tv", 0, 0, 4, 4, { presentation: "full" })];
    const copied = copyTiles(source, big, source.pages.flatMap((page) => page.tiles.map((item) => item.id)));
    const target = layoutOf([]);
    const pasted = pasteTiles(target, grid, copied, 0, rules());
    // 2 x 3: the 3 x 2 camera becomes 2 x 2, the 4 x 1 row a wide tile, the page-filling player a page of its own; a
    // small tile fills the gap the wide one left.
    expect(places(pasted.layout, 0)).toEqual([["camera.door", 0, 0, 2, 2], ["light.a", 2, 0, 1, 1], ["light.b", 2, 1, 1, 1]]);
    expect(pasted.layout.pages[0].tiles[0].appearance.presentation).toBe("square");
    expect(places(pasted.layout, 1)).toEqual([["sensor.t", 0, 0, 2, 1], ["light.c", 1, 0, 1, 1], ["light.d", 1, 1, 1, 1], ["light.e", 2, 0, 1, 1]]);
    expect(pasted.layout.pages[1].tiles[0].appearance.presentation).toBe("wide");
    expect(places(pasted.layout, 2)).toEqual([["media_player.tv", 0, 0, 2, 3]]);
    expect([pasted.newPages, pasted.skipped]).toEqual([2, 0]);
  });
  it("leaves out what the screen doesn't take: a refused entity, a Go to page tile of another screen, past its tiles or pages", () => {
    const a = tile("light.a", 0, 0), b = tile("light.b", 0, 1);
    const nav: PageTile = { ...tile("x", 1, 0), content: { kind: "navigation", target: { kind: "page", pageId: "0123456789abcdef" } } };
    const layout = layoutOf([a, b, nav]);
    const copied = copyTiles(layout, grid, [a.id, b.id, nav.id]);
    const elsewhere = layoutOf([]);
    const pasted = pasteTiles(elsewhere, grid, copied, 0, rules({ allowed: (_tile, entity) => entity !== "light.b" }));
    expect([places(pasted.layout, 0), pasted.skipped]).toEqual([[["light.a", 0, 0, 1, 1]], 2]);
    expect(pasteTiles(elsewhere, grid, copied, 0, rules({ room: 1 })).added).toHaveLength(1);
    const full = layoutOf([tile("x.1", 0, 0, 2, 3, { presentation: "full" })]);
    expect(pasteTiles(full, grid, copied, 0, rules({ pages: 1 })).skipped).toBe(3);
  });
  it("finds the largest size a tile takes on a grid, or none", () => {
    const wide = tile("weather.home", 0, 0, 3, 1, { presentation: "3x1", display: "forecast" });
    expect(fitTile(wide, grid, "weather.home", ["single", "wide"])?.appearance.presentation).toBe("wide");
    expect(fitTile(tile("light.a", 0, 0, 2, 2, { presentation: "square" }), grid, "light.a", ["single", "wide"])?.appearance.presentation).toBe("wide");
  });
});

const screen = (id: string, tiles: Tile[] = [], pages = 1, shape = { columns: 2, rows: 3, width: 480, height: 480 }) =>
  screenFixture({ id, name: id, online: true, firmware: "0.56.0", shape, layout: { title: id, tiles, pages } } as unknown as Screen);
function open(...screens: Screen[]) {
  fakeApi({ states: { states: {} }, capabilities: { capabilities: {} }, "POST header-preview": { items: [] } });
  useInventoryStore().inventory = { connected: true, screens, entities: [] } as unknown as Inventory;
  openScreen(screens[0].id);
  return { doc: useDocumentStore(), insp: useInspectorStore() };
}
const tileOf = (entity: string) => useDocumentStore().layout!.tiles.find((item) => item.entity === entity)!;

describe("tiles chosen together", () => {
  it("are chosen with a modifier, a whole page or a band, and leave the choice when they go", async () => {
    const { doc, insp } = open(screen("hall", [{ entity: "light.a", name: "", slot: 0 }, { entity: "light.b", name: "", slot: 1 }, { entity: "light.c", name: "", slot: 6 }], 2));
    insp.openTile(tileOf("light.a"));
    insp.toggleTile(tileOf("light.b"));
    expect([insp.inspector, insp.selection]).toEqual([{ kind: "tiles" }, [tileOf("light.a").id, tileOf("light.b").id]]);
    expect([insp.isPicked(tileOf("light.a")), insp.isPicked(tileOf("light.c")), doc.selectedTileId]).toEqual([true, false, null]);
    // One left is that tile's own drawer.
    insp.toggleTile(tileOf("light.a"));
    expect([insp.inspector, doc.selectedTileId]).toEqual([{ kind: "tile" }, tileOf("light.b").id]);
    doc.selectedPageId = doc.document!.pages[0].id;
    selectPage();
    expect(insp.chosenTiles.map((item) => item.entity)).toEqual(["light.a", "light.b"]);
    removeTiles(insp.chosenTiles);
    await nextTick();
    expect([doc.layout!.tiles.map((item) => item.entity), insp.inspector]).toEqual([["light.c"], null]);
    doc.undo();
    expect(doc.layout!.tiles).toHaveLength(3);
    // Something else opened lets go of them.
    insp.selectTiles([tileOf("light.a").id!, tileOf("light.c").id!]);
    insp.openPage(doc.document!.pages[1].id);
    expect(insp.selection).toEqual([]);
  });
  it("are copied to another page and another screen, and cut", async () => {
    forgetCopied();
    const { doc, insp } = open(
      screen("big", [{ entity: "light.a", name: "Desk", slot: 0, options: { icon: "account-child" } }, { entity: "light.b", name: "", slot: 1 }], 2,
        { columns: 3, rows: 3, width: 800, height: 480 }),
      screen("small", [{ entity: "light.z", name: "", slot: 0 }], 1));
    insp.selectTiles([tileOf("light.a").id!, tileOf("light.b").id!]);
    expect(copyChosen()).toBe(true);
    // On the second page of the same screen, in the same places, as one step of undo, chosen afterwards.
    doc.selectedPageId = doc.document!.pages[1].id;
    expect(await pasteCopied()).toBe(true);
    expect(doc.document!.pages[1].tiles.map((item) => [item.appearance.label, item.appearance.icon, item.placement.column])).toEqual([["Desk", "account-child", 0], ["", undefined, 1]]);
    expect(insp.chosenTiles.map((item) => item.slot)).toEqual([9, 10]);
    doc.undo();
    expect(doc.document!.pages[1].tiles).toEqual([]);
    // On another screen, where the first places are taken.
    openScreen("small");
    await nextTick();
    expect(copiedTiles()?.tiles).toHaveLength(2);
    expect(await pasteCopied()).toBe(true);
    expect(useDocumentStore().layout!.tiles.map((item) => [item.entity, item.slot])).toEqual([["light.z", 0], ["light.a", 2], ["light.b", 3]]);
    // Cut: copied and gone, one step of undo.
    const { insp: inspector } = { insp: useInspectorStore() };
    inspector.selectTiles([tileOf("light.z").id!, tileOf("light.a").id!]);
    expect(cutChosen()).toBe(true);
    expect(useDocumentStore().layout!.tiles.map((item) => item.entity)).toEqual(["light.b"]);
    expect(copiedTiles()?.tiles.map((item) => item.tile.content)).toEqual([{ kind: "entity", entityId: "light.z" }, { kind: "entity", entityId: "light.a" }]);
  });
});

it("a band touches what it overlaps, edges included", () => {
  const band = { left: 10, top: 10, right: 50, bottom: 50 };
  expect(touches(band, { left: 50, top: 50, right: 90, bottom: 90 })).toBe(true);
  expect(touches(band, { left: 51, top: 0, right: 90, bottom: 90 })).toBe(false);
  expect(touches(band, { left: 0, top: 0, right: 100, bottom: 100 })).toBe(true);
});
