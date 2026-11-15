"""Project the garment photos onto the UV lanes used by Blender's fit."""
from pathlib import Path
from PIL import Image, ImageEnhance


ROOT = Path(__file__).resolve().parent
for kind, stem, background in (
    ("Tunic", "RedTunic", (100, 41, 37)),
    ("Trousers", "RedTrousers", (57, 47, 40)),
    ("Boots", "RedWalkingBoot", (75, 44, 34)),
):
    source = Image.open(ROOT / f"{stem}_Projection_input.png").convert("RGBA")
    alpha = source.getchannel("A")
    bounds = alpha.point(lambda a: 255 if a > 174 else 0).getbbox()
    source = source.crop(bounds)
    source = source.resize((1024, 1024), Image.Resampling.LANCZOS)
    front = Image.new("RGB", (1024, 1024), background)
    front.paste(source.convert("RGB"), (0, 0), source.getchannel("A"))
    if kind in {"Tunic", "Trousers"}:
        region = (365, 400, 460, 610) if kind == "Tunic" else (530, 470, 630, 700)
        fabric = ImageEnhance.Color(front.crop(region)).enhance(0.85)
        back = Image.new("RGB", (1024, 1024), background)
        for y in range(0, 1024, fabric.height):
            for x in range(0, 1024, fabric.width):
                back.paste(fabric, (x, y))
    else:
        back = front.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    atlas = Image.new("RGB", (2048, 1024))
    atlas.paste(front, (0, 0))
    atlas.paste(back, (1024, 0))
    atlas.save(ROOT / f"Red{kind}_Atlas.png")
