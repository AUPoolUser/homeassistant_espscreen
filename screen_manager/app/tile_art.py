"""Prepare bounded rectangular tile artwork in the add-on, never on the board.

An atlas reuses the screen's existing live-image buffer. Frames use canvas
coordinates, so mixed tile footprints and repeated entities need no extra bitmap
per tile. The allocation is bounded by the paired screen's reported canvas.
"""
import contextlib
import io
import json


def parse(value, canvas, count, overlap=False):
    """Validated immutable (width, height, frames), or None for malformed input.

    Each frame is x, y, width, height, corner radius, darkening (0 or 170).
    The last two fields are baked into RGB pixels, avoiding device mask layers.
    Frames of different tiles never overlap; the places of one plugin tile may (`overlap`, plugin API 0.10): they are
    layers of one card, painted in their order (layers()).
    """
    if not isinstance(value, str) or len(value) > 8192 or not 1 <= count <= 64:
        return None
    try:
        frames = json.loads(value)
    except (ValueError, TypeError):
        return None
    if not isinstance(frames, list) or len(frames) != count:
        return None
    width, height = canvas
    if width <= 0 or height <= 0:
        return None
    checked = []
    right = bottom = 0
    for frame in frames:
        if not isinstance(frame, list) or len(frame) != 6 or any(type(n) is not int for n in frame):
            return None
        x, y, w, h, radius, shade = frame
        if x < 0 or y < 0 or w < 1 or h < 1 or x+w > width or y+h > height:
            return None
        if not 0 <= radius <= min(w, h)//2 or shade not in (0, 170):
            return None
        if not overlap and any(x < a+c and a < x+w and y < b+d and b < y+h for a,b,c,d,_,_ in checked):
            return None
        checked.append(tuple(frame))
        right, bottom = max(right, x+w), max(bottom, y+h)
    return right, bottom, tuple(checked)


# A plugin tile's picture turned in its place (plugin API 0.10, tessera::Turn), as the covers beside the middle one of a
# cover flow: the far edge this share of the near one's height. A reflection under a picture (tessera::ui mirror) takes
# MIRROR_PERCENT of the picture's height under it (plugin_api.h MIRROR_PERCENT, a test keeps them equal), starting at
# MIRROR_ALPHA of the picture and fading out.
FAR_EDGE = 0.70
MIRROR_PERCENT = 30
MIRROR_ALPHA = 0.38
TURNS = ('', 'left', 'right')


def _perspective(size, quad):
    """Pillow's PERSPECTIVE coefficients that draw a picture of `size` into `quad` (its top left, top right, bottom
    right and bottom left corners in the output): the transform maps each output point back to the picture."""
    w, h = size
    source = [(0, 0), (w, 0), (w, h), (0, h)]
    rows, rhs = [], []
    for (x, y), (u, v) in zip(quad, source):
        rows.append([x, y, 1, 0, 0, 0, -u * x, -u * y]); rhs.append(u)
        rows.append([0, 0, 0, x, y, 1, -v * x, -v * y]); rhs.append(v)
    # Gaussian elimination with partial pivoting: eight equations, no numpy in the app.
    n = 8
    m = [row + [r] for row, r in zip(rows, rhs)]
    for c in range(n):
        pivot = max(range(c, n), key=lambda r: abs(m[r][c]))
        m[c], m[pivot] = m[pivot], m[c]
        for r in range(n):
            if r != c and m[c][c]:
                f = m[r][c] / m[c][c]
                m[r] = [a - f * b for a, b in zip(m[r], m[c])]
    return [m[i][n] / m[i][i] for i in range(n)]


def layer(raw, w, h, radius, fit, turn='', mirror=False):
    """One place's picture as an RGBA layer of w x h: cut to the place (fit 'fill') or whole within it ('within'),
    corners rounded; with `mirror` the picture takes the top of the place and a reflection fades out under it; turned
    ('left' or 'right') the picture (and its reflection) is drawn whole in perspective, its near edge the place's height,
    its far edge FAR_EDGE of it. Transparent where nothing is drawn, so what lies under it shows."""
    from PIL import Image, ImageDraw, ImageOps
    picture_h = max(1, round(h * 100 / (100 + MIRROR_PERCENT))) if mirror else h
    with (contextlib.nullcontext(raw) if isinstance(raw, Image.Image) else Image.open(io.BytesIO(raw))) as source:
        source = ImageOps.exif_transpose(source).convert('RGBA')
        if turn:
            # Whole, at its own proportions: the turn squeezes it into the place as a cover turned away is squeezed.
            base = source.resize((max(1, round(picture_h * source.width / source.height)), picture_h), Image.Resampling.LANCZOS)
        elif fit == 'within':
            base = ImageOps.contain(source, (w, picture_h), method=Image.Resampling.LANCZOS)
        else:
            base = ImageOps.fit(source, (w, picture_h), method=Image.Resampling.LANCZOS)
    if radius:
        mask = Image.new('L', (base.width * 4, base.height * 4))
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, base.width * 4 - 1, base.height * 4 - 1), radius=radius * 4, fill=255)
        mask = mask.resize(base.size, Image.Resampling.LANCZOS)
        base.putalpha(Image.composite(base.getchannel('A'), Image.new('L', base.size), mask))
    total = base.height + (h - picture_h if mirror else 0)
    tall = Image.new('RGBA', (base.width, total))
    tall.paste(base, (0, 0))
    if mirror and total > base.height:
        reflection = base.transpose(Image.Transpose.FLIP_TOP_BOTTOM).crop((0, 0, base.width, total - base.height))
        ramp = Image.linear_gradient('L').resize((base.width, reflection.height))
        fade = ramp.point(lambda v: round((255 - v) * MIRROR_ALPHA))
        alpha = Image.composite(fade, Image.new('L', reflection.size), reflection.getchannel('A'))
        reflection.putalpha(alpha)
        tall.paste(reflection, (0, base.height))
    if not turn:
        out = Image.new('RGBA', (w, h))
        out.paste(tall, ((w - tall.width) // 2, (picture_h - base.height) // 2))
        return out
    # Turned: the near edge the full height, the far edge FAR_EDGE of the picture's height, both about the middle of
    # the picture (the reflection follows the same lines).
    inset = picture_h * (1 - FAR_EDGE) / 2
    far_total = total * FAR_EDGE
    if turn == 'left':    # facing left: the left edge far, the right edge near (a cover right of the middle)
        quad = [(0, inset), (w, 0), (w, total), (0, inset + far_total)]
    else:                 # facing right: the right edge far (a cover left of the middle)
        quad = [(0, 0), (w, inset), (w, inset + far_total), (0, total)]
    coefficients = _perspective(tall.size, quad)
    return tall.transform((w, h), Image.Transform.PERSPECTIVE, coefficients, Image.Resampling.BICUBIC)


def layers(raws, ground, atlas, styles, compact=False):
    """A plugin tile's atlas (plugin API 0.10): its places painted in their order, each over what the ones before it
    left, on the card's colour `ground` where nothing lies yet. `styles` gives each frame (fit, turn, mirror). The screen
    draws its places in the same order, the later over the earlier, and each place shows its piece of this one picture,
    so places that overlap show as layers."""
    from PIL import Image
    width, height, frames = atlas
    colour = tuple((ground >> shift) & 255 for shift in (16, 8, 0))
    image = Image.new('RGBA', (width, height), colour + (255,))
    for raw, frame, (fit, turn, mirror) in zip(raws, frames, styles):
        x, y, w, h, radius, _shade = frame
        if raw is None:
            continue
        try:
            painted = layer(raw, w, h, radius, fit, turn, mirror)
        except Exception:   # a picture Pillow cannot read stays the card's colour
            continue
        image.alpha_composite(painted, (x, y))
    return bmp(image.convert('RGB'), compact)


# The shade under a camera's name (app 0.3.8): the bottom share of the card, from clear to this much black.
FADE_SHARE = 0.42
FADE_DEPTH = 150


def bmp(image, compact=False):
    """A BMP of `image`: 24-bit, or with `compact` 8-bit on a palette of the picture's own 256 colours, dithered so a
    shade stays smooth (app 0.3.8). A third of the bytes, which is what a screen downloads and decodes in its main loop,
    at about the quality of its RGB565 glass; Pillow's fast octree keeps it cheap on a Raspberry Pi."""
    from PIL import Image
    if compact:
        palette = image.quantize(256, method=Image.Quantize.FASTOCTREE)
        image = image.quantize(palette=palette, dither=Image.Dither.FLOYDSTEINBERG)
    output = io.BytesIO()
    image.save(output, 'BMP')
    return output.getvalue()


def encode(raws, grounds, atlas, modes=None, compact=False):
    """A native-sized BMP, cropped, dimmed and rounded before transmission.

    `modes` gives each frame (fit, fade) for a camera that fills its card (app 0.3.8): fit 'fill' cuts the picture
    to the frame, 'contain' shows all of it on black and 'within' all of it on the frame's own ground (a plugin
    tile's picture, plugin API 0.10); fade darkens the bottom of the frame, where the screen writes the name. Without
    it every frame is filled, as the album covers of firmware 0.3.1 are."""
    from PIL import Image, ImageDraw, ImageOps
    width, height, frames = atlas
    image = Image.new('RGB', (width, height))
    modes = modes or [('fill', False)] * len(frames)
    for raw, background, frame, (fit, fade) in zip(raws, grounds, frames, modes):
        x, y, w, h, radius, shade = frame
        colour = tuple((background >> shift) & 255 for shift in (16, 8, 0))
        tile = Image.new('RGB', (w, h), colour)
        if raw is not None:
            # A picture the app drew itself comes as a picture, not as bytes (a map, app 0.4.33).
            with (contextlib.nullcontext(raw) if isinstance(raw, Image.Image) else Image.open(io.BytesIO(raw))) as source:
                if not isinstance(raw, Image.Image):
                    source.draft('RGB', (w*2, h*2))
                source = ImageOps.exif_transpose(source)
                # Transparent source pixels use the tile's ground, not black.
                rgba = source.convert('RGBA')
                opaque = Image.new('RGBA', rgba.size, colour + (255,))
                opaque.alpha_composite(rgba)
                if fit in ('contain', 'within'):
                    inner = ImageOps.contain(opaque.convert('RGB'), (w, h), method=Image.Resampling.LANCZOS)
                    cover = Image.new('RGB', (w, h), colour if fit == 'within' else (0, 0, 0))
                    cover.paste(inner, ((w - inner.width) // 2, (h - inner.height) // 2))
                else:
                    cover = ImageOps.fit(opaque.convert('RGB'), (w, h), method=Image.Resampling.LANCZOS)
            if fade:
                ramp = Image.linear_gradient('L').resize((w, max(1, round(h * FADE_SHARE))))
                shadow = Image.new('L', (w, h))
                shadow.paste(ramp.point(lambda v: v * FADE_DEPTH // 255), (0, h - ramp.height))
                cover = Image.composite(Image.new('RGB', (w, h)), cover, shadow)
            if shade:
                cover = Image.blend(cover, Image.new('RGB', cover.size), shade/255)
            mask = Image.new('L', (w*4, h*4))
            ImageDraw.Draw(mask).rounded_rectangle((0, 0, w*4-1, h*4-1), radius=radius*4, fill=255)
            mask = mask.resize((w, h), Image.Resampling.LANCZOS)
            tile.paste(cover, mask=mask)
        image.paste(tile, (x, y))
    return bmp(image, compact)
