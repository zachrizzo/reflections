"""Pavement lane centrelines for Gray London, computed offline from an exported OSM tile (no editor needed).

Gray London's pavements are not separate meshes: roads are the tile's GL_Road triangles (flat, Z 28 cm) and the
pavement is the city ground (Z 10 cm) between a road and the building fronts (GL_Roof footprints). So a pavement lane
runs 1-3 m outside a road edge and at least 1 m clear of any building:

  band = cells 1..3 m from a road, not road, not within 1 m of a roof footprint   (1 m grid)
  -> thinned to centrelines (Zhang-Suen) -> polylines split at junctions -> points every 6 m, Z = 13 cm.

Output JSON (UE cm; calib identity: x = east_m * 100, y = north_m * 100) for crowd_lanes.py stage 'json', which only
spawns the ZoneShapes. Usage (repository root, NumPy):
  python Tools/Crowd/lanes_from_tile.py Saved/CityPCG/Tile_p03_p00.glb 3000 0 0 --box 3220 230 3500 500 \
      --out Tools/Crowd/graylondon_lanes.json
Uses Codex's GLB reader (Tools/CityPCG/extract_tile_frontages.py) and its verified axis convention.
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'CityPCG'))
import extract_tile_frontages as tile  # noqa: E402

GROUND_Z_CM = 10.0
LANE_LIFT_CM = 3.0


def raster(vertices, indices, x0, y0, nx, ny, cell):
    """Cells whose centre lies in any triangle (2D, x/y in metres)."""
    out = np.zeros((nx, ny), dtype=bool)
    v = np.asarray(vertices, dtype=np.float64)[:, :2]
    tris = v[np.asarray(indices, dtype=np.int64).reshape(-1, 3)]
    for a, b, c in tris:
        lo = np.floor((np.minimum(np.minimum(a, b), c) - (x0, y0)) / cell).astype(int)
        hi = np.ceil((np.maximum(np.maximum(a, b), c) - (x0, y0)) / cell).astype(int)
        i0, j0 = max(lo[0], 0), max(lo[1], 0)
        i1, j1 = min(hi[0], nx - 1), min(hi[1], ny - 1)
        if i0 > i1 or j0 > j1:
            continue
        ii, jj = np.meshgrid(np.arange(i0, i1 + 1), np.arange(j0, j1 + 1), indexing='ij')
        px = x0 + (ii + 0.5) * cell
        py = y0 + (jj + 0.5) * cell
        d = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
        if abs(d) < 1e-12:
            continue
        l1 = ((b[1] - c[1]) * (px - c[0]) + (c[0] - b[0]) * (py - c[1])) / d
        l2 = ((c[1] - a[1]) * (px - c[0]) + (a[0] - c[0]) * (py - c[1])) / d
        inside = (l1 >= 0) & (l2 >= 0) & (l1 + l2 <= 1)
        out[ii[inside], jj[inside]] = True
    return out


def dilate(mask):
    out = mask.copy()
    out[1:, :] |= mask[:-1, :]
    out[:-1, :] |= mask[1:, :]
    out[:, 1:] |= mask[:, :-1]
    out[:, :-1] |= mask[:, 1:]
    out[1:, 1:] |= mask[:-1, :-1]
    out[:-1, :-1] |= mask[1:, 1:]
    out[1:, :-1] |= mask[:-1, 1:]
    out[:-1, 1:] |= mask[1:, :-1]
    return out


def distance_levels(mask, steps):
    """Chessboard distance (cells) from mask, up to steps; larger = steps + 1."""
    dist = np.full(mask.shape, steps + 1, dtype=np.int32)
    cur = mask.copy()
    dist[cur] = 0
    for k in range(1, steps + 1):
        nxt = dilate(cur)
        dist[nxt & ~cur] = k
        cur = nxt
    return dist


def thin(img):
    """Zhang-Suen thinning, vectorised."""
    a = np.pad(img.astype(np.uint8), 1)
    while True:
        changed = False
        for step in (0, 1):
            p2, p3, p4 = a[:-2, 1:-1], a[:-2, 2:], a[1:-1, 2:]
            p5, p6, p7 = a[2:, 2:], a[2:, 1:-1], a[2:, :-2]
            p8, p9 = a[1:-1, :-2], a[:-2, :-2]
            seq = [p2, p3, p4, p5, p6, p7, p8, p9, p2]
            b = p2 + p3 + p4 + p5 + p6 + p7 + p8 + p9
            t = sum(((seq[k] == 0) & (seq[k + 1] == 1)).astype(np.uint8) for k in range(8))
            c = a[1:-1, 1:-1] == 1
            if step == 0:
                kill = c & (b >= 2) & (b <= 6) & (t == 1) & (p2 * p4 * p6 == 0) & (p4 * p6 * p8 == 0)
            else:
                kill = c & (b >= 2) & (b <= 6) & (t == 1) & (p2 * p4 * p8 == 0) & (p2 * p6 * p8 == 0)
            if kill.any():
                a[1:-1, 1:-1][kill] = 0
                changed = True
        if not changed:
            return a[1:-1, 1:-1].astype(bool)


def components(mask):
    """Label 8-connected components (small grids; iterative flood fill)."""
    labels = np.zeros(mask.shape, dtype=np.int32)
    n = 0
    for i, j in zip(*np.nonzero(mask)):
        if labels[i, j]:
            continue
        n += 1
        stack = [(i, j)]
        labels[i, j] = n
        while stack:
            ci, cj = stack.pop()
            for di in (-1, 0, 1):
                for dj in (-1, 0, 1):
                    a, b = ci + di, cj + dj
                    if 0 <= a < mask.shape[0] and 0 <= b < mask.shape[1] and mask[a, b] and not labels[a, b]:
                        labels[a, b] = n
                        stack.append((a, b))
    return labels, n


def polylines(sk):
    on = set(zip(*[x.tolist() for x in np.nonzero(sk)]))

    def neigh(p):
        i, j = p
        return [(i + di, j + dj) for di in (-1, 0, 1) for dj in (-1, 0, 1) if (di or dj) and (i + di, j + dj) in on]

    nodes = {p for p in on if len(neigh(p)) != 2}
    used, lines = set(), []
    for n in nodes:
        for m in neigh(n):
            if (n, m) in used:
                continue
            line, prev, cur = [n], n, m
            used.add((n, m))
            while True:
                line.append(cur)
                if cur in nodes:
                    used.add((cur, prev))
                    break
                nxt = [q for q in neigh(cur) if q != prev and q not in line[-3:]]
                if not nxt:
                    break
                prev, cur = cur, nxt[0]
                used.add((prev, cur))
            lines.append(line)
    seen = {p for line in lines for p in line}
    for p in sorted(on - seen):
        if p in seen:
            continue
        ring, prev, cur = [p], None, p
        seen.add(p)
        while True:
            nxt = [q for q in neigh(cur) if q != prev and q not in seen]
            if not nxt:
                break
            prev, cur = cur, nxt[0]
            ring.append(cur)
            seen.add(cur)
        if len(ring) > 3 and ring[0] in neigh(ring[-1]):
            ring.append(ring[0])
        lines.append(ring)
    return lines


def join(lines, gap):
    """Join polylines whose ends lie within gap cells (pieces the band broke apart), longest first."""
    lines = [list(line) for line in lines]
    merged = True
    while merged:
        merged = False
        lines.sort(key=len, reverse=True)
        for a in range(len(lines)):
            for b in range(a + 1, len(lines)):
                la, lb = lines[a], lines[b]
                if la[0] == la[-1] or lb[0] == lb[-1]:
                    continue  # rings stay rings
                options = [(la[-1], lb[0], la + lb), (la[-1], lb[-1], la + lb[::-1]),
                           (la[0], lb[-1], lb + la), (la[0], lb[0], lb[::-1] + la)]
                for p, q, joined in options:
                    if max(abs(p[0] - q[0]), abs(p[1] - q[1])) <= gap:
                        lines[a] = joined
                        del lines[b]
                        merged = True
                        break
                if merged:
                    break
            if merged:
                break
    return lines


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('glb', type=Path)
    ap.add_argument('origin', type=float, nargs=3, help='tile origin in metres (from <tile>.asset.json origin_m)')
    ap.add_argument('--road-primitive', type=int, default=2)
    ap.add_argument('--roof-primitive', type=int, default=1)
    ap.add_argument('--box', type=float, nargs=4, required=True, help='east0 north0 east1 north1 (metres)')
    ap.add_argument('--cell', type=float, default=1.0)
    ap.add_argument('--near', type=int, default=1, help='band starts this many cells from the road edge')
    ap.add_argument('--far', type=int, default=3, help='band ends this many cells from the road edge')
    ap.add_argument('--clear', type=int, default=1, help='cells kept clear of building footprints')
    ap.add_argument('--step', type=int, default=6, help='point spacing in cells (<= 10 m)')
    ap.add_argument('--min-cells', type=int, default=8)
    ap.add_argument('--join-gap', type=int, default=3, help='join pieces whose ends are this close (cells)')
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()

    data, blob = tile.read_glb(args.glb)
    e0, n0, e1, n1 = args.box
    cell = args.cell
    nx, ny = int((e1 - e0) / cell), int((n1 - n0) / cell)
    rv, _, ri = tile.primitive_mesh(data, blob, args.road_primitive, tuple(args.origin))
    fv, _, fi = tile.primitive_mesh(data, blob, args.roof_primitive, tuple(args.origin))
    road = raster(rv, ri, e0, n0, nx, ny, cell)
    roof = raster(fv, fi, e0, n0, nx, ny, cell)
    for _ in range(args.clear):
        roof = dilate(roof)
    dist = distance_levels(road, args.far)
    band = (dist >= args.near) & (dist <= args.far) & ~road & ~roof
    labels, n = components(band)
    sizes = np.bincount(labels.ravel())
    small = np.isin(labels, np.nonzero(sizes < 15)[0]) & band
    band &= ~small
    sk = thin(band)
    lanes = []
    for line in join(polylines(sk), args.join_gap):
        if len(line) < args.min_cells:
            continue
        picks = line[::args.step]
        if picks[-1] != line[-1]:
            picks.append(line[-1])
        pts = [[round((e0 + (i + 0.5) * cell) * 100.0, 1), round((n0 + (j + 0.5) * cell) * 100.0, 1),
                GROUND_Z_CM + LANE_LIFT_CM] for i, j in picks]
        if len(pts) >= 2:
            lanes.append(pts)
    out = {
        'source': {'glb': str(args.glb).replace('\\', '/'), 'origin_m': args.origin, 'box_m': args.box, 'cell_m': cell,
                   'band_m': [args.near * cell, args.far * cell], 'clear_m': args.clear * cell},
        'stats': {'grid': [nx, ny], 'road_cells': int(road.sum()), 'roof_cells': int(roof.sum()),
                  'band_cells': int(band.sum()), 'skeleton_cells': int(sk.sum()), 'lanes': len(lanes),
                  'points': sum(len(p) for p in lanes),
                  'length_m': round(sum(float(np.hypot(*np.diff(np.array(p)[:, :2], axis=0).T).sum()) for p in lanes) / 100.0, 1)},
        'note': 'x/y/z in UE cm (x = east_m*100, y = north_m*100); z = city ground 10 cm + 3. Spawned by Tools/Crowd/crowd_lanes.py stage json.',
        'lanes': lanes,
    }
    args.out.write_text(json.dumps(out, indent=0))
    print(json.dumps(out['stats']))


if __name__ == '__main__':
    main()
