"""One row of pictures from a capture folder.

  python shot_sheet.py <capture folder> <out.png> "<title>" <shot> [<shot> ...] [--crop x0,y0,x1,y1] [--cell 520]
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw

from compare_sheet import font


def main():
    args = sys.argv[1:]
    crop, cell = None, 520
    if "--crop" in args:
        i = args.index("--crop"); crop = tuple(float(v) for v in args[i + 1].split(",")); del args[i:i + 2]
    if "--cell" in args:
        i = args.index("--cell"); cell = int(args[i + 1]); del args[i:i + 2]
    folder, out, title, shots = Path(args[0]), Path(args[1]), args[2], args[3:]
    pad, head = 8, 70
    tiles = []
    for shot in shots:
        image = Image.open(folder / f"{shot}.png").convert("RGB")
        if crop:
            w, h = image.size
            image = image.crop((int(crop[0] * w), int(crop[1] * h), int(crop[2] * w), int(crop[3] * h)))
        tiles.append(image.resize((cell, int(cell * image.height / image.width))))
    height = max(t.height for t in tiles)
    sheet = Image.new("RGB", (pad + len(tiles) * (cell + pad), head + height + 30 + pad), (250, 250, 250))
    draw = ImageDraw.Draw(sheet)
    draw.text((pad, 8), title, fill=(20, 20, 20), font=font(26))
    for i, (tile, shot) in enumerate(zip(tiles, shots)):
        x = pad + i * (cell + pad)
        draw.text((x + 4, head - 28), shot.replace("_", " "), fill=(40, 40, 40), font=font(20))
        sheet.paste(tile, (x, head))
    sheet.save(out)
    print(out, sheet.size)


if __name__ == "__main__":
    main()
