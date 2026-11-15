"""Lays out pictures from Saved/NpcUnified as one labelled contact sheet (PNG).

Usage: python make_contact_sheet.py <out.png> <title> <picture name>=<caption> [...]
Pictures that are missing are left out; the sheet says how many it found. Standard library plus Pillow.
"""
import os
import sys

from PIL import Image, ImageDraw, ImageFont

SAVED = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'Saved', 'NpcUnified')


def font(size):
    for name in ('segoeui.ttf', 'arial.ttf'):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def main(out_path, title, pairs):
    cells = []
    for pair in pairs:
        name, _, caption = pair.partition('=')
        path = os.path.join(SAVED, name if name.lower().endswith('.png') else name + '.png')
        if os.path.exists(path):
            cells.append((Image.open(path).convert('RGB'), caption or name))
    if not cells:
        print('no pictures found')
        return 1
    columns = 2 if len(cells) <= 4 else 3
    cell_w, cell_h, label_h, pad, head_h = 800, 450, 46, 14, 64
    rows = (len(cells) + columns - 1) // columns
    sheet = Image.new('RGB', (pad + columns * (cell_w + pad), head_h + rows * (cell_h + label_h + pad) + pad), (18, 18, 20))
    draw = ImageDraw.Draw(sheet)
    draw.text((pad, 16), title, fill=(240, 240, 240), font=font(30))
    for index, (picture, caption) in enumerate(cells):
        scale = min(cell_w / picture.width, cell_h / picture.height)
        fitted = picture.resize((max(1, round(picture.width * scale)), max(1, round(picture.height * scale))), Image.LANCZOS)
        x = pad + (index % columns) * (cell_w + pad)
        y = head_h + (index // columns) * (cell_h + label_h + pad)
        sheet.paste(fitted, (x + (cell_w - fitted.width) // 2, y + (cell_h - fitted.height) // 2))
        draw.text((x + 4, y + cell_h + 8), caption, fill=(220, 220, 220), font=font(22))
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    sheet.save(out_path)
    print('wrote %s with %d of %d pictures' % (out_path, len(cells), len(pairs)))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1], sys.argv[2], sys.argv[3:]))
