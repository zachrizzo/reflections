"""Make an offline, trace-gated street overlay plan from an exported OSM tile."""

import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np

from build_opening_ground import accessor, clip, cross, read_glb


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def rounded_coordinates(values):
    """Round centimetre coordinates to 0.01 mm for a stable handoff."""
    return np.round(values, 3).tolist()


def street_axes(section, frontages):
    span = [frontages[key] for key in section['frontages']]
    for left, right in zip(span, span[1:]):
        if math.dist(left['end'][:2], right['start'][:2]) > .03:
            raise ValueError(f'Gap between frontage {left["id"]} and {right["id"]}')
    start = np.asarray(span[0]['start'][:2], dtype=np.float64) * 100
    end = np.asarray(span[-1]['end'][:2], dtype=np.float64) * 100
    forward = end - start
    full_length = np.linalg.norm(forward)
    if full_length <= 2 * section['axis_end_trim_cm'] + 150:
        raise ValueError('The frontage span is too short for the requested trim')
    forward /= full_length
    outward = np.array((-forward[1], forward[0]))
    if all(np.dot(outward, item['outward']) < -.97 for item in span):
        outward *= -1
    if any(np.dot(outward, item['outward']) < .97 for item in span):
        raise ValueError('Frontages must face the same street')
    trim = section['axis_end_trim_cm']
    start += forward * trim
    end -= forward * trim
    length = np.linalg.norm(end - start)
    near, gutter, far = (section[key] for key in ('near_edge_setback_cm', 'gutter_setback_cm', 'far_edge_setback_cm'))
    if not 0 < near < gutter < far:
        raise ValueError('Street requires ordered positive offsets and a useful span')
    band = np.array((start + outward*near, end + outward*near, end + outward*far, start + outward*far))
    if cross(band[1]-band[0], band[2]-band[0]) < 0:
        band = band[::-1]
    lower_x, lower_y, upper_x, upper_y = section['bounds_m']
    if np.any(band.min(axis=0) < 100*np.array((lower_x,lower_y))) or np.any(band.max(axis=0) > 100*np.array((upper_x,upper_y))):
        raise ValueError('Street outline left the reviewed district')
    return start, forward, outward, length, band


def clip_road(tile, section, band):
    document, binary = read_glb(tile)
    primitive = document['meshes'][0]['primitives'][section['road_primitive_index']]
    positions = accessor(document, binary, primitive['attributes']['POSITION']).astype(np.float64)
    positions = positions[:, (0, 2, 1)] * 100 + np.asarray(section['tile_origin_cm'])
    indices = accessor(document, binary, primitive['indices']).reshape(-1, 3)
    faces = positions[indices]
    low, high = band.min(axis=0), band.max(axis=0)
    near = np.all(faces[:, :, :2].max(axis=1) >= low, axis=1) & np.all(faces[:, :, :2].min(axis=1) <= high, axis=1)
    road = []
    for face in faces[near]:
        xy = face[:, :2]
        patch = np.asarray(clip(xy, band))
        if len(patch) < 3:
            continue
        # The export contains source Z at each corner. Evaluate its exact plane
        # at every clipped vertex instead of making a new flat strip.
        ab, ac = face[1:] - face[0]
        normal = np.cross(ab, ac)
        if abs(normal[2]) < .001:
            continue
        slope = -normal[:2] / normal[2]
        if np.linalg.norm(slope) > .16:
            raise ValueError('Clipped road triangle has unsupported slope')
        heights = face[0, 2] + (patch - face[0, :2]) @ slope
        if np.min(heights) <= section['city_ground_height_cm'] + 1 or np.max(heights) > 65:
            raise ValueError('Clipped primitive is not a raised street surface')
        area = sum(cross(a - patch[0], b - patch[0]) for a, b in zip(patch, np.roll(patch,-1,axis=0))) / 2
        if abs(area) < 1:
            continue
        if area < 0:
            patch, heights = patch[::-1], heights[::-1]
        road.append((patch, heights, slope))
    if not road:
        raise ValueError('No raised road geometry crossed this street section')
    return road


def surface_at(road, point, section):
    matching = []
    for polygon, z, slope in road:
        if all(cross(b - a, point - a) >= -1e-4 for a, b in zip(polygon, np.roll(polygon,-1,axis=0))):
            value = z[0] + (point - polygon[0]) @ slope
            matching.append(float(value))
    if matching:
        return section['tile_actor'], max(matching)
    return section['city_ground_actor'], section['city_ground_height_cm']


def make_guards(section, axes, road):
    start, forward, outward, length, _ = axes
    near, far = (section[key] for key in ('near_edge_setback_cm','far_edge_setback_cm'))
    positions = []
    for along in np.linspace(16, length - 16, math.ceil(length / 135) + 1):
        for across in np.linspace(17 + near, far - 17, math.ceil((far-near) / 130) + 1):
            positions.append(start + along*forward + across*outward)
    positions.extend(polygon.mean(axis=0) for polygon, _, _ in road)
    checks = []
    for index, coord in enumerate(positions):
        point = np.round(coord, 3)
        actor, height = surface_at(road, point, section)
        checks.append({
            'id': f'floor_{index:03}', 'xy_cm': point.tolist(),
            'from_z_cm': 70, 'to_z_cm': -120,
            'expect_actor': actor, 'expect_z_cm': round(height, 3),
            'tolerance_z_cm': .8, 'min_normal_z': .98,
        })
    return checks


def make_patches(section, axes, road):
    start, forward, outward, length, band = axes
    atlas_x, atlas_y = section['atlas_cm']
    lift = section['lift_cm']

    def polygon(xy, z, owner):
        u = (xy-start) @ forward / length
        across = (xy-start) @ outward
        # Straighten the opening atlas's drainage seam along the street axis
        # and retain the small irregular original seam variation.
        seam = 360 + .205*u*atlas_x
        v = (seam + (across - section['gutter_setback_cm'])*section['atlas_cross_scale']) / atlas_y
        uv = np.stack((u, v), axis=1)
        if np.any(uv < -1e-6) or np.any(uv > 1+1e-6):
            raise ValueError('Street atlas must not repeat past its outer edges')
        heights = np.broadcast_to(z, (len(xy),)) + lift
        return {
            'source_actor': owner, 'world_vertices_cm': rounded_coordinates(np.column_stack((xy, heights))),
            'uv_top_left': np.round(np.clip(uv, 0, 1), 6).tolist(),
            'triangles': [[0, i, i+1] for i in range(1, len(xy)-1)],
        }

    return [
        polygon(band, section['city_ground_height_cm'], section['city_ground_actor']),
        *(polygon(xy, z, section['tile_actor']) for xy, z, _ in road),
    ]


def validate_observations(guards, observations):
    by_id = {sample['id']: sample for sample in observations}
    expected_ids = {guard['id'] for guard in guards}
    if len(observations) != len(by_id) or set(by_id) != expected_ids:
        raise ValueError('Trace evidence must match every guard ID exactly once')
    failures = []
    for guard in guards:
        hit = by_id[guard['id']]
        if (hit['actor'] != guard['expect_actor'] or
                math.dist(hit['xy_cm'], guard['xy_cm']) > .02 or
                abs(hit['z_cm'] - guard['expect_z_cm']) > guard['tolerance_z_cm'] or
                hit['normal_z'] < guard['min_normal_z']):
            failures.append(guard['id'])
    if failures:
        raise ValueError('Street floor trace mismatch: '+', '.join(failures))


def build_plan(section, survey, tile, observations=None):
    sha = hashlib.sha256(tile.read_bytes()).hexdigest()
    if section['tile_sha256'] != sha:
        raise ValueError('Source OSM tile hash changed; repeat the district floor survey')
    if survey['coordinate_system'] != 'ue_local_m':
        raise ValueError('Expected a frontage survey in Unreal metres')
    geometry = survey['source_geometry']
    if (geometry['road_primitive'] != section['road_primitive_index'] or
            geometry['origin_m'] != [value/100 for value in section['tile_origin_cm']]):
        raise ValueError('The frontage survey and road export must use the same primitive and origin')
    if not 0 < section['lift_cm'] <= 1:
        raise ValueError('Cosmetic surface lift must be between zero and one centimetre')
    axes = street_axes(section, {row['id']: row for row in survey['frontages']})
    start, forward, outward, length, band = axes
    road = clip_road(tile, section, band)
    patches = make_patches(section, axes, road)
    guards = make_guards(section, axes, road)
    if observations is not None:
        validate_observations(guards, observations)
    return {
        'id': section['id'], 'coordinate_system': 'ue_cm', 'tile_sha256': sha,
        'source_tile_actor': section['tile_actor'],
        'source_attribution': survey['attribution'],
        'frontages': section['frontages'],
        'start_cm': rounded_coordinates(start), 'axis_xy': np.round(forward, 6).tolist(),
        'outward_xy': np.round(outward, 6).tolist(),
        'length_cm': round(length, 3),
        'width_cm': section['far_edge_setback_cm'] - section['near_edge_setback_cm'],
        'lift_cm': section['lift_cm'], 'collision_profile': 'NoCollision',
        'material_asset': section['material_asset'], 'patches': patches,
        'trace_status': 'verified' if observations is not None else 'requires_live_editor_traces',
        'floor_trace_guards': guards,
    }


def main():
    here = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('tile', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--section', type=Path, default=here/'west_street_section.json')
    parser.add_argument('--survey', type=Path, default=here.parent/'west_district_frontages.json')
    parser.add_argument('--observations', type=Path)
    args = parser.parse_args()
    plan = build_plan(read_json(args.section), read_json(args.survey), args.tile,
                      read_json(args.observations) if args.observations else None)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(plan, indent=2)+'\n', encoding='utf-8')
    print(f"{plan['id']}: {len(plan['patches'])} patches, "
          f"{len(plan['floor_trace_guards'])} trace guards, {plan['trace_status']}")


if __name__ == '__main__':
    main()
