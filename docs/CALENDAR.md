# The calendar card

A tile for a Home Assistant calendar (`calendar.*`), or for several calendars on one card. It shows more as it gets more
room, and a tap opens a full screen with the day, the week and the month. It works with any calendar Home Assistant
has: Local Calendar, Google, CalDAV, a remote ICS feed and others.

## What it shows

The card picks its view from the room it gets, never from the board it runs on:

| Room | View | What you see |
|---|---|---|
| One cell | Now | The event of the moment (or Free) and until when, with a thin bar of how far it has come. |
| A taller or 2 x 2 card | Up next | The calendar's name and today's date, then one block in the event's colour with its title as large as fits. Between events it shows the next one and how long until it starts. |
| Room for a list | Agenda | Up next, and the few events that follow, grouped by day. The rest is one quiet line ("12 more this week"). |
| A wide card | Columns | Today and the next days side by side. |
| A large card (four days of 16 mm and six readable hours) | Week | Days as columns, hours as rows, a red line at now, and a tag such as "1 earlier" on a day with events outside the hours shown. |

The round icon follows Home Assistant's own icons for a calendar: a calendar with a check mark in amber while an event
with times runs, an empty calendar in grey while none does. An all-day event alone does not count as busy.

## The full screen

A tap on the card opens the full screen. Its header has a close key, the card's name, a view key that names the view
on show (Up next, Day, Week or Month), Today, and back and forward. A narrow screen leaves out back and forward.

- **Week**: the days of the week as columns. The day heads and all-day events stay in place while the hours scroll,
  and the week opens an hour before now. Glass too small for a readable week shows the week as colour without words.
- **Day**: a strip of the week's days with a dot per calendar that has something that day; a tap on a day shows it.
  On tall glass the day is a timeline you can scroll, else a list of blocks in the calendars' colours.
- **Month**: the month at a glance. Large cells show the first titles, small cells a dot per calendar. On wide glass
  the chosen day's events stand beside the month.
- **An event**: a tap opens a sheet with its title, calendar, day, times, place and notes.

## The card's choices

Set in the editor's inspector for the tile:

- **Show**: "Events" (titles, what comes next, the week, the month) or "Free or busy" (a large Free, Starts soon or
  Busy, the next booking and how long until it, titles optional). Both work everywhere: a family calendar at home or a
  sign beside a meeting room.
- **Calendars**: the calendars on the card. The tile's own is first; up to five more can join it.
- **Place**: only events at these places, for example one meeting room. The choices are the places your calendars'
  events name.
- **Words in the title**: only events with one of these words, or leave out events with them.
- **All-day events**, **Tentative events** and **Hide titles** (titles shown as "Busy").
- **Looks ahead**: how many days the list and the week hold (1 to 31, 14 by default).
- **Starts soon**: how many minutes before an event the card says Starts soon (off by default).
- **Full screen opens on**: Auto, Up next, Day, Week or Month.

The app does the filtering: the screen only gets the events it shows.

## How the events reach the screen

The app asks Home Assistant for the events of a card's calendars with `calendar.get_events`, from the Monday of this
week through the days ahead and the whole month on show, and fetches again after two minutes or as soon as one of the
calendars changes in Home Assistant. Home Assistant writes out repeating events itself.

It follows Home Assistant's rules: a start without a time is an all-day event whose end does not count, an event with
times keeps its own time zone and is shown in Home Assistant's, and a calendar's colour is the one set for it in Home
Assistant, else the colour Home Assistant's calendar panel gives it.

The events travel in the tile's state message (`x.cal`), nearest first, within a fixed budget of the message; an event
that does not fit is counted and shown as "more", never dropped in silence. A screen without PSRAM keeps up to 24
events, one with PSRAM up to 80.

## Where it lives

| Part | File |
|---|---|
| The views and the full screen, planned | `components/smart_display/calendar_card.h` |
| Painting a plan, one object per card | `components/smart_display/calendar_paint.h`, `calendar_view.cpp` |
| Fetching, filtering and packing the events | `screen_manager/app/calendar_feed.py` |
| The type | `catalogue/calendar.yaml` |
| Tests | `tests/test_calendar_card.cpp`, `tests/test_calendar_feed.py` |
| A study of every view on every board, in host LVGL | `tools/render/calendar_firmware.py` |
