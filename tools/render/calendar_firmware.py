"""Render the calendar card's real planner and painter (components/smart_display/calendar_card.h, calendar_paint.h) on real board metrics.

Host-only design study: no firmware files, storage or device configuration change. Run with ESPHome's Python, e.g.
uv run --no-project --python 3.13 --with esphome==2026.9.0 --with pillow python tools/render/calendar_card.py
Needs SDL2 and Pillow. CAL_BOARDS=cyd,guition limits the boards.
"""
import json, os, subprocess, sys
from pathlib import Path
from PIL import Image
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
import profiles
WORK=ROOT/'.esphome/calendar-design/firmware'
OUT=Path(os.environ.get('CALENDAR_RENDER_OUT',str(WORK/'out'))).resolve()
BOARDS=tuple(os.environ.get('CAL_BOARDS','cyd,guition,waveshare43,waveshare7,reterminald1001,jc8012p4a1,crowpanel101,cyd_portrait,waveshare43_portrait,reterminald1001_portrait,jc8012p4a1_portrait').split(','))
SPANS=((1,1),(2,1),(1,2),(2,2),(3,1),(3,2),(2,3),(3,3),(4,2),(4,3),(4,4),(5,2),(5,3),(5,4),(5,5),(1,3),(1,4),(2,4),(3,4),(3,6))
BUSY=14*60+10  # Wednesday 14:10, in the design review
FREE=16*60+20  # Wednesday 16:20, before the presentation

def renders(cols,rows):
    out=[]
    spans=list(dict.fromkeys([(c,r) for c,r in SPANS if c<=cols and r<=rows]+[(cols,rows)]))
    for c,r in spans: out.append((f'{c}x{r}-busy',c,r,BUSY,False,0))
    for c,r in ((1,1),(2,2),(cols,rows)):
        if (c,r) in spans: out.append((f'{c}x{r}-free',c,r,FREE,False,0))
    for c,r in ((1,1),(2,2),(cols,rows)):
        if (c,r) in spans: out.append((f'{c}x{r}-busy-dark',c,r,BUSY,True,0))
    out+=[('full-upnext',0,0,BUSY,False,1),('full-day',0,0,BUSY,False,2),('full-week',0,0,BUSY,False,3),('full-week-dark',0,0,BUSY,True,3),
          ('full-month',0,0,BUSY,False,4),('full-viewkey',0,0,BUSY,False,13),('full-event',0,0,BUSY,False,23)]
    return list(dict.fromkeys(out))

def project():
    shapes=json.loads((ROOT/'screen_manager/app/boards.json').read_text())
    chars=''.join(dict.fromkeys(''.join(chr(i) for i in range(32,127))+'°·–'))
    icons=''.join(chr(i) for i in (0xF00ED,0xF00EE,0xF00EF,0xF035D,0xF012C,0xF0156,0xF0141,0xF0142,0xF07D9,0xF0150,0xF02DC,0xF0335,0xF050F))
    entries=(('label','LABEL','Roboto-700.ttf'),('sub','SUBLABEL','Roboto-400.ttf'),('sub_big','SUBLABEL_BIG','Roboto-400.ttf'),
             ('headline','HEADLINE','Roboto-500.ttf'),('value','WATCH_VALUE','Roboto-500.ttf'),('digits','CLOCK_DIGITS','Roboto-500.ttf'),
             ('icon','ICON_MINI','materialdesignicons-webfont.ttf'),('tile_icon','ICON','materialdesignicons-webfont.ttf'))  # the order of calendar_card::Face
    fonts=[];lines=[]
    for b in BOARDS:
        base=b.removesuffix('_portrait')
        s=profiles.substitutions(f'checkout/{base}.yaml');side=shapes[f'checkout/{base}.yaml']['orientations']['portrait' if b.endswith('_portrait') else 'landscape']
        for role,key,file in entries:
            fonts.append(f'  - file: "{ROOT}/fonts/{file}"\n    id: {b}_{role}\n    size: {s["FONT_"+key+"_SIZE"]}\n    bpp: 4\n    glyphs: {json.dumps(icons if file.startswith("material") else chars, ensure_ascii=False)}\n')
        nums=[side['width'],side['height'],round(float(s['DISPLAY_DPI'])),side['columns'],side['rows'],
              *[int(s[k]) for k in ('SCROLL_Y','PAGE_BAR_H','GRID_MARGIN','GRID_GAP_X','GRID_GAP_Y','TILE_ICON_SIZE')]]
        fs=', '.join(f'id({b}_{role})->get_lv_font()' for role,_,_ in entries)
        lines.append(f'{{ calfw::Board b{{"{b}", "{s["LOOK"]}", {", ".join(map(str,nums))}, {{{fs}}}}};')
        for name,c,r,minute,dark,mode in renders(side['columns'],side['rows']):
            lines.append(f'  calfw::render(b,"{OUT}","{b}-{name}",{c},{r},{minute},{str(dark).lower()},{mode});')
        lines.append('}')
    lines.append('exit(0);')
    WORK.mkdir(parents=True,exist_ok=True)
    (WORK/'card.h').write_text((ROOT/'tools/render/calendar_firmware.h').read_text().replace('"../../components/',f'"{ROOT}/components/'))
    return f'''esphome:
  name: calendar-firmware
  includes: ["{WORK}/card.h"]
  platformio_options:
    build_flags: [-DLV_USE_SNAPSHOT=1]
  on_boot:
    priority: -100
    then:
      - lambda: |-
{chr(10).join('          '+line for line in lines)}
host:
logger:
  level: WARN
display:
  - platform: sdl
    id: glass
    dimensions:
      width: 1280
      height: 1280
    auto_clear_enabled: false
    update_interval: never
font:
{''.join(fonts)}
lvgl:
  default_font: {BOARDS[0]}_sub
  displays: glass
  pages:
    - id: study
      pad_all: 0
      scrollable: false
      widgets:
        - label:
            hidden: true
            text: ""
'''

def convert():
    for path in OUT.glob('*.ppm'):
        with Image.open(path) as im: im.save(path.with_suffix('.png'))
        path.unlink()

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    for old in OUT.glob('*.png'): old.unlink()
    config=WORK/'calendar-firmware.yaml';config.write_text(project())
    if '--no-build' not in sys.argv:
        esphome=os.environ.get('ESPHOME',str(Path(sys.executable).with_name('esphome')))
        result=subprocess.run([esphome,'compile',str(config)],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
        (WORK/'build.log').write_text(result.stdout)
        if result.returncode: print(result.stdout[-7000:]);raise SystemExit(result.returncode)
    program=WORK/'.esphome/build/calendar-firmware/.pioenvs/calendar-firmware/program'
    env={**os.environ,'SDL_VIDEODRIVER':'dummy','SDL_RENDER_DRIVER':'software'}
    result=subprocess.run([str(program)],env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=600)
    (WORK/'render.log').write_text(result.stdout)
    views={l.split()[1]:l.split()[2] for l in result.stdout.splitlines() if l.startswith('VIEW ')}
    (OUT/'views.json').write_text(json.dumps(views,indent=1))
    if result.returncode or '[Warn]' in result.stdout: print(result.stdout[-4000:]);raise SystemExit(result.returncode or 1)
    convert();print(OUT,len(views),'renders')
if __name__=='__main__':main()
