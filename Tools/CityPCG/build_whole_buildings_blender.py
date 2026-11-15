"""Generate closed medieval buildings from a reviewed survey and matching plan."""

import argparse
from dataclasses import replace
import hashlib
import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Vector

TOOLS = Path(__file__).resolve().parent
PROJECT = TOOLS.parents[1]
ART = PROJECT / 'ArtDirection/CityPCG/MedievalOpening'
SAVED = PROJECT / 'Saved/CityPCG'
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(ART / 'WholeBuildings'))
from build_mark_lane import (Bay, BuildingStyle, contains, cross, crossbeam, doorway, dress_gables, elevation,
                             inset, leaded, local_frame, make_object, move_elevation, party_wall, preview,
                             ring_pairs, roof_z, shell, shutter, tiled_roof, verify_envelope)
from prepare_mark_lane_ue_fbx import mesh_facts, prepare, solid_volume
from whole_building_styles import STYLE_PRESETS, read_style_overrides


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def sha256(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def paired_edges(plan):
    edges = {}
    for party in plan.get('party_walls', []):
        if party.get('keep_sealed') is not True or len(party['edges']) != 2:
            raise ValueError('A party wall must be sealed and identify two reviewed edges')
        for building_id, edge in party['edges'].items():
            if edge in edges.setdefault(building_id, set()):
                raise ValueError(f'{building_id}: repeated party-wall edge {edge}')
            edges[building_id].add(edge)
    return edges


def styles_for(plan_row, style_plan, shared, override=None):
    front_width = plan_row['dimensions_x_y_m'][1]
    eave = float(style_plan['eave_m'])
    if not 5.2 <= eave <= 11.4:
        raise ValueError(f'{plan_row["id"]}: eave must fit the two- to four-storey building kit')
    storeys = max(2, round(eave / 2.7))
    floors = tuple(eave * i / storeys for i in range(storeys + 1))
    party_edge = min(shared) if shared else None
    name = override
    if name is None:
        if front_width >= 23:
            name = 'TradingRange'
        elif 'market' in plan_row['role'].casefold():
            name = 'SteppedMarket'
        else:
            name = 'DeepWorkshop'
    ground, upper, timber, shutter_color, window_bays = STYLE_PRESETS[name]
    return BuildingStyle(name, party_edge, ground, upper, timber, shutter_color, floors, eave, window_bays)


def roof_profile(plot, plan_row, style_plan):
    profile = [tuple(knot) for knot in plan_row['roof_profile_local_y_z_m']]
    count = style_plan['roof_ranges']
    if len(profile) != 2 * count + 1 or not all(a[0] < b[0] for a, b in zip(profile, profile[1:])):
        raise ValueError(f'{plan_row["id"]}: expected a monotonic sequence of planned gables')
    profile[0] = (min(point[1] for point in plot), profile[0][1])
    profile[-1] = (max(point[1] for point in plot), profile[-1][1])
    if any(abs(z - style_plan['eave_m']) > .00001 for _, z in profile[::2]):
        raise ValueError(f'{plan_row["id"]}: planned eaves disagree with the facade height')
    # Keep the major ridge at the planned height and lower adjoining ranges.
    # The odd heights preserve all the planned eave and valley positions.
    seed = int(hashlib.sha256(plan_row['id'].encode()).hexdigest()[:8], 16)
    main = seed % count
    roof_skin = .089
    ceiling = min(style_plan['ridge_m'], plan_row['source_max_height_m']) - roof_skin
    for index in range(count):
        slot = index * 2 + 1
        y, z = profile[slot]
        drop = 0 if index == main else (.38, .70, .98)[(seed + index) % 3]
        top = min(ceiling, z) - drop
        if top < style_plan['eave_m'] + 1.65:
            raise ValueError(f'{plan_row["id"]}: the planned roof is too shallow for this kit')
        profile[slot] = (y, top)
    return profile


def entrance_wall(length, center, opening, style):
    details = Bay()
    span, height = opening[0] / 2, opening[1]
    left, right = -.5 * length + .38, .5 * length - .38
    if center - span - .31 < left or center + span + .31 > right:
        raise ValueError('The selected door does not fit the measured, inset street wall')
    doorway(details, center, style.name != 'DeepWorkshop', style.wood,
            span=span, spring=height - .3, rise=.3)
    # Run the larger entrance framing behind the recess rather than across the access line.
    for z in style.floors[1:]:
        details.band(left, right, z - .15, z + .009, -.018, .18, style.wood)
    bents = max(1, math.ceil((right - left) / 2.7))
    weights = [(1.13, .79, 1.07, 1.24, .91)[index % 5] for index in range(bents)]
    divisions = [left]
    for weight in weights:
        divisions.append(divisions[-1] + (right - left) * weight / sum(weights))
    for y in divisions:
        details.band(y - .077, y + .077, style.floors[1], style.eaves - .075, -.018, .135, style.wood)
    for index, (a, b) in enumerate(zip(divisions, divisions[1:])):
        middle = (a + b) * .5
        half = min((.58, .68, .42, .63)[index % 4], (b - a) * .31)
        if abs(middle - center) >= span + half + .33:
            if style.name == 'TradingRange' and index % 4 == 0:
                shutter(details, middle - half, middle + half, 1.03, 2.06, .063, style.accent)
            else:
                leaded(details, middle - half, middle + half, 1.1, 2.04, .021, True)
            details.band(middle - half - .13, middle + half + .13, .96, 1.08, .022, .167, style.wood)
        for level, (bottom, top) in enumerate(zip(style.floors[1:], style.floors[2:])):
            low = bottom + (.54, .75, .66, .59)[(index + level) % 4]
            high = min(low + (.92, 1.19, .82)[index % 3], top - .28)
            brace = (style.name == 'SteppedMarket' and (index + level) % 4 == 0
                     or style.name == 'TradingRange' and index % 9 == 7)
            if half < .30 or brace:
                if b - a > .5:
                    crossbeam(details, -.023, .118, (a + .13, bottom + .09), (b - .13, top - .16), .124, style.wood)
                    if b - a > 1.65:
                        crossbeam(details, -.023, .123, (b - .13, bottom + .09), (a + .13, top - .16), .124, style.wood)
                continue
            if style.name == 'TradingRange' and index % 7 == 3:
                shutter(details, middle - half, middle + half, low, high, .073, style.accent)
                for y in (middle - half, middle + half):
                    details.band(y - .047, y + .047, low - .041, high + .041, .029, .129, style.wood)
                continue
            leaded(details, middle - half, middle + half, low, high, .03, style.name == 'TradingRange')
            if style.name == 'DeepWorkshop' and b - middle - half > .34:
                shutter(details, middle + half, middle + half + .26, low, high, .105, style.accent)
    if style.name == 'DeepWorkshop':
        details.band(center - span - .22, center + span + .22, height + .22, height + .31, .036, .22, style.wood)
    return details


def interior_spans(plot, y):
    intersections = sorted(a[0] + (b[0] - a[0]) * (y - a[1]) / (b[1] - a[1])
                           for a, b in ring_pairs(plot) if (a[1] > y) != (b[1] > y))
    return sorted(zip(intersections[::2], intersections[1::2]), key=lambda span: span[1] - span[0], reverse=True)


def chimney(bay, cx, cy, bottom, top):
    back, front, left, right = cx - .32, cx + .32, cy - .41, cy + .41
    bay.band(left, right, bottom, top - .20, back, front, 'GuildRubble')
    row = 0
    z = bottom + .035
    while z < top - .27:
        upper = min(top - .205, z + .118)
        for side in (back, front - .001):
            brick_left = left - (.122 if row % 2 else 0)
            while brick_left < right - .012:
                a = max(left, brick_left)
                b = min(right, brick_left + .226)
                if b - a > .018:
                    bay.band(a, b, z, upper, side - .026, side + .027, 'ClayTile')
                brick_left += .24
        for x in (back, cx - .18, cx + .035, front - .126):
            bay.band(left - .028, left + .012, z, upper, x, min(front, x + .125), 'ClayTile')
            bay.band(right - .012, right + .028, z, upper, x, min(front, x + .125), 'ClayTile')
        z += .134
        row += 1
    bay.band(left - .062, right + .062, top - .213, top - .101, back - .066, front + .065, 'GuildDressed')
    for y in (cy - .217, cy + .217):
        bay.band(y - .115, y + .115, top - .111, top, cx - .157, cx + .157, 'WeatheredOak')


def add_chimneys(bay, plot, profile, style):
    limit = 3 if style.name == 'TradingRange' else 2 if style.name == 'SteppedMarket' else 1
    heads = []
    cap = max(z for _, z in profile) + .089
    for range_index in range(0, len(profile) - 1, 2):
        if len(heads) >= limit:
            break
        low, high = profile[range_index][0], profile[range_index + 2][0]
        for fraction in (.26, .73, .18, .82):
            y = low + (high - low) * fraction
            for first, last in interior_spans(plot, y):
                if last - first < 2.5:
                    continue
                x = first + (last - first) * (.42 if range_index % 4 == 0 else .67)
                envelope = [(x + dx, y + dy) for dx in (-.49, .49) for dy in (-.53, .53)]
                lower = min(roof_z(yy, profile) for _, yy in envelope) - .12
                roof_top = max(roof_z(yy, profile) for _, yy in envelope) + .089
                top = min(cap - .02, roof_top + 1.0)
                if top - roof_top >= .63 and all(contains(point, plot) for point in envelope):
                    chimney(bay, x, y, lower, top)
                    heads.append((x, y, top))
                    break
            else:
                continue
            break
    return heads


def from_plan(record, planned, style_plan, shared, override=None, roof_variation=None):
    plot, x_axis, y_axis = local_frame(record)
    if (math.dist(record['origin_m'], planned['origin_m']) > .00002
            or len(plot) != len(planned['footprint_local_m'])
            or any(math.dist(a, b) > .00002 for a, b in zip(plot, planned['footprint_local_m']))):
        raise ValueError(f'{record["id"]}: the plan and surveyed footprint disagree')
    yaw = math.degrees(math.atan2(x_axis[1], x_axis[0]))
    if abs(math.remainder(yaw - planned['rotation_yaw_deg'], 360)) > .00001:
        raise ValueError(f'{record["id"]}: the plan and surveyed orientation disagree')
    if any(not 0 <= edge < len(plot) for edge in shared):
        raise ValueError(f'{record["id"]}: one or more party-wall edges lie outside the footprint')
    entry_edge = planned['entry']['edge']
    if entry_edge != record['entry']['edge'] or entry_edge in shared:
        raise ValueError(f'{record["id"]}: door must be on its reviewed, exposed edge')
    style = styles_for(planned, style_plan, shared, override)
    walls = inset(plot, .315)
    gables = inset(plot, .14)
    profile = roof_profile(plot, planned, style_plan)
    if roof_variation is not None:
        if roof_variation != 'asymmetric-ridges-v1':
            raise ValueError('Unknown opt-in roof variation')
        from whole_building_ridge_variation import vary_ridges
        profile = vary_ridges(profile, planned['id'], planned['source_max_height_m'], shared)
    bay = Bay()
    shell(bay, plot, walls, gables, profile, style)
    tiled_roof(bay, plot, profile)
    dress_gables(bay, gables, profile, style)
    for edge in shared:
        party_wall(bay, plot, walls, replace(style, party_edge=edge))
    for edge, (a, b) in enumerate(ring_pairs(walls)):
        if edge in shared:
            continue
        center = (Vector(a) + Vector(b)) / 2
        direction = (Vector(b) - Vector(a)).normalized()
        if edge == entry_edge:
            entry = planned['entry']
            position = (Vector(entry['center_local_xy_m']) - center).dot(direction)
            details = entrance_wall(math.dist(a, b), position, entry['recessed_closed_opening_width_height_m'], style)
        else:
            details = elevation(a, b, edge, entry_edge, 0.5, style, 0.0, 0.0)
        move_elevation(bay, details, center, (direction.y, -direction.x))
    stacks = add_chimneys(bay, plot, profile, style)
    verify_envelope(bay, plot, planned['source_max_height_m'])
    return bay, plot, profile, style, x_axis, y_axis, stacks


def segment_in_footprint(a, b, outline, edges):
    """Split a projected edge at every boundary crossing and test each open interval."""
    direction = (b[0] - a[0], b[1] - a[1])
    if math.hypot(*direction) < 1e-7:
        return True
    stations = [0.0, 1.0]
    for c, edge, box in edges:
        if (max(a[0], b[0]) < box[0] or min(a[0], b[0]) > box[1]
                or max(a[1], b[1]) < box[2] or min(a[1], b[1]) > box[3]):
            continue
        delta = (c[0] - a[0], c[1] - a[1])
        denominator = cross(direction, edge)
        if abs(denominator) > 1e-10:
            edge_fraction = cross(delta, direction) / denominator
            fraction = cross(delta, edge) / denominator
            if -.0001 <= edge_fraction <= 1.0001 and 1e-7 < fraction < 1 - 1e-7:
                stations.append(fraction)
    stations.sort()
    for low, high in zip(stations, stations[1:]):
        mid = (low + high) / 2
        if not contains((a[0] + mid * direction[0], a[1] + mid * direction[1]), outline):
            return False
    return True


def audit_mesh(obj, outline, expected):
    mesh = obj.data
    facts = mesh_facts(mesh)
    if facts != expected or facts['uv_layers'] != ['UV0'] or not facts['materials']:
        raise ValueError(f'{obj.name}: round trip changed geometry, UV0, or material order')
    if any(abs(value) > 1e-5 for value in (*obj.location, *obj.rotation_euler)) or any(
        abs(value - 1) > 1e-5 for value in obj.scale
    ):
        raise ValueError(f'{obj.name}: object must export at an identity transform')
    if any(not node.image or (not node.image.packed_file and not Path(bpy.path.abspath(node.image.filepath)).is_file())
           for material in mesh.materials if material.use_nodes
           for node in material.node_tree.nodes if node.type == 'TEX_IMAGE'):
        raise ValueError(f'{obj.name}: round-trip texture path did not resolve')
    edges = [(a, (b[0] - a[0], b[1] - a[1]), (min(a[0], b[0]), max(a[0], b[0]), min(a[1], b[1]), max(a[1], b[1])))
             for a, b in ring_pairs(outline)]
    vertex_xy = [(point.co.x, point.co.y) for point in mesh.vertices]
    if any(not contains(point, outline) for point in vertex_xy):
        raise ValueError(f'{obj.name}: a projected vertex escaped the surveyed shell')
    seen = set()
    for triangle in mesh.loop_triangles:
        if triangle.area < 1e-10:
            raise ValueError(f'{obj.name}: degenerate imported triangle {triangle.index}')
        for a, b in ring_pairs(tuple(triangle.vertices)):
            key = tuple(sorted((a, b)))
            if key not in seen:
                seen.add(key)
                if not segment_in_footprint(vertex_xy[a], vertex_xy[b], outline, edges):
                    raise ValueError(f'{obj.name}: triangle {triangle.index} crosses a surveyed recess')
    volume = solid_volume(mesh)
    if volume <= 0:
        raise ValueError(f'{obj.name}: non-positive enclosed volume')
    return {'checked_triangle_edges': len(seen), 'signed_volume_m3': volume, 'closed_solid_edges': True}


def arguments():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--candidate', type=Path, default=ART / 'west_connector_whole_buildings_candidate.json')
    cli.add_argument('--plan', type=Path, default=SAVED / 'MedievalSurvey/west_connector_whole_building_plan.json')
    cli.add_argument('--style-overrides', type=Path, help='Optional plan-pinned style presets by surveyed building ID')
    cli.add_argument('--roof-variation', choices=('asymmetric-ridges-v1',),
                     help='Opt in to reviewed asymmetric ridge positions; rejects party walls')
    cli.add_argument('--review-source-facts', action='store_true',
                     help='Record extra pre-export mesh channel counts for a review round trip')
    cli.add_argument('--output', type=Path, default=SAVED / 'WholeBuildings/WestConnector')
    cli.add_argument('--prefix', default='WestConnector')
    cli.add_argument('--preview', action='store_true')
    cli.add_argument('--prepare-unreal', action='store_true')
    return cli.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])


def main():
    args = arguments()
    candidate, plan = read_json(args.candidate), read_json(args.plan)
    records = {row['id']: row for row in candidate['buildings']}
    if (candidate['source_tile'] != plan['source_tile'] or candidate['source_export_sha256'] != plan['source_export_sha256']
            or set(records) != set(plan['styles']) or set(records) != {row['id'] for row in plan['buildings']}):
        raise ValueError('The candidate and approved model plan must have matching source and shell IDs')
    if not args.prefix.isascii() or not args.prefix.isalnum():
        raise ValueError('Asset name prefix must be ASCII alphanumeric')
    plan_hash = sha256(args.plan)
    overrides = read_style_overrides(args.style_overrides, args.plan, records.keys()) if args.style_overrides else {}
    if args.roof_variation and paired_edges(plan):
        raise ValueError('Roof variation cannot run on plans containing shared party-wall edges')
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError(f'Choose a fresh output directory; refusing to overwrite {output}')
    meshes = output / 'Source'
    meshes.mkdir(parents=True)
    report = {'schema': 1, 'source_tile': candidate['source_tile'], 'pivot': 'survey origin at ground; +X entrance; +Z up',
              'candidate_sha256': sha256(args.candidate), 'plan_sha256': plan_hash, 'buildings': {}}
    if args.style_overrides:
        report['style_overrides_sha256'] = sha256(args.style_overrides)
    if args.roof_variation:
        report['roof_variation'] = args.roof_variation
    shared_edges = paired_edges(plan)
    if not shared_edges.keys() <= records.keys():
        raise ValueError('Party wall references an unknown plan building')
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.scene.unit_settings.system = 'METRIC'
    audit = []
    for row in plan['buildings']:
        key = row['id']
        bay, outline, profile, style, x_axis, y_axis, stacks = from_plan(
            records[key], row, plan['styles'][key], shared_edges.get(key, set()), overrides.get(key),
            args.roof_variation)
        name = f'SM_GLMedieval_{args.prefix}_{style.name}_{key.rsplit("_", 1)[-1][:8]}'
        obj = make_object(bay, name)
        source = meshes / f'{name}.fbx'
        expected = mesh_facts(obj.data)
        if args.review_source_facts:
            pre_export_channels = {'vertices': len(obj.data.vertices), 'edges': len(obj.data.edges),
                                   'polygons': len(obj.data.polygons),
                                   'color_attributes': len(obj.data.color_attributes)}
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        bpy.ops.export_scene.fbx(filepath=str(source), use_selection=True, object_types={'MESH'},
                                 axis_forward='-Z', axis_up='Y', mesh_smooth_type='FACE', bake_anim=False,
                                 path_mode='COPY', embed_textures=True)
        if args.preview:
            preview(output / f'{name}.png', [obj])
        bpy.data.objects.remove(obj, do_unlink=True)
        report['buildings'][key] = dict(expected, fbx=f'Source/{source.name}', style=style.name,
                                        world_pivot_m=row['origin_m'], yaw_deg=row['rotation_yaw_deg'],
                                        axis_x_world_xy=x_axis, axis_y_world_xy=y_axis,
                                        footprint_local_m=outline, roof_profile_local_y_z_m=profile,
                                        chimney_heads_local_m=stacks,
                                        source_height_cm=100 * row['source_max_height_m'], entry=row['entry'],
                                        party_wall_edges=sorted(shared_edges.get(key, set())), collision=False)
        if args.review_source_facts:
            report['buildings'][key]['pre_export_channels'] = pre_export_channels
        audit.append((key, source, outline, expected))
    for key, source, outline, expected in audit:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.import_scene.fbx(filepath=str(source))
        obj, = [item for item in bpy.context.scene.objects if item.type == 'MESH']
        if obj.name != source.stem:
            raise ValueError(f'{source}: imported mesh name drifted')
        report['buildings'][key]['roundtrip'] = dict(audit_mesh(obj, outline, expected), fbx_sha256=sha256(source))
    if args.prepare_unreal:
        bridge = output / 'UnrealSource'
        bridge.mkdir(exist_ok=True)
        for key, source, _, _ in audit:
            row = report['buildings'][key]
            prepared = bridge / source.name
            row['unreal_bridge'] = dict(prepare(source, prepared, row), fbx=f'UnrealSource/{source.name}')
    (output / 'whole_buildings_kit.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(f'Exported and audited {len(audit)} reviewed buildings to {output}')


if __name__ == '__main__':
    main()
