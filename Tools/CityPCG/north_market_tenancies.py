"""Add closed, period-inspired market bays to a pinned building source.

This produces a separate review OBJ and a separate overlay OBJ. The original
OBJ/FBX and its channels are never rewritten. Door and hatch motifs are
decorative: the existing building shell remains closed behind them.
"""
import hashlib
import json
import math
from pathlib import Path
import shutil


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'ArtDirection/CityPCG/MedievalOpening/WholeBuildings/NorthMarketDetailedObj'
PLAN = ROOT / 'ArtDirection/CityPCG/MedievalOpening/FollowOn20261115/north_market_east_plan_20261115.json'
MODEL = 'SM_GLMedieval_NorthMarketDetail_east_0a73564b'
BUILDING = 'Tile_p03_p01_roof_0a73564b5b0ed26a'
PINNED = {
    'obj': '5ca906f6b995d50cd956d89c9382856ba464366c23db6b93f0a886dfaec1a57f',
    'plan': 'acafb36160175ef164756753481a66273e7c6e9865e79508f94fd59ea4d6b4f7',
    'manifest': 'a9aeb89aab3a35914d505475b697ddfa01fb48ad43b1a98c6562bf89bdf49095',
    'mtl': '8b4485d8b96298d2586f0c0821697cc993cbf739c3ae645cb89576540ccdfec6',
}
TILES = {'Oak': .8, 'WeatheredOak': .8, 'ShopRed': .8, 'ShopGreen': .8,
         'LimePlaster': 1.8, 'WarmPlaster': 1.8, 'Interior': 1., 'Lead': 1.}


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def cross(a, b):
    return a[0] * b[1] - a[1] * b[0]


def inset(points, distance=.315):
    """Use the same offset-line construction as the original building kit."""
    lines = []
    for a, b in zip(points, points[1:] + points[:1]):
        dx, dy = b[0] - a[0], b[1] - a[1]
        length = math.hypot(dx, dy)
        if not math.isfinite(length) or length < 1e-7:
            raise ValueError('Invalid footprint edge')
        u = (dx / length, dy / length)
        lines.append(((a[0] - u[1] * distance, a[1] + u[0] * distance), u))
    result = []
    for i, (a, u) in enumerate(lines):
        b, v = lines[i - 1]
        denominator = cross(u, v)
        scale = 0. if abs(denominator) < .0001 else cross((b[0] - a[0], b[1] - a[1]), v) / denominator
        result.append((a[0] + u[0] * scale, a[1] + u[1] * scale))
    return result


def contains(point, plot, tolerance=1e-7):
    x, y = point
    inside = False
    for a, b in zip(plot, plot[1:] + plot[:1]):
        dx, dy = b[0] - a[0], b[1] - a[1]
        length2 = dx * dx + dy * dy
        if length2 <= 1e-14:
            raise ValueError('Degenerate footprint')
        fraction = ((x-a[0])*dx + (y-a[1])*dy) / length2
        if -tolerance <= fraction <= 1+tolerance and abs(cross((x-a[0], y-a[1]), (dx, dy))) <= tolerance * math.sqrt(length2):
            return True
        if (a[1] > y) != (b[1] > y) and x < a[0] + (y-a[1])*dx/dy:
            inside = not inside
    return inside


def segment_inside(a, b, plot):
    """Check open intervals between boundary intersections, including concavities."""
    direction = (b[0]-a[0], b[1]-a[1])
    if math.hypot(*direction) < 1e-10:
        return contains(a, plot)
    stations = [0., 1.]
    for c, d in zip(plot, plot[1:] + plot[:1]):
        edge = (d[0]-c[0], d[1]-c[1])
        offset = (c[0]-a[0], c[1]-a[1])
        den = cross(direction, edge)
        if abs(den) < 1e-12:
            continue
        t, u = cross(offset, edge)/den, cross(offset, direction)/den
        if 0. < t < 1. and -1e-9 <= u <= 1.+1e-9:
            stations.append(t)
    stations.sort()
    return contains(a, plot) and contains(b, plot) and all(
        contains((a[0] + (lo+hi)*.5*direction[0], a[1] + (lo+hi)*.5*direction[1]), plot)
        for lo, hi in zip(stations, stations[1:]) if hi-lo > 1e-10)


class Mesh:
    def __init__(self, plot, ceiling):
        self.plot, self.ceiling = plot, ceiling
        self.vertices, self.faces, self.roles = [], [], []

    def box(self, origin, tangent, normal, left, right, low, high, back, front, role):
        values = (*origin, *tangent, *normal, left, right, low, high, back, front)
        if (role not in TILES or not all(math.isfinite(v) for v in values)
                or left >= right or low < 0 or low >= high or high > self.ceiling
                or back < 0 or back >= front or front > .300001):
            raise ValueError('Invalid detail box or projection')
        def xy(station, depth):
            return (origin[0] + tangent[0]*station + normal[0]*depth,
                    origin[1] + tangent[1]*station + normal[1]*depth)
        footprint = [xy(left, back), xy(right, back), xy(right, front), xy(left, front)]
        if any(not segment_inside(a, b, self.plot) for a, b in zip(footprint, footprint[1:] + footprint[:1])):
            raise ValueError('Detail crosses the surveyed footprint')
        start = len(self.vertices)
        for depth in (back, front):
            self.vertices.extend((*xy(s, depth), z) for s, z in
                                 ((left, low), (right, low), (right, high), (left, high)))
        self.faces.extend([tuple(start+i for i in (3, 2, 1, 0)),
                           tuple(start+i for i in (4, 5, 6, 7))] +
                          [tuple(start+i for i in (j, (j+1)%4, (j+1)%4+4, j+4)) for j in range(4)])
        self.roles.extend([role]*6)


def open_intervals(length, entry):
    """Retain a generous, visibly clear interval around the existing doorway."""
    intervals = [(.50, length-.50)]
    if entry is not None:
        center, width = entry
        low, high = center-width/2-.55, center+width/2+.55
        intervals = [(a, min(b, low)) for a, b in intervals] + [(max(a, high), b) for a, b in intervals]
    return [(a, b) for a, b in intervals if b-a >= 2.65]


def shop(mesh, origin, tangent, normal, left, right, style, eave):
    """One varied, shallow, nonfunctional closed shop frontage in local metres."""
    add = lambda a, b, z0, z1, d0, d1, role: mesh.box(
        origin, tangent, normal, a, b, z0, z1, d0, d1, role)
    finish = ('ShopRed', 'ShopGreen', 'WeatheredOak')[style % 3]
    plaster = ('LimePlaster', 'WarmPlaster', 'LimePlaster')[style % 3]
    left += .07
    right -= .07
    # A panel covers earlier repeated windows; all relief remains < 0.30 m
    # forward of the inset wall and therefore inside the surveyed plot.
    add(left, right, .08, 2.52, .228, .242, plaster)
    door_width = min(.95, (right-left)*.27)
    door_left = left+.22 if style % 2 == 0 else right-.22-door_width
    door_right = door_left + door_width
    add(door_left, door_right, .08, 2.13, .243, .254, 'Interior')
    plank = door_width / 6
    for i in range(6):
        add(door_left+i*plank+.008, door_left+(i+1)*plank-.008, .09, 2.09, .255, .267, finish)
    for z in (.48, 1.62):
        add(door_left+.03, door_right-.03, z, z+.045, .268, .281, 'Lead')
    for y in (door_left-.045, door_right-.045):
        add(y, y+.09, .08, 2.22, .256, .290, 'Oak')
    add(door_left-.045, door_right+.045, 2.12, 2.22, .256, .290, 'Oak')
    hatch_left = door_right+.18 if style % 2 == 0 else left+.16
    hatch_right = right-.16 if style % 2 == 0 else door_left-.18
    if hatch_right-hatch_left < .6:
        raise ValueError('Tenancy is too narrow for a hatch')
    add(hatch_left, hatch_right, 1.00, 2.03, .243, .254, 'Interior')
    count = max(3, math.floor((hatch_right-hatch_left)/.25))
    width = (hatch_right-hatch_left)/count
    for i in range(count):
        add(hatch_left+i*width+.008, hatch_left+(i+1)*width-.008, 1.02, 2.01,
            .255, .268, finish if style % 3 != 2 else 'Oak')
    for z in (1.13, 1.85):
        add(hatch_left+.03, hatch_right-.03, z, z+.055, .269, .283, 'WeatheredOak')
    add(hatch_left-.08, hatch_right+.08, .90, 1.00, .255, .299, 'Oak')
    for y in (left, right-.09):
        add(y, y+.09, .05, min(eave-.12, 7.7), .252, .294, 'WeatheredOak' if style % 2 else 'Oak')
    add(left, right, 2.40, 2.52, .252, .294, 'Oak')
    # Small colored trade board, intentionally symbolic rather than text.
    sign_center = (hatch_left+hatch_right)/2
    add(sign_center-.34, sign_center+.34, 2.17, 2.37, .253, .283, finish)
    add(sign_center-.035, sign_center+.035, 2.20, 2.34, .284, .297, 'Lead')


def make_details(building, party_edges=()):
    plot = [tuple(p) for p in building['footprint_local_m']]
    walls = inset(plot)
    entry = building['entry']
    mesh = Mesh(plot, float(building['source_max_height_m']))
    units = []
    seed = int(hashlib.sha256(building['id'].encode()).hexdigest()[:8], 16) % 3
    for edge, (a, b) in enumerate(zip(walls, walls[1:] + walls[:1])):
        if edge in party_edges:
            continue
        dx, dy = b[0]-a[0], b[1]-a[1]
        length = math.hypot(dx, dy)
        if length < 4.3:
            continue
        tangent = (dx/length, dy/length)
        normal = (tangent[1], -tangent[0])
        if normal[0] < .94:
            continue
        protected = None
        if edge == entry['edge']:
            center = entry['center_local_xy_m']
            station = (center[0]-a[0])*tangent[0] + (center[1]-a[1])*tangent[1]
            protected = (station, entry['recessed_closed_opening_width_height_m'][0])
        for low, high in open_intervals(length, protected):
            count = max(1, math.floor((high-low)/3.5))
            width = (high-low)/count
            if width > 5.0:
                raise ValueError('Cannot divide frontage into legible tenancies')
            for i in range(count):
                left, right = low+i*width, low+(i+1)*width
                style = (seed + len(units)) % 3
                shop(mesh, a, tangent, normal, left, right, style, float(building['source_max_height_m']))
                units.append({'edge': edge, 'station_m': [left, right], 'style': style})
    if not units:
        raise ValueError('No suitable exposed frontage was found')
    return mesh, units


def normal_and_uv(points, tile):
    a, b, c = points[:3]
    u = tuple(b[i]-a[i] for i in range(3))
    v = tuple(c[i]-a[i] for i in range(3))
    n = (u[1]*v[2]-u[2]*v[1], u[2]*v[0]-u[0]*v[2], u[0]*v[1]-u[1]*v[0])
    length = math.sqrt(sum(x*x for x in n))
    if not math.isfinite(length) or length < 1e-12:
        raise ValueError('Degenerate detail polygon')
    n = tuple(x/length for x in n)
    axis = max(range(3), key=lambda i: abs(n[i]))
    u_axis, v_axis = ((1, 2), (0, 2), (0, 1))[axis]
    return n, [(p[u_axis]/tile, p[v_axis]/tile) for p in points]


def write_geometry(out, mesh, offsets=(0, 0, 0)):
    vertex_base, uv_base, normal_base = offsets
    for p in mesh.vertices:
        out.write('v ' + ' '.join(repr(x) for x in p) + '\n')
    last = None
    for index, (face, role) in enumerate(zip(mesh.faces, mesh.roles), 1):
        if role != last:
            out.write('usemtl M_GLMedieval_' + role + '\n')
            last = role
        normal, uvs = normal_and_uv([mesh.vertices[i] for i in face], TILES[role])
        for uv in uvs:
            out.write('vt ' + ' '.join(repr(x) for x in uv) + '\n')
        out.write('vn ' + ' '.join(repr(x) for x in normal) + '\n')
        out.write('f ' + ' '.join(f'{vertex_base+v+1}/{uv_base+i+1}/{normal_base+index}'
                                  for i, v in enumerate(face)) + '\n')
        uv_base += len(face)


def source_counts(path):
    counts = {'v': 0, 'vt': 0, 'vn': 0}
    with path.open('r', encoding='utf-8') as stream:
        for line in stream:
            word = line.split(' ', 1)[0]
            if word in counts:
                counts[word] += 1
    if not all(counts.values()):
        raise ValueError('Incomplete source OBJ')
    return tuple(counts[key] for key in ('v', 'vt', 'vn'))


def generate(output):
    """Generate into a fresh directory; intended for the isolated hosted job."""
    original = SOURCE / (MODEL + '.obj')
    inputs = {'obj': original, 'plan': PLAN, 'manifest': SOURCE/'detailed_obj_manifest.json',
              'mtl': SOURCE/'NorthMarketDetail.mtl'}
    if any(digest(path) != PINNED[key] for key, path in inputs.items()):
        raise ValueError('Pinned building input changed')
    plan = json.loads(PLAN.read_text(encoding='utf-8'))
    matches = [b for b in plan['buildings'] if b['id'] == BUILDING]
    if len(matches) != 1:
        raise ValueError('Expected exactly one selected building')
    party = {edge for item in plan.get('party_walls', []) for key, edge in item['edges'].items() if key == BUILDING}
    mesh, units = make_details(matches[0], party)
    counts = source_counts(original)
    output = Path(output)
    output.mkdir(parents=False, exist_ok=False)
    shutil.copyfile(SOURCE/'NorthMarketDetail.mtl', output/'NorthMarketDetail.mtl')
    if digest(output/'NorthMarketDetail.mtl') != PINNED['mtl']:
        raise ValueError('Material copy mismatch')
    manifest = json.loads((SOURCE/'detailed_obj_manifest.json').read_text(encoding='utf-8'))
    texture_dir = output/'Textures'
    texture_dir.mkdir()
    for info in manifest['textures'].values():
        src = SOURCE/'Textures'/Path(info['path']).name
        dst = texture_dir/src.name
        if digest(src) != info['sha256'] or dst.exists():
            raise ValueError('Unexpected source texture')
        shutil.copyfile(src, dst)
        if digest(dst) != info['sha256']:
            raise ValueError('Texture copy mismatch')
    overlay, combined = output/'tenancies_overlay.obj', output/(MODEL+'_tenancies_review.obj')
    with overlay.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write('# Closed visual details only; no gameplay openings.\nmtllib NorthMarketDetail.mtl\n')
        write_geometry(stream, mesh)
    with combined.open('xb') as stream, original.open('rb') as source:
        shutil.copyfileobj(source, stream, 65536)
        stream.write(b'\n# Added closed tenancy details, review only.\n')
    with combined.open('a', encoding='utf-8', newline='\n') as stream:
        write_geometry(stream, mesh, counts)
    with original.open('rb') as source, combined.open('rb') as result:
        for chunk in iter(lambda: source.read(65536), b''):
            if result.read(len(chunk)) != chunk:
                raise ValueError('Combined variant changed the source OBJ prefix')
    if any(digest(path) != PINNED[key] for key, path in inputs.items()):
        raise ValueError('Source changed during generation')
    report = {'status': 'review_only_not_unreal_validated', 'building': BUILDING,
              'source_obj_sha256': PINNED['obj'], 'source_plan_sha256': PINNED['plan'],
              'units': units, 'added_vertices': len(mesh.vertices), 'added_faces': len(mesh.faces),
              'overlay_sha256': digest(overlay), 'combined_sha256': digest(combined),
              'limits': ['Closed visual motifs; no physical door or hatch openings.',
                         'No Blender round-trip, Unreal placement, collision, navigation or gameplay validation.']}
    with (output/'tenancies.report.json').open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    return report


def main():
    import north_market_hosted_blender as adapter
    workspace = adapter.hosted_context()
    report = generate(workspace/'ci-north-market-tenancy')
    print(json.dumps({'status': report['status'], 'unit_count': len(report['units']),
                      'added_vertices': report['added_vertices'], 'added_faces': report['added_faces']}))


if __name__ == '__main__':
    main()
