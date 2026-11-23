"""Before / after sheet from two capture folders.

  python compare_sheet.py <before folder> <after folder> <out.png> "<title>" <shot> [<shot> ...] [--crop x0,y0,x1,y1]
Shots are file names without .png (Standing_back, Standing_left, walk_12_back ...). Top row before, bottom row after.
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def font(size):
    for name in ("segoeui.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default()


def main():
    args = sys.argv[1:]
    crop = None
    if "--crop" in args:
        i = args.index("--crop")
        crop = tuple(float(v) for v in args[i + 1].split(","))
        del args[i:i + 2]
    before, after, out, title = Path(args[0]), Path(args[1]), Path(args[2]), args[3]
    shots = args[4:]
    cell = 620
    pad, head = 10, 86
    sheet = Image.new("RGB", (pad + len(shots) * (cell + pad), head + 2 * (cell + 34 + pad)), (250, 250, 250))
    draw = ImageDraw.Draw(sheet)
    draw.text((pad, 10), title, fill=(20, 20, 20), font=font(30))
    for row, (label, folder) in enumerate((("BEFORE", before), ("AFTER", after))):
        y = head + row * (cell + 34 + pad)
        for col, shot in enumerate(shots):
            image = Image.open(folder / f"{shot}.png").convert("RGB")
            if crop:
                w, h = image.size
                image = image.crop((int(crop[0] * w), int(crop[1] * h), int(crop[2] * w), int(crop[3] * h)))
            image = image.resize((cell, int(cell * image.height / image.width)))
            image = image.crop((0, 0, cell, min(cell, image.height)))
            x = pad + col * (cell + pad)
            sheet.paste(image, (x, y + 34))
            draw.text((x + 4, y), f"{label}: {shot.replace('_', ' ')}", fill=(160, 30, 30) if row == 0 else (20, 110, 40), font=font(24))
    sheet.save(out)
    print(out, sheet.size)


if __name__ == "__main__":
    main()
