"""Split the reviewed medieval WatchGate into frame and quest-state pennants."""

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import struct

from subtract_building_shells import write_glb


PROJECT = Path(__file__).resolve().parents[2]
SAVED = PROJECT / 'Saved'
WATCH_GATE = PROJECT / 'ArtDirection/CityPCG/MedievalOpening/StrongholdKit/Source/SM_GL1450_WatchGate.glb'
SOURCE_SHA256 = '20fd9e3ee78b8d402f9f1a2573c40e89e13ad9961855611bf13514c43f700c0b'
FRAME = ('Palisade Oak', 'Palisade Weathered', 'Palisade Hewn', 'Palisade Iron', 'Palisade Rope')
CLOTH = ('Occupied Burgundy Wool', 'Occupied Pale Badge', 'Occupied Dark Binding')
SOURCE_MATERIALS = (*FRAME[:4], *CLOTH, FRAME[-1])
OCCUPIED = 'SM_GL1450_StrongholdPennantsOccupied'
RECLAIMED = 'SM_GL1450_StrongholdPennantsReclaimed'
NEUTRAL = 'SM_GL1450_StrongholdGateFrame'
RECLAIMED_MATERIALS = (
    ('Reclaimed Green Wool', [.055, .153, .113, 1]),
    ('Reclaimed Green Repair', [.055, .153, .113, 1]),
    ('Reclaimed Pale Binding', [.66, .54, .34, 1]),
)


def read_glb(raw):
    signature, version, size = struct.unpack_from('<4sII', raw)
    if signature != b'glTF' or version != 2 or size != len(raw):
        raise ValueError('Expected a complete glTF 2 binary')
    json_length, kind = struct.unpack_from('<I4s', raw, 12)
    buffer_length, buffer_kind = struct.unpack_from('<I4s', raw, 20 + json_length)
    if kind != b'JSON' or buffer_kind != b'BIN\0' or 28 + json_length + buffer_length != size:
        raise ValueError('Expected exactly one JSON and one binary chunk')
    return json.loads(raw[20:20 + json_length]), raw[28 + json_length:]


def triangle_count(document, primitives):
    total = 0
    for primitive in primitives:
        accessor = document['accessors'][primitive['indices']]
        count = accessor['count']
        if primitive.get('mode', 4) != 4 or accessor['type'] != 'SCALAR' or count % 3:
            raise ValueError('Watch kit requires indexed triangle primitives')
        total += count // 3
    return total


def split_source(document):
    if (len(document.get('meshes', [])) != 1 or document.get('nodes') != [{'mesh': 0, 'name': WATCH_GATE.stem}]
            or document.get('extensionsUsed') or len(document.get('buffers', [])) != 1):
        raise ValueError('Expected the reviewed single-mesh source at its base-center pivot')
    materials = tuple(entry['name'] for entry in document['materials'])
    if materials != SOURCE_MATERIALS:
        raise ValueError('Reviewed gate material names or slot order have changed')
    originals = document['meshes'][0]['primitives']
    if [primitive.get('material') for primitive in originals] != list(range(len(SOURCE_MATERIALS))):
        raise ValueError('Reviewed gate primitive material order has changed')
    frame, cloth = [], []
    for primitive in originals:
        if set(primitive['attributes']) != {'POSITION', 'NORMAL', 'TEXCOORD_0'}:
            raise ValueError('Watch gate geometry lost its audited position, normal or UV stream')
        material = materials[primitive['material']]
        (frame if material in FRAME else cloth).append(primitive)
    return frame, cloth


def variant(document, primitives, name, reclaimed=False):
    result = deepcopy(document)
    updated = deepcopy(primitives)
    materials = [deepcopy(document['materials'][primitive['material']]) for primitive in primitives]
    for index, primitive in enumerate(updated):
        primitive['material'] = index
    if reclaimed:
        if tuple(material['name'] for material in materials) != CLOTH:
            raise ValueError('Cannot pair reclaimed materials to the occupied cloth order')
        for material, (label, rgba) in zip(materials, RECLAIMED_MATERIALS):
            material['name'] = label
            material['pbrMetallicRoughness']['baseColorFactor'] = rgba
    result['meshes'][0]['name'] = name
    result['meshes'][0]['primitives'] = updated
    result['nodes'][0]['name'] = name
    result['materials'] = materials
    return result


def build(source, output):
    raw = source.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != SOURCE_SHA256:
        raise ValueError('Watch gate source does not match the reviewed GLB SHA-256')
    document, binary = read_glb(raw)
    frame, cloth = split_source(document)
    reports = {}
    plans = ((NEUTRAL, frame, False), (OCCUPIED, cloth, False), (RECLAIMED, cloth, True))
    output.mkdir(parents=True)
    for name, primitives, reclaimed in plans:
        result = variant(document, primitives, name, reclaimed)
        destination = output / f'{name}.glb'
        write_glb(destination, result, bytearray(binary))
        rebuilt, blob = read_glb(destination.read_bytes())
        if rebuilt != result or blob != binary:
            raise RuntimeError(f'{name}: export changed the selected streams or mesh data')
        reports[name] = {'file': destination.name, 'sha256': hashlib.sha256(destination.read_bytes()).hexdigest(),
                         'triangles': triangle_count(result, result['meshes'][0]['primitives']),
                         'materials': [material['name'] for material in result['materials']]}
    total = triangle_count(document, document['meshes'][0]['primitives'])
    if (reports[NEUTRAL]['triangles'] + reports[OCCUPIED]['triangles'] != total
            or reports[OCCUPIED]['triangles'] != reports[RECLAIMED]['triangles']):
        raise RuntimeError('Frame and pennants did not partition all reviewed source geometry')
    return {'status': 'offline_only', 'source': str(source), 'source_sha256': digest,
            'source_triangles': total, 'pivot': 'source gate base-center', 'fit_scale': [1, 1, 1],
            'collision': False, 'same_pennant_geometry_in_both_states': True, 'meshes': reports}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=WATCH_GATE)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to(SAVED.resolve()) or output.exists():
        parser.error('Select a fresh output directory inside this project’s Saved directory')
    report = build(args.source, output)
    (output / 'stronghold_kit_audit.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(f'Split and verified {len(report["meshes"])} visual modules in {output}')


if __name__ == '__main__':
    main()
