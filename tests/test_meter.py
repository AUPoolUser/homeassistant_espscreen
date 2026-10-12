"""A sensor's meter (screen_manager/app/meter.py, firmware 0.56.0): its choices checked and stored without defaults, kept
only while the tile shows the meter, and sent to the screen with its colours as numbers."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'screen_manager/app'))
import core  # noqa: E402
import meter  # noqa: E402
import page_layout  # noqa: E402


def layout(entity='sensor.office_co2', **options):
    return {'title': 'Meters', 'tiles': [{'entity': entity, 'options': options}]}


def stored(entity='sensor.office_co2', **options):
    return core.validate_layout(layout(entity, **options))['tiles'][0].get('options', {})


class Validate(unittest.TestCase):
    def test_defaults_are_not_stored(self):
        self.assertEqual(meter.validate({'display': 'meter', 'meter': 'ring', 'segments': 1}), {'display': 'meter'})
        self.assertEqual(meter.validate({'display': 'meter', 'segments': 3, 'colors': ['green', 'orange', 'red']}),
                         {'display': 'meter', 'segments': 3})
        self.assertEqual(meter.validate({'display': 'meter', 'segments': 2, 'colors': ['green', 'red']}),
                         {'display': 'meter', 'segments': 2})

    def test_own_choices_are_kept(self):
        options = {'display': 'meter', 'meter': 'tape', 'min': 400, 'max': 1600, 'segments': 3,
                   'colors': ['red', 'orange', 'green'], 'thresholds': [800, 1200.5]}
        self.assertEqual(meter.validate(options), options)
        # One colour of its own instead of the tile's.
        self.assertEqual(meter.validate({'display': 'meter', 'colors': ['blue']}), {'display': 'meter', 'colors': ['blue']})

    def test_wrong_choices_name_their_key(self):
        for options, key in (({'meter': 'dial'}, 'meter'), ({'min': 10}, 'max'), ({'min': 10, 'max': 10}, 'max'),
                             ({'min': 'low', 'max': 5}, 'min'), ({'min': True, 'max': 5}, 'min'),
                             ({'segments': 4}, 'segments'), ({'segments': '2'}, 'segments'),
                             ({'segments': 2, 'colors': ['green']}, 'colors'), ({'colors': ['chartreuse']}, 'colors'),
                             ({'segments': 3, 'thresholds': [90, 80]}, 'thresholds'),
                             ({'segments': 2, 'thresholds': [80, 90]}, 'thresholds'),
                             ({'segments': 2, 'thresholds': [float('nan')]}, 'thresholds')):
            with self.subTest(options=options), self.assertRaises(ValueError) as caught:
                meter.validate({'display': 'meter', **options})
            self.assertEqual(str(caught.exception), key)

    def test_another_display_keeps_none(self):
        self.assertEqual(meter.validate({'display': 'graph', 'meter': 'tape', 'min': 0, 'max': 5, 'segments': 9}), {'display': 'graph'})

    def test_screen_gets_numbers(self):
        self.assertEqual(meter.screen_options({'display': 'meter', 'segments': 2, 'colors': ['green', 'deep-orange']}),
                         {'display': 'meter', 'segments': 2, 'colors': [0x4CAF50, 0xFF6F22]})


class Layout(unittest.TestCase):
    def test_a_sensor_keeps_its_meter(self):
        self.assertEqual(stored(display='meter', meter='bar', min=400, max=1600, segments=3, thresholds=[800, 1200]),
                         {'display': 'meter', 'meter': 'bar', 'min': 400, 'max': 1600, 'segments': 3, 'thresholds': [800, 1200]})

    def test_a_wrong_choice_is_refused(self):
        with self.assertRaises(ValueError):
            stored(display='meter', segments=5)

    def test_only_a_sensor_has_a_meter(self):
        with self.assertRaises(ValueError):
            stored('light.kitchen', display='meter')
        # A sensor showing its graph leaves stale meter choices behind.
        self.assertEqual(stored(display='graph', meter='tape', segments=2), {'display': 'graph'})

    def test_page_document_names(self):
        for key, option in (('meterStyle', 'meter'), ('meterMin', 'min'), ('meterMax', 'max'), ('meterSegments', 'segments'),
                            ('meterColors', 'colors'), ('meterThresholds', 'thresholds')):
            self.assertEqual(page_layout.APPEARANCE[key], option)

    def test_screen_options(self):
        tile = {'entity': 'sensor.office_co2', 'options': {'display': 'meter', 'segments': 3, 'colors': ['red', 'orange', 'green']}}
        sent = core.screen_options(tile, {})
        self.assertEqual(sent['colors'], [0xF44336, 0xFF9800, 0x4CAF50])

    def test_event_options(self):
        options = core.tile_options({'display': 'meter', 'min': '0', 'max': '21,5', 'segments': '3', 'colors': 'red, orange, green',
                                     'thresholds': '10, 20'})
        self.assertEqual(meter.validate(options), {'display': 'meter', 'min': 0, 'max': 21.5, 'segments': 3,
                                                   'colors': ['red', 'orange', 'green'], 'thresholds': [10.0, 20.0]})

    def test_catalogue_offers_it_on_sensors_only(self):
        self.assertIn('meter', core.DISPLAYS['sensor'])
        self.assertFalse(any('meter' in displays for domain, displays in core.DISPLAYS.items() if domain != 'sensor'))


if __name__ == '__main__':
    unittest.main()
