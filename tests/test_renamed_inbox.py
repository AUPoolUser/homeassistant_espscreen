from manager_fixtures import with_screen_grid
"""Firmware 0.2.34 gave the screen entities English names. Home Assistant removes a renamed ESPHome entity
and registers it under a new entity id, so the manager moves a screen's layout and update history to the
new inbox id instead of orphaning them (app 0.2.40)."""
import asyncio
from datetime import timezone
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'screen_manager/app'))
from core import FIRMWARE_VERSION, device_prefixes, discover_screens, entity_slug, inbox_prefix

HAS_AIOHTTP = importlib.util.find_spec('aiohttp') is not None

DUTCH = {'text': 'Tegelinstellingen', 'firmware': 'Schermfirmware', 'node': 'Apparaatnaam', 'ip': 'IP-adres'}
ENGLISH = {'text': 'Tile settings', 'firmware': 'Screen firmware', 'node': 'Device name', 'ip': 'IP address'}


def entities(prefix, device, names, firmware, node, ip='10.0.0.5'):
    """Registry entries and states one screen creates; 'Node Status' is a name the translation kept."""
    ids = {'text': f'text.{prefix}_{entity_slug(names["text"])}', 'firmware': f'sensor.{prefix}_{entity_slug(names["firmware"])}',
           'node': f'sensor.{prefix}_{entity_slug(names["node"])}', 'ip': f'sensor.{prefix}_{entity_slug(names["ip"])}',
           'status': f'binary_sensor.{prefix}_node_status'}
    registry = [{'entity_id': ids[key], 'platform': 'esphome', 'original_name': names[key], 'device_id': device} for key in names]
    registry.append({'entity_id': ids['status'], 'platform': 'esphome', 'original_name': 'Node Status', 'device_id': device})
    states = {ids['text']: {'state': 'Synced'}, ids['firmware']: {'state': firmware}, ids['node']: {'state': node},
              ids['ip']: {'state': ip}, ids['status']: {'state': 'on'}}
    registry.append({'entity_id': f'sensor.{prefix}_screen_layout', 'platform': 'esphome', 'device_id': device, 'original_name': 'Screen layout'})
    states[f'sensor.{prefix}_screen_layout'] = {'state': '320x240 2x3 143dpi compact'}
    return registry, states


class PrefixTests(unittest.TestCase):
    def test_slugs_and_prefixes(self):
        self.assertEqual([entity_slug(n) for n in ('Tile settings', 'IP-adres', 'Node Status', 'Guition schermtype')],
                         ['tile_settings', 'ip_adres', 'node_status', 'guition_schermtype'])
        self.assertEqual(inbox_prefix('text.office_1_tegelinstellingen'), 'office_1')
        self.assertEqual(inbox_prefix('text.office_1_tile_settings'), 'office_1')
        for other in ('text.tile_settings', 'sensor.office_1_tile_settings', 'text.office_1_tile_settings_2', 'text.my_inbox', None):
            self.assertIsNone(inbox_prefix(other), other)
        registry, _ = entities('office_1', 'd1', ENGLISH, '0.2.34', 'office-1')
        registry.append({'entity_id': 'text.renamed_by_hand', 'platform': 'esphome', 'original_name': 'Tile settings', 'device_id': 'd1'})
        registry.append({'entity_id': 'light.office_1_lamp', 'platform': 'hue', 'original_name': 'Lamp', 'device_id': 'd1'})
        self.assertEqual(device_prefixes(registry, 'd1'), {'office_1'})
        self.assertEqual(device_prefixes(registry, 'd2'), set())

    def test_both_languages_are_discovered(self):
        for names, inbox in ((DUTCH, 'text.office_1_tegelinstellingen'), (ENGLISH, 'text.office_1_tile_settings')):
            registry, states = entities('office_1', 'd1', names, '0.2.33', 'office-1')
            [screen] = discover_screens(registry, states, [{'id': 'd1', 'name': 'Office 1'}], [])
            self.assertEqual((screen['id'], screen['firmware'], screen['node'], screen['ip']), (inbox, '0.2.33', 'office-1', '10.0.0.5'))


class FakeFirmware:
    """The ESPHome CLI stand-in: an install reflashes the screen with English entity names."""
    def __init__(self, ha):
        self.ha, self.task, self.job, self.calls = ha, None, None, []

    def profile_names(self):
        return {'office-1.yaml': {'node': 'office-1', 'friendly': 'Office 1'}}

    # A screen's last image against its slot (Firmware.image_room): none here, the profile was never built.
    def image_room(self, name, word=None):
        return None

    def start(self, data):
        self.calls.append(data)
        self.job = {'state': 'running', **data}
        self.task = asyncio.create_task(self.run())
        return self.job

    async def run(self):
        await asyncio.sleep(0)
        registry, states = entities('office_1', 'd1', ENGLISH, FIRMWARE_VERSION, 'office-1')
        self.ha.registry = registry + [item for item in self.ha.registry if item.get('device_id') != 'd1']
        self.ha.states = {**{k: v for k, v in self.ha.states.items() if 'office_1' not in k}, **states}
        self.job['state'] = 'success'


def fake_ha():
    class HA:
        online = True
        time_zone = timezone.utc

        def __init__(self):
            office, office_states = entities('office_1', 'd1', DUTCH, '0.2.30', 'office-1')
            kitchen, kitchen_states = entities('kitchen', 'd2', ENGLISH, FIRMWARE_VERSION, 'kitchen', '10.0.0.6')
            self.registry = office + kitchen + [{'entity_id': 'light.a', 'platform': 'hue'}]
            self.states = {**office_states, **kitchen_states, 'light.a': {'state': 'on', 'attributes': {'friendly_name': 'Lamp'}}}
            self.devices, self.areas = [{'id': 'd1', 'name': 'Office 1'}, {'id': 'd2', 'name': 'Kitchen'}], []
            self.changed, self.dirty, self.relevant, self.messages, self.calls = asyncio.Event(), set(), None, [], []

        async def send(self, inbox, message, action=None):
            self.messages.append((inbox, message, action))

        async def request(self, kind, **data):
            self.calls.append((kind, data))
    return HA()


OLD, NEW, KITCHEN = 'text.office_1_tegelinstellingen', 'text.office_1_tile_settings', 'text.kitchen_tile_settings'
LAYOUT = {'title': 'Office', 'tiles': [{'entity': 'light.a', 'name': 'Lamp', 'slot': 0}]}


@unittest.skipUnless(HAS_AIOHTTP, 'Run using .venv-portal/bin/python for server tests')
class RenamedInboxTests(unittest.IsolatedAsyncioTestCase):
    def manager(self, path, stored=None, updates=None, ha=None):
        from server import Manager
        if stored is not None:
            (Path(path) / 'screens.json').write_text(json.dumps({'version': 1, 'screens': stored}))
        if updates is not None:
            (Path(path) / 'updates.json').write_text(json.dumps({'version': 1, 'auto': False, **updates}))
        m = Manager(with_screen_grid(ha or fake_ha()), Path(path) / 'screens.json')
        m.firmware = FakeFirmware(m.ha)
        for attr in ('verify_timeout', 'settle_seconds', 'pause_seconds', 'poll_seconds'):
            setattr(m.updates, attr, 1 if attr == 'verify_timeout' else 0)
        return m

    def reflash(self, m):
        registry, states = entities('office_1', 'd1', ENGLISH, FIRMWARE_VERSION, 'office-1')
        m.ha.registry = registry + [item for item in m.ha.registry if item.get('device_id') != 'd1']
        m.ha.states = {**{k: v for k, v in m.ha.states.items() if 'office_1' not in k}, **states}
        m.screens()
        m.refresh_page_records()

    async def test_reflash_moves_layout_and_update_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            kitchen = {'title': 'Kitchen', 'tiles': []}
            m = self.manager(tmp, {OLD: LAYOUT, KITCHEN: kitchen},
                             {'hosts': {OLD: '10.0.0.5'}, 'results': {OLD: {'state': 'success', 'message': 'Updated.'}}})
            self.assertEqual(sorted(s['id'] for s in m.screens()), [KITCHEN, OLD])
            self.assertEqual(m.aliases, {})
            self.reflash(m)
            self.assertEqual(sorted(s['id'] for s in m.screens()), [KITCHEN, NEW])
            self.assertEqual(m.layouts[NEW]['title'], 'Office')
            self.assertNotIn(OLD, m.layouts)
            self.assertEqual(m.layouts[KITCHEN]['title'], kitchen['title'])
            self.assertEqual(m.layouts[KITCHEN]['tiles'], kitchen['tiles'])
            self.assertEqual(json.loads((Path(tmp) / 'screens.json').read_text())['screens'].keys(), {NEW, KITCHEN})
            self.assertEqual((m.updates.hosts, list(m.updates.results)), ({NEW: '10.0.0.5'}, [NEW]))
            self.assertEqual(json.loads((Path(tmp) / 'updates.json').read_text())['hosts'], {NEW: '10.0.0.5'})
            self.assertEqual(m.aliases, {OLD: NEW})
            self.assertEqual(m.screen(OLD)['id'], NEW, 'lookups by the old id follow the screen')
            # A page opened before the rename still saves to the right screen.
            m.save(OLD, {**LAYOUT, 'title': 'Office 2'})
            self.assertEqual((m.layouts[NEW]['title'], OLD in m.layouts), ('Office 2', False))
            # The sync loop sends the layout to the new inbox.
            m.ha.changed.set()
            runner = asyncio.create_task(m.run())
            for _ in range(50):
                await asyncio.sleep(0.02)
                if any(inbox == NEW for inbox, _, _ in m.ha.messages):
                    break
            runner.cancel()
            self.assertTrue(any(inbox == NEW and msg['op'] == 'layout' and msg['inbox'] == NEW for inbox, msg, _ in m.ha.messages))

    async def test_pages_opened_before_the_rename_keep_working(self):
        from aiohttp.test_utils import TestClient, TestServer
        from server import create_app
        with tempfile.TemporaryDirectory() as tmp:
            m = self.manager(tmp, {OLD: LAYOUT})
            async with TestClient(TestServer(create_app(m, True))) as client:
                csrf = (await (await client.get('/api/inventory?light=1')).json())['csrf']
                self.reflash(m)
                light = await (await client.get('/api/inventory?light=1')).json()
                office = next(s for s in light['screens'] if s['node'] == 'office-1')
                self.assertEqual((office['id'], office['layout']['title']), (NEW, 'Office'))
                inspected = await (await client.get(f'/api/screens/{OLD}/inspect')).json()
                self.assertEqual((inspected['screen']['id'], [t['entity'] for t in inspected['tiles']]), (NEW, ['light.a']))
                document = m.store.get(NEW)
                saved = await client.put(f'/api/screens/{OLD}', headers={'X-Screen-CSRF': csrf}, json={
                    'format': 'pages-v2', 'revision': document['revision'], 'layout': {**document['layout'], 'title': 'Office 3'}})
                self.assertEqual(saved.status, 200)
                self.assertEqual((m.layouts[NEW]['title'], OLD in m.layouts), ('Office 3', False))

    async def test_restart_after_reflash_adopts_by_device_prefix(self):
        with tempfile.TemporaryDirectory() as tmp:
            ha = fake_ha()
            registry, states = entities('office_1', 'd1', ENGLISH, FIRMWARE_VERSION, 'office-1')
            ha.registry = registry + [item for item in ha.registry if item.get('device_id') != 'd1']
            ha.states = {**{k: v for k, v in ha.states.items() if 'office_1' not in k}, **states}
            m = self.manager(tmp, {OLD: LAYOUT}, ha=ha)
            self.assertEqual(sorted(s['id'] for s in m.screens()), [KITCHEN, NEW])
            self.assertEqual(list(m.layouts), [NEW])
            self.assertIn(NEW, [screen['id'] for screen in m.inventory()[0]])

    async def test_orphaned_layouts_of_other_screens_stay_put(self):
        with tempfile.TemporaryDirectory() as tmp:
            hall = 'text.hall_tegelinstellingen'
            m = self.manager(tmp, {hall: LAYOUT})
            self.reflash(m)
            m.screens()
            self.assertEqual(list(m.store.records()), [hall], 'a removed screen keeps its layout; nobody else takes it')
            self.assertEqual(json.loads(m.store.get(hall)['payload']), LAYOUT)
            self.assertEqual(m.aliases, {})

    async def test_a_layout_on_the_new_id_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            newer = {'title': 'New', 'tiles': []}
            m = self.manager(tmp, {OLD: LAYOUT, NEW: newer})
            self.reflash(m)
            m.screens()
            self.assertEqual(m.layouts[NEW]['title'], newer['title'])
            self.assertEqual(m.layouts[OLD]['tiles'], LAYOUT['tiles'])
            self.assertEqual(m.aliases, {OLD: NEW})
            m.ha.registry = list(m.ha.registry)  # a later registry refresh does not try again
            before = dict(m.layouts)
            m.screens()
            self.assertEqual((m.layouts, m.aliases), (before, {OLD: NEW}))

    async def test_update_round_follows_the_screen_through_the_rename(self):
        with tempfile.TemporaryDirectory() as tmp:
            m = self.manager(tmp, {OLD: LAYOUT})
            [screen] = [s for s in m.screens() if s['id'] == OLD]
            self.assertTrue(m.updates.state_for(screen)['available'])
            m.updates.start(OLD)
            await m.build_queue.idle()
            self.assertEqual(m.firmware.calls, [{'file': 'office-1.yaml', 'action': 'install', 'target': '10.0.0.5'}])
            self.assertEqual(list(m.updates.results), [NEW])
            self.assertEqual(m.updates.results[NEW]['state'], 'success', m.updates.results[NEW]['message'])
            self.assertEqual((m.updates.current, m.updates.queue), (None, []))
            self.assertEqual(list(m.layouts), [NEW])
            [after] = [s for s in m.screens() if s['id'] == NEW]
            self.assertFalse(m.updates.state_for(after)['available'])

    async def test_nightly_round_reports_through_the_new_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            m = self.manager(tmp, {OLD: LAYOUT})
            async def fails_after_rename():
                await asyncio.sleep(0)
                self.reflash(m)
                m.firmware.job['state'] = 'failed'
            m.firmware.run = fails_after_rename
            await m.updates.run_round([OLD], automatic=True)
            self.assertEqual(m.updates.results[NEW]['state'], 'failed')
            self.assertEqual(m.ha.calls[0][1]['domain'], 'persistent_notification')
            self.assertIn('Office 1', m.ha.calls[0][1]['service_data']['message'])


if __name__ == '__main__':
    unittest.main()
