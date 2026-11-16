"""Offline check of a MedievalLondon crowd file against the town layout: route segments and spots inside a house
footprint or a landmark (the bell tower), strictly and with walker clearance.

Usage (repository root):  python Tools/Crowd/check_medieval_crowd.py [CROWD_JSON] [--streets PATH]
Defaults: Content/Crowd/Spots/MedievalLondon.json against Saved/MedievalLondon_Narrow_streets.json + the tower.
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_medieval_crowd as gen  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('crowd', nargs='?', default=str(gen.OUT))
    ap.add_argument('--streets', default=str(gen.NARROW))
    args = ap.parse_args()
    crowd = json.loads(Path(args.crowd).read_text(encoding='utf-8'))
    streets = json.loads(Path(args.streets).read_text(encoding='utf-8-sig'))
    houses = gen.Obstacles([tuple(b) for b in streets['house_boxes']])
    tower_boxes = [b for rows in gen.EXTRA_OBSTACLES.values() for b in rows] + gen.landmark_boxes(streets)
    tower = gen.Obstacles(tower_boxes)
    res_boxes = sorted(set(tower_boxes))
    nodes = crowd['routes']['nodes']
    edges = crowd['routes']['edges']
    res = {'crowd_file': args.crowd, 'streets_file': args.streets, 'streets_status': streets.get('status'),
           'house_boxes': len(streets['house_boxes']), 'route_edges': len(edges), 'spots': len(crowd['spots']),
           'tower_boxes': res_boxes}
    for label, obs in (('house', houses), ('tower', tower)):
        inside = sum(1 for a, b in edges if not obs.segment_clear(nodes[a][:2], nodes[b][:2], 1.0))
        near = sum(1 for a, b in edges if not obs.segment_clear(nodes[a][:2], nodes[b][:2], 35.0))
        sp_in = [s['name'] for s in crowd['spots'] if obs.blocked([(s['x'], s['y'])], 1.0)[0]]
        sp_near = [s['name'] for s in crowd['spots'] if obs.blocked([(s['x'], s['y'])], 30.0)[0]]
        res[label] = {'route_edges_through': inside, 'route_edges_within_35cm': near,
                      'spots_inside': len(sp_in), 'spots_within_30cm': len(sp_near), 'spots_inside_names': sp_in[:12]}
    print(json.dumps(res, indent=1))


if __name__ == '__main__':
    main()
