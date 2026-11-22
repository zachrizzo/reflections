"""Bake wardrobe skin coverage shared by all supplied reference sizes."""
import argparse
import json
from pathlib import Path
from PIL import Image, ImageChops, ImageDraw, ImageFilter

def bake(root, names, label, tile):
    size = 1024
    common = Image.new("L", (size, size), 255)
    for name in names:
        polygons = json.loads((root / f"mask_uv_{name}.json").read_text())
        layer = Image.new("L", (size, size))
        draw = ImageDraw.Draw(layer)
        count = 0
        for polygon in polygons:
            if not all(tile <= u <= tile + 1 and 0 <= v <= 1 for u, v in polygon):
                continue
            draw.polygon([((u - tile) * (size-1), (1-v) * (size-1)) for u,v in polygon], fill=255)
            count += 1
        if not count:
            raise ValueError(f"Missing {label} UV coverage on {name}")
        common = ImageChops.darker(common, layer)
    # The 3D pattern already reserves a 24 mm band around openings.
    mask = ImageChops.invert(common.filter(ImageFilter.MinFilter(5)))
    if mask.getextrema() != (0, 255):
        raise ValueError(f"Empty {label} map")
    mask.convert("RGB").save(root / f"T_WayfarersTunic_{label}Mask.png")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("names", nargs="+")
    args = parser.parse_args()
    for label, tile in (("Body", 1), ("Head", 0)):
        bake(args.source, args.names, label, tile)
