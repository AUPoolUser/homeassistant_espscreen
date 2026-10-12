"""Render pages of meters (firmware 0.56.0, docs/METER.md) with the real firmware on the host (tools/render/host.py), for
the README and the website: whole dashboards of rings, tapes and bars of cells, light and Dark mode.

    python3 tools/render/meter_pages.py jc8012p4a1 guition waveshare43 cyd

Every page is a layout as the editor would store it, sent with the add-on's own message builder (core.state_message),
the sensors made up but shaped as Home Assistant reports them, each with a day of history for a ring's graph.
Shots land in .esphome/meter-pages/out/<variant>/<page>-<look>.png.
"""
import argparse
import asyncio
import json
import math
import os
import shlex
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run  # noqa: E402
import host  # noqa: E402
import send_layout  # noqa: E402

# ---- the house: (name, unit, device class, value, a day of it from midnight to now as (low, high, peak hour))
SENSORS = {
    'living': ('Living room', '°C', 'temperature', 21.4, (19.6, 22.8, 15)),
    'bedroom': ('Bedroom', '°C', 'temperature', 19.2, (18.1, 20.4, 22)),
    'kitchen': ('Kitchen', '°C', 'temperature', 22.6, (19.8, 24.1, 18)),
    'outside': ('Outside', '°C', 'temperature', 8.6, (5.2, 11.9, 14)),
    'fridge': ('Fridge', '°C', 'temperature', 4.1, (3.6, 5.2, 19)),
    'freezer': ('Freezer', '°C', 'temperature', -18.4, (-19.6, -16.9, 12)),
    'office_co2': ('Office CO2', 'ppm', 'carbon_dioxide', 840, (430, 1180, 14)),
    'bedroom_co2': ('Bedroom CO2', 'ppm', 'carbon_dioxide', 1260, (480, 1310, 7)),
    'bathroom': ('Bathroom', '%', 'humidity', 58, (51, 78, 8)),
    'humidity': ('Humidity', '%', 'humidity', 47, (41, 56, 6)),
    'phone': ('Phone', '%', 'battery', 64, (58, 92, 1)),
    'house': ('House', 'kW', 'power', 1.84, (0.21, 4.6, 18)),
    'solar': ('Solar', 'kW', 'power', 3.42, (0.0, 4.9, 13)),
    'grid': ('Grid', 'W', 'power', 640, (180, 3800, 18)),
    'cpu': ('CPU usage', '%', None, 12, (3, 64, 9)),
    'disk': ('Disk usage', 'GiB', 'data_size', 10.4, (10.3, 10.4, 12)),
    'memory': ('Memory', 'MiB', 'data_size', 803, (640, 1210, 9)),
    'wind': ('Wind', 'km/h', 'wind_speed', 11, (4, 34, 12)),
    'pressure': ('Pressure', 'hPa', 'atmospheric_pressure', 1012, (1004, 1016, 3)),
    'noise': ('Noise', 'dB', 'sound_pressure', 42, (31, 68, 17)),
    'lux': ('Daylight', 'lx', 'illuminance', 620, (0, 980, 13)),
}
# The sizes that have a name are stored by it (core.event_size): a span is only what no name says.
NAMES = {(1, 1): 'single', (2, 1): 'wide', (1, 2): 'tall', (2, 2): 'square'}
GREEN_ORANGE_RED = {'segments': 3}
BATTERY = {'segments': 3, 'colors': ['red', 'orange', 'green'], 'thresholds': [20, 50]}
CO2 = {'segments': 3, 'thresholds': [800, 1200], 'min': 400, 'max': 1600}
# Each sensor's icon (a name of tile_icons.ICONS: Home Assistant's own per device class needs a Home Assistant) and, for
# some, a colour of its own instead of Home Assistant's for the sensor, the way a tile is given one.
ICONS = {'living': 'sofa', 'bedroom': 'bed', 'kitchen': 'stove', 'outside': 'thermometer', 'fridge': 'fridge',
         'freezer': 'snowflake', 'office_co2': 'molecule-co2', 'bedroom_co2': 'molecule-co2', 'bathroom': 'shower',
         'humidity': 'water-percent', 'phone': 'battery-high', 'house': 'home', 'solar': 'solar-power', 'grid': 'meter-electric',
         'cpu': 'laptop', 'disk': 'gauge', 'memory': 'cog', 'wind': 'weather-windy', 'pressure': 'gauge', 'noise': 'microphone',
         'lux': 'weather-sunny'}
COLOURS = {'living': 'amber', 'outside': 'light-blue', 'fridge': 'light-blue', 'freezer': 'blue', 'house': 'purple',
           'solar': 'amber', 'grid': 'indigo', 'disk': 'deep-orange', 'wind': 'teal', 'lux': 'yellow', 'kitchen': 'deep-orange'}
RANGES = {'living': (16, 26), 'bedroom': (14, 24), 'kitchen': (16, 28), 'outside': (-5, 20), 'fridge': (0, 10),
          'freezer': (-25, -10), 'house': (0, 7), 'solar': (0, 6), 'grid': (0, 5000), 'disk': (0, 32), 'memory': (0, 2048),
          'wind': (0, 60), 'pressure': (980, 1040), 'noise': (30, 90), 'lux': (0, 1000)}


def meter(key, look='ring', **more):
    options = {'display': 'meter', **({'meter': look} if look != 'ring' else {}), 'icon': ICONS[key]}
    if key in COLOURS and 'segments' not in more:
        options['colors'] = [COLOURS[key]]
    if key in RANGES:
        options['min'], options['max'] = RANGES[key]
    options.update(more)
    return key, options


# ---- the pages: (name, title, [(sensor, options, column, row, columns, rows)]) on a grid of the board's own
def place(cells):
    return [(key, options, c, r, w, h) for (key, options), (c, r, w, h) in cells]


PAGES = {
    # The ten-inch: five by five cells.
    (5, 5): [
        ('bars', 'Sensors', place([
            (meter('living', 'bar'), (0, 0, 2, 2)), (meter('office_co2', 'bar', **CO2), (2, 0, 1, 2)),
            (meter('bathroom', 'bar'), (3, 0, 1, 2)), (meter('phone', 'bar', **BATTERY), (4, 0, 1, 2)),
            (meter('house', 'bar'), (0, 2, 2, 1)), (meter('cpu', 'bar', **GREEN_ORANGE_RED), (2, 2, 1, 1)),
            (meter('disk', 'bar'), (3, 2, 1, 1)), (meter('memory', 'bar'), (4, 2, 1, 1)),
            (meter('wind', 'bar'), (0, 3, 1, 2)), (meter('outside', 'bar'), (1, 3, 2, 2)),
            (meter('bedroom_co2', 'bar', **CO2), (3, 3, 2, 2))])),
        ('rings', 'Home', place([
            (meter('living'), (0, 0, 2, 2)), (meter('office_co2', **CO2), (2, 0, 1, 2)),
            (meter('bathroom'), (3, 0, 1, 2)), (meter('phone', **BATTERY), (4, 0, 1, 2)),
            (meter('solar'), (0, 2, 2, 2)), (meter('cpu', **GREEN_ORANGE_RED), (2, 2, 1, 1)),
            (meter('disk'), (3, 2, 1, 1)), (meter('memory'), (4, 2, 1, 1)),
            (meter('outside'), (2, 3, 1, 1)), (meter('wind'), (3, 3, 1, 1)), (meter('pressure'), (4, 3, 1, 1)),
            (meter('grid'), (0, 4, 3, 1)), (meter('fridge'), (3, 4, 1, 1)), (meter('freezer'), (4, 4, 1, 1))])),
        ('tapes', 'Climate', place([
            (meter('living', 'tape'), (0, 0, 2, 1)), (meter('bedroom', 'tape'), (2, 0, 2, 1)),
            (meter('kitchen', 'tape'), (4, 0, 1, 1)),
            (meter('outside', 'tape'), (0, 1, 2, 1)), (meter('humidity', 'tape'), (2, 1, 1, 1)),
            (meter('pressure', 'tape'), (3, 1, 2, 1)),
            (meter('solar', 'tape'), (0, 2, 3, 2)), (meter('wind', 'tape'), (3, 2, 2, 2)),
            (meter('fridge', 'tape'), (0, 4, 1, 1)), (meter('noise', 'tape', **GREEN_ORANGE_RED), (1, 4, 1, 1)),
            (meter('lux', 'tape'), (2, 4, 2, 1)), (meter('office_co2', 'tape', **CO2), (4, 4, 1, 1))])),
        ('mix', 'Overview', place([
            (meter('living'), (0, 0, 2, 2)), (meter('office_co2', 'bar', **CO2), (2, 0, 1, 2)),
            (meter('phone', **BATTERY), (3, 0, 1, 1)), (meter('humidity', 'tape'), (4, 0, 1, 1)),
            (meter('cpu', 'bar', **GREEN_ORANGE_RED), (3, 1, 1, 1)), (meter('pressure', 'tape'), (4, 1, 1, 1)),
            (meter('house', 'tape'), (0, 2, 2, 1)), (meter('disk'), (2, 2, 1, 1)), (meter('memory', 'bar'), (3, 2, 2, 1)),
            (meter('solar'), (0, 3, 2, 2)), (meter('wind', 'bar'), (2, 3, 1, 2)), (meter('outside', 'tape'), (3, 3, 2, 1)),
            (meter('fridge'), (3, 4, 1, 1)), (meter('freezer', 'bar'), (4, 4, 1, 1))])),
    ],
    # The 4.3-inch and the 5-inch: three by three.
    (3, 3): [
        ('mix', 'Overview', place([
            (meter('living'), (0, 0, 2, 1)), (meter('phone', **BATTERY), (2, 0, 1, 1)),
            (meter('office_co2', 'bar', **CO2), (0, 1, 1, 2)), (meter('house', 'tape'), (1, 1, 2, 1)),
            (meter('cpu', **GREEN_ORANGE_RED), (1, 2, 1, 1)), (meter('humidity', 'tape'), (2, 2, 1, 1))])),
        ('bars', 'Sensors', place([
            (meter('living', 'bar'), (0, 0, 1, 2)), (meter('office_co2', 'bar', **CO2), (1, 0, 1, 2)),
            (meter('phone', 'bar', **BATTERY), (2, 0, 1, 2)),
            (meter('house', 'bar'), (0, 2, 2, 1)), (meter('cpu', 'bar', **GREEN_ORANGE_RED), (2, 2, 1, 1))])),
    ],
    # The 4-inch Guition and the CYD: two by three.
    (2, 3): [
        ('mix', 'Overview', place([
            (meter('phone', **BATTERY), (0, 0, 1, 1)), (meter('humidity', 'tape'), (1, 0, 1, 1)),
            (meter('house', 'bar'), (0, 1, 2, 1)), (meter('living'), (0, 2, 2, 1))])),
        ('climate', 'Climate', place([
            (meter('office_co2', 'bar', **CO2), (0, 0, 1, 2)), (meter('living', 'tape'), (1, 0, 1, 1)),
            (meter('outside'), (1, 1, 1, 1)), (meter('pressure', 'tape'), (0, 2, 2, 1))])),
    ],
}


def day(key):
    """24 hourly samples of the last day, ending in the sensor's value now: low before dawn, high at its peak hour."""
    _, _, _, now, (low, high, peak) = SENSORS[key]
    values = []
    for h in range(24):
        hour = (run.MOMENT.hour - 23 + h) % 24
        distance = min(abs(hour - peak), 24 - abs(hour - peak))
        level = 0.5 + 0.5 * math.cos(math.pi * min(distance, 10) / 10)
        # A little of a day's own unrest, the same every run.
        level += 0.025 * math.sin(h * 1.7 + len(key)) + 0.012 * math.sin(h * 4.3)
        values.append(low + (high - low) * max(0.0, min(1.0, level)))
    # The last hours lead to the value now.
    gap = now - values[-1]
    for i in range(18, 24):
        values[i] += gap * (i - 17) / 6
    return [round(v, 2) for v in values]


def state_of(key):
    _, unit, device_class, value, _ = SENSORS[key]
    attributes = {'unit_of_measurement': unit, 'state_class': 'measurement'}
    if device_class:
        attributes['device_class'] = device_class
    return {'state': str(value), 'attributes': attributes}


class Pages(run.Run):
    def __init__(self, build, out, pictures):
        super().__init__(build, out, pictures, (1280, 720))

    async def drive(self):
        self.client = run.APIClient('127.0.0.1', self.item.port, None)
        for _ in range(240):
            if self.process.poll() is not None:
                raise RuntimeError(f'the program exited with {self.process.returncode}')
            try:
                await self.client.connect(login=True)
                break
            except Exception:
                await asyncio.sleep(0.5)
        entities, services = await self.client.list_entities_services()
        self.services = {s.name: s for s in services}
        self.inbox = next(e for e in entities if type(e).__name__ == 'TextInfo' and e.name == 'Tile settings')
        dark = next(e for e in entities if getattr(e, 'name', '') == 'Dark mode')
        self.subscribe_logs()
        if 'render_skip_calibration' in self.services:
            await self.call('render_skip_calibration')
        await self.call('render_time', epoch=int(run.MOMENT.timestamp()))
        shape = json.loads((run.REPO / 'screen_manager/app/boards.json').read_text())[self.item.board]
        side = shape['orientations']['portrait' if self.item.rotation else 'landscape']
        grid = send_layout.Grid(side['columns'], side['rows'])
        pages = PAGES[(grid.columns, grid.rows)]
        self.sender = send_layout.api_sender(self.client, services)
        region = dict(keepalive=120, clock_24h=True, numbers='point', group_min=1, percent_space=False)
        tiles, states = [], {}
        for page, (_, _, cells) in enumerate(pages):
            for n, (key, options, c, r, w, h) in enumerate(cells):
                entity = f'sensor.{key}_p{page}_{n}'
                size = NAMES.get((w, h), f'{w}x{h}')
                tiles.append(dict(entity=entity, name=SENSORS[key][0], slot=page * grid.slots + r * grid.columns + c,
                                  options={**options, 'size': size}))
                states[entity] = state_of(key)
        layout = dict(title='Meters', tiles=tiles, page_titles=[title for _, title, _ in pages])
        record = send_layout.migrate_legacy(layout, grid)
        compiled = send_layout.compile_tiles(record['layout'], grid)
        values = []
        for i, tile in enumerate(compiled):
            message = send_layout.state_message(i, tile, states)
            key = next(k for k in SENSORS if tile['entity'].startswith(f'sensor.{k}_p'))
            message['history'] = {'hours': 24, 'values': day(key)}
            values.append(message)
        bars = [[{'k': 'clock'}] for _ in record['layout']['pages']]
        await self.sender.synchronize(self.inbox.object_id, record, region, values, bars)
        shots = 0
        for look in ('light', 'dark'):
            self.client.switch_command(dark.key, look == 'dark')
            await asyncio.sleep(1.0)
            for page, (name, _, _) in enumerate(pages):
                await self.call('render_page', page=page)
                await self.page_done(page)
                await asyncio.sleep(0.5)
                await self.render(f'{name}-{look}', timeout=6)
                shots += 1
        self.client.switch_command(dark.key, False)
        return len(pages), shots


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('variants', nargs='+')
    parser.add_argument('--out', type=Path, default=run.REPO / '.esphome' / 'meter-pages' / 'out')
    args = parser.parse_args()
    args.out = args.out.resolve()
    esphome = shlex.split(os.environ.get('ESPHOME', 'esphome'))
    pictures = run.Pictures()
    for key in args.variants:
        item = host.variant(key)
        build = host.Build(item, tree=run.REPO, work=None, esphome=esphome)
        started = time.monotonic()
        ok, output = build.compile()
        if not ok:
            print(f'{key}: BUILD FAILED\n{output[-6000:]}', flush=True)
            continue
        pages = Pages(build, args.out / key, pictures)
        try:
            summary = asyncio.run(pages.run())
        except Exception as error:
            summary = f'stopped: {type(error).__name__}: {error}'
        print(f'{key}: {summary} ({time.monotonic() - started:.0f} s) {pages.warnings}', flush=True)


if __name__ == '__main__':
    main()
