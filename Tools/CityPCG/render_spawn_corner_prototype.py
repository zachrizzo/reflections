"""Draw two lightweight software views of the offline opening-corner render model."""

import argparse
from array import array
import math
from pathlib import Path
import sys

if __name__ == "__main__":
    sys.dont_write_bytecode = True

from PIL import Image, ImageDraw, ImageFont

from build_spawn_corner_prototype import ART_ROOT, MATERIALS, REPRODUCTION_ROOT, build_shell, texture_coordinates
from scan_opening_view_alternatives import cross, delta, dot


def unit(vector):
    length = math.hypot(*vector)
    return tuple(value / length for value in vector)


def load_materials():
    result = {}
    for label, (color, filename) in MATERIALS.items():
        pixels = None
        if filename:
            with Image.open(ART_ROOT / "Textures" / filename) as source:
                thumbnail = source.convert("RGB").resize((64, 64))
                pixels = tuple(thumbnail.getpixel((x, y)) for y in range(64) for x in range(64))
        result[label] = (color, pixels)
    return result


def render(mesh, model, materials, size, eye, target, vertical_fov):
    width, height = size
    canvas = Image.new("RGB", size)
    pixels = canvas.load()
    pen = ImageDraw.Draw(canvas)
    for y in range(height):
        ratio = y / height
        pen.line((0, y, width, y), fill=tuple(round(235 - ratio * c) for c in (23, 28, 31)))
    depths = array("f", [0.]) * (width * height)
    view = unit(delta(target, eye))
    right = unit((-view[1], view[0], 0))
    up = cross(view, right)
    focal = height / (2 * math.tan(math.radians(vertical_fov / 2)))
    light = unit((-.65, -.58, 1.0))

    for _, material, points in mesh.faces:
        normal = unit(cross(delta(points[1], points[0]), delta(points[2], points[0])))
        relative = [delta(point, eye) for point in points]
        z = [dot(p, view) for p in relative]
        if min(z) < .1 or dot(normal, relative[0]) >= 0:
            continue
        zs = [1 / value for value in z]
        (a, b), (c, d), (e, f) = [
            (width / 2 + dot(p, right) * focal * inv, height / 2 - dot(p, up) * focal * inv)
            for p, inv in zip(relative, zs)
        ]
        denom = (d - f) * (a - e) + (e - c) * (b - f)
        if abs(denom) < 1e-6:
            continue
        left, right_px = max(0, math.floor(min(a, c, e))), min(width - 1, math.ceil(max(a, c, e)))
        upper, lower = max(0, math.floor(min(b, d, f))), min(height - 1, math.ceil(max(b, d, f)))
        relief = .80 + .25 * max(0, dot(normal, light))
        color, texture = materials[material]
        solid = tuple(min(255, round(value * relief)) for value in color)
        uv = texture_coordinates(points, model)
        us, vs = tuple(tuple(point[i] * inv for point, inv in zip(uv, zs)) for i in (0, 1))
        for y in range(upper, lower + 1):
            for x in range(left, right_px + 1):
                alpha = ((d - f) * (x + .5 - e) + (e - c) * (y + .5 - f)) / denom
                beta = ((f - b) * (x + .5 - e) + (a - e) * (y + .5 - f)) / denom
                gamma = 1 - alpha - beta
                if min(alpha, beta, gamma) < 0:
                    continue
                depth = alpha * zs[0] + beta * zs[1] + gamma * zs[2]
                index = y * width + x
                if depth <= depths[index]:
                    continue
                depths[index] = depth
                if texture:
                    u = int((alpha * us[0] + beta * us[1] + gamma * us[2]) / depth * 64) % 64
                    v = int((alpha * vs[0] + beta * vs[1] + gamma * vs[2]) / depth * 64) % 64
                    texel = texture[(63 - v) * 64 + u]
                    pixels[x, y] = tuple(min(255, round((.55 * base + .45 * image) * relief))
                                         for base, image in zip(color, texel))
                else:
                    pixels[x, y] = solid
    return canvas


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="New path for the preview PNG.")
    parser.add_argument("--visual-study", action="store_true", help="Preview the three-gable art study.")
    args = parser.parse_args()
    output = args.output or REPRODUCTION_ROOT / ("GabledPreview.png" if args.visual_study else "StructuralPreview.png")
    if output.exists() or output.is_symlink():
        parser.error(f"Preview file must be new: {output}")
    mesh, model = build_shell(args.visual_study)
    materials = load_materials()
    primary = render(mesh, model, materials, (514, 324), (3291.076, 310.977, 1.654),
                     (3304.8, 315.7, 8.8), 57)
    upper = render(mesh, model, materials, (292, 324), (3272., 281., 39.), (3320.2, 312., 7.8), 45)
    canvas = Image.new("RGB", (840, 427), "#1a2328")
    canvas.paste(primary, (12, 54))
    canvas.paste(upper, (536, 54))
    pen = ImageDraw.Draw(canvas)
    font_file = Path("C:/Windows/Fonts/segoeui.ttf")
    heading = ImageFont.truetype(str(font_file), 23) if font_file.is_file() else ImageFont.load_default()
    small = ImageFont.truetype(str(font_file), 15) if font_file.is_file() else ImageFont.load_default()
    pen.text((12, 13), "Great Tower Street corner", fill="#f5e9d4", font=heading)
    pen.text((647, 19), "Offline render · Review only", fill="#bfc9c5", font=small)
    pen.text((13, 389), "Framed from the saved spawn camera position", fill="#f5e9d4", font=small)
    roof_caption = "Three gables within the original roof limit" if args.visual_study else "Full shell and retained roof level"
    pen.text((537, 389), roof_caption, fill="#f5e9d4", font=small)
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        with output.open("xb") as stream:
            canvas.save(stream, format="PNG")
    except FileExistsError:
        parser.error(f"Preview file must be new: {output}")
    print(output.resolve())


if __name__ == "__main__":
    main()
