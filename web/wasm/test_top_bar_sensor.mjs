// A sensor in the top bar opens the card its tile opens (firmware 0.56.0): the real firmware's decoder, top bar and card,
// with a finger on the item. A duration says itself in hours and minutes on the bar and on the card ("0h 12m", as Home
// Assistant writes it), and the open card follows the bar's next state. Runs on the smallest, a middle and the largest glass.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import createModule from '../src/wasm/firmware_preview.js';
import { connection, configure } from './test_protocol.mjs';

const wasmBinary = readFileSync(new URL('../src/wasm/firmware_preview.wasm', import.meta.url));
const SHAPES = [
  { key: 'cyd', width: 320, height: 240, dpi: 143, columns: 3, rows: 2 },
  { key: 'guition', width: 480, height: 480, dpi: 170, columns: 3, rows: 3 },
  { key: 'jc8012p4a1', width: 1280, height: 800, dpi: 149, columns: 5, rows: 4 },
];
// What the app sends for a sensor's item (header_bar.entity_item): its text, and `d` for its card.
const left = (hours, words) => ({ k: 'text', t: words, d: ['sensor.dishwasher_left', hours, 'h', 'Dishwasher', words] });
const light = { entity: 'light.kitchen', name: 'Kitchen', state: 'on', a: { brightness: 200 }, o: {}, slot: 0 };

for (const shape of SHAPES) {
  const m = await createModule({ wasmBinary });
  assert.equal(m._preview_init(shape.width, shape.height, shape.dpi, shape.columns, shape.rows), 1);
  const raw = connection(m);
  // The page carries the bar: configure() sends pages without items, so this one names its own.
  const receive = packet => raw(packet.op === 'page' ? { ...packet, items: [left('0.2', '0h 12m')] } : packet);
  configure(receive, 'Kitchen', 1, [light]);
  let ms = 0;
  const tick = (n = 4) => { for (let i = 0; i < n; i++) { ms += 32; m._preview_time(ms, 1789401840, 7200); m._preview_render(); } };
  const objects = () => JSON.parse(m.ccall('preview_layout', 'string', [], [])).objects;
  const texts = () => objects().filter((o) => o.type === 'label').map((o) => o.text);
  const touch = (x, y) => { m._preview_touch(x, y, 1); tick(2); m._preview_touch(x, y, 0); tick(6); };
  tick(12);

  const item = objects().find((o) => o.type === 'label' && o.text === '0h 12m');
  assert.ok(item, `${shape.key}: the duration on the top bar (${texts().join(' | ')})`);
  const x = Math.round((item.x1 + item.x2) / 2), y = Math.round((item.y1 + item.y2) / 2);
  const area = objects().find((o) => o.clickable && o.x1 <= x && x <= o.x2 && o.y1 <= y && y <= o.y2 && o.card < 0);
  assert.ok(area, `${shape.key}: a finger's area over the sensor's item`);
  touch(x, y);
  assert.ok(texts().includes('Dishwasher'), `${shape.key}: the sensor's card opens with its name (${texts().join(' | ')})`);
  assert.ok(texts().filter((t) => t === '0h 12m').length >= 1 && !texts().includes('0'),
    `${shape.key}: the card says the duration as the bar does, not its number read as 0 (${texts().join(' | ')})`);

  // The bar's next state reaches the open card.
  raw({ op: 'bar', p: 0, items: [left('0.5', '0h 30m')] });
  tick(6);
  assert.ok(texts().includes('0h 30m'), `${shape.key}: the open card follows the bar (${texts().join(' | ')})`);
}
console.log(`PASS top bar sensor: a tap opens its card, a duration in hours and minutes, on ${SHAPES.map((s) => s.key).join(', ')}`);
