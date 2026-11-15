"""Generate original, repeatable base-color tiles for the London facade kit."""

from pathlib import Path

import numpy as np
from PIL import Image


TEXTURES = Path(__file__).resolve().parent / 'Textures'
SIZE = 512


def periodic_field(rng, cells_x, cells_y):
    cells = rng.normal(0, 1, (cells_y, cells_x)).astype(np.float32)
    cells = np.pad(cells, 1, mode='wrap')
    pad_x = SIZE // cells_x
    pad_y = SIZE // cells_y
    enlarged = Image.fromarray(cells).resize(
        (SIZE + pad_x * 2, SIZE + pad_y * 2), Image.Resampling.BICUBIC
    )
    return np.asarray(enlarged)[pad_y:pad_y + SIZE, pad_x:pad_x + SIZE]


def write(name, pixels):
    rgb = np.clip(pixels, 0, 255).astype(np.uint8)
    Image.fromarray(rgb).save(TEXTURES / f'T_GLPCG_{name}.png')


def brick(rng):
    # A 1.024 m repeat contains four running-bond courses across and fourteen up.
    y, x = np.mgrid[0:SIZE, 0:SIZE] / SIZE
    course = np.floor(y * 14).astype(int)
    across = (x * 4 + (course % 2) * .5) % 4
    brick_x = np.floor(across).astype(int)
    u = across % 1.0
    v = (y * 14) % 1.0
    edge = np.minimum(np.minimum(u, 1.0 - u) * 4, np.minimum(v, 1.0 - v))
    feather = np.clip((edge - .055) / .03, 0, 1)
    hue = rng.normal(0, 10, (14, 4))[course, brick_x]
    mottling = 3.6 * periodic_field(rng, 32, 32) + 5.0 * periodic_field(rng, 8, 8)
    surface = np.array((117, 68, 48)) + (hue + mottling + rng.normal(0, 1.5, u.shape))[..., None]
    mortar = np.array((104, 94, 79)) + (mottling * .5)[..., None]
    write('RedBrick', surface * feather[..., None] + mortar * (1.0 - feather[..., None]))


def stone(rng, name, color, variation):
    pores = periodic_field(rng, 64, 64)
    cloud = periodic_field(rng, 8, 8)
    streaks = periodic_field(rng, 32, 4)
    brightness = variation * (.26 * pores + .40 * cloud + .16 * streaks)
    brightness += rng.normal(0, 1.2, (SIZE, SIZE))
    write(name, np.array(color) + brightness[..., None])


if __name__ == '__main__':
    TEXTURES.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(1908)
    brick(rng)
    stone(rng, 'PortlandStone', (166, 157, 140), 11)
    stone(rng, 'GreyGranite', (115, 117, 116), 18)
