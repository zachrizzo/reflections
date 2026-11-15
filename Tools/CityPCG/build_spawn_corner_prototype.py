"""Build a review-only whole-building render mesh inside the measured opening shell."""

import argparse
from collections import Counter
import json
import math
import os
from pathlib import Path
import sys

if __name__ == "__main__":
    sys.dont_write_bytecode = True

from extract_building_shells import faces, signed_area
from extract_tile_frontages import read_glb
from group_stacked_roofs import interval_fraction, ring_edges, segment_in_triangle, triangle_intersection
from plan_whole_building_replacements import distance_to_building
from scan_opening_view_alternatives import cross, delta
from subtract_building_shells import digest, read_json
from verify_spawn_building_review import ART, DEFAULT_REVIEW, PROJECT, SOURCE, verify


ART_ROOT = PROJECT / ART
REVIEW_ROOT = ART_ROOT / "WholeBuildings/SpawnCorner"
REPRODUCTION_ROOT = PROJECT / "Saved/CityPCG/MedievalSurvey/SpawnCornerReproduction"
NAME = "SM_GLMedieval_SpawnCorner_Review"
MATERIALS = {
    "WarmLime": ((190, 173, 143), "T_GLMedieval_WarmPlaster.png"),
    "CoolLime": ((198, 191, 165), "T_GLMedieval_LimePlaster.png"),
    "DarkOak": ((75, 47, 33), "T_GLMedieval_WeatheredOak.png"),
    "LightOak": ((115, 78, 51), "T_GLMedieval_Oak.png"),
    "Fieldstone": ((132, 118, 100), "T_GLMedieval_Fieldstone.png"),
    "ClayDeck": ((118, 74, 63), "T_GLMedieval_ClayTile.png"),
    "PaintedGreen": ((49, 78, 66), "T_GLMedieval_ShopGreen.png"),
    "PaintedRed": ((99, 49, 38), "T_GLMedieval_ShopRed.png"),
    "LeadedGlass": ((62, 75, 74), None),
    "WindowGlow": ((125, 102, 61), None),
    "Iron": ((52, 54, 51), None),
}


class Mesh:
    def __init__(self):
        self.faces = []

    def face(self, group, material, a, b, c):
        points = tuple(tuple(round(value, 7) for value in point) for point in (a, b, c))
        self.faces.append((group, material, points))

    def quad(self, group, material, a, b, c, d):
        self.face(group, material, a, b, c)
        self.face(group, material, a, c, d)


def wall_frame(start, end):
    width = math.dist(start, end)
    dx, dy = (end[i] - start[i] for i in (0, 1))

    def point(u, z, depth):
        return (start[0] + (dx * u - dy * depth) / width,
                start[1] + (dy * u + dx * depth) / width, z)

    return width, point


def relief(mesh, group, material, wall_point, profile, front, back):
    if signed_area(tuple(profile)) < 0:
        profile = list(reversed(profile))
    near = [wall_point(u, z, front) for u, z in profile]
    far = [wall_point(u, z, back) for u, z in profile]
    for i in range(1, len(near) - 1):
        mesh.face(group, material, near[0], near[i], near[i + 1])
        mesh.face(group, material, far[0], far[i + 1], far[i])
    for i in range(len(near)):
        j = (i + 1) % len(near)
        mesh.quad(group, material, near[j], near[i], far[i], far[j])


def rectangle(x0, z0, x1, z1):
    return [(x0, z0), (x1, z0), (x1, z1), (x0, z1)]


def arched(x0, z0, x1, z1):
    return [(x0, z0), (x1, z0), (x1, z1 - .28), (x1 - .22, z1),
            (x0 + .22, z1), (x0, z1 - .28)]


def diagonal(x0, z0, x1, z1, thickness):
    length = math.hypot(x1 - x0, z1 - z0)
    nx, nz = (z0 - z1) * thickness / length / 2, (x1 - x0) * thickness / length / 2
    return [(x0 + nx, z0 + nz), (x0 - nx, z0 - nz), (x1 - nx, z1 - nz), (x1 + nx, z1 + nz)]


def decorate(mesh, edge, length, margin, point, back, varied=False):
    group_prefix = f"Edge_{edge:02}_"
    first, last = margin + .035, length - margin - .035
    serial = 0

    def add(material, profile, front=.020, rear=None):
        nonlocal serial
        serial += 1
        relief(mesh, f"{group_prefix}{serial:03}", material, point, profile, front, back if rear is None else rear)

    def box(material, x0, z0, x1, z1, front=.020, rear=None):
        add(material, rectangle(x0, z0, x1, z1), front, rear)

    span = last - first
    count = max(1, round(span / 3.15))
    bays = [first + i * (span / count) for i in range(count + 1)]
    street = varied and edge == 7
    if street:
        bays = [first + fraction * span for fraction in (0., .20, .53, .79, 1.)]
    box("Fieldstone", first, .40, last, 1.08, .048)
    rails = ((1.08, .13, "LightOak"), (3.98, .25, "DarkOak"), (7.24, .23, "DarkOak"),
             (10.57, .23, "DarkOak"), (13.76, .27, "DarkOak"), (14.28, .20, "LightOak"))
    if street:
        rails = rails[:4] + ((12.75, .13, "DarkOak"),)
    highest_rail = rails[-1][0] if street else 13.76
    for z, height, material in rails:
        box(material, first, z, last, z + height, .017)
    if span < 1.15:
        box("DarkOak", first + span * .4, 1.21, first + span * .6, highest_rail)
        return
    for center in bays:
        x0, x1 = max(first, center - .09), min(last, center + .09)
        box("DarkOak", x0, 1.21, x1, highest_rail, .021)

    for i, (x0, x1) in enumerate(zip(bays, bays[1:])):
        bay = x1 - x0
        mid = (x0 + x1) / 2
        door = edge == 7 and i in (0, len(bays) - 2) or edge != 7 and i == 0
        fill = "PaintedGreen" if i % 2 == 0 else "PaintedRed"
        if door:
            half = min(.58, bay * .28)
            add("DarkOak", arched(mid - half - .08, 1.10, mid + half + .08, 3.53), .033)
            add(fill, arched(mid - half, 1.15, mid + half, 3.42), .029, .095)
            box("Iron", mid + half * .58, 2.19, mid + half * .70, 2.31, .011, .056)
        else:
            half = bay * .36
            box("LightOak", mid - half - .08, 1.38, mid + half + .08, 3.49, .053)
            box("LeadedGlass", mid - half, 1.49, mid + half, 3.38, .044, .099)
            for bar in (-.5, 0., .5):
                x = mid + half * bar
                box("DarkOak", x - .034, 1.49, x + .034, 3.38, .024, .076)
            box(fill, mid - half - .14, 1.32, mid + half + .14, 1.48, .020)
            box("LightOak", mid - half - .14, 3.39, mid + half + .14, 3.55, .019)
            if street:
                box("DarkOak", mid - half - .17, 1.14, mid + half + .17, 1.32, .013)
                for sign_x in (mid - half * .40, mid, mid + half * .40):
                    add("LightOak", [(sign_x, 1.44), (sign_x + .043, 1.40),
                                     (sign_x, 1.36), (sign_x - .043, 1.40)], .012, .024)

        for floor, window in enumerate((4.97, 8.31, 11.54)):
            half = min(.64, bay * .27)
            h = 1.33 if floor < 2 else 1.21
            center = mid
            if street:
                window += ((i * 2 + floor) % 3 - 1) * .23
                h = (1.22, 1.46, .97)[(i + floor) % 3] if floor < 2 else .84
                half *= (.86, 1.15, 1., .80)[i]
                center += ((i + floor) % 3 - 1) * bay * .068
                if (i, floor) in ((0, 2), (2, 1), (3, 2)):
                    box(fill, center - half, window, center + half, window + h, .024, .114)
                    add("LightOak", diagonal(center - half * .75, window + .14,
                                             center + half * .70, window + h - .14, .077), .016, .030)
                    box("Fieldstone", center - half - .13, window - .13, center + half + .13, window - .025, .015)
                    continue
                if (i, floor) in ((1, 0), (2, 0), (3, 1)):
                    for wing in (-1, 1):
                        left, right = sorted((center + wing * (half + .07), center + wing * (half + .38)))
                        box(fill, left, window, right, window + h, .027, .129)
            box("LightOak", center - half - .09, window - .08, center + half + .09, window + h + .09, .047)
            box("WindowGlow" if (i + floor + edge) % 5 == 0 else "LeadedGlass",
                center - half, window, center + half, window + h, .040, .089)
            box("DarkOak", center - .039, window, center + .039, window + h, .020, .085)
            box("DarkOak", center - half, window + h * .46, center + half, window + h * .46 + .052, .022, .080)
            for wing in (-1, 1):
                a, b = center + wing * half * .16, center + wing * half * .83
                add("Iron", diagonal(a, window + .16, b, window + h - .16, .043), .028, .063)
            box("Fieldstone", center - half - .13, window - .13, center + half + .13, window - .025, .016)
            brace_x = x0 + .20 if (i + floor) % 2 == 0 else x1 - .20
            tip_x = center - half * .60 if brace_x < center else center + half * .60
            use_long_brace = street and (i + floor) % 2 == 0
            add("DarkOak", diagonal(brace_x, window - (.74 if use_long_brace else .62),
                                    tip_x, window - .20, .16 if use_long_brace else .115), .022)


def front_gables(roof, plant, top):
    a, b = plant[7], plant[0]
    length, point = wall_frame(a, b)
    roof_edge = [triangle for triangle in roof if {a, b} <= {p[:2] for p in triangle}]
    if len(roof_edge) != 1:
        raise ValueError("The exposed gables require one owned street roof edge.")
    apex = next(p for p in roof_edge[0] if p[:2] not in (a, b))
    profile = ((0., top), (.055, 13.10), (.20, 14.76), (.34, 13.10), (.50, top),
               (.655, 13.10), (.80, 14.59), (.945, 13.10), (1., top))
    upper = [point(fraction * length, height, 0.) for fraction, height in profile]
    lower = [point(fraction * length, 13.02, 0.) for fraction, _ in profile]
    lower[0], lower[-1] = upper[0], upper[-1]
    roof_surface = [triangle for triangle in roof if triangle != roof_edge[0]]
    roof_surface.extend((a, b, apex) for a, b in zip(upper, upper[1:]))
    return upper, lower, roof_surface


def build_shell(varied=False):
    verified = verify()
    review = read_json(DEFAULT_REVIEW)["shell_geometry"]
    plant = tuple(tuple(point) for point in review["footprint_m"])
    party = {row["edge"] for row in review["party_wall_review"]}
    base, top = review["foundation_m"], review["source_roof_m"]
    document, blob = read_glb(PROJECT / SOURCE)
    roof = faces(document, blob, review["source_ordinary_roof_primitive"], [3000, 0, 0])
    roof = [roof[index] for index in review["roof_face_ordinals"]]
    if varied:
        upper, lower, roof_surface = front_gables(roof, plant, top)
    else:
        roof_surface = roof
    mesh = Mesh()
    for triangle in roof_surface:
        top_face = list(triangle)
        if signed_area([p[:2] for p in top_face]) < 0:
            top_face.reverse()
        mesh.face("Structure", "ClayDeck", *top_face)
        if not varied:
            mesh.face("Structure", "Fieldstone", *(p[:2] + (base,) for p in reversed(top_face)))
    if varied:
        for triangle in roof:
            bottom_face = list(triangle)
            if signed_area([p[:2] for p in bottom_face]) > 0:
                bottom_face.reverse()
            mesh.face("Structure", "Fieldstone", *(p[:2] + (base,) for p in bottom_face))
    for edge, (a, b) in enumerate(ring_edges(plant)):
        length, point = wall_frame(a, b)
        matter = "WarmLime" if edge % 2 else "CoolLime"
        street = varied and edge == 7
        wall_top = lower[1][2] if street else top
        corners = [point(u, z, 0) for u, z in rectangle(0, base, length, wall_top)]
        if street:
            corners[2], corners[3] = lower[-1], lower[0]
        if edge in party or length < 2.75:
            mesh.quad("Structure", matter, *corners)
            continue
        margin, depth = min(.48, length * .16), min(.24, length * .06)
        panel = [point(u, z, depth) for u, z in rectangle(margin, base + .16, length - margin, wall_top - .16)]
        for i in range(4):
            j = (i + 1) % 4
            if street and i == 2:
                for right, left in zip(reversed(lower[1:]), reversed(lower[:-1])):
                    mesh.face("Structure", matter, right, left, panel[2])
                mesh.face("Structure", matter, corners[3], panel[3], panel[2])
            else:
                mesh.quad("Structure", "Fieldstone" if i == 0 else matter, corners[i], corners[j], panel[j], panel[i])
        mesh.quad("Structure", matter, *panel)
        if street:
            mesh.face("Structure", matter, lower[0], lower[1], upper[1])
            for i in range(1, len(lower) - 2):
                mesh.quad("Structure", matter, lower[i], lower[i + 1], upper[i + 1], upper[i])
            mesh.face("Structure", matter, lower[-2], lower[-1], upper[-2])
        decorate(mesh, edge, length, margin, point, depth + .025, varied)
    report = audit(mesh, plant, roof, party, base, top, roof_surface if varied else None)
    pivot = (*plant[0], base)
    a, b = plant[-1], plant[0]
    width = math.dist(a, b)
    forward = ((b[1] - a[1]) / width, (a[0] - b[0]) / width)
    output = {**verified, **report, "status": "blocked_review_only", "world_pivot_m": pivot,
              "forward_xy": forward, "roof_held_world_z_m": top, "party_edges": sorted(party),
              "collision": "Original tile collision is the unchanged reference. This file is render geometry only."}
    if varied:
        output["render_roof"] = {"profile": "three street gables merging into original flat deck",
                                 "minimum_world_z_m": 13.1, "maximum_world_z_m": top,
                                 "required_live_review": ["roof visual/support gap", "FirstPage camera and sightlines"]}
    return mesh, output


def audit(mesh, plant, roof, party, base, top, render_roof=None):
    plane = [tuple(point[:2] for point in triangle) for triangle in roof]
    expected_roof = {tuple(sorted(tuple(round(v, 7) for v in p) for p in triangle))
                     for triangle in (render_roof if render_roof is not None else roof)}
    groups, declared_roof = {}, set()
    for group, material, points in mesh.faces:
        area_vector = cross(delta(points[1], points[0]), delta(points[2], points[0]))
        if len(set(points)) != 3 or math.hypot(*area_vector) < 1e-10:
            raise ValueError(f"Degenerate face in {group}.")
        for x, y, z in points:
            if not base - 1e-7 <= z <= top + 1e-7 or distance_to_building((x, y), plant) > 1e-6:
                raise ValueError(f"Vertex leaves the source envelope in {group}: {(x, y, z)}.")
        xy = tuple(p[:2] for p in points)
        area = abs(signed_area(xy))
        if area > 1e-8:
            covered = sum(triangle_intersection(xy, triangle) for triangle in plane)
            if abs(covered - area) > 1e-6:
                raise ValueError(f"Projected face crosses the source perimeter in {group}.")
        else:
            for a, b in ring_edges(xy):
                if a != b and interval_fraction(segment_in_triangle(a, b, t) for t in plane) < 1. - 1e-6:
                    raise ValueError(f"Vertical face crosses the source perimeter in {group}.")
        if (group, material) == ("Structure", "ClayDeck"):
            declared_roof.add(tuple(sorted(points)))
        edges = groups.setdefault(group, Counter())
        edges.update(ring_edges(points))
    if declared_roof != expected_roof:
        raise ValueError("The render roof triangles differ from the audited profile.")
    for group, directed in groups.items():
        if any(count != 1 or directed[b, a] != 1 for (a, b), count in directed.items()):
            raise ValueError(f"{group} is not a closed, consistently wound mesh.")
    for edge, (a, b) in enumerate(ring_edges(plant)):
        if edge not in party:
            continue
        quad = {(*p, z) for p in (a, b) for z in (base, top)}
        support = [face for group, _, face in mesh.faces if group == "Structure" and set(face) <= quad]
        if len(support) != 2 or {v for face in support for v in face} != quad:
            raise ValueError(f"Party wall {edge} no longer spans the original envelope.")
    return {"render_triangles": len(mesh.faces), "closed_components": len(groups),
            "structural_triangles": sum(group == "Structure" for group, _, _ in mesh.faces)}


def local_point(point, frame):
    x, y, z = (p - q for p, q in zip(point, frame["world_pivot_m"]))
    forward_x, forward_y = frame["forward_xy"]
    return (x * forward_x + y * forward_y, -x * forward_y + y * forward_x, z)


def texture_coordinates(points, report):
    local = [local_point(p, report) for p in points]
    normal = cross(delta(local[1], local[0]), delta(local[2], local[0]))
    drop = max(range(3), key=lambda i: abs(normal[i]))
    return [tuple(v / 2.5 for i, v in enumerate(point) if i != drop) for point in local]


def write_obj(mesh, report, output):
    obj, mtl = output / f"{NAME}.obj", output / f"{NAME}.mtl"
    with obj.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(f"# Review-only render model, metres, +X outward, +Z up.\nmtllib {mtl.name}\n")
        vertices = {}
        for _, _, points in mesh.faces:
            for point in points:
                if point not in vertices:
                    vertices[point] = len(vertices) + 1
                    stream.write("v " + " ".join(f"{p:.9f}" for p in local_point(point, report)) + "\n")
        previous = (None, None)
        texture_index = 0
        for group, material, points in mesh.faces:
            if group != previous[0]:
                stream.write(f"g {group}\n")
            if material != previous[1]:
                stream.write(f"usemtl {material}\n")
            previous = group, material
            for u, v in texture_coordinates(points, report):
                stream.write(f"vt {u:.6f} {v:.6f}\n")
            stream.write("f " + " ".join(f"{vertices[p]}/{texture_index + i}" for i, p in enumerate(points, 1)) + "\n")
            texture_index += 3
    with mtl.open("x", encoding="utf-8", newline="\n") as stream:
        for index, (label, (color, image)) in enumerate(MATERIALS.items()):
            if index:
                stream.write("\n")
            stream.write(f"newmtl {label}\nKd " + " ".join(f"{v / 255:.6f}" for v in color) + "\n")
            if image:
                path = os.path.relpath(ART_ROOT / "Textures" / image, output).replace("\\", "/")
                stream.write(f"map_Kd {path}\n")
    return {path.name: digest(path.read_bytes()) for path in (obj, mtl)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="New directory for the OBJ, MTL and audit.")
    parser.add_argument("--visual-study", action="store_true", help="Generate a separate three-gable art study.")
    args = parser.parse_args()
    output = args.output or REPRODUCTION_ROOT / ("GabledModel" if args.visual_study else "StructuralModel")
    if output.exists() or output.is_symlink():
        parser.error(f"Output directory must be new: {output}")
    mesh, report = build_shell(args.visual_study)
    try:
        output.mkdir(parents=True)
    except FileExistsError:
        parser.error(f"Output directory must be new: {output}")
    output = output.resolve()
    report["source_files_sha256"] = write_obj(mesh, report, output)
    with (output / "spawn_corner_prototype_audit.json").open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(report, stream, indent=2)
        stream.write("\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
