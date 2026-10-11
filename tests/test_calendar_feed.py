"""The calendar card's events (screen_manager/app/calendar_feed.py) against Home Assistant's own rules, on events read
from a real Home Assistant: three local calendars with test events on the bench (tests/fixtures/calendar/bench.json).

Home Assistant's rules: a start without a time is an all-day event whose end does not count; a datetime carries its own
zone; a calendar's colour is its registry's own, else the frontend's palette by its place among all calendars."""
import json
import sys
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'screen_manager/app'))
import calendar_feed as cf  # noqa: E402

DATA = json.loads((ROOT / 'tests/fixtures/calendar/bench.json').read_text())
TZ = ZoneInfo('Europe/Amsterdam')
NOW = datetime(2026, 10, 11, 14, 10, tzinfo=TZ)  # a Sunday, during the Planning session (Work, 13:50 - 15:20)


def card(entity='calendar.work', **options):
    return cf.card({'entity': entity, 'options': options}, DATA['events'], DATA['states'], {}, TZ, NOW)


def titles(data):
    return [row[4] for row in data['e']]


class Card(unittest.TestCase):
    def test_today_and_window(self):
        data = card()
        self.assertEqual(data['d'], [2026, 10, 11, 6])
        # From the Monday of this week through the days ahead.
        self.assertEqual(data['r'], [-6, cf.AHEAD_DEFAULT])

    def test_all_day_spans_whole_days_with_an_exclusive_end(self):
        sprint = next(row for row in card()['e'] if row[4] == 'Sprint week')
        self.assertEqual(sprint[2] & cf.ALL_DAY, cf.ALL_DAY)
        self.assertEqual((sprint[0], sprint[1]), (0, 4 * 1440))  # 11 up to (not including) 15 October

    def test_times_are_minutes_from_today_in_home_assistants_zone(self):
        design = next(row for row in card()['e'] if row[4] == 'Design review')
        self.assertEqual((design[0], design[1]), (13 * 60 + 30, 15 * 60))
        self.assertEqual(design[5], 'Room A')

    def test_calendars_of_the_card_and_their_colours(self):
        data = card(calendars=['calendar.family', 'calendar.rooms'])
        names = [name for _, name in data['c']]
        self.assertEqual(names, ['Work', 'Family', 'Rooms'])
        # The palette by place among all calendars sorted by id, as Home Assistant's calendar panel picks it.
        every = sorted(DATA['states'])
        self.assertEqual(data['c'][0][0], cf.PALETTE[every.index('calendar.work')])
        self.assertEqual({row[3] for row in data['e']}, {0, 1, 2})

    def test_registry_colour_wins(self):
        self.assertEqual(cf.colour_of('calendar.work', {'options': {'calendar': {'color': '#123456'}}}, list(DATA['states'])), 0x123456)
        self.assertEqual(cf.colour_of('calendar.work', {'options': {'calendar': {'color': 'red'}}}, list(DATA['states'])), 0xF44336)

    def test_place_filter(self):
        data = card(calendars=['calendar.rooms', 'calendar.family'], places=['room a'])
        self.assertTrue(data['e'])
        self.assertTrue(all(row[5] == 'Room A' for row in data['e']))

    def test_word_filters(self):
        self.assertEqual(set(titles(card(words=['review']))), {'Design review', 'Retainer review'})
        self.assertNotIn('Kick-off call', titles(card(hide_words=['kick-off'])))

    def test_all_day_and_private(self):
        self.assertNotIn('Sprint week', titles(card(all_day=False)))
        data = card(private=True)
        self.assertTrue(all(row[4] == '' and row[5] == '' and row[2] & cf.PRIVATE for row in data['e']))
        self.assertEqual(data['n'], '')

    def test_month_glance_marks_the_days(self):
        data = card(calendars=['calendar.family'])
        start, masks = data['g']
        self.assertEqual(len(masks), 42)
        today = -start
        self.assertTrue(masks[today] & 1 and masks[today] & 2)  # Work and Family both have something today

    def test_budget_counts_what_it_leaves_out(self):
        many = {'calendar.work': [{'start': f'2026-10-{12 + i // 8:02d}T{8 + i % 8:02d}:00:00+02:00',
                                   'end': f'2026-10-{12 + i // 8:02d}T{8 + i % 8:02d}:30:00+02:00',
                                   'summary': 'A rather long meeting title for the budget ' + str(i), 'location': 'Room A'}
                                  for i in range(80)]}
        data = cf.card({'entity': 'calendar.work'}, many, DATA['states'], {}, TZ, NOW)
        self.assertLessEqual(len(json.dumps(data, separators=(',', ':')).encode()), cf.BUDGET + 200)
        self.assertGreater(data['m'], 0)
        self.assertEqual(len(data['e']) + data['m'], 80)


class Validate(unittest.TestCase):
    def test_defaults_are_not_stored(self):
        self.assertEqual(cf.validate({'all_day': True, 'tentative': True, 'private': False, 'ahead': 14, 'style': 'events',
                                      'soon': 0, 'start_view': 'auto', 'places': [' ', '']}), {})

    def test_choices(self):
        self.assertEqual(cf.validate({'calendars': ['calendar.a', 'calendar.a'], 'places': [' Room A '], 'soon': 15, 'style': 'busy_free'}),
                         {'calendars': ['calendar.a'], 'places': ['Room A'], 'soon': 15, 'style': 'busy_free'})

    def test_refuses(self):
        for options in ({'calendars': ['light.a']}, {'ahead': 0}, {'ahead': 40}, {'soon': 200}, {'style': 'x'},
                        {'start_view': 'year'}, {'all_day': 'yes'}, {'places': 'Room A'}):
            with self.assertRaises(ValueError):
                cf.validate(options)


if __name__ == '__main__':
    unittest.main()
