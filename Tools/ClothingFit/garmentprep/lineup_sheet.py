"""Contact sheet of one picture per body from a lineup folder.

  python lineup_sheet.py <lineup folder> <out.png> "<title>" <shot> [--crop x0,y0,x1,y1] [--cell 300] [--columns 9]
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw

from compare_sheet import font


def main():
    args = sys.argv[1:]
    crop, cell, columns = None, 300, 9
    for flag in ("--crop", "--cell", "--columns"):
        if flag in args:
            i = args.index(flag)
            value = args[i + 1]
            del args[i:i + 2]
            if flag == "--crop":
                crop = tuple(float(v) for v in value.split(","))
            elif flag == "--cell":
                cell = int(value)
            else:
                columns = int(value)
    folder, out, title, shot = Path(args[0]), Path(args[1]), args[2], args[3]
    bodies = sorted(p for p in folder.iterdir() if (p / f"{shot}.png").exists())
    tiles = []
    for body in bodies:
        image = Image.open(body / f"{shot}.png").convert("RGB")
        if crop:
            w, h = image.size
            image = image.crop((int(crop[0] * w), int(crop[1] * h), int(crop[2] * w), int(crop[3] * h)))
        tiles.append((body.name, image.resize((cell, int(cell * image.height / image.width)))))
    height = max(t.height for _, t in tiles)
    rows = (len(tiles) + columns - 1) // columns
    pad, head = 6, 56
    sheet = Image.new("RGB", (pad + columns * (cell + pad), head + rows * (height + 26 + pad)), (250, 250, 250))
    draw = ImageDraw.Draw(sheet)
    draw.text((pad, 8), f"{title} ({len(tiles)} bodies, {shot.replace('_', ' ')})", fill=(20, 20, 20), font=font(26))
    for i, (name, tile) in enumerate(tiles):
        x = pad + (i % columns) * (cell + pad)
        y = head + (i // columns) * (height + 26 + pad)
        draw.text((x + 2, y), name, fill=(40, 40, 40), font=font(17))
        sheet.paste(tile, (x, y + 24))
    sheet.save(out)
    print(out, sheet.size)


if __name__ == "__main__":
    main()
