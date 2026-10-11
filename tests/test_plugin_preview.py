"""The plugin bench (tools/render/plugin_preview.py, the plugins repository's tools/preview.py) before the compiler: a
glass no board has written into the host mirror, the bench's own actions in a build with a plugin, the sizes a tile is
shown at on each grid, preview.yaml's moments, and what a plugin adds read from its manifest and its code.

The bench itself builds and drives the firmware, which needs ESPHome and SDL2; the parts here that need its driver
(aioesphomeapi) are skipped where it is not installed.
"""
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools' / 'render'))
sys.path.insert(0, str(ROOT / 'tools'))
import host  # noqa: E402

PROBE = ROOT / 'tests' / 'fixtures' / 'plugins' / 'host_probe'
DRIVER = importlib.util.find_spec('aioesphomeapi') is not None


class Glass(unittest.TestCase):
    def test_a_glass_of_its_own_replaces_the_boards_sizes_look_and_grids(self):
        glass = {'PANEL_W': '1024', 'PANEL_H': '600', 'DISPLAY_DPI': '170', 'GRID_COLS': '4', 'GRID_ROWS': '3',
                 'GRID_COLS_PORTRAIT': '2', 'GRID_ROWS_PORTRAIT': '5', 'look': 'compact'}
        with tempfile.TemporaryDirectory() as tmp:
            build = host.Build(host.variant('guition'), work=tmp, glass=glass)
            build.package()
            mirror = Path(tmp) / 'host' / 'guition' / 'packages'
            board = (mirror / 'boards' / host.variant('guition').file).read_text()
            for key, value in glass.items():
                if key != 'look':
                    self.assertRegex(board, rf'(?m)^  {key}: "{value}"$', key)
            self.assertIn('look: !include ../looks/compact.yaml', board)
            self.assertTrue((mirror / 'looks' / 'compact.yaml').is_file(), 'the new look is mirrored with the chain')
            hardware = (Path(tmp) / 'host' / 'guition' / 'host-hw.yaml').read_text()
            self.assertIn('width: 1024', hardware)
            self.assertIn('height: 600', hardware)

    def test_the_bench_actions_come_with_a_plugin_only(self):
        item = host.variant('cyd')
        with tempfile.TemporaryDirectory() as tmp:
            plain = host.Build(item, work=tmp).package()
            with_plugin = host.Build(item, work=tmp, plugin=PROBE).package()
        for action in ('render_open_card', 'render_plugin_audit', 'render_bar_item'):
            self.assertNotIn(action, plain)
            self.assertIn(f'- action: {action}', with_plugin)
        self.assertIn('tessera::open_card("host_probe"', with_plugin)
        self.assertIn('- action: render_settings', plain)


@unittest.skipUnless(DRIVER, 'the bench\'s driver (aioesphomeapi) is not installed')
class Bench(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import plugin_preview
        cls.pp = plugin_preview

    def grid(self, columns, rows):
        return self.pp.send_layout.Grid(columns, rows)

    def test_sizes_by_their_names_where_a_grid_takes_them(self):
        name = self.pp.size_name
        grid = self.grid(3, 3)
        self.assertEqual([name(1, 1, grid), name(2, 1, grid), name(1, 2, grid), name(2, 2, grid), name(3, 2, grid)],
                         ['single', 'wide', 'tall', 'square', '3x2'])
        self.assertIsNone(name(3, 3, grid), 'the whole page is a size of its own')
        self.assertEqual(name(3, 3, grid, full=True), 'full')
        self.assertIsNone(name(2, 1, self.grid(1, 4)), 'one column takes no wide tile')

    def test_moments_are_made_from_the_time_of_the_run(self):
        now = 1791734400   # 2026-10-11 16:00 in Amsterdam
        made = self.pp.moments({'a': '{now+5m}', 'b': '{epoch-1h}', 'c': ['at {now}'], 'd': 3}, 'Europe/Amsterdam', now)
        self.assertEqual(made, {'a': '2026-10-11T18:05:00', 'b': now - 3600, 'c': ['at 2026-10-11T18:00:00'], 'd': 3})

    def test_what_a_plugin_adds_is_read_from_its_manifest_and_its_code(self):
        import plugins
        entry = plugins.read_folder(PROBE)
        adds = self.pp.adds(entry, PROBE)
        self.assertEqual([t['id'] for t in adds['tiles']], ['probe'])
        self.assertEqual([c['id'] for c in adds['cards']], ['detail', 'closer'])
        self.assertEqual([b['id'] for b in adds['bar_items']], ['mark'])
        self.assertTrue(adds['settings_rows'])
        self.assertTrue(adds['large_digits'])
        self.assertEqual(adds['mismatches'], [])

    def test_every_example_at_every_size_the_grid_takes(self):
        import plugins
        entry = plugins.read_folder(PROBE)
        examples = self.pp.examples_of(entry, {'tiles': [{'tile': 'probe', 'name': 'One', 'options': {'word': 'Hi'}}]})
        record, compiled, origins, bars, left = self.pp.layout_of(entry, examples, self.grid(2, 3))
        self.assertEqual(sorted(origins[i][1] for i in range(len(compiled))), ['1x1', '1x2', '2x1', '2x2'])
        self.assertTrue(all(t['options']['plugin'] == {'word': 'Hi'} for t in compiled))
        self.assertEqual(bars[0][0], {'k': 'plugin', 't': 'plugin:host_probe.mark'})
        _, compiled, _, _, left = self.pp.layout_of(entry, examples, self.grid(1, 4))
        self.assertEqual(sorted(span for _, span in left), ['2x1', '2x2'])


if __name__ == '__main__':
    unittest.main()
