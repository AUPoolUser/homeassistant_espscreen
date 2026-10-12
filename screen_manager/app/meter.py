"""The meter display of a sensor tile (firmware 0.56.0): a ring, a tape or a bar of cells showing where a value stands in
its range (components/smart_display/meter_card.h draws it). docs/METER.md says what each choice does.

The range is Home Assistant's unless the tile sets its own: a percentage runs from 0 to 100, and any other value from 0 to
100 as Home Assistant's gauge card has it, so a temperature or CO2 sensor wants a range of its own. The colour is one
(the tile's own, or one chosen) or two or three segments, each a colour of Home Assistant's up to a threshold in the
sensor's own unit. The inspector writes the thresholds it starts from (80 % and 90 % of the range); without them the
screen works out the same places.
"""
from __future__ import annotations

import math

# A meter's own choices on a tile's options, each first or default the one never stored.
STYLES = ('ring', 'tape', 'bar')
SEGMENTS = (1, 2, 3)
# Where the thresholds start when a tile has none of its own, as shares of the range (two segments: the first; three: both).
SHARES = (0.8, 0.9)
# The colours a segment may have: Home Assistant's own theme colours by name (its frontend's compute-color.ts
# THEME_COLORS), the ones a gauge reads in. The screen gets the colour, never the name.
COLORS = {
    'red': 0xF44336, 'pink': 0xE91E63, 'purple': 0x926BC7, 'deep-purple': 0x6E41AB, 'indigo': 0x3F51B5,
    'blue': 0x2196F3, 'light-blue': 0x03A9F4, 'cyan': 0x00BCD4, 'teal': 0x009688, 'green': 0x4CAF50,
    'light-green': 0x8BC34A, 'lime': 0xCDDC39, 'yellow': 0xFFEB3B, 'amber': 0xFFC107, 'orange': 0xFF9800,
    'deep-orange': 0xFF6F22, 'brown': 0x795548, 'grey': 0x9E9E9E, 'blue-grey': 0x607D8B}
# The colours a choice of segments starts with: green, then red; green, orange and red. One segment is the tile's own.
DEFAULT_COLORS = {2: ('green', 'red'), 3: ('green', 'orange', 'red')}
KEYS = ('meter', 'min', 'max', 'segments', 'colors', 'thresholds')
# The largest number a range or a threshold takes: what fits the screen's float with room to spare.
LIMIT = 1e9


def number(value):
    """A finite number of JSON (not a bool), else None."""
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or abs(value) > LIMIT:
        return None
    return value


def validate(options):
    """The meter choices of a tile's options, checked and without defaults; ValueError(key) on a wrong one. A tile whose
    display is not the meter keeps none of them."""
    if options.get('display') != 'meter':
        return {k: v for k, v in options.items() if k not in KEYS}
    out = dict(options)
    if 'meter' in out:
        if out['meter'] not in STYLES:
            raise ValueError('meter')
        if out['meter'] == STYLES[0]:
            del out['meter']
    if 'min' in out or 'max' in out:
        low, high = number(out.get('min')), number(out.get('max'))
        if low is None or high is None or not low < high:
            raise ValueError('min' if low is None else 'max')
    segments = out.get('segments', 1)
    if type(segments) is not int or segments not in SEGMENTS:
        raise ValueError('segments')
    if segments == 1:
        out.pop('segments', None)
    if 'colors' in out:
        colors = out['colors']
        if not isinstance(colors, list) or len(colors) != segments or any(c not in COLORS for c in colors):
            raise ValueError('colors')
        if segments > 1 and tuple(colors) == DEFAULT_COLORS[segments]:
            del out['colors']
    if 'thresholds' in out:
        values = out['thresholds']
        if not isinstance(values, list) or len(values) != segments - 1 or any(number(v) is None for v in values) or \
                any(a >= b for a, b in zip(values, values[1:])):
            raise ValueError('thresholds')
        if not values:
            del out['thresholds']
    return out


def screen_options(options):
    """A meter's choices as the screen reads them: the colours as numbers (0xRRGGBB), everything else as stored."""
    if 'colors' not in options:
        return options
    return {**options, 'colors': [COLORS[c] for c in options['colors'] if c in COLORS]}
