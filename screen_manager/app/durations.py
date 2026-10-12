"""A duration sensor's value as Home Assistant shows it (wishlist 107): "1.5 h" is "1h 30m", "0.20 h" is "12m".

Home Assistant's frontend does this for a sensor with device class duration and a unit of min, h or d
(compute_state_display.ts and formatDuration in src/common/datetime/format_duration.ts): it rounds the value to the
entity's display precision when it has one, splits it into whole days and hours, hours and minutes, or minutes and
seconds, and writes them with Intl.DurationFormat in its narrow style, the smaller unit only when it is not nought. One
choice of ours: a larger unit that is nought is left out too ("12m", where Home Assistant writes "0h 12m"), unless it is
all there is ("0h"). A value in seconds stays a number with its unit. The words below are what that narrow style
writes in the languages of the screens (CLDR, as a browser's Intl.DurationFormat gives them), so a screen says what
Home Assistant says in the same language.
"""
from __future__ import annotations

import math

UNITS = ('min', 'h', 'd')
# Per language: each unit's word for one and for more ({n} is the number), and what stands between two units.
WORDS = {
    'en': ({'d': ('{n}d', '{n}d'), 'h': ('{n}h', '{n}h'), 'm': ('{n}m', '{n}m'), 's': ('{n}s', '{n}s')}, ' '),
    'nl': ({'d': ('{n} d', '{n} d'), 'h': ('{n} u', '{n} u'), 'm': ('{n} m', '{n} m'), 's': ('{n} s', '{n} s')}, ', '),
    'de': ({'d': ('{n} T', '{n} T'), 'h': ('{n}h', '{n}h'), 'm': ('{n} Min.', '{n} Min.'), 's': ('{n} Sek.', '{n} Sek.')}, ', '),
    'es': ({'d': ('{n}d', '{n}d'), 'h': ('{n}h', '{n}h'), 'm': ('{n}min', '{n}min'), 's': ('{n}s', '{n}s')}, ' '),
    'fr': ({'d': ('{n}j', '{n}j'), 'h': ('{n}h', '{n}h'), 'm': ('{n}min', '{n}min'), 's': ('{n}s', '{n}s')}, ' '),
    'hu': ({'d': ('{n} nap', '{n} nap'), 'h': ('{n} ó', '{n} ó'), 'm': ('{n} p', '{n} p'), 's': ('{n} mp', '{n} mp')}, ' és '),
    'it': ({'d': ('{n}g', '{n}gg'), 'h': ('{n}h', '{n}h'), 'm': ('{n}min', '{n}min'), 's': ('{n}s', '{n}s')}, ' '),
    'pl': ({'d': ('{n} d.', '{n} d.'), 'h': ('{n} h', '{n} h'), 'm': ('{n} min', '{n} min'), 's': ('{n} s', '{n} s')}, ' i '),
    'pt': ({'d': ('{n} dia', '{n} dias'), 'h': ('{n} h', '{n} h'), 'm': ('{n} min', '{n} min'), 's': ('{n} s', '{n} s')}, ' '),
}


def _one(language, n):
    """CLDR's plural category "one" for these languages: 1, and in Portuguese 0 as well."""
    return n in (0, 1) if (language or "en").split("-")[0].lower() == "pt" else n == 1


def text(value, unit, language='en', precision=None):
    """The duration as Home Assistant writes it, or None when it is not one Home Assistant writes that way."""
    if unit not in UNITS:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number) or number < 0:
        return None
    if type(precision) is int and 0 <= precision <= 6:
        number = round(number, precision)
    big = math.floor(number)
    small = math.floor((number - big) * (24 if unit == 'd' else 60) + 1e-9)
    names = {'d': ('d', 'h'), 'h': ('h', 'm'), 'min': ('m', 's')}[unit]
    words, joiner = WORDS.get((language or 'en').split('-')[0].lower(), WORDS['en'])
    def part(name, n):
        one, other = words[name]
        return (one if _one(language, n) else other).format(n=n)
    # A nought before the smaller unit says nothing: "12m", not "0h 12m" (the one place we differ from Home Assistant).
    parts = ([part(names[0], big)] if big or not small else []) + ([part(names[1], small)] if small else [])
    return joiner.join(parts)


def is_duration(attributes):
    """A sensor Home Assistant writes as a duration: device class duration, in minutes, hours or days."""
    attributes = attributes if isinstance(attributes, dict) else {}
    return attributes.get('device_class') == 'duration' and attributes.get('unit_of_measurement') in UNITS
