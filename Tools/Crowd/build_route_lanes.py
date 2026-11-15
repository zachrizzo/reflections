"""Gray London crowd lanes along the hero route, merged over several OSM tiles (offline, NumPy only).

Runs Tools/Crowd/lanes_from_tile.py for every route box of every exported tile (Saved/CityPCG/<tile>.glb plus
<tile>.asset.json: origin_m, road_primitive, primitives order for GL_Roof) and writes one JSON for crowd_lanes.py
stage 'json'. Tiles not exported yet are skipped and listed. Usage (repository root):
  python Tools/Crowd/build_route_lanes.py
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CITY = ROOT / 'Saved' / 'CityPCG'
OUT = ROOT / 'Tools' / 'Crowd' / 'graylondon_lanes.json'

# east0 north0 east1 north1 (metres) per tile: the route from the intro (Great Tower St) to Tower Hill, Fenchurch St,
# Lime St and Leadenhall. Tiles are 1 km squares centred on their origin (p03_p00: 2500-3500 x -500-500).
ROUTE = {
    'Tile_p03_p00': [(3100, 230, 3500, 500)],     # Great Tower St, Byward St, Mark Lane, Seething Lane, Fenchurch St, Lime St south
    'Tile_p04_p00': [(3500, 230, 3660, 480)],     # Trinity Square / Tower Hill, Cooper's Row, London Wall
    'Tile_p03_p01': [(3000, 500, 3350, 680)],     # Lime St, Leadenhall Market, Gracechurch St, Fenchurch St north side
}


def main():
    lanes, used, missing = [], [], []
    for name, boxes in ROUTE.items():
        glb, manifest = CITY / f'{name}.glb', CITY / f'{name}.asset.json'
        if not glb.exists() or not manifest.exists():
            missing.append(name)
            continue
        spec = json.loads(manifest.read_text())
        prims = list(spec.get('primitives', {}).keys())
        roof = prims.index('GL_Roof') if 'GL_Roof' in prims else 1
        road = spec.get('road_primitive', prims.index('GL_Road') if 'GL_Road' in prims else 2)
        for b, box in enumerate(boxes):
            tmp = OUT.with_name(f'_lanes_{name}_{b}.json')
            cmd = [sys.executable, str(ROOT / 'Tools' / 'Crowd' / 'lanes_from_tile.py'), str(glb),
                   *[str(v) for v in spec['origin_m']], '--road-primitive', str(road), '--roof-primitive', str(roof),
                   '--box', *[str(v) for v in box], '--far', '3', '--min-cells', '12', '--out', str(tmp)]
            subprocess.run(cmd, check=True)
            part = json.loads(tmp.read_text())
            tmp.unlink()
            lanes += part['lanes']
            used.append({'tile': name, 'box_m': box, 'stats': part['stats']})
    out = {
        'note': 'x/y/z in UE cm (x = east_m*100, y = north_m*100); z = city ground 10 cm + 3. Spawned by '
                'Tools/Crowd/crowd_lanes.py stage json. Built by Tools/Crowd/build_route_lanes.py.',
        'tiles_used': used, 'tiles_missing': missing,
        'stats': {'lanes': len(lanes), 'points': sum(len(p) for p in lanes)},
        'lanes': lanes,
    }
    OUT.write_text(json.dumps(out, indent=0))
    print(json.dumps({'tiles_used': [u['tile'] for u in used], 'tiles_missing': missing, **out['stats']}))


if __name__ == '__main__':
    main()
