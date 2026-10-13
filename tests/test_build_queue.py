"""The app's one build line (build_queue.py, docs/BUILDS.md): updates, plugin builds, New screen and Firmware & USB wait
their turn in it, one build at a time, and nothing is refused because something else builds."""
import asyncio
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'screen_manager/app'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_queue import BuildQueue, Round  # noqa: E402

HAS_AIOHTTP = importlib.util.find_spec('aiohttp') is not None


class Firmware:
    """ESPHome as the line sees it: one job at a time (Firmware.start refuses a second), each held until the test lets it
    go (`gate`), with a log of its own."""

    def __init__(self):
        self.task, self.job, self.logs, self.calls, self.gate, self.fail = None, None, [], [], None, set()

    def check(self, data):
        if data.get('file') == 'missing.yaml':
            raise ValueError('Choose a profile.')

    def start(self, data):
        assert not (self.task and not self.task.done()), 'two builds at once'
        self.calls.append((data['file'], data['action']))
        self.job = {'file': data['file'], 'action': data['action'], 'state': 'running', 'started': len(self.calls)}
        self.logs = [f"ESPHome: {data['action']} {data['file']}"]
        self.task = asyncio.get_running_loop().create_task(self.run(data))

    async def run(self, data):
        if self.gate:
            await self.gate.wait()
        await asyncio.sleep(0)
        failed = (data['file'], data['action']) in self.fail
        self.logs.append('ERROR it broke' if failed else f"Succeeded: {data['action']}")
        self.job['state'] = 'failed' if failed else 'success'


class Owner:
    def __init__(self):
        self.firmware = Firmware()
        self.build_queue = BuildQueue(self)
        self.told = 0

    def notify(self):
        self.told += 1


def one_step(line, file, action='install'):
    """A build of one ESPHome action, as Firmware & USB asks it."""
    async def run(build):
        return 'success' if await line.step({'file': file, 'action': action, 'target': '10.0.0.1'}) else 'failed'
    return run


class TheLine(unittest.IsolatedAsyncioTestCase):
    async def test_one_build_at_a_time_in_the_order_asked(self):
        owner = Owner()
        line = owner.build_queue
        owner.firmware.gate = asyncio.Event()
        first = line.add('update', 'hall.yaml', one_step(line, 'hall.yaml'), screen='hall')
        # It runs at once: the page never sees a build wait for nothing.
        self.assertEqual(first.state, 'running')
        second = line.add('update', 'desk.yaml', one_step(line, 'desk.yaml'), screen='desk')
        third = line.add('plugins', 'kitchen.yaml', one_step(line, 'kitchen.yaml'), screen='kitchen')
        self.assertEqual([(b.file, b.state) for b in (second, third)], [('desk.yaml', 'queued'), ('kitchen.yaml', 'queued')])
        self.assertEqual([line.view(b)['place'] for b in (second, third)], [1, 2])
        self.assertEqual(line.view(second)['after'], 'hall.yaml')
        owner.firmware.gate.set()
        await line.idle()
        self.assertEqual([c[0] for c in owner.firmware.calls], ['hall.yaml', 'desk.yaml', 'kitchen.yaml'])
        self.assertEqual([b.state for b in (first, second, third)], ['success'] * 3)

    async def test_what_a_person_follows_goes_before_what_waits_but_never_stops_what_runs(self):
        owner = Owner()
        line = owner.build_queue
        owner.firmware.gate = asyncio.Event()
        running = line.add('update', 'hall.yaml', one_step(line, 'hall.yaml'), screen='hall')
        waiting = line.add('plugins', 'desk.yaml', one_step(line, 'desk.yaml'), screen='desk')
        new_screen = line.attended({'file': 'new.yaml', 'action': 'download'})
        check = line.attended({'file': 'desk.yaml', 'action': 'validate'})
        self.assertEqual(line.line, [new_screen, check, waiting])
        self.assertEqual((running.state, new_screen.by, check.by), ('running', 'install', 'check'))
        # Asked twice (a second click): it waits once.
        self.assertIs(line.attended({'file': 'new.yaml', 'action': 'download'}), new_screen)
        # A wrong request is said at once, before it waits.
        with self.assertRaisesRegex(ValueError, 'Choose a profile'):
            line.attended({'file': 'missing.yaml', 'action': 'install'})
        owner.firmware.gate.set()
        await line.idle()
        self.assertEqual(owner.firmware.calls, [('hall.yaml', 'install'), ('new.yaml', 'download'), ('desk.yaml', 'validate'),
                                                ('desk.yaml', 'install')])

    async def test_a_build_keeps_its_outcome_and_its_log_when_the_next_starts_at_once(self):
        owner = Owner()
        line = owner.build_queue
        owner.firmware.fail.add(('hall.yaml', 'install'))
        failed = line.add('plugins', 'hall.yaml', one_step(line, 'hall.yaml'), screen='hall')
        ok = line.add('update', 'desk.yaml', one_step(line, 'desk.yaml'), screen='desk')
        await line.idle()
        self.assertEqual((failed.state, ok.state), ('failed', 'success'))
        # ESPHome's log is desk's now; hall's own stays with its build, and so does how it ended.
        self.assertIn('Succeeded: install', owner.firmware.logs)
        self.assertEqual(line.log(failed.id)['logs'], ['ESPHome: install hall.yaml', 'ERROR it broke'])
        self.assertEqual([b['id'] for b in line.payload()], [ok.id, failed.id], 'newest first')
        self.assertFalse(failed.installed)
        self.assertTrue(ok.installed)
        with self.assertRaises(ValueError):
            line.log(999)

    async def test_only_the_last_ones_that_ended_are_kept(self):
        owner = Owner()
        line = owner.build_queue
        for n in range(BuildQueue.ENDED + 3):
            line.add('install', f'{n}.yaml', one_step(line, f'{n}.yaml'), attended=True)
        await line.idle()
        self.assertEqual(len(line.payload()), BuildQueue.ENDED)

    async def test_a_build_refused_at_its_turn_fails_with_the_reason_and_the_line_goes_on(self):
        owner = Owner()
        line = owner.build_queue

        async def refused(build):
            raise ValueError('The profile is no longer there.')

        async def broken(build):
            raise RuntimeError('a bug')
        first = line.add('install', 'gone.yaml', refused, attended=True)
        second = line.add('install', 'odd.yaml', broken, attended=True)
        third = line.add('update', 'hall.yaml', one_step(line, 'hall.yaml'), screen='hall')
        with self.assertLogs('screen_manager', 'ERROR'):
            await line.idle()
        self.assertEqual((first.state, line.view(first)['reason']), ('failed', 'The profile is no longer there.'))
        self.assertEqual((second.state, third.state), ('failed', 'success'))

    async def test_a_plugin_build_and_an_update_of_one_screen_are_one_build(self):
        owner = Owner()
        line = owner.build_queue
        owner.firmware.gate = asyncio.Event()
        settled = []
        line.add('update', 'other.yaml', one_step(line, 'other.yaml'), screen='other')
        plugins = line.add('plugins', 'hall.yaml', one_step(line, 'hall.yaml'), screen='hall', plugins={'add': ['bus']})
        plugins.ends.append(lambda build: settled.append((build.by, build.installed, build.plugins['add'])))
        update_ran = []

        async def update(build):
            update_ran.append(build.id)
            return 'success' if await line.step({'file': 'hall.yaml', 'action': 'install', 'target': '10.0.0.1'}) else 'failed'
        round = Round()
        same = line.add('update', 'hall.yaml', update, screen='hall', round=round)
        self.assertIs(same, plugins)
        self.assertEqual((same.by, same.plugins['add'], round.builds), ('update', ['bus'], [same]))
        # And a plugin asked again while it waits joins too; one taken off is no longer added.
        line.add('plugins', 'hall.yaml', one_step(line, 'hall.yaml'), screen='hall', plugins={'add': ['waste'], 'remove': ['bus']})
        self.assertEqual((same.plugins['add'], same.plugins['remove']), (['waste'], ['bus']))
        owner.firmware.gate.set()
        await round.wait()
        await line.idle()
        self.assertEqual(owner.firmware.calls, [('other.yaml', 'install'), ('hall.yaml', 'install')])
        self.assertEqual(update_ran, [same.id])
        self.assertEqual(settled, [('update', True, ['waste'])])

    async def test_a_build_that_runs_takes_nothing_more(self):
        owner = Owner()
        line = owner.build_queue
        owner.firmware.gate = asyncio.Event()
        running = line.add('plugins', 'hall.yaml', one_step(line, 'hall.yaml'), screen='hall', plugins={'add': ['bus']})
        later = line.add('plugins', 'hall.yaml', one_step(line, 'hall.yaml'), screen='hall', plugins={'add': ['waste']})
        self.assertIsNot(later, running)
        self.assertEqual(line.waiting('hall.yaml'), later)
        owner.firmware.gate.set()
        await line.idle()
        self.assertEqual(owner.firmware.calls, [('hall.yaml', 'install'), ('hall.yaml', 'install')])

    async def test_a_round_that_fails_leaves_the_rest_of_its_round_out_not_what_was_asked_apart(self):
        owner = Owner()
        line = owner.build_queue
        owner.firmware.fail.add(('hall.yaml', 'install'))
        round = Round()
        line.add('update', 'hall.yaml', one_step(line, 'hall.yaml'), screen='hall', round=round)
        apart = line.add('update', 'kitchen.yaml', one_step(line, 'kitchen.yaml'), screen='kitchen')
        rest = line.add('update', 'desk.yaml', one_step(line, 'desk.yaml'), screen='desk', round=round)
        await round.wait()
        await line.idle()
        self.assertEqual((rest.state, apart.state), ('skipped', 'success'))
        self.assertEqual([c[0] for c in owner.firmware.calls], ['hall.yaml', 'kitchen.yaml'])

    async def test_a_screen_that_goes_or_is_renamed(self):
        owner = Owner()
        line = owner.build_queue
        owner.firmware.gate = asyncio.Event()
        running = line.add('update', 'hall.yaml', one_step(line, 'hall.yaml'), screen='text.old')
        waiting = line.add('update', 'desk.yaml', one_step(line, 'desk.yaml'), screen='text.desk')
        line.renamed('text.old', 'text.new')
        self.assertEqual(running.screen, 'text.new')
        line.drop_screen('text.desk')
        self.assertEqual((waiting.state, line.line), ('skipped', []))
        owner.firmware.gate.set()
        await line.idle()

    async def test_the_app_stops(self):
        owner = Owner()
        line = owner.build_queue
        owner.firmware.gate = asyncio.Event()
        running = line.add('update', 'hall.yaml', one_step(line, 'hall.yaml'), screen='hall')
        waiting = line.add('update', 'desk.yaml', one_step(line, 'desk.yaml'), screen='desk')
        await asyncio.sleep(0)
        await line.close()
        self.assertEqual((running.state, waiting.state), ('interrupted', 'interrupted'))
        self.assertTrue(running.done.is_set())
        owner.firmware.task.cancel()


@unittest.skipUnless(HAS_AIOHTTP, 'Run using .venv-portal/bin/python for server tests')
class TheApp(unittest.IsolatedAsyncioTestCase):
    """The whole app: what a person asks while something builds waits its turn instead of being refused."""

    def setup_manager(self, path):
        from test_updates import UpdaterTests
        manager = UpdaterTests.setup_manager(self, path)
        manager.updates.hosts['text.screen2'] = '10.0.0.6'
        return manager

    async def test_an_update_asked_while_another_runs_waits_its_turn(self):
        """GitHub discussion on dev: Update on a second screen while the first updated showed a 2 and fell back."""
        with tempfile.TemporaryDirectory() as tmp:
            m = self.setup_manager(tmp)
            gate = m.firmware.gate = asyncio.Event()
            original = m.firmware.run

            async def held(data):
                await gate.wait()
                await original(data)
            m.firmware.run = held
            first = m.updates.start('text.screen1')
            self.assertEqual(first['state'], 'running')
            second = m.updates.start('text.screen2')
            self.assertEqual(second['state'], 'queued')
            # Asked again while it waits: still the one update it was.
            self.assertEqual(m.updates.start('text.screen2')['state'], 'queued')
            screens = m.screens()
            builds = m.builds(screens)
            self.assertEqual((builds['text.screen1']['state'], builds['text.screen2']['state'], builds['text.screen2']['place']),
                             ('running', 'queued', 1))
            self.assertEqual(m.updates.summary(screens)['busy'], 'text.screen1')
            gate.set()
            await m.build_queue.idle()
            self.assertEqual([c['file'] for c in m.firmware.calls], ['living-room.yaml', 'kitchen.yaml'])
            self.assertEqual({k: v['state'] for k, v in m.updates.results.items()}, {'text.screen1': 'success', 'text.screen2': 'success'})

    async def test_update_all_while_one_runs_adds_the_others_and_a_plugin_build_waits_for_the_whole_update(self):
        with tempfile.TemporaryDirectory() as tmp:
            m = self.setup_manager(tmp)
            gate = asyncio.Event()
            original = m.firmware.run

            async def held(data):
                await gate.wait()
                await original(data)
            m.firmware.run = held
            m.updates.start('text.screen1')
            self.assertEqual(m.updates.start_all(), ['text.screen2'])
            with self.assertRaises(ValueError):
                m.updates.start_all()   # nothing left to add

            async def plugin_step(build):
                return 'success' if await m.build_queue.step({'file': 'other.yaml', 'action': 'install', 'target': '10.0.0.9'}) else 'failed'
            later = m.build_queue.add('plugins', 'other.yaml', plugin_step, screen='text.other')
            gate.set()
            await m.build_queue.idle()
            # Every step of an update (install, then the check that the screen reports it) before the next build.
            self.assertEqual([c['file'] for c in m.firmware.calls], ['living-room.yaml', 'kitchen.yaml', 'other.yaml'])
            self.assertEqual(later.state, 'success')

    async def test_new_screen_and_firmware_and_usb_wait_their_turn_over_the_api(self):
        from server import create_app
        from aiohttp.test_utils import TestClient, TestServer
        with tempfile.TemporaryDirectory() as tmp:
            m = self.setup_manager(tmp)
            gate = asyncio.Event()

            async def held(build):
                await gate.wait()
                return 'success'
            running = m.build_queue.add('update', 'living-room.yaml', held, screen='text.screen1')
            m.firmware.check = lambda data: None
            m.firmware.status = lambda: {'job': None, 'logs': []}
            async with TestClient(TestServer(create_app(m, True))) as client:
                inventory = await (await client.get('/api/inventory')).json()
                headers = {'X-Screen-CSRF': inventory['csrf']}
                response = await client.post('/api/firmware/jobs', headers=headers, json={'file': 'kitchen.yaml', 'action': 'validate'})
                self.assertEqual(response.status, 200)
                check = await response.json()
                self.assertEqual((check['state'], check['place'], check['by'], check['after']), ('queued', 1, 'check', 'living-room.yaml'))
                gate.set()
                await m.build_queue.idle()
                line = (await (await client.get('/api/firmware')).json())['builds']
                self.assertEqual([(b['id'], b['state']) for b in line], [(check['id'], 'success'), (running.id, 'success')])
                log = await client.get(f"/api/firmware/builds/{check['id']}/log")
                self.assertEqual(log.status, 200)
                self.assertEqual((await client.get('/api/firmware/builds/nothing/log')).status, 400)


if __name__ == '__main__':
    unittest.main()
