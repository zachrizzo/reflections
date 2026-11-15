"""Generate the shopfront wear map and painted fascia textures for Unreal."""
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont


OUTPUT = Path(__file__).resolve().parent / 'Textures'
FONTS = Path('C:/Windows/Fonts')
SIZE = 512


def periodic_noise(rng, columns, rows):
    grid = rng.random((rows, columns))
    grid = np.pad(grid, 1, mode='wrap')
    image = Image.fromarray(grid.astype(np.float32))
    pad_x = SIZE // columns
    pad_y = SIZE // rows
    enlarged = image.resize((SIZE + 2 * pad_x, SIZE + 2 * pad_y), Image.Resampling.BICUBIC)
    return np.asarray(enlarged)[pad_y:pad_y + SIZE, pad_x:pad_x + SIZE]


def surface_map():
    rng = np.random.default_rng(411)
    speckle = rng.random((SIZE, SIZE))
    cloud = periodic_noise(rng, 8, 8)
    mineral = cloud * .53 + periodic_noise(rng, 64, 64) * .32 + speckle * .15
    paint = periodic_noise(rng, 64, 4) * .53 + cloud * .30 + speckle * .17
    streaks = periodic_noise(rng, 32, 4) * .66 + periodic_noise(rng, 8, 8) * .34
    pixels = (np.clip(np.dstack((mineral, paint, streaks)), 0, 1) * 255).astype(np.uint8)
    Image.fromarray(pixels).save(OUTPUT / 'T_GL_SurfaceWear.png')


def fascia(name, title, subtitle, background):
    width, height = 1024, 128
    rng = np.random.default_rng(653)
    dust = rng.normal(0, 1.25, (height, width, 1))
    grain = rng.normal(0, 1.5, (height, 1, 1))
    pixels = np.clip(np.array(background) + dust + grain, 0, 255).astype(np.uint8)
    image = Image.fromarray(pixels)
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((9, 9, 1014, 118), radius=8, outline=(142, 113, 65), width=2)
    draw.line((33, 31, 114, 31), fill=(142, 113, 65), width=2)
    draw.line((910, 31, 991, 31), fill=(142, 113, 65), width=2)
    for x in (36, 988):
        draw.polygon(((x - 6, 59), (x, 53), (x + 6, 59), (x, 65)), fill=(190, 153, 88))
    title_font = ImageFont.truetype(str(FONTS / 'georgiab.ttf'), 60)
    subtitle_font = ImageFont.truetype(str(FONTS / 'georgia.ttf'), 19)
    draw.text((513, 54), title, anchor='mm', font=title_font, fill=(12, 14, 13))
    draw.text((512, 52), title, anchor='mm', font=title_font, fill=(221, 192, 133))
    draw.text((512, 99), subtitle, anchor='mm', font=subtitle_font, fill=(195, 174, 129))
    image.save(OUTPUT / f'T_GL_Fascia_{name}.png')


if __name__ == '__main__':
    OUTPUT.mkdir(parents=True, exist_ok=True)
    surface_map()
    fascia('Books', 'LAMPLIGHT BOOKS', 'SECONDHAND & RARE VOLUMES', (26, 45, 37))
    fascia('Provisions', 'MARK LANE PROVISIONS', 'TEA  •  COFFEE  •  DRY GOODS', (28, 38, 52))
    fascia('Lantern', 'THE LANTERN ROOM', 'PUBLIC HOUSE', (56, 30, 34))
