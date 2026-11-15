"""Read the static triangle subset of the audited Blender UE bridge FBXs."""

from dataclasses import dataclass
import hashlib
import importlib
import math
from pathlib import Path
import sys
from types import ModuleType


@dataclass
class BuildingMesh:
    positions: list
    corner_vertices: list
    normals: list
    uv0: list
    materials: list
    face_materials: list


def load_decoder(directory):
    directory = Path(directory).resolve()
    if not (directory / "parse_fbx.py").is_file():
        raise ValueError("Point --fbx-decoder-dir at Blender's io_scene_fbx add-on.")
    # The stand-alone decoder needs its sibling modules, but not the add-on's bpy initialization.
    name = "_gray_london_fbx_decoder"
    if name in sys.modules:
        if sys.modules[name].__path__ != [str(directory)]:
            raise ValueError("The process already loaded its FBX decoder from another directory.")
    else:
        module = ModuleType(name)
        module.__path__ = [str(directory)]
        sys.modules[name] = module
    return importlib.import_module(f"{name}.parse_fbx").parse


def element(parent, name):
    matches = [child for child in parent.elems if child.id == name]
    if len(matches) != 1:
        raise ValueError(f"Expected one {name!r} FBX element, got {len(matches)}.")
    return matches[0]


def property_value(parent, name):
    return element(parent, name).props[0]


def obj_properties(parent):
    return {item.props[0]: item.props[4:] for item in element(parent, b"Properties70").elems if item.id == b"P"}


def tuples(values, width):
    if not values or len(values) % width or not all(math.isfinite(value) for value in values):
        raise ValueError("A mesh channel has invalid numeric data.")
    return [tuple(values[start:start + width]) for start in range(0, len(values), width)]


def fbx_name(node):
    return node.props[1].split(b"\x00\x01")[0].decode("utf-8")


def material_definitions(path, parse):
    """Fingerprint the authored material and its embedded textures independently of FBX IDs."""
    data, version = parse(str(path))
    if version != 7400:
        raise ValueError(f"{path}: expected the audited FBX 7.4 source format.")
    objects = {item.props[0]: item for item in element(data, b"Objects").elems if item.props}
    connections = element(data, b"Connections").elems

    def facts(node, ignored=(), inactive_properties=()):
        rows = []
        for value in node.elems:
            if value.id in ignored:
                continue
            if value.id == b"Properties70":
                definitions = sorted((item.props for item in value.elems if item.id == b"P"
                                      and item.props[0] != b"Path" and item.props[0] not in inactive_properties),
                                     key=lambda p: p[0])
                rows.append((value.id, definitions))
            else:
                rows.append((value.id, value.props, facts(value)))
        return sorted(rows, key=repr)

    output = {}
    for key, material in objects.items():
        if material.id != b"Material":
            continue
        textures = []
        for link in connections:
            if link.props[2] != key:
                continue
            texture = objects[link.props[1]]
            if texture.id != b"Texture" or len(link.props) != 4 or link.props[0] != b"OP":
                raise ValueError(f"{path}: unsupported material input on {fbx_name(material)}.")
            videos = [objects[row.props[1]] for row in connections if row.props[2] == link.props[1]]
            if len(videos) != 1 or videos[0].id != b"Video":
                raise ValueError(f"{path}: expected exactly one image per texture input.")
            video = videos[0]
            content = property_value(video, b"Content")
            if not isinstance(content, bytes) or not content:
                raise ValueError(f"{path}: missing embedded texture bytes.")
            textures.append((link.props[3], facts(texture, (b"FileName", b"RelativeFilename")),
                             facts(video, (b"Content", b"Filename", b"RelativeFilename")),
                             hashlib.sha256(content).hexdigest()))
        name = fbx_name(material)
        if name in output:
            raise ValueError(f"{path}: duplicate authored material {name}.")
        # Legacy Blender exports varied this color while explicitly multiplying it by zero.
        inactive = (b"AmbientColor",) if obj_properties(material).get(b"AmbientFactor") == [0.] else ()
        definition = repr((facts(material, inactive_properties=inactive), sorted(textures, key=repr))).encode("utf-8")
        output[name] = hashlib.sha256(definition).hexdigest()
    return output


def corner_channel(geometry, layer_name, value_name, index_name, width, count):
    layer = element(geometry, layer_name)
    if property_value(layer, b"MappingInformationType") != b"ByPolygonVertex":
        raise ValueError(f"{layer_name!r} must be addressed by triangle corner.")
    if layer_name == b"LayerElementUV" and property_value(layer, b"Name") != b"UV0":
        raise ValueError("Expected the authored UV0 layer.")
    values = tuples(property_value(layer, value_name), width)
    reference = property_value(layer, b"ReferenceInformationType")
    if reference == b"Direct" and len(values) == count:
        return values
    if reference == b"IndexToDirect":
        indices = property_value(layer, index_name)
        if len(indices) == count and all(0 <= index < len(values) for index in indices):
            return [values[index] for index in indices]
    raise ValueError(f"Invalid {layer_name!r} index or reference data.")


def read_mesh(path, parse):
    data, version = parse(str(path))
    if version != 7400:
        raise ValueError(f"{path}: expected the audited FBX 7.4 bridge format.")
    settings = obj_properties(element(data, b"GlobalSettings"))
    required_axes = {b"UpAxis": 2, b"UpAxisSign": 1, b"FrontAxis": 1, b"FrontAxisSign": -1,
                     b"CoordAxis": 0, b"CoordAxisSign": 1, b"UnitScaleFactor": 1.}
    if any(list(settings.get(key, [])) != [value] for key, value in required_axes.items()):
        raise ValueError(f"{path}: expected centimetre Z-up prepared FBX axes.")
    objects = element(data, b"Objects")
    model, geometry = element(objects, b"Model"), element(objects, b"Geometry")
    if model.props[2] != b"Mesh" or geometry.props[2] != b"Mesh":
        raise ValueError(f"{path}: expected one mesh model.")
    properties = obj_properties(model)
    # The bridge stores vertices in metres under a uniform 100x model scale.
    for key, expected in ((b"Lcl Translation", [0., 0., 0.]), (b"Lcl Rotation", [0., 0., 0.]),
                          (b"Lcl Scaling", [100., 100., 100.]), (b"PreRotation", [0., 0., 0.]),
                          (b"PostRotation", [0., 0., 0.]), (b"GeometricTranslation", [0., 0., 0.]),
                          (b"GeometricRotation", [0., 0., 0.]), (b"GeometricScaling", [1., 1., 1.])):
        actual = properties.get(key, expected)
        if len(actual) != 3 or any(abs(a - b) > 1e-5 for a, b in zip(actual, expected)):
            raise ValueError(f"{path}: nonidentity FBX transform {key!r}.")
    model_id, geom_id = model.props[0], geometry.props[0]
    connections = [row.props[1:3] for row in element(data, b"Connections").elems if row.props[0] == b"OO"]
    if [source for source, target in connections if source == model_id and target == 0] != [model_id]:
        raise ValueError(f"{path}: expected one root mesh model.")
    material_ids = {row.props[0]: fbx_name(row) for row in objects.elems if row.id == b"Material"}
    attached = [source for source, target in connections if target == model_id]
    if attached.count(geom_id) != 1 or any(item != geom_id and item not in material_ids for item in attached):
        raise ValueError(f"{path}: unexpected mesh attachments.")
    materials = [material_ids[item] for item in attached if item != geom_id]
    if not materials or len(materials) != len(set(materials)):
        raise ValueError(f"{path}: expected distinct authored material slots.")

    positions = tuples(property_value(geometry, b"Vertices"), 3)
    polygon = property_value(geometry, b"PolygonVertexIndex")
    if not polygon or len(polygon) % 3 or any((idx < 0) != (i % 3 == 2) for i, idx in enumerate(polygon)):
        raise ValueError(f"{path}: mesh has a nontriangle polygon.")
    corners = [~index if index < 0 else index for index in polygon]
    if any(index >= len(positions) for index in corners):
        raise ValueError(f"{path}: triangle corner references a missing vertex.")
    normal = corner_channel(geometry, b"LayerElementNormal", b"Normals", b"NormalsIndex", 3, len(corners))
    uv0 = corner_channel(geometry, b"LayerElementUV", b"UV", b"UVIndex", 2, len(corners))
    layer = element(geometry, b"LayerElementMaterial")
    if (property_value(layer, b"MappingInformationType") != b"ByPolygon" or
            property_value(layer, b"ReferenceInformationType") != b"IndexToDirect"):
        raise ValueError(f"{path}: expected material indices per polygon.")
    face_materials = list(property_value(layer, b"Materials"))
    if len(face_materials) * 3 != len(corners) or set(face_materials) != set(range(len(materials))):
        raise ValueError(f"{path}: triangle materials do not cover every declared material.")
    return BuildingMesh(positions, corners, normal, uv0, materials, face_materials)
