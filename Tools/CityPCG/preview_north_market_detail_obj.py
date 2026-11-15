"""Make flat-color review previews of the detailed source OBJs without Blender."""

import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

import verify_north_market_detail_obj as verifier


OUTPUT = verifier.OUTPUT / "FlatColorPreviews"


def normalize(vector):
    length = math.sqrt(sum(value * value for value in vector))
    return tuple(value / length for value in vector)


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def color_channel(value):
    value = max(0., min(1., value))
    return round(255 * (12.92 * value if value <= .0031308 else 1.055 * value ** (1 / 2.4) - .055))


def materials(path):
    result = {}
    role = None
    for line in path.read_text(encoding="utf-8").splitlines():
        fields = line.split()
        if fields and fields[0] == "newmtl":
            role = fields[1]
        elif fields and fields[0] == "Kd":
            result[role] = tuple(map(float, fields[1:]))
    return result


def mesh(path):
    vertices, normals, faces = [], [], []
    role = None
    with path.open("r", encoding="utf-8") as stream:
        for line in stream:
            fields = line.split()
            if not fields:
                continue
            if fields[0] == "v":
                vertices.append(tuple(map(float, fields[1:])))
            elif fields[0] == "vn":
                normals.append(tuple(map(float, fields[1:])))
            elif fields[0] == "usemtl":
                role = fields[1]
            elif fields[0] == "f":
                corners = [tuple(map(int, corner.split("/"))) for corner in fields[1:]]
                faces.append(([corner[0] - 1 for corner in corners], normals[corners[0][2] - 1], role))
    return vertices, faces


def render(path, palette, destination, label):
    vertices, faces = mesh(path)
    eye = normalize((1.55, -1.15, 1.03))
    right = normalize(cross((0., 0., 1.), eye))
    up = normalize(cross(eye, right))
    projected = [(dot(point, right), dot(point, up), dot(point, eye)) for point in vertices]
    xmin, xmax = min(p[0] for p in projected), max(p[0] for p in projected)
    ymin, ymax = min(p[1] for p in projected), max(p[1] for p in projected)
    width, height = 1400, 1000
    scale = min((width - 120) / (xmax - xmin), (height - 210) / (ymax - ymin))
    xcenter, ycenter = (xmin + xmax) / 2, (ymin + ymax) / 2
    pixels = [(width / 2 + (x - xcenter) * scale, height / 2 + 35 - (y - ycenter) * scale)
              for x, y, _ in projected]
    light = normalize((-.45, -.6, 1.))
    image = Image.new("RGB", (width, height), (222, 217, 207))
    draw = ImageDraw.Draw(image)
    ordered = sorted(faces, key=lambda face: sum(projected[index][2] for index in face[0]) / len(face[0]))
    for indices, normal, role in ordered:
        shade = .55 + .45 * abs(dot(normal, light))
        color = tuple(color_channel(value * shade) for value in palette[role])
        draw.polygon([pixels[index] for index in indices], fill=color)
    try:
        title = ImageFont.truetype("arial.ttf", 29)
        note = ImageFont.truetype("arial.ttf", 19)
    except OSError:
        title = note = ImageFont.load_default()
    draw.text((32, 24), label, fill=(44, 39, 35), font=title)
    draw.text((32, height - 46), "Unreviewed source mesh  |  flat colors  |  not an Unreal render",
              fill=(65, 58, 52), font=note)
    image.save(destination, "PNG")


def main():
    source = verifier.OUTPUT
    report = json.loads((source / "detailed_obj_manifest.json").read_text(encoding="utf-8"))
    palette = materials(source / report["material_file"])
    OUTPUT.mkdir(parents=True, exist_ok=False)
    for row in report["buildings"].values():
        name = row["source_artifact"]["file"]
        render(source / name, palette, OUTPUT / (Path(name).stem + ".png"),
               f"North Market {row['side']}  ·  {row['style']}")
    print(f'Created {len(report["buildings"])} flat-color geometry previews in {OUTPUT}')


if __name__ == "__main__":
    main()
