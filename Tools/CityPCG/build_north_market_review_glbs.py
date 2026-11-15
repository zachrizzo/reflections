"""Make isolated, review-only GLBs from the four pinned North Market OBJs.

No editor, asset, map, group, or source file is modified.  A complete manifest
is written only after all four outputs have passed readback.  An interrupted
directory is intentionally left incomplete; never use it as a runtime asset.
"""

from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import secrets
import struct
import time

from build_grouped_tile_derivatives import TRAIN_HEADER, memory_headroom
from fetch_triposr_weights import window_open


PROJECT = Path(__file__).resolve().parents[2]
BUNDLE = PROJECT / "ArtDirection/CityPCG/MedievalOpening/WholeBuildings/NorthMarketDetailedObj"
MANIFEST = BUNDLE / "detailed_obj_manifest.json"
MANIFEST_SHA = "a9aeb89aab3a35914d505475b697ddfa01fb48ad43b1a98c6562bf89bdf49095"
MAX_NONPLANAR_M = 0.00001
MAX_FACE_CORNERS = 128
MIN_PHYSICAL = 4 * 1024**3
MIN_COMMIT = 10 * 1024**3


def leading_train():
    with (PROJECT / "Saved/PIE_QUEUE.md").open(encoding="utf-8-sig") as stream:
        for line in stream:
            match = TRAIN_HEADER.match(line)
            if match:
                status = re.match(r"\s*:?\s*([A-Za-z_]+)\b", match.group(2))
                if not status or status.group(1).upper() != "LOADED":
                    raise RuntimeError("The leading editor train is not LOADED")
                if re.search(r"\b(others?\s+wait|reserv\w*|proof\s+round|npc-unify|restart\w*)\b", line, re.I):
                    raise RuntimeError("The leading queue entry reserves the editor window")
                return match.group(1)
    raise RuntimeError("No leading editor train status")


class SessionGuard:
    def __init__(self):
        window_open()  # no lease, train not building, editor running, and 4/10 GiB
        self.train = leading_train()
        self.physical, self.commit = memory_headroom()
        self.last = 0.0
        self.check(force=True)

    def check(self, force=False):
        now = time.monotonic()
        # Check the lease every time; rate-limit the process and memory probes.
        lock = PROJECT / "Saved/PIE_LOCK.json"
        if os.path.lexists(lock):
            raise RuntimeError("An editor lease appeared; stopping offline conversion")
        if not force and now - self.last < 1.0:
            return
        window_open()
        if leading_train() != self.train:
            raise RuntimeError("Editor train changed; stopping offline conversion")
        physical, commit = memory_headroom()
        if (physical < max(MIN_PHYSICAL, self.physical - 1024**3) or
                commit < max(MIN_COMMIT, self.commit - 2 * 1024**3)):
            raise RuntimeError("Available memory fell during conversion")
        self.last = now


def digest(path, check=lambda: None):
    result = hashlib.sha256()
    with path.open("rb") as stream:
        while True:
            chunk = stream.read(256 * 1024)
            if not chunk:
                break
            check()
            result.update(chunk)
    return result.hexdigest()


def cross2(a, b, c):
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def triangulate(points):
    """Ear-clip one simple near-planar ring, preserving its corner winding."""
    n = len(points)
    if n < 3 or n > MAX_FACE_CORNERS or any(len(p) != 3 or not all(map(math.isfinite, p)) for p in points):
        raise ValueError("Invalid polygon corners")
    normal = [sum((a[(i + 1) % 3] - b[(i + 1) % 3]) *
                  (a[(i + 2) % 3] + b[(i + 2) % 3])
                  for a, b in zip(points, points[1:] + points[:1])) for i in range(3)]
    length = math.sqrt(sum(v * v for v in normal))
    if length <= 1e-12:
        raise ValueError("Degenerate polygon normal")
    unit = [v / length for v in normal]
    nonplanar = max(abs(sum((p[i] - points[0][i]) * unit[i] for i in range(3))) for p in points)
    if nonplanar > MAX_NONPLANAR_M:
        raise ValueError(f"Non-planar polygon: {nonplanar:.9g} m")
    axis = max(range(3), key=lambda i: abs(normal[i]))
    keep = [i for i in range(3) if i != axis]
    p = [(v[keep[0]], v[keep[1]]) for v in points]
    span = max(max(v[i] for v in p) - min(v[i] for v in p) for i in range(2))
    length_eps = 1e-9 * max(1.0, span)
    area_eps = 1e-12 * max(1.0, span * span)
    if any(math.dist(p[i], p[j]) <= length_eps for i in range(n) for j in range(i)):
        raise ValueError("Repeated or ambiguous polygon corner")

    def on_segment(a, b, c):
        return (abs(cross2(a, b, c)) <= area_eps and
                min(a[0], b[0]) - length_eps <= c[0] <= max(a[0], b[0]) + length_eps and
                min(a[1], b[1]) - length_eps <= c[1] <= max(a[1], b[1]) + length_eps)

    def intersects(a, b, c, d):
        u, v, w, x = cross2(a, b, c), cross2(a, b, d), cross2(c, d, a), cross2(c, d, b)
        if ((u > area_eps and v < -area_eps) or (u < -area_eps and v > area_eps)) and \
           ((w > area_eps and x < -area_eps) or (w < -area_eps and x > area_eps)):
            return True
        return any((on_segment(a, b, c), on_segment(a, b, d),
                    on_segment(c, d, a), on_segment(c, d, b)))

    for i in range(n):
        for j in range(i + 1, n):
            if (i + 1) % n == j or (j + 1) % n == i:
                continue
            if intersects(p[i], p[(i + 1) % n], p[j], p[(j + 1) % n]):
                raise ValueError("Self-intersecting or touching polygon")
    signed = sum(a[0] * b[1] - a[1] * b[0] for a, b in zip(p, p[1:] + p[:1]))
    if abs(signed) <= area_eps:
        raise ValueError("Degenerate projected area")
    direction = 1 if signed > 0 else -1
    remaining, result = list(range(n)), []
    while len(remaining) > 3:
        for offset, b in enumerate(remaining):
            a, c = remaining[offset - 1], remaining[(offset + 1) % len(remaining)]
            if direction * cross2(p[a], p[b], p[c]) <= area_eps:
                continue
            if any(all(direction * cross2(p[x], p[y], p[k]) >= -area_eps
                       for x, y in ((a, b), (b, c), (c, a)))
                   for k in remaining if k not in (a, b, c)):
                continue
            result.append((a, b, c))
            del remaining[offset]
            break
        else:
            raise ValueError("Polygon cannot be triangulated unambiguously")
    if direction * cross2(*(p[i] for i in remaining)) <= area_eps:
        raise ValueError("Degenerate final triangle")
    result.append(tuple(remaining))
    area = sum(cross2(*(p[i] for i in tri)) for tri in result)
    if len(result) != n - 2 or abs(area - signed) > max(area_eps * n, abs(signed) * 1e-10):
        raise ValueError("Triangulation area mismatch")
    return result, nonplanar, tuple(unit)


def materials(manifest, check):
    path = BUNDLE / manifest["material_file"]
    if path.name != "NorthMarketDetail.mtl" or digest(path, check) != manifest["material_sha256"]:
        raise ValueError("Pinned material library differs")
    result, current = {}, None
    for raw in path.read_text(encoding="utf-8").splitlines():
        fields = raw.split()
        if not fields or fields[0].startswith("#"):
            continue
        if fields[0] == "newmtl" and len(fields) == 2 and fields[1] not in result:
            current = result[fields[1]] = {}
        elif fields[0] == "Kd" and current is not None and len(fields) == 4 and "color" not in current:
            color = [float(value) for value in fields[1:]]
            if not all(math.isfinite(v) and 0 <= v <= 1 for v in color):
                raise ValueError("Invalid material color")
            current["color"] = color
        elif fields[0] == "map_Kd" and current is not None and len(fields) == 2 and "texture" not in current:
            relative = PurePosixPath(fields[1])
            if len(relative.parts) != 2 or relative.parts[0] != "Textures" or relative.name in (".", ".."):
                raise ValueError("Unexpected material texture path")
            current["texture"] = fields[1]
        else:
            raise ValueError(f"Unsupported or duplicate material record: {raw}")
    for name, item in result.items():
        if "color" not in item or not name.startswith("M_GLMedieval_"):
            raise ValueError("Incomplete material")
        role = name.removeprefix("M_GLMedieval_")
        if role in manifest["textures"]:
            expected = manifest["textures"][role]
            if item.get("texture") != "Textures/" + Path(expected["path"]).name:
                raise ValueError("Material texture does not match the manifest")
            texture = (BUNDLE / item["texture"]).resolve(strict=True)
            if not texture.is_relative_to(BUNDLE.resolve(strict=True)) or digest(texture, check) != expected["sha256"]:
                raise ValueError("Pinned texture differs or leaves its bundle")
            data = texture.read_bytes()
            if not data.startswith(b"\x89PNG\r\n\x1a\n"):
                raise ValueError("Expected a PNG texture")
            item["data"] = data
            item["sha256"] = expected["sha256"]
        elif "texture" in item:
            raise ValueError("Unexpected texture")
    return result


def convert_obj(path, record, palette, check):
    if digest(path, check) != record["source_artifact"]["sha256"]:
        raise ValueError(f"Source hash differs: {path.name}")
    positions, uvs, normals, groups = [], [], [], {}
    current, libraries = None, []
    counts, faces, largest_error = Counter(), 0, 0.0
    max_errors = {"position_m": 0.0, "normal": 0.0, "uv": 0.0}
    with path.open(encoding="utf-8") as stream:
        for line_no, raw in enumerate(stream, 1):
            if line_no % 256 == 0:
                check()
            f = raw.split()
            if not f or f[0].startswith("#"):
                continue
            kind = f[0]
            if kind == "mtllib" and len(f) == 2:
                libraries.append(f[1])
            elif kind in ("v", "vt", "vn"):
                size = 2 if kind == "vt" else 3
                if len(f) != size + 1:
                    raise ValueError(f"{path.name}:{line_no} unsupported {kind}")
                value = tuple(float(x) for x in f[1:])
                if not all(map(math.isfinite, value)):
                    raise ValueError(f"{path.name}:{line_no} non-finite {kind}")
                if kind == "vn" and abs(math.sqrt(sum(x*x for x in value)) - 1) > 1e-5:
                    raise ValueError(f"{path.name}:{line_no} malformed normal")
                {"v": positions, "vt": uvs, "vn": normals}[kind].append(value)
            elif kind == "usemtl" and len(f) == 2 and f[1] in palette:
                current = f[1]
            elif kind == "f" and current:
                try:
                    corners = [tuple(int(i) for i in item.split("/")) for item in f[1:]]
                    if any(len(c) != 3 or min(c) <= 0 or c[0] > len(positions) or
                           c[1] > len(uvs) or c[2] > len(normals) for c in corners):
                        raise ValueError("Invalid OBJ corner reference")
                    triangles, error, normal = triangulate([positions[c[0]-1] for c in corners])
                    largest_error = max(largest_error, error)
                    group = groups.setdefault(current, {"POSITION": bytearray(), "NORMAL": bytearray(),
                                                         "TEXCOORD_0": bytearray(), "count": 0})
                    for triangle in triangles:
                        transformed = []
                        for index in triangle:
                            v, uv, vn = corners[index]
                            position = positions[v-1]
                            norm = normals[vn-1]
                            uv = uvs[uv-1]
                            values = {"POSITION": (position[0], position[2], -position[1]),
                                      "NORMAL": (norm[0], norm[2], -norm[1]),
                                      "TEXCOORD_0": (uv[0], 1.0-uv[1])}
                            for key, value in values.items():
                                packed = struct.pack("<" + "f" * len(value), *value)
                                unpacked = struct.unpack("<" + "f" * len(value), packed)
                                if not all(map(math.isfinite, unpacked)):
                                    raise ValueError("Float32 overflow")
                                label = {"POSITION": "position_m", "NORMAL": "normal", "TEXCOORD_0": "uv"}[key]
                                max_errors[label] = max(max_errors[label], *(abs(x-y) for x, y in zip(value, unpacked)))
                                group[key].extend(packed)
                                if key == "POSITION":
                                    transformed.append(unpacked)
                            group["count"] += 1
                        a, b, c = transformed
                        edge1 = [b[i]-a[i] for i in range(3)]
                        edge2 = [c[i]-a[i] for i in range(3)]
                        cp = (edge1[1]*edge2[2]-edge1[2]*edge2[1],
                              edge1[2]*edge2[0]-edge1[0]*edge2[2],
                              edge1[0]*edge2[1]-edge1[1]*edge2[0])
                        rotated_normal = (normal[0], normal[2], -normal[1])
                        if sum(cp[i]*rotated_normal[i] for i in range(3)) <= 1e-12:
                            raise ValueError("Float32 collapsed or inverted a triangle")
                    faces += 1
                    counts[current.removeprefix("M_GLMedieval_")] += 1
                except (ValueError, IndexError) as error:
                    raise ValueError(f"{path.name}:{line_no}: {error}") from error
            else:
                raise ValueError(f"{path.name}:{line_no}: unsupported or unbound {kind}")
    if (libraries != ["NorthMarketDetail.mtl"] or len(positions) != record["vertices"] or
            faces != record["polygons"] or len(uvs) != record["source_artifact"]["readback"]["uv_corners"] or
            dict(counts) != record["material_polygons"] or not groups):
        raise ValueError(f"{path.name}: source counts, materials or library differ from manifest")
    if digest(path, check) != record["source_artifact"]["sha256"]:
        raise ValueError(f"Source changed during processing: {path.name}")
    return groups, {"polygons": faces, "triangles": sum(g["count"] // 3 for g in groups.values()),
                    "max_polygon_nonplanarity_m": largest_error, "max_float32_error": max_errors}


def glb_bytes(groups, palette):
    binary = bytearray()
    views, accessors, images, textures, mats, primitives = [], [], [], [], [], []

    def view(data, target=None):
        while len(binary) % 4:
            binary.append(0)
        result = {"buffer": 0, "byteOffset": len(binary), "byteLength": len(data)}
        if target is not None:
            result["target"] = target
        views.append(result)
        binary.extend(data)
        return len(views) - 1

    for name, group in sorted(groups.items()):
        source = palette[name]
        # make_material connects textured PNGs directly to Base Color; Kd is
        # only the untextured fallback, not an additional texture multiplier.
        color_factor = [1., 1., 1., 1.] if "data" in source else source["color"] + [1.]
        pbr = {"baseColorFactor": color_factor, "metallicFactor": 0, "roughnessFactor": 1}
        if "data" in source:
            image_view = view(source["data"])
            images.append({"name": Path(source["texture"]).name, "bufferView": image_view, "mimeType": "image/png"})
            textures.append({"source": len(images)-1})
            pbr["baseColorTexture"] = {"index": len(textures)-1}
        mats.append({"name": name, "pbrMetallicRoughness": pbr})
        attrs = {}
        for key, width, type_name in (("POSITION", 3, "VEC3"), ("NORMAL", 3, "VEC3"), ("TEXCOORD_0", 2, "VEC2")):
            data = group[key]
            if len(data) != group["count"] * width * 4:
                raise ValueError("Malformed attribute stream")
            accessor = {"bufferView": view(data, 34962), "componentType": 5126,
                        "count": group["count"], "type": type_name}
            if key == "POSITION":
                rows = list(struct.iter_unpack("<fff", data))
                accessor["min"] = [min(row[i] for row in rows) for i in range(3)]
                accessor["max"] = [max(row[i] for row in rows) for i in range(3)]
            accessors.append(accessor)
            attrs[key] = len(accessors)-1
        primitives.append({"attributes": attrs, "material": len(mats)-1, "mode": 4})
    while len(binary) % 4:
        binary.append(0)
    doc = {"asset": {"version": "2.0", "generator": "North Market review-only OBJ converter"},
           "scene": 0, "scenes": [{"nodes": [0]}], "nodes": [{"mesh": 0}],
           "meshes": [{"primitives": primitives}], "materials": mats,
           "buffers": [{"byteLength": len(binary)}], "bufferViews": views, "accessors": accessors}
    if images:
        doc["images"], doc["textures"] = images, textures
    encoded = json.dumps(doc, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    encoded += b" " * (-len(encoded) % 4)
    size = 12 + 8 + len(encoded) + 8 + len(binary)
    return (struct.pack("<4sII", b"glTF", 2, size) + struct.pack("<I4s", len(encoded), b"JSON") + encoded +
            struct.pack("<I4s", len(binary), b"BIN\x00") + binary)


def verify_glb(path, groups, palette, check):
    check()
    data = path.read_bytes()
    magic, version, total = struct.unpack_from("<4sII", data)
    js_len, js_kind = struct.unpack_from("<I4s", data, 12)
    if (magic, version, total, js_kind) != (b"glTF", 2, len(data), b"JSON"):
        raise ValueError("Invalid GLB header")
    document = json.loads(data[20:20+js_len])
    offset = 20 + js_len
    bin_len, bin_kind = struct.unpack_from("<I4s", data, offset)
    binary = memoryview(data)[offset+8:]
    if bin_kind != b"BIN\x00" or len(binary) != bin_len or document["buffers"][0]["byteLength"] != bin_len:
        raise ValueError("Invalid GLB binary chunk")
    if document["nodes"] != [{"mesh": 0}] or len(document["meshes"][0]["primitives"]) != len(groups):
        raise ValueError("Unexpected node or primitive set")

    def read_view(index):
        item = document["bufferViews"][index]
        start, length = item["byteOffset"], item["byteLength"]
        if item["buffer"] != 0 or start < 0 or length < 0 or start + length > len(binary):
            raise ValueError("Invalid buffer view")
        return binary[start:start+length]

    for primitive in document["meshes"][0]["primitives"]:
        mat = document["materials"][primitive["material"]]
        name = mat["name"]
        if name not in groups or primitive["mode"] != 4:
            raise ValueError("Unexpected material or primitive")
        group = groups[name]
        for key, expected in ((k, group[k]) for k in ("POSITION", "NORMAL", "TEXCOORD_0")):
            accessor = document["accessors"][primitive["attributes"][key]]
            if (accessor["componentType"] != 5126 or accessor["count"] != group["count"] or
                    read_view(accessor["bufferView"]) != expected):
                raise ValueError("GLB attribute readback differs")
        pbr = mat["pbrMetallicRoughness"]
        expected_color = [1., 1., 1., 1.] if "data" in palette[name] else palette[name]["color"] + [1.]
        if pbr["baseColorFactor"] != expected_color:
            raise ValueError("Material color readback differs")
        if "data" in palette[name]:
            texture = document["textures"][pbr["baseColorTexture"]["index"]]
            image = document["images"][texture["source"]]
            if image["mimeType"] != "image/png" or hashlib.sha256(read_view(image["bufferView"])).hexdigest() != palette[name]["sha256"]:
                raise ValueError("Texture readback differs")
        elif "baseColorTexture" in pbr:
            raise ValueError("Unexpected texture readback")
    return hashlib.sha256(data).hexdigest()


def fresh_output_file(output, parent, filename):
    """Recheck that a fresh target remains under the unredirected new folder."""
    if (parent.resolve(strict=True) != parent or output.parent != parent or output.is_symlink() or
            getattr(output, "is_junction", lambda: False)() or output.resolve(strict=True) != output or
            not output.is_dir()):
        raise ValueError("Review output folder was redirected")
    if Path(filename).name != filename:
        raise ValueError("Unsafe review output filename")
    target = output / filename
    if os.path.lexists(target) or target.resolve().parent != output:
        raise ValueError("Review output already exists or was redirected")
    return target


def main():
    guard = SessionGuard()
    check = guard.check
    if digest(MANIFEST, check) != MANIFEST_SHA:
        raise ValueError("Pinned source manifest differs")
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if manifest.get("status") != "unreviewed_detailed_obj_source" or len(manifest["buildings"]) != 4:
        raise ValueError("Expected exactly four unreviewed source buildings")
    palette = materials(manifest, check)
    inputs = []
    for ident, record in sorted(manifest["buildings"].items()):
        filename = record["source_artifact"]["file"]
        if Path(filename).name != filename or not filename.endswith(".obj"):
            raise ValueError("Unexpected source path")
        path = (BUNDLE / filename).resolve(strict=True)
        if path.parent != BUNDLE.resolve(strict=True):
            raise ValueError("Source path leaves its bundle")
        groups, summary = convert_obj(path, record, palette, check)
        del groups
        inputs.append((ident, record, path, summary))
    check(force=True)
    intended_parent = PROJECT / "Saved/CityPCG"
    parent = intended_parent.resolve(strict=True)
    if (intended_parent.is_symlink() or getattr(intended_parent, "is_junction", lambda: False)() or
            parent != intended_parent.absolute() or
            not parent.is_relative_to((PROJECT / "Saved").resolve(strict=True))):
        raise ValueError("Output parent leaves Saved")
    name = "NorthMarketReviewGLB_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ_") + secrets.token_hex(4)
    output = parent / name
    if output.resolve().parent != parent or os.path.lexists(output):
        raise ValueError("Unsafe or existing output folder")
    output.mkdir()
    results = {}
    for ident, record, path, preflight in inputs:
        check(force=True)
        groups, summary = convert_obj(path, record, palette, check)
        if summary != preflight:
            raise ValueError("Conversion and preflight differ")
        blob = glb_bytes(groups, palette)
        target = fresh_output_file(output, parent, path.stem + ".glb")
        with target.open("xb") as stream:
            for offset in range(0, len(blob), 256 * 1024):
                check()
                stream.write(blob[offset:offset+256*1024])
        verified = verify_glb(target, groups, palette, check)
        results[ident] = {"file": target.name, "sha256": verified,
                          "source_obj_sha256": record["source_artifact"]["sha256"],
                          "source_world_pivot_m": record["world_pivot_m"], "source_yaw_deg": record["yaw_deg"],
                          "summary": summary}
        print(f"Verified review GLB: {target.name}", flush=True)
    check(force=True)
    if digest(MANIFEST, check) != MANIFEST_SHA:
        raise ValueError("Source manifest changed during conversion")
    materials(manifest, check)
    for _, record, path, _ in inputs:
        if digest(path, check) != record["source_artifact"]["sha256"]:
            raise ValueError("A source changed during conversion")
    report = {"status": "review_only_not_runtime_ready", "source_manifest_sha256": MANIFEST_SHA,
              "source_material_sha256": manifest["material_sha256"], "source_tile_glb_sha256": manifest["source_glb_sha256"],
              "axis_conversion": "OBJ (x,y,z) -> glTF (x,z,-y), determinant +1; local origin retained",
              "uv_conversion": "OBJ (u,v) -> glTF (u,1-v), lower-left to upper-left image convention",
              "material_assumptions": "Embedded PNG directly supplies textured base color; MTL diffuse for untextured; metallic=0, roughness=1",
              "limits": ["Review copies only; no UE import, placement, source-section binding or collision verified.",
                         "Source normals carried through the basis change, not independently validated.",
                         "Texture appearance and UV orientation require visual review.",
                         "Near-planar source polygons are tessellated; maximum deviation recorded per mesh."],
              "buildings": results}
    check(force=True)
    manifest_path = fresh_output_file(output, parent, "review_manifest.json")
    with manifest_path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(report, stream, indent=2)
        stream.write("\n")
    print(f"Review-only output complete: {output}", flush=True)


if __name__ == "__main__":
    main()
