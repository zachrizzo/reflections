"""Build original masonry tiles for the guildhall frontage."""

from pathlib import Path

import numpy as np
from PIL import Image


ROOT = Path(__file__).resolve().parent
SIZE = 512


def masonry(name, rows, columns, color, noise, seed):
    rng = np.random.default_rng(seed)
    v, u = np.indices((SIZE, SIZE), dtype=np.float32) / SIZE
    y = v * rows
    row = np.floor(y).astype(int)
    joint_offsets = rng.uniform(0, 1, rows)
    x = (u * columns + joint_offsets[row]) % columns
    column = np.floor(x).astype(int)
    px, py = x % 1, y % 1
    distress = np.sin((u * 131 + v * 29) * np.pi * 2) * np.sin((u * 11 - v * 73) * np.pi * 2)
    broad = np.sin((u * 5 + v * 3) * np.pi * 2) + np.cos((u * 7 - v * 3) * np.pi * 2)
    fine = rng.normal(0, 3.0, u.shape)
    tone = rng.normal(0, noise, (rows, columns))[row, column]
    edge = np.minimum(np.minimum(px, 1 - px) * rows / columns, np.minimum(py, 1 - py))
    mortar = np.clip((edge - .045 - distress * .025) / .045, 0, 1)
    rim = np.clip((.14 - edge) / .14, 0, 1) * 17 - np.clip((.057 - edge) / .057, 0, 1) * 14
    stone_value = tone + fine + distress * 4 + broad * 4.5 + rim
    mortar_rgb = np.array((89, 82, 67)) + (fine + broad * 4)[..., None]
    stone_rgb = np.array(color) + stone_value[..., None]
    rgb = mortar_rgb * (1 - mortar[..., None]) + stone_rgb * mortar[..., None]
    Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8)).save(ROOT / 'Textures' / f'T_GLMedieval_{name}.png')


if __name__ == '__main__':
    (ROOT / 'Textures').mkdir(parents=True, exist_ok=True)
    masonry('GuildRubble', 8, 5, (135, 124, 103), 18, 1450)
    masonry('GuildAshlar', 4, 3, (169, 155, 128), 10, 1411)
