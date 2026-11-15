"""Strict, bounded geometry/vertex-colour and placement checks for market trials.

This module performs no Unreal, Blender, network, or filesystem writes.  It is
deliberately conservative: unsupported GLB layouts must be reviewed, rather
than silently interpreted with the wrong pivot, coordinate system, or colour.
"""

from collections import Counter, defaultdict
import hashlib
import itertools
import json
import math
import struct


LEVEL = "/Game/GrayLondon/Maps/MedievalLondon"
ASSET_ROOT = "/Game/GrayLondon/MedievalOpening/MarketDressing/TripoSR"
TARGET_LONGEST_CM = {"AppleBasket": 55.0, "MerchantCrate": 72.0,
                     "PottersStock": 63.0, "BakersTray": 62.0,
                     "MarketHandcart": 180.0, "MarketWell": 253.0}
MAX_BYTES = 100 * 1024 * 1024
MAX_TRIANGLES = 500_000
POS_QUANTUM_M = 0.0001
ROUNDTRIP_POSITION_TOLERANCE_M = 0.000001


def finite(value):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError("Expected a finite number")
    return float(value)


def vector(value, size=3):
    if not isinstance(value, (list, tuple)) or len(value) != size:
        raise ValueError("Unexpected vector")
    return tuple(finite(x) for x in value)


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def _json(data):
    def bad_constant(_):
        raise ValueError("Non-finite JSON constant")
    return json.loads(data, object_pairs_hook=_pairs, parse_constant=bad_constant)


def _index(items, index):
    if type(index) is not int or index < 0 or index >= len(items):
        raise ValueError("Invalid GLB index")
    return items[index]


def _identity(node):
    if any(key in node for key in ("skin", "camera", "weights", "extensions")):
        raise ValueError("Unsupported node content")
    if "matrix" in node:
        if any(key in node for key in ("translation", "rotation", "scale")):
            raise ValueError("Mixed matrix and TRS")
        matrix = vector(node["matrix"], 16)
        expected = tuple(1.0 if i in (0, 5, 10, 15) else 0.0 for i in range(16))
        if any(abs(a - b) > 1e-9 for a, b in zip(matrix, expected)):
            raise ValueError("Non-identity node matrix; preserve and review transform first")
    for name, identity in (("translation", (0, 0, 0)), ("rotation", (0, 0, 0, 1)),
                           ("scale", (1, 1, 1))):
        if any(abs(a - b) > 1e-9 for a, b in zip(vector(node.get(name, identity), len(identity)), identity)):
            raise ValueError("Non-identity node transform; preserve and review transform first")


def _accessor(doc, binary, index, allowed):
    accessor = _index(doc.get("accessors", []), index)
    key = (accessor.get("type"), accessor.get("componentType"))
    if key not in allowed or "sparse" in accessor or "bufferView" not in accessor:
        raise ValueError("Unsupported GLB accessor")
    width = {"SCALAR": 1, "VEC3": 3, "VEC4": 4}[key[0]]
    code, byte_size = {5121: ("B", 1), 5123: ("H", 2), 5125: ("I", 4), 5126: ("f", 4)}[key[1]]
    normalized = accessor.get("normalized", False)
    if type(normalized) is not bool:
        raise ValueError("Invalid accessor normalized flag")
    if key[0].startswith("VEC") and key[1] != 5126 and not normalized:
        raise ValueError("Integer vertex colours must be normalized")
    if key[1] == 5126 and normalized:
        raise ValueError("Float accessor cannot be normalized")
    view = _index(doc.get("bufferViews", []), accessor["bufferView"])
    if view.get("buffer") != 0 or "extensions" in view:
        raise ValueError("Unsupported buffer view")
    start, length = view.get("byteOffset", 0), view.get("byteLength")
    offset, count = accessor.get("byteOffset", 0), accessor.get("count")
    stride = view.get("byteStride", width * byte_size)
    values = (start, length, offset, count, stride)
    if any(type(v) is not int or v < 0 for v in values) or count == 0 or count > MAX_TRIANGLES * 3:
        raise ValueError("Invalid accessor bounds")
    if key[0] == "SCALAR" and normalized:
        raise ValueError("Triangle indices cannot be normalized")
    if stride < width * byte_size or stride % byte_size or (start + offset) % byte_size:
        raise ValueError("Invalid accessor alignment/stride")
    end = offset + (count - 1) * stride + width * byte_size
    if end > length or start + length > doc["buffers"][0]["byteLength"]:
        raise ValueError("GLB accessor extends beyond its buffer")
    unpack = struct.Struct("<" + code * width).unpack_from
    divisor = {5121: 255., 5123: 65535.}.get(key[1], 1.) if normalized else 1.
    return [tuple(x / divisor for x in unpack(binary, start + offset + i * stride))
            for i in range(count)]


def parse_glb(raw, *, source=True, include_raw_faces=False):
    """Parse a simple identity-scene GLB and retain per-corner geometry + colour.

    Repeated vertices/triangles and winding are significant; one mesh may use
    multiple primitives.  glTF node transforms, animation, textures, and morphs
    are intentionally unsupported until an actual source is reviewed.
    """
    if not isinstance(raw, bytes) or len(raw) < 28 or len(raw) > MAX_BYTES:
        raise ValueError("GLB size exceeds the checked bounds")
    magic, version, total = struct.unpack_from("<4sII", raw)
    if magic != b"glTF" or version != 2 or total != len(raw):
        raise ValueError("Invalid GLB header")
    position = 12
    chunks = []
    while position < len(raw):
        if position + 8 > len(raw):
            raise ValueError("Truncated chunk header")
        size, kind = struct.unpack_from("<I4s", raw, position)
        position += 8
        if size % 4 or position + size > len(raw):
            raise ValueError("Invalid GLB chunk length")
        chunks.append((kind, raw[position:position + size]))
        position += size
    if len(chunks) != 2 or [x[0] for x in chunks] != [b"JSON", b"BIN\0"]:
        raise ValueError("Expected one JSON and one binary chunk")
    doc = _json(chunks[0][1].decode("utf-8"))
    binary = chunks[1][1]
    buffers = doc.get("buffers", [])
    if len(buffers) != 1 or "uri" in buffers[0] or type(buffers[0].get("byteLength")) is not int:
        raise ValueError("Expected one embedded buffer")
    if not 0 <= len(binary) - buffers[0]["byteLength"] <= 3:
        raise ValueError("Embedded buffer length differs from GLB")
    if doc.get("extensionsRequired") or doc.get("animations") or doc.get("skins"):
        raise ValueError("Compressed, animated or skinned source is unsupported")
    nodes, scenes = doc.get("nodes", []), doc.get("scenes", [])
    scene = _index(scenes, doc.get("scene", 0))
    pending, seen, mesh_nodes = list(scene.get("nodes", [])), set(), []
    while pending:
        index = pending.pop()
        if index in seen:
            raise ValueError("Repeated or cyclic GLB node")
        seen.add(index)
        node = _index(nodes, index)
        _identity(node)
        pending.extend(node.get("children", []))
        if "mesh" in node:
            mesh_nodes.append(node["mesh"])
    if seen != set(range(len(nodes))) or mesh_nodes != [0] or len(doc.get("meshes", [])) != 1:
        raise ValueError("Expected one reachable identity mesh and no hidden nodes")
    mesh = doc["meshes"][0]
    if mesh.get("weights") or mesh.get("extensions"):
        raise ValueError("Mesh-level morphs/extensions are unsupported")
    primitives = mesh.get("primitives", [])
    if not primitives:
        raise ValueError("Mesh contains no primitives")
    faces = Counter()
    raw_faces = []
    bounds = [[math.inf] * 3, [-math.inf] * 3]
    colors_seen = set()
    triangles = 0
    normal_presence = set()
    for primitive in primitives:
        if primitive.get("mode", 4) != 4 or primitive.get("extensions") or primitive.get("targets"):
            raise ValueError("Only ordinary triangle primitives are supported")
        attrs = primitive.get("attributes", {})
        normal_presence.add("NORMAL" in attrs)
        if "POSITION" not in attrs or "COLOR_0" not in attrs or "indices" not in primitive:
            raise ValueError("Triangle positions, indices and COLOR_0 are required")
        if source and "material" in primitive:
            material = _index(doc.get("materials", []), primitive["material"])
            pbr = material.get("pbrMetallicRoughness", {})
            if (material.get("alphaMode", "OPAQUE") != "OPAQUE" or pbr.get("baseColorTexture") or
                    vector(pbr.get("baseColorFactor", (1, 1, 1, 1)), 4) != (1, 1, 1, 1)):
                raise ValueError("Source material modifies vertex colour; review it first")
        positions = _accessor(doc, binary, attrs["POSITION"], {("VEC3", 5126)})
        colors = _accessor(doc, binary, attrs["COLOR_0"],
                           {(shape, ty) for shape in ("VEC3", "VEC4") for ty in (5121, 5123, 5126)})
        indices = _accessor(doc, binary, primitive["indices"],
                            {("SCALAR", 5121), ("SCALAR", 5123), ("SCALAR", 5125)})
        if len(positions) != len(colors) or len(indices) % 3 or len(indices) < 3:
            raise ValueError("Invalid geometry or colour counts")
        triangles += len(indices) // 3
        if triangles > MAX_TRIANGLES:
            raise ValueError("Triangle bound exceeded")
        corners, raw_corners = [], []
        for xyz, color in zip(positions, colors):
            xyz = vector(xyz)
            color = vector(color, len(color))
            if any(c < 0 or c > 1 for c in color) or (len(color) == 4 and abs(color[3] - 1) > 1 / 255):
                raise ValueError("Unsupported colour range or opacity")
            rgb = tuple(round(c * 255) for c in color[:3])
            colors_seen.add(rgb)
            for axis, value in enumerate(xyz):
                bounds[0][axis] = min(bounds[0][axis], value)
                bounds[1][axis] = max(bounds[1][axis], value)
            corners.append(tuple(round(x / POS_QUANTUM_M) for x in xyz) + rgb)
            if include_raw_faces:
                raw_corners.append((xyz, rgb))
        for start in range(0, len(indices), 3):
            triple = tuple(int(indices[start + i][0]) for i in range(3))
            if any(i < 0 or i >= len(corners) for i in triple):
                raise ValueError("Triangle index out of bounds")
            face = tuple(corners[i] for i in triple)
            faces[min(face, face[1:] + face[:1], face[2:] + face[:2])] += 1
            if include_raw_faces:
                raw_faces.append(tuple(raw_corners[i] for i in triple))
    if source and len(colors_seen) < 2:
        raise ValueError("Source has no colour variation to verify")
    if len(normal_presence) != 1:
        raise ValueError("Only some source primitives contain normals")
    if any(not math.isfinite(x) for row in bounds for x in row):
        raise ValueError("Non-finite source bounds")
    result = {"sha256": hashlib.sha256(raw).hexdigest(), "faces": faces,
            "triangles": triangles, "bounds_gltf_units": bounds,
            "distinct_rgb8": len(colors_seen), "has_normals": normal_presence == {True}}
    if include_raw_faces:
        result["raw_faces"] = raw_faces
    return result


def compare_glb(source_bytes, result_bytes):
    before = parse_glb(source_bytes, include_raw_faces=True)
    after = parse_glb(result_bytes, source=False, include_raw_faces=True)
    if before["triangles"] != after["triangles"]:
        raise ValueError("Imported triangle count differs")
    tolerance = ROUNDTRIP_POSITION_TOLERANCE_M
    # Index each oriented corner by exact RGB8 and a spatial bucket. Looking at
    # adjacent buckets avoids rejecting sub-micron changes at grid boundaries.
    # Candidate faces are consumed exactly once, preserving multiplicity and
    # winding even when geometry contains duplicated vertices/triangles.
    index = defaultdict(list)
    observed = after["raw_faces"]
    for face_id, face in enumerate(observed):
        for rotation, (point, rgb) in enumerate(face):
            bucket = tuple(math.floor(value / tolerance) for value in point)
            index[(rgb, bucket)].append((face_id, rotation))
    consumed = set()
    max_distance = 0.
    for source in before["raw_faces"]:
        point, rgb = source[0]
        bucket = tuple(math.floor(value / tolerance) for value in point)
        matched = None
        for delta in itertools.product((-1, 0, 1), repeat=3):
            key = (rgb, tuple(a + b for a, b in zip(bucket, delta)))
            for face_id, rotation in index.get(key, ()):
                if face_id in consumed:
                    continue
                candidate = observed[face_id][rotation:] + observed[face_id][:rotation]
                if any(a[1] != b[1] for a, b in zip(source, candidate)):
                    continue
                distances = tuple(math.dist(a[0], b[0]) for a, b in zip(source, candidate))
                if max(distances) <= tolerance:
                    matched = (face_id, max(distances))
                    break
            if matched:
                break
        if matched is None:
            raise ValueError("Imported oriented triangle positions or attached RGB8 differ beyond tolerance")
        consumed.add(matched[0])
        max_distance = max(max_distance, matched[1])
    if len(consumed) != len(observed):
        raise ValueError("Imported triangle multiplicity differs")
    return {"source_sha256": before["sha256"], "roundtrip_sha256": after["sha256"],
            "triangles": before["triangles"], "distinct_rgb8": before["distinct_rgb8"],
            "max_corner_distance_gltf_units": max_distance,
            "position_tolerance_gltf_units": tolerance, "color_comparison": "exact RGB8",
            "source_bounds_gltf_units": before["bounds_gltf_units"]}


def normalize_z_up_glb(raw):
    """Return a new GLB rotated -90 degrees about X, keeping raw input intact.

    This is deliberately opt-in: use it only after the raw source's Z-up
    orientation has been visually established. POSITION, NORMAL and TANGENT
    vectors are rotated; other channels and triangle indices are left alone.
    Interleaved/overlapping target buffer views are rejected rather than guessed.
    """
    original = parse_glb(raw)
    json_size, json_kind = struct.unpack_from("<I4s", raw, 12)
    if json_kind != b"JSON":
        raise ValueError("Missing GLB JSON")
    json_end = 20 + json_size
    bin_size, bin_kind = struct.unpack_from("<I4s", raw, json_end)
    if bin_kind != b"BIN\0":
        raise ValueError("Missing GLB binary")
    doc = _json(raw[20:json_end].decode("utf-8"))
    binary = bytearray(raw[json_end + 8:json_end + 8 + bin_size])
    accessors = doc["accessors"]
    targets = {}
    for primitive in doc["meshes"][0]["primitives"]:
        for semantic, index in primitive["attributes"].items():
            if semantic in ("POSITION", "NORMAL", "TANGENT"):
                expected = "VEC4" if semantic == "TANGENT" else "VEC3"
                if index in targets and targets[index] != expected:
                    raise ValueError("An accessor has incompatible vector semantics")
                targets[index] = expected
            elif not (semantic.startswith("COLOR_") or semantic.startswith("TEXCOORD_")):
                raise ValueError("Unreviewed source vertex attribute")
    view_owners = {}
    for index, shape in targets.items():
        accessor = _index(accessors, index)
        view_id = accessor.get("bufferView")
        if view_id in view_owners and view_owners[view_id] != index:
            raise ValueError("Interleaved vector accessors are unsupported")
        view_owners[view_id] = index
        view = _index(doc["bufferViews"], view_id)
        start, end = view.get("byteOffset", 0), view.get("byteOffset", 0) + view["byteLength"]
        for other_id, other in enumerate(doc["bufferViews"]):
            other_start = other.get("byteOffset", 0)
            if other_id != view_id and start < other_start + other["byteLength"] and other_start < end:
                raise ValueError("Overlapping GLB buffer views are unsupported")
        for other_id, other in enumerate(accessors):
            if other_id != index and other.get("bufferView") == view_id:
                raise ValueError("A rotated view is shared with another accessor")
        vectors = _accessor(doc, binary, index, {(shape, 5126)})
        offset = start + accessor.get("byteOffset", 0)
        stride = view.get("byteStride", 4 * (4 if shape == "VEC4" else 3))
        rotated = []
        for i, item in enumerate(vectors):
            item = vector(item, 4 if shape == "VEC4" else 3)
            changed = (item[0], item[2], -item[1]) + item[3:]
            struct.pack_into("<" + "f" * len(changed), binary, offset + stride * i, *changed)
            rotated.append(changed)
        for field, function in (("min", min), ("max", max)):
            if field in accessor:
                accessor[field] = [function(row[axis] for row in rotated) for axis in range(len(rotated[0]))]
    encoded = json.dumps(doc, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")
    encoded += b" " * (-len(encoded) % 4)
    normalized = (struct.pack("<4sII", b"glTF", 2, 12 + 8 + len(encoded) + 8 + len(binary)) +
                  struct.pack("<I4s", len(encoded), b"JSON") + encoded +
                  struct.pack("<I4s", len(binary), b"BIN\0") + bytes(binary))
    result = parse_glb(normalized)
    expected_faces = Counter()
    for face, count in original["faces"].items():
        turned = tuple((corner[0], corner[2], -corner[1], *corner[3:]) for corner in face)
        expected_faces[min(turned, turned[1:] + turned[:1], turned[2:] + turned[:2])] += count
    if result["faces"] != expected_faces:
        raise ValueError("Axis normalization changed topology or vertex-colour attachment")
    return normalized, {"raw_sha256": original["sha256"], "normalized_sha256": result["sha256"],
                        "rotation": "-90 degrees about X: (x,y,z) -> (x,z,-y)",
                        "triangles": result["triangles"], "distinct_rgb8": result["distinct_rgb8"]}


def distance_segment(point, a, b):
    point, a, b = vector(point, 2), vector(a, 2), vector(b, 2)
    dx, dy = b[0] - a[0], b[1] - a[1]
    squared = dx * dx + dy * dy
    if squared <= 1e-8:
        raise ValueError("Degenerate walking-reserve segment")
    along = max(0., min(1., ((point[0] - a[0]) * dx + (point[1] - a[1]) * dy) / squared))
    return math.hypot(point[0] - a[0] - along * dx, point[1] - a[1] - along * dy)


def placement(kind, bounds_cm, support_cm, yaw_deg, target_cm=None):
    if kind not in TARGET_LONGEST_CM:
        raise ValueError("Unknown reviewed prop kind")
    lo, hi = (vector(row) for row in bounds_cm)
    spans = tuple(b - a for a, b in zip(lo, hi))
    if min(spans) <= 0 or max(spans) > 100_000:
        raise ValueError("Invalid imported bounds")
    support = vector(support_cm)
    yaw = finite(yaw_deg)
    target = finite(TARGET_LONGEST_CM[kind] if target_cm is None else target_cm)
    if target < .5 * TARGET_LONGEST_CM[kind] or target > 1.5 * TARGET_LONGEST_CM[kind]:
        raise ValueError("Requested size is outside the candidate's review range")
    scale = target / max(spans)
    if not .0001 <= scale <= 1000:
        raise ValueError("Unexpected source scale")
    x, y = -scale * (lo[0] + hi[0]) / 2, -scale * (lo[1] + hi[1]) / 2
    angle = math.radians(yaw)
    location = (support[0] + x * math.cos(angle) - y * math.sin(angle),
                support[1] + x * math.sin(angle) + y * math.cos(angle), support[2] - lo[2] * scale)
    return {"kind": kind, "support_cm": support, "location_cm": location, "yaw_deg": yaw,
            "scale": (scale, scale, scale), "size_cm": tuple(s * scale for s in spans),
            "radius_cm": .5 * math.hypot(spans[0] * scale, spans[1] * scale)}


def check_clearance(placements, walking_segments, *, margin_cm=20.):
    margin = finite(margin_cm)
    if margin < 0 or not placements or not walking_segments or len(placements) > 24:
        raise ValueError("A bounded placement set and measured walking reserve are required")
    for row in placements:
        center, radius = row["support_cm"][:2], finite(row["radius_cm"])
        if radius <= 0:
            raise ValueError("Invalid prop radius")
        for segment in walking_segments:
            half = finite(segment["half_width_cm"])
            if half < 125 or distance_segment(center, segment["a_cm"], segment["b_cm"]) < half + radius + margin:
                raise ValueError("A prop overlaps the protected walking reserve")
    for i, left in enumerate(placements):
        for right in placements[i + 1:]:
            if math.dist(left["support_cm"][:2], right["support_cm"][:2]) < left["radius_cm"] + right["radius_cm"]:
                raise ValueError("Prop footprint envelopes overlap")
    return True
