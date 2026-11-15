"""Generate original repeat textures for the 27 Great Tower Street study."""

from pathlib import Path
import sys

import numpy as np
from PIL import Image


SIZE = 512


def grain(rng, samples):
    image = Image.fromarray(rng.random((samples, samples)).astype(np.float32))
    return np.asarray(image.resize((SIZE, SIZE), Image.Resampling.BICUBIC)) - 0.5


def rgb(base, shade):
    return np.clip(np.asarray(base)[None, None, :] * shade[:, :, None], 0, 255).astype(np.uint8)


def build(output):
    output.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(2701914)
    y, x = np.mgrid[:SIZE, :SIZE]
    fine = grain(rng, 127)
    coarse = grain(rng, 13)

    # A 1.024 m square covers sixteen courses and four standard stretchers.
    course = y // 32
    shifted_x = (x + (course % 2) * 64) % SIZE
    brick_id = shifted_x // 128
    joint = (shifted_x % 128 < 4) | (y % 32 < 4)
    body = rgb((123, 58, 43), 1 + rng.uniform(-0.20, 0.20, (16, 4))[course, brick_id] + .18*fine + .22*coarse)
    body[joint] = rgb((114, 97, 80), 1 + .33*fine + .20*coarse)[joint]
    Image.fromarray(body).save(output / 'stock_brick.png')

    stone = rgb((174, 162, 142), .95 + .18*fine + .22*coarse)
    Image.fromarray(stone).save(output / 'portland_stone.png')

    # Overlapped tile courses with staggered vertical joints.
    course = y // 32
    shifted_x = (x + (course % 2) * 32) % SIZE
    edge = (shifted_x % 64 < 2) | (y % 32 < 3)
    slate = rgb((75, 70, 67), 1 + rng.uniform(-.20, .19, (16, 8))[course, shifted_x//64] + .13*fine)
    slate[edge] = rgb((37, 34, 32), .95 + .30*fine)[edge]
    Image.fromarray(slate).save(output / 'roof_tile.png')


if __name__ == '__main__':
    build(Path(sys.argv[1]).resolve())
