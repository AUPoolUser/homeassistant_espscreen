"""Render the meter's real planner and painter (components/smart_display/meter_card.h, meter_paint.h) on real board metrics.

Host only: no firmware files, storage or device configuration change. Every look (ring, tape, bar) on every span a board's
grid takes, lying down and standing up, with a few sensors (CO2 in three segments, a percentage, a long name, a sensor that
is unavailable), and the run counts every word that had to be shortened (CUT) and everything outside its card (OVERFLOW).
Run with ESPHome's Python:
  uv run --no-project --python 3.13 --with esphome==2026.9.0 --with pillow python tools/render/meter_firmware.py [build|sheets]
Needs SDL2. METER_BOARDS=cyd,guition limits the variants.
"""
import json, os, subprocess, sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import profiles
WORK = ROOT / '.esphome/meter-render'
OUT = Path(os.environ.get('METER_RENDER_OUT', str(WORK / 'out'))).resolve()
# (variant, board, orientation)
VARIANTS = [('cyd', 'cyd', 'landscape'), ('cyd_portrait', 'cyd', 'portrait'), ('guition', 'guition', 'landscape'),
            ('waveshare43', 'waveshare43', 'landscape'), ('waveshare43_portrait', 'waveshare43', 'portrait'),
            ('waveshare7', 'waveshare7', 'landscape'), ('jc8012p4a1', 'jc8012p4a1', 'landscape'),
            ('reterminald1001_portrait', 'reterminald1001', 'portrait'), ('tab5', 'tab5', 'landscape')]
if os.environ.get('METER_BOARDS'):
    keep = os.environ['METER_BOARDS'].split(',')
    VARIANTS = [v for v in VARIANTS if v[0] in keep]
LOOKS = ('ring', 'tape', 'bar')
ICONS = {'thermometer': 0xF050F, 'molecule-co2': 0xF07E4, 'cpu-64-bit': 0xF0EE0, 'battery-70': 0xF0080, 'flash': 0xF0241}
FACES = (('label', 'LABEL', 'Roboto-700.ttf'), ('small', 'SUBLABEL', 'Roboto-400.ttf'), ('control', 'SUBLABEL_BIG', 'Roboto-400.ttf'),
         ('headline', 'HEADLINE', 'Roboto-500.ttf'), ('value', 'WATCH_VALUE', 'Roboto-500.ttf'), ('digits', 'SETPOINT', 'Roboto-400.ttf'),
         ('icon_watch', 'WATCH_ICON', 'materialdesignicons-webfont.ttf'), ('icon_mini', 'ICON_MINI', 'materialdesignicons-webfont.ttf'),
         ('icon', 'ICON', 'materialdesignicons-webfont.ttf'), ('icon_big', 'ICON_BIG', 'materialdesignicons-webfont.ttf'))
DAY_CO2 = [440, 432, 430, 431, 436, 450, 470, 520, 640, 760, 880, 960, 1020, 1100, 1180, 1040, 900, 760, 700, 720, 760, 800, 820, 840]
DAY_TEMP = [19.6, 19.5, 19.4, 19.4, 19.5, 19.7, 20.1, 20.6, 21.2, 21.8, 22.2, 22.5, 22.7, 22.8, 22.8, 22.6, 22.4, 22.2, 22.0, 21.9, 21.8, 21.9, 21.6, 21.4]
# (key, name, icon, unit, state, low, high, segments, colours, thresholds, own, history)
SCENES = [
    ('co2', 'Office', 'molecule-co2', 'ppm', '840', 400, 1600, 3, ('GREEN', 'ORANGE', 'RED'), (800, 1200), 'GREEN', DAY_CO2),
    ('cpu', 'CPU usage', 'cpu-64-bit', '%', '86', 0, 100, 3, ('GREEN', 'ORANGE', 'RED'), (None, None), 'GREEN', []),
    ('long', 'Living room temperature by the window', 'thermometer', '°C', '21.4', 16, 26, 1, (None, None, None), (None, None), 'DEEP_ORANGE', DAY_TEMP),
    ('off', 'House power', 'flash', 'kW', 'unavailable', 0, 7, 1, (None, None, None), (None, None), 'PURPLE', []),
]

def board_struct(variant, board, orientation):
    shapes = json.loads((ROOT / 'screen_manager/app/boards.json').read_text())
    s = profiles.substitutions(f'checkout/{board}.yaml')
    side = shapes[f'checkout/{board}.yaml']['orientations'][orientation]
    nums = [side['width'], side['height'], round(float(s['DISPLAY_DPI'])), side['columns'], side['rows'],
            *[int(s[k]) for k in ('SCROLL_Y', 'PAGE_BAR_H', 'GRID_MARGIN', 'GRID_GAP_X', 'GRID_GAP_Y', 'TILE_RADIUS', 'TILE_PAD')]]
    faces = ', '.join(f'id({board}_{role})->get_lv_font()' for role, _, _ in FACES)
    return f'{{"{variant}", "{s["LOOK"]}", ' + ', '.join(map(str, nums)) + ', {' + faces + '}}'

def project():
    chars = ''.join(dict.fromkeys(''.join(chr(i) for i in range(32, 127)) + '°·–…'))
    icons = ''.join(chr(c) for c in ICONS.values())
    fonts, seen = [], set()
    for _, board, _ in VARIANTS:
        if board in seen: continue
        seen.add(board)
        s = profiles.substitutions(f'checkout/{board}.yaml')
        for role, key, file in FACES:
            glyphs = icons if 'icon' in role else ('-.,°%0123456789' if role == 'digits' else chars)
            fonts.append(f'  - file: "{ROOT}/fonts/{file}"\n    id: {board}_{role}\n    size: {s["FONT_" + key + "_SIZE"]}\n    bpp: 4\n'
                         f'    glyphs: {json.dumps(glyphs, ensure_ascii=False)}\n')
    def f(v): return 'NAN' if v is None else f'{float(v)}f'
    scenes = []
    for key, name, icon, unit, state, lo, hi, seg, cols, th, own, hist in SCENES:
        c = ', '.join('0' if x is None else f'theme::ha::{x}' for x in cols)
        h = ', '.join(f(v) for v in hist)
        glyph = ''.join(f'\\U{ICONS[icon]:08X}')
        scenes.append(f'{{"{name}", "{glyph}", "{unit}", "{state}", {f(lo)}, {f(hi)}, {seg}, {{{c}}}, {{{f(th[0])}, {f(th[1])}}}, theme::ha::{own}, {{{h}}}}}')
    lam = 'std::vector<meter_firmware::Scene> scenes = {' + ',\n'.join(scenes) + '};\n'
    lam += 'const char *keys[] = {' + ', '.join(f'"{s[0]}"' for s in SCENES) + '};\n'
    for variant, board, orientation in VARIANTS:
        lam += f'{{ meter_firmware::Board b={board_struct(variant, board, orientation)};\n'
        lam += f'  for (int st = 0; st < 3; ++st) for (size_t k = 0; k < scenes.size(); ++k) {{\n'
        lam += f'    meter_firmware::spans(b, "{OUT}", scenes[k], keys[k], (meter_card::Style) st, false);\n'
        lam += f'    if (k == 0) meter_firmware::spans(b, "{OUT}", scenes[k], keys[k], (meter_card::Style) st, true);\n  }}\n}}\n'
    lam += 'printf("CUTS %d OVERFLOWS %d\\n", meter_firmware::cuts, meter_firmware::overflows);\nexit(0);'
    return f'''esphome:
  name: meter-render
  includes: ["{WORK}/meter_firmware.h"]
  platformio_options:
    build_flags: [-DLV_USE_SNAPSHOT=1]
  on_boot:
    priority: -100
    then:
      - lambda: |-
{chr(10).join('          ' + line for line in lam.splitlines())}
host:
logger:
  level: WARN
display:
  - platform: sdl
    id: glass
    dimensions:
      width: 1400
      height: 1400
    auto_clear_enabled: false
    update_interval: never
font:
{''.join(fonts)}
lvgl:
  default_font: {VARIANTS[0][1]}_small
  displays: glass
  pages:
    - id: render
      pad_all: 0
      scrollable: false
      widgets:
        - label:
            hidden: true
            text: ""
        - arc:
            hidden: true
'''

def build():
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob('*'): old.unlink()
    WORK.mkdir(parents=True, exist_ok=True)
    (WORK / 'meter_firmware.h').write_text((ROOT / 'tools/render/meter_firmware.h').read_text().replace('"../../components/', f'"{ROOT}/components/'))
    config = WORK / 'meter-render.yaml'
    config.write_text(project())
    esphome = os.environ.get('ESPHOME', str(Path(sys.executable).with_name('esphome')))
    result = subprocess.run([esphome, 'compile', str(config)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    (WORK / 'build.log').write_text(result.stdout)
    if result.returncode: print(result.stdout[-7000:]); raise SystemExit(result.returncode)
    program = WORK / '.esphome/build/meter-render/.pioenvs/meter-render/program'
    env = {**os.environ, 'SDL_VIDEODRIVER': 'dummy', 'SDL_RENDER_DRIVER': 'software'}
    result = subprocess.run([str(program)], env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=900)
    (WORK / 'render.log').write_text(result.stdout)
    lines = result.stdout.splitlines()
    print('\n'.join(l for l in lines if l.startswith(('CUT ', 'OVERFLOW')))[:8000])
    print([l for l in lines if l.startswith('CUTS')])
    if result.returncode: print(result.stdout[-4000:]); raise SystemExit(result.returncode)

def sheets():
    for path in OUT.glob('*.ppm'):
        with Image.open(path) as im: im.save(path.with_suffix('.png'))
        path.unlink()
    font = ImageFont.truetype(str(ROOT / 'fonts/Roboto-500.ttf'), 26)
    small = ImageFont.truetype(str(ROOT / 'fonts/Roboto-400.ttf'), 18)
    shapes = json.loads((ROOT / 'screen_manager/app/boards.json').read_text())
    for variant, board, orientation in VARIANTS:
        side = shapes[f'checkout/{board}.yaml']['orientations'][orientation]
        for look in LOOKS:
            for key in [s[0] for s in SCENES] + ['co2-dark']:
                scene, dark = key.replace('-dark', ''), key.endswith('-dark')
                rows = []
                for r in range(1, side['rows'] + 1):
                    row = [(f'{c}x{r}', OUT / f'{variant}-{look}-{scene}-{c}x{r}{"-dark" if dark else ""}.png') for c in range(1, side['columns'] + 1)]
                    rows.append([(l, Image.open(p).convert('RGB')) for l, p in row if p.exists()])
                if not any(rows): continue
                scale = 2 if side['width'] <= 480 else 1
                rows = [[(l, im.resize((im.width * scale, im.height * scale), Image.Resampling.LANCZOS)) for l, im in row] for row in rows]
                W = max(sum(im.width + 20 for _, im in row) for row in rows) + 40
                H = sum(max(im.height for _, im in row) + 40 for row in rows if row) + 80
                canvas = Image.new('RGB', (W, H), '#111' if dark else '#f5f6f8')
                d = ImageDraw.Draw(canvas)
                d.text((20, 20), f'{variant} · {look} · {key}', font=font, fill='#e8eaed' if dark else '#17202c')
                y = 70
                for row in rows:
                    if not row: continue
                    x = 20
                    for label, im in row:
                        d.text((x, y), label, font=small, fill='#9aa4ae'); canvas.paste(im, (x, y + 22)); x += im.width + 20
                    y += max(im.height for _, im in row) + 40
                canvas.save(OUT / f'sheet-{variant}-{look}-{key}.png')

if __name__ == '__main__':
    step = sys.argv[1] if len(sys.argv) > 1 else 'all'
    if step in ('build', 'all'): build()
    if step in ('sheets', 'all'): sheets()
