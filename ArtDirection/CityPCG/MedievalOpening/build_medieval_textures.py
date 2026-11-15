"""Build seamless wall and wood base colors for the medieval facade kit."""

import json
from pathlib import Path

import numpy as np
from PIL import Image


ROOT = Path(__file__).resolve().parent
SIZE = 512
Y, X = np.mgrid[0:SIZE, 0:SIZE] / SIZE


def noise(rng, nx, ny):
    grid = rng.uniform(-1, 1, (ny, nx))
    ux, uy = X * nx, Y * ny
    ix, iy = ux.astype(int), uy.astype(int)
    fx, fy = ux - ix, uy - iy
    fx, fy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)
    low = grid[iy, ix] * (1 - fx) + grid[iy, (ix + 1) % nx] * fx
    high = grid[(iy + 1) % ny, ix] * (1 - fx) + grid[(iy + 1) % ny, (ix + 1) % nx] * fx
    return low * (1 - fy) + high * fy


def mortar_cells(rng, cells, amplitude):
    field = np.zeros_like(X)
    for y in range(cells):
        width = cells + (y % 2)
        masonry_x = np.mod(X + (.5 / width if y % 2 else 0), 1) * width
        row = (Y >= y / cells) & (Y < (y + 1) / cells)
        cell_ids = masonry_x.astype(int)
        details = rng.uniform(.79, 1.18, width)[cell_ids]
        seam = ((masonry_x % 1 < .035) | (Y * cells % 1 < .065))
        field[row] = np.where(seam, amplitude, details)[row]
    return field


def texel_factors(role):
    rng = np.random.default_rng(34571532)
    grit = .048 * noise(rng, 180, 180) + .057 * noise(rng, 64, 64)
    if role == "ClayTile":
        return mortar_cells(rng, 12, .49) + .09 * noise(rng, 13, 11) + grit
    if role == "Fieldstone":
        return mortar_cells(rng, 5, .55) + .21 * noise(rng, 16, 21) + grit
    if "Plaster" in role:
        worn = noise(rng, 21, 13) * .16 + noise(rng, 4, 6) * .10
        exposed = np.maximum(0, noise(rng, 10, 15) - .59) * -.35
        streak = np.maximum(0, noise(rng, 49, 5) - .11) * -.09
        return 1 + worn + grit + exposed + streak
    fine = noise(rng, 111, 5)
    undulating_grain = .12 * np.sin((Y + .009 * noise(rng, 9, 7)) * np.pi * 2 * 41)
    coarse = .17 * noise(rng, 8, 54) + .059 * fine + .22 * noise(rng, 52, 6)
    return 1 + undulating_grain + coarse + grit


def write_texture(path, rgb, factor):
    linear = np.clip(factor[:, :, None] * np.array(rgb), 0, 1)
    srgb = np.where(linear <= .0031308, 12.92 * linear, 1.055 * linear ** (1 / 2.4) - .055)
    Image.fromarray(np.rint(srgb * 255).astype(np.uint8)).save(path, optimize=True)


def main():
    kit = json.loads((ROOT / "medieval_kit.json").read_text(encoding="utf-8"))
    (ROOT / "Textures").mkdir(exist_ok=True)
    for name, info in kit["materials"].items():
        if info["texture"]:
            write_texture(ROOT / info["texture"], info["linear_rgba"][:3], texel_factors(name.removeprefix("M_GLMedieval_")))


if __name__ == "__main__":
    main()
