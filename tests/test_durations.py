"""Home Assistant's way with a sensor's value (wishlist 107 and the meters' feedback): a duration in hours and minutes as
its frontend writes it (durations.py), and its display precision set where Home Assistant keeps it (the entity registry,
server.HomeAssistant.set_display_precision)."""
import asyncio
import sys
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'screen_manager/app'))
import durations  # noqa: E402
import ha_catalogue  # noqa: E402
import header_bar  # noqa: E402
import i18n  # noqa: E402


def duration(value, unit='h'):
    return {'state': value, 'attributes': {'device_class': 'duration', 'unit_of_measurement': unit, 'friendly_name': 'Dishwasher left'}}


class Durations(unittest.TestCase):
    def test_as_home_assistant_writes_them(self):
        # What Intl.DurationFormat's narrow style writes in a browser, which Home Assistant's formatDuration uses, without
        # a leading nought ("12m" where Home Assistant writes "0h 12m").
        cases = {('0.20', 'h'): '12m', ('0', 'h'): '0h', ('0.5', 'd'): '12h', ('0.5', 'min'): '30s', ('1.5', 'h'): '1h 30m', ('2', 'h'): '2h', ('95', 'min'): '95m',
                 ('12.5', 'min'): '12m 30s', ('1.25', 'd'): '1d 6h', ('2', 'd'): '2d'}
        for (value, unit), text in cases.items():
            self.assertEqual(durations.text(value, unit, 'en'), text)
        self.assertEqual(durations.text('0.20', 'h', 'nl'), '12 m')
        self.assertEqual(durations.text('0.20', 'h', 'de'), '12 Min.')
        self.assertEqual(durations.text('1.25', 'd', 'pt-BR'), '1 dia 6 h')
        self.assertEqual(durations.text('2', 'd', 'it'), '2gg')
        self.assertEqual(durations.text('0.2', 'h', 'hu'), '12 p')

    def test_only_what_home_assistant_writes_that_way(self):
        self.assertIsNone(durations.text('12', 's'))       # seconds stay a number with their unit
        self.assertIsNone(durations.text('unknown', 'h'))
        self.assertIsNone(durations.text('-1', 'h'))
        self.assertTrue(durations.is_duration(duration('1')['attributes']))
        self.assertFalse(durations.is_duration({'device_class': 'duration', 'unit_of_measurement': 's'}))

    def test_the_display_precision_rounds_first(self):
        self.assertEqual(durations.text('1.999', 'h', 'en', 1), '2h')
        self.assertEqual(durations.text('1.999', 'h', 'en'), '1h 59m')

    def test_a_tile_and_the_top_bar_say_it(self):
        attributes = duration('0.2')['attributes']
        self.assertEqual(ha_catalogue.screen_word('sensor.left', '0.2', attributes, None, {}), '12m')
        self.assertEqual(header_bar.value('sensor.left', duration('0.2'))[0], '12m')
        # Any other number keeps its unit.
        self.assertIsNone(ha_catalogue.screen_word('sensor.t', '21.4', {'unit_of_measurement': '°C'}, None, {}))


class DisplayPrecision(unittest.TestCase):
    def ha(self, registry):
        import server
        ha = types.SimpleNamespace(registry=registry, sent=[])
        async def request(kind, **data):
            ha.sent.append((kind, data))
            entry = dict(next(e for e in ha.registry if e['entity_id'] == data['entity_id']))
            entry['options'] = {'sensor': {**(entry.get('options') or {}).get('sensor', {}), 'display_precision': data['options']['display_precision']}}
            return {'entity_entry': entry}
        ha.request = request
        ha.display_precision = server.HomeAssistant.display_precision.__get__(ha)
        ha.set_display_precision = server.HomeAssistant.set_display_precision.__get__(ha)
        return ha

    def test_read_as_home_assistants_entity_settings(self):
        ha = self.ha([{'entity_id': 'sensor.t', 'options': {'sensor': {'suggested_display_precision': 2}}}])
        self.assertEqual(ha.display_precision('sensor.t'), {'own': None, 'suggested': 2, 'editable': True})
        self.assertEqual(ha.display_precision('sensor.yaml_only'), {'own': None, 'suggested': None, 'editable': False})

    def test_set_where_home_assistant_keeps_it(self):
        ha = self.ha([{'entity_id': 'sensor.t', 'options': {'sensor': {'suggested_display_precision': 2}}}])
        answer = asyncio.run(ha.set_display_precision('sensor.t', 0))
        # The sensor's other options go back as they are: Home Assistant replaces them as a whole.
        self.assertEqual(ha.sent, [('config/entity_registry/update', {'entity_id': 'sensor.t', 'options_domain': 'sensor',
                                                                     'options': {'suggested_display_precision': 2, 'display_precision': 0}})])
        self.assertEqual(answer, {'own': 0, 'suggested': 2, 'editable': True})
        # Default again is None, as Home Assistant's dialog sends it.
        self.assertEqual(asyncio.run(ha.set_display_precision('sensor.t', None))['own'], None)


if __name__ == '__main__':
    unittest.main()
