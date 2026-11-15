"""Fit Codex-generated garments onto one MetaHuman donor body. Fitting only: no remodelling.

Run headless from the project root (Blender 5.3):
    blender -b --factory-startup --python Tools/ClothingFit/fit_codex_garments.py -- <config.json>

Config (JSON):
{
  "id": "Gilt_CivilianWorker_M_FerryPilot",
  "body": "FerryPilot",            # Intermediate/ClothingFit2026_11_14/Bodies/<body>_Body.fbx (+ _Face.fbx for the neck)
  "front": "-Y",                   # garment front axis after FBX import (MetaHuman faces -Y in Blender)
  "pieces": [                      # inner layer first; each later piece is fitted over the earlier ones
    {"name": "SK_GiltWorker_M_Feet",  "fbx": "...", "kind": "feet"},
    {"name": "SK_GiltWorker_M_Lower", "fbx": "...", "kind": "lower"},
    {"name": "SK_GiltWorker_M_Upper", "fbx": "...", "kind": "upper"}
  ],
  "out_dir": "Intermediate/ClothingFit2026_11_14/Out/<id>"
}
kind: upper | lower | skirt | feet

What it does per piece, in this order:
1. Align to the body's bind pose. Per-axis scale and offset by trimmed ICP against the body (scale clamped to
   0.85..1.15), then for sleeves a rotation about the shoulder joint so the sleeve axis matches the body's arm.
2. Trim caps. Image-to-3D shells are closed at the neck, cuffs, waist and ankles. Faces buried inside the body
   (every corner more than TRIM_CM inside) are those caps, and are removed. Skirts also lose their flat bottom cap.
3. Conform. Each vertex wants to sit OFFSET above the body (or the layers fitted before it). The per-vertex
   correction is low-pass filtered over the mesh before it is applied, so the garment's own detail (seams,
   lapels, buttons, pockets, piping, the waistcoat edge over the shirt) rides on top unchanged. A short clean-up
   pass then pushes out anything still inside.
4. Skin weights. Transferred from the body (nearest face, interpolated), smoothed, limited to 8 bones, normalised.
   Hems that hang below the pelvis (shirt tails, skirts) are blended toward the pelvis so they don't split.
5. Pose checks. walk, run, cast, crouch and arms-up poses on the body's own armature; counts garment vertices
   that end up inside the deformed body. Results go to <out_dir>/<id>_report.json.
6. Export each piece as a skeletal mesh FBX on the body's armature (same settings as the hero coat that already
   imports onto metahuman_base_skel), plus a .blend of the whole fit and a front/side/back preview render.
"""

import json
import math
import os
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Matrix, Vector, kdtree
from mathutils.bvhtree import BVHTree

PROJECT = Path(__file__).resolve().parents[2]
BODIES = PROJECT / 'Intermediate/ClothingFit2026_11_14/Bodies'

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
CFG = json.loads(Path(argv[0]).read_text())
OUT = PROJECT / CFG.get('out_dir', 'Intermediate/ClothingFit2026_11_14/Out/' + CFG['id'])
OUT.mkdir(parents=True, exist_ok=True)

# Tight: the user wants garments formed to the body with no air gap (2026-11-14 18:50). Skin that a garment covers
# is removed from a per-outfit body copy (hide_body), so these small offsets don't need to hide skin in motion.
OFFSET = {'upper': 0.003, 'coat': 0.003, 'lower': 0.003, 'skirt': 0.004, 'feet': 0.003, 'gloves': 0.002,
          'helmet': 0.004}   # metres above the target surface
LAYER_GAP = 0.003          # extra gap over a garment fitted earlier
MIN_CLEAR = 0.0015         # nothing ends up closer than this to the body
PROTECT = ('hand', 'thumb', 'index', 'middle', 'ring', 'pinky', 'neck', 'head')   # never hidden: hands, neck, face
if any(pc['kind'] == 'gloves' for pc in CFG['pieces']):
    PROTECT = ('neck', 'head')      # gloved hands are hidden like any other covered skin
COVER_REACH = 0.06         # skin counts as covered if a garment sheet is within this along its normal...
HIDE_MARGIN_RINGS = 1      # ...and so is every neighbour this many edge rings out (~3.5 cm of skin kept at edges)
TRIM_CM = 1.5              # caps: faces whose corners are all deeper than this inside the body
REACH = 0.12               # vertices further than this from the body are left where alignment put them
SMOOTH_ITERS = int(os.environ.get('FIT_SMOOTH_ITERS', 10))   # on the skin (edges ~3.5 cm): ~8 cm low-pass
REPORT = {'id': CFG['id'], 'body': CFG['body'], 'pieces': {}}


# ------------------------------------------------------------------ helpers
def select_only(*objs):
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]


def import_fbx(path):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=str(path))
    return [o for o in bpy.data.objects if o not in before]


def world_bvh(objs):
    """BVH of evaluated meshes in world space, plus per-vertex positions and face normals."""
    dg = bpy.context.evaluated_depsgraph_get()
    verts, polys = [], []
    for o in objs:
        ev = o.evaluated_get(dg)
        me = ev.to_mesh()
        base = len(verts)
        mw = o.matrix_world
        verts += [mw @ v.co for v in me.vertices]
        polys += [[base + i for i in p.vertices] for p in me.polygons]
        ev.to_mesh_clear()
    return BVHTree.FromPolygons(verts, polys, all_triangles=False), verts


def signed(bvh, p, reach=1.0):
    hit = bvh.find_nearest(p, reach)
    if hit[0] is None:
        return None, None, None
    loc, nrm = hit[0], hit[1]
    return loc, nrm, (p - loc).dot(nrm)


def mesh_neighbours(me):
    nb = [[] for _ in me.vertices]
    for e in me.edges:
        a, b = e.vertices
        nb[a].append(b)
        nb[b].append(a)
    return nb


def lowpass(field, nb, iters, keep=None):
    """Laplacian smoothing of a per-vertex vector field over mesh topology."""
    f = [v.copy() for v in field]
    for _ in range(iters):
        g = []
        for i, n in enumerate(nb):
            if not n:
                g.append(f[i])
                continue
            acc = Vector()
            for j in n:
                acc += f[j]
            g.append(f[i] * 0.5 + acc * (0.5 / len(n)))
        f = g
        if keep is not None:
            f = [keep(i, v) for i, v in enumerate(f)]
    return f


def islands(me):
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.verts.ensure_lookup_table()
    label = [-1] * len(bm.verts)
    sizes = []
    for v in bm.verts:
        if label[v.index] >= 0:
            continue
        k = len(sizes)
        stack, n = [v], 0
        label[v.index] = k
        while stack:
            x = stack.pop()
            n += 1
            for e in x.link_edges:
                y = e.other_vert(x)
                if label[y.index] < 0:
                    label[y.index] = k
                    stack.append(y)
        sizes.append(n)
    bm.free()
    return label, sizes


def rel(path):
    try:
        return Path(path).relative_to(PROJECT).as_posix()
    except ValueError:
        return Path(path).as_posix()


def smoothstep(a, b, x):
    t = max(0.0, min(1.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


# ------------------------------------------------------------------ body
def load_body(key):
    objs = import_fbx(BODIES / f'{key}_Body.fbx')
    rig = next(o for o in objs if o.type == 'ARMATURE')
    body = next(o for o in objs if o.type == 'MESH')
    body.name = 'Body_' + key
    rig.name = 'Rig_' + key
    face = None
    fpath = BODIES / f'{key}_Face.fbx'
    if fpath.exists():
        fobjs = import_fbx(fpath)
        face = next((o for o in fobjs if o.type == 'MESH'), None)
        if face:
            face.name = 'Face_' + key
        # The face comes with its own copy of the skeleton; only its rest-pose mesh is used, as the neck target.
        for o in fobjs:
            if o.type == 'ARMATURE':
                o.hide_render = True
    return rig, body, face


bpy.ops.wm.read_factory_settings(use_empty=True)
RIG, BODY, FACE = load_body(CFG['body'])
bones = RIG.data.bones
J = {b.name: RIG.matrix_world @ b.head_local for b in bones}
BODY_TOP = max((BODY.matrix_world @ v.co).z for v in BODY.data.vertices)
# Dominant bone per body vertex, for sleeve classification and pose-check reporting.
gname = {g.index: g.name for g in BODY.vertex_groups}
BODY_DOM = []
for v in BODY.data.vertices:
    best = max(v.groups, key=lambda g: g.weight, default=None)
    BODY_DOM.append(gname[best.group] if best else '')
BODY_KD = kdtree.KDTree(len(BODY.data.vertices))
for i, v in enumerate(BODY.data.vertices):
    BODY_KD.insert(BODY.matrix_world @ v.co, i)
BODY_KD.balance()


def side_of(bone):
    if bone.endswith('_l') or '_l_' in bone:
        return 'l'
    if bone.endswith('_r') or '_r_' in bone:
        return 'r'
    return ''


def is_arm(bone):
    return any(k in bone for k in ('upperarm', 'lowerarm', 'hand', 'thumb', 'index', 'middle', 'ring', 'pinky'))


# ------------------------------------------------------------------ garment import
def load_piece(piece):
    objs = import_fbx(PROJECT / piece['fbx'] if not os.path.isabs(piece['fbx']) else piece['fbx'])
    meshes = [o for o in objs if o.type == 'MESH']
    mws = {o: o.matrix_world.copy() for o in meshes}
    for o in meshes:
        o.modifiers.clear()
        o.parent = None
        o.matrix_world = mws[o]
    for o in objs:
        if o.type != 'MESH':
            bpy.data.objects.remove(o, do_unlink=True)
    select_only(*meshes)
    if len(meshes) > 1:
        bpy.ops.object.join()
    g = bpy.context.view_layer.objects.active
    g.name = piece['name']
    g.data.name = piece['name']
    for vg in list(g.vertex_groups):
        g.vertex_groups.remove(vg)
    select_only(g)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    front = CFG.get('front', '-Y')
    turn = {'-Y': 0, '+Y': 180, '+X': -90, '-X': 90}[front]
    if turn:
        g.data.transform(Matrix.Rotation(math.radians(turn), 4, 'Z'))
    return g


# ------------------------------------------------------------------ 1. align
def coarse_fit(g, kind, rep):
    """Uniform scale and height before the fine ICP: Codex's first delivery came 1.45x life size and 55 cm too high,
    beyond the fine fit's +-15 %. Searches scale 0.5..1.6 and height, centred in X and on the torso in Y, for the
    lowest trimmed skin-distance error; a garment sunk into the body costs three times as much as one standing off."""
    me = g.data
    pts = [v.co.copy() for v in me.vertices]
    sample = pts[::max(1, len(pts) // 600)]
    bvh = world_bvh([BODY] + ([FACE] if FACE else []))[0]
    zs = [p.z for p in pts]
    cx = (min(p.x for p in pts) + max(p.x for p in pts)) / 2
    cy = (min(p.y for p in pts) + max(p.y for p in pts)) / 2
    top = max(zs)
    if kind == 'feet':
        mw = BODY.matrix_world
        foot = [mw @ v.co for k, v in enumerate(BODY.data.vertices)
                if side_of(BODY_DOM[k]) == 'l' and any(t in BODY_DOM[k] for t in ('foot', 'ball', 'toe'))]
        z0 = min(zs)
        xe = max(p.x for p in pts) - min(p.x for p in pts)
        ye = max(p.y for p in pts) - min(p.y for p in pts)
        if xe < 0.6 * ye:     # a pair side by side is about as wide as long; one boot is well under 0.6 of its length
            # One boot delivered: mirror it into a pair (right boot = the left mirrored in X), 12 cm either side.
            bx = (max(p.x for p in pts) + min(p.x for p in pts)) / 2
            bm = bmesh.new()
            bm.from_mesh(me)
            for v in bm.verts:
                v.co.x += 0.12 - bx
            dup = bmesh.ops.duplicate(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:])
            dverts = [e for e in dup['geom'] if isinstance(e, bmesh.types.BMVert)]
            for v in dverts:
                v.co.x = -v.co.x
            dfaces = [e for e in dup['geom'] if isinstance(e, bmesh.types.BMFace)]
            bmesh.ops.reverse_faces(bm, faces=dfaces)
            bm.to_mesh(me)
            bm.free()
            me.update()
            pts = [v.co.copy() for v in me.vertices]
            zs = [p.z for p in pts]
            rep['mirrored_single_boot'] = True
        boot = [p for p in pts if p.x > 0 and p.z < z0 + 0.07]      # the foot part, below the ankle
        if len(foot) < 10 or len(boot) < 10:
            return
        foot_len = max(p.y for p in foot) - min(p.y for p in foot)
        boot_len = max(p.y for p in boot) - min(p.y for p in boot)
        sc = 1.12 * foot_len / boot_len
        if abs(sc - 1.0) < 0.06:
            rep['coarse'] = {'scale': 1.0, 'note': 'boot already within 6 % of 1.12 x foot length'}
            return
        z0 = min(zs)
        for v in me.vertices:
            v.co = Vector((v.co.x * sc, v.co.y * sc, z0 + (v.co.z - z0) * sc))
        me.update()
        rep['coarse'] = {'scale': round(sc, 3), 'foot_len_cm': round(foot_len * 100, 1), 'boot_len_cm': round(boot_len * 100, 1)}
        return
    if kind == 'skirt':
        # A skirt stands off the legs below the hips, so skin distance would shrink it: size it waist to ankle.
        anchor = J['pelvis'].z + 0.10
        sc = (anchor - 0.10) / max(1e-3, top - min(zs))
        for v in me.vertices:
            p = v.co
            v.co = Vector(((p.x - cx) * sc, (p.y - cy) * sc + J['pelvis'].y, anchor + (p.z - top) * sc))
        me.update()
        rep['coarse'] = {'scale': round(sc, 3), 'top_z_cm': round(anchor * 100, 1), 'by': 'height waist..ankle'}
        return
    if kind in ('upper', 'coat'):
        anchor, body_y = BODY_TOP + 0.04, J['spine_05'].y
    elif kind == 'lower':
        anchor, body_y = J['pelvis'].z + 0.10, J['pelvis'].y
    else:
        return
    off = OFFSET[kind]
    best = None
    for k in range(56):
        sc = 0.5 + 0.02 * k
        for j in range(26):
            dz = -0.25 + 0.02 * j
            err = []
            for p in sample:
                q = Vector(((p.x - cx) * sc, (p.y - cy) * sc + body_y, anchor + dz + (p.z - top) * sc))
                loc, nrm, fi, dist = bvh.find_nearest(q, 1.0)
                if loc is None:
                    err.append(1.0)
                    continue
                d = (q - loc).dot(nrm)
                err.append(abs(d - off) * (3.0 if d < 0 else 1.0))
            err.sort()
            n = int(len(err) * 0.8)
            e = sum(err[:n]) / n
            if best is None or e < best[0]:
                best = (e, sc, dz)
    e, sc, dz = best
    for v in me.vertices:
        p = v.co
        v.co = Vector(((p.x - cx) * sc, (p.y - cy) * sc + body_y, anchor + dz + (p.z - top) * sc))
    me.update()
    rep['coarse'] = {'scale': round(sc, 3), 'top_z_cm': round((anchor + dz) * 100, 1), 'err_cm': round(e * 100, 2)}


def icp_align(g, target_bvh, kind, rep):
    me = g.data
    pts = [v.co.copy() for v in me.vertices]
    step = max(1, len(pts) // 2500)
    sample = list(range(0, len(pts), step))
    off = OFFSET[kind]
    S = Vector((1, 1, 1))
    T = Vector((0, 0, 0))
    centre = Vector((0, 0, 0))
    for i in sample:
        centre += pts[i]
    centre /= len(sample)
    hist = []
    for it in range(25):
        pairs = []
        for i in sample:
            p = Vector([(pts[i][a] - centre[a]) * S[a] + centre[a] + T[a] for a in range(3)])
            loc, nrm, d = signed(target_bvh, p)
            if loc is None:
                continue
            if kind in ('upper', 'coat'):
                bi = BODY_KD.find(loc)[1]
                if is_arm(BODY_DOM[bi]):
                    continue   # sleeves are posed separately
            if kind in ('skirt', 'coat') and p.z < J['thigh_l'].z - 0.10:
                continue       # below the crotch a skirt or coat stands off the legs by design
            q = loc + nrm * off
            pairs.append((abs(d - off), i, q))
        pairs.sort(key=lambda x: x[0])
        pairs = pairs[: int(len(pairs) * 0.8)]   # trimmed: ignore the worst 20 %
        hist.append(round(sum(x[0] for x in pairs) / len(pairs) * 100, 2))
        for a in range(3):
            xs = [pts[i][a] - centre[a] for _, i, _ in pairs]
            ys = [q[a] - centre[a] for _, _, q in pairs]
            n = len(xs)
            mx, my = sum(xs) / n, sum(ys) / n
            vxx = sum((x - mx) ** 2 for x in xs)
            vxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
            s = vxy / vxx if vxx > 1e-9 else 1.0
            s = max(0.85, min(1.15, s))
            if kind == 'feet':
                s = 1.0     # boot soles and toe boxes sit well off the skin: fitting scale to them shrinks the boot
                if a in (0, 2):
                    # Height: a thick sole would pull the boot down into the floor. Sideways: the pair must stay
                    # centred, or the left/right split cuts a boot in two (each boot is centred on its foot later).
                    T[a] = 0.0
                    S[a] = 1.0
                    continue
            S[a] = s
            T[a] = my - s * mx
    for v in me.vertices:
        v.co = Vector([(v.co[a] - centre[a]) * S[a] + centre[a] + T[a] for a in range(3)])
    me.update()
    rep['align_scale'] = [round(x, 4) for x in S]
    rep['align_offset_cm'] = [round(x * 100, 2) for x in T]
    rep['align_mean_err_cm'] = hist[::4] + [hist[-1]]


def align_feet(g, rep):
    """Boots: scale each boot about its heel (length, then width) to the smallest size that holds the foot.
    Toe boxes and soles stand off the skin by design, so skin-distance fitting is the wrong measure for them."""
    me = g.data
    mw = BODY.matrix_world
    rot = mw.to_3x3().normalized()
    out = {}
    pair_cx = (max(v.co.x for v in me.vertices) + min(v.co.x for v in me.vertices)) / 2
    for s, sx in (('l', 1), ('r', -1)):
        idx = [v.index for v in me.vertices if (v.co.x - pair_cx) * sx > 0]
        if len(idx) < 50:
            continue
        top = max(me.vertices[i].co.z for i in idx)
        skin = [(mw @ v.co, (rot @ v.normal).normalized()) for k, v in enumerate(BODY.data.vertices)
                if side_of(BODY_DOM[k]) == s and any(t in BODY_DOM[k] for t in ('foot', 'ball', 'toe'))
                and (mw @ v.co).z < top - 0.015]
        if skin:
            fx = (min(p.x for p, n in skin) + max(p.x for p, n in skin)) / 2
            bx = (min(me.vertices[i].co.x for i in idx) + max(me.vertices[i].co.x for i in idx)) / 2
            zlow = min(me.vertices[i].co.z for i in idx) + 0.07
            low = [i for i in idx if me.vertices[i].co.z < zlow] or idx
            dy = (max(p.y for p, n in skin) + 0.012) - max(me.vertices[i].co.y for i in low)
            for i in idx:
                me.vertices[i].co.x += fx - bx
                me.vertices[i].co.y += dy
        if len(skin) < 10:
            continue
        # 1) Height. The MetaHuman foot stands at z = 0. Whether a delivered boot's outsole or its insole is at
        #    z = 0 depends on how it was modelled, so the drop is set per delivery in the config after looking at it
        #    ("boot_drop_cm"); a ray measure of the insole is unreliable under a toe box.
        drop = CFG.get('boot_drop_cm', 'auto' if not CFG.get('hide_body', True) else 0.0)
        insole = None
        if drop == 'auto':
            # Under the heel a vertical ray meets only the sole stack (outsole, heel block, insole): the highest
            # boot surface there below 6 cm is the insole. The toe box would confuse this test, the heel doesn't.
            heel_pts = [p for p, n in skin if n.z < -0.6]
            if heel_pts:
                ymax = max(p.y for p in heel_pts)
                heel_pts = [p for p in heel_pts if p.y > ymax - 0.05]
                cx = sum(p.x for p in heel_pts) / len(heel_pts)
                cy = sum(p.y for p in heel_pts) / len(heel_pts)
                skin_z = min(p.z for p in heel_pts)
                bvh0 = BVHTree.FromPolygons([v.co for v in me.vertices], [list(p.vertices) for p in me.polygons],
                                            all_triangles=False)
                o, hits = Vector((cx, cy, -0.3)), []
                for _ in range(12):
                    hit = bvh0.ray_cast(o, Vector((0, 0, 1)), 0.5)
                    if hit[0] is None or hit[0].z > 0.06:
                        break
                    hits.append(hit[0].z)
                    o = hit[0] + Vector((0, 0, 1e-4))
                if hits:
                    insole = max(hits)
                    drop = max(0.0, (insole - skin_z + 0.003) * 100)
            if drop == 'auto':
                drop = 0.0
        dz = -float(drop) / 100.0
        for i in idx:
            me.vertices[i].co.z += dz
        # Sole-of-foot points can't be fixed by length/width, so they are not part of the size test.
        skin = [(p, n) for p, n in skin if n.z > -0.6 and p.z < top + dz - 0.015]
        if len(skin) < 10:
            continue
        orig = {i: me.vertices[i].co.copy() for i in idx}
        zb = min(c.z for c in orig.values())
        heel = Vector((sum(c.x for c in orig.values()) / len(orig),
                       max(c.y for c in orig.values() if c.z < zb + 0.07), zb))

        def poking(syy, sxx):
            pts = {i: Vector((heel.x + (c.x - heel.x) * sxx, heel.y + (c.y - heel.y) * syy, c.z)) for i, c in orig.items()}
            loc = {i: k for k, i in enumerate(pts)}
            polys = [[loc[j] for j in p.vertices] for p in me.polygons if all(j in loc for j in p.vertices)]
            bvh = BVHTree.FromPolygons(list(pts.values()), polys, all_triangles=False)
            return sum(1 for p, n in skin if bvh.ray_cast(p + n * 0.001, n, 0.08)[0] is None) / len(skin), pts

        # Smallest change in length and width (about the heel) that holds the foot: <= 3 % of foot points whose
        # outward ray misses the boot. If nothing reaches that, the size with the fewest misses.
        grid = [0.94 + 0.02 * k for k in range(16)]     # 0.94 .. 1.24
        if CFG.get('hide_body', True):
            grid = [1.0]     # the foot inside is hidden: keep the delivered proportions (and both boots alike)
        tried = []
        for syy in grid[:11]:           # length 0.94 .. 1.14
            for sxx in grid:
                frac, _ = poking(syy, sxx)
                tried.append((frac, max(abs(syy - 1), abs(sxx - 1)), syy, sxx))
        # With body hiding on, skin inside a boot is removed, so a toe through the leather can't show: keep the
        # delivered proportions unless more than 15 % of the foot sticks out.
        limit = 0.15 if CFG.get('hide_body', True) else 0.03
        ok = [t for t in tried if t[0] <= limit]
        pick = min(ok, key=lambda t: (t[1], t[0])) if ok else min(tried, key=lambda t: (t[0], t[1]))
        best = (pick[2], pick[3])
        frac, pts = poking(*best)
        for i, c in pts.items():
            me.vertices[i].co = c
        out[s] = {'drop_cm': round(-dz * 100, 2), 'insole_z_cm': round(insole * 100, 2) if insole is not None else None,
                  'length_scale': round(best[0], 3), 'width_scale': round(best[1], 3), 'foot_points_out': round(frac * 100, 1)}
    me.update()
    rep['boot_fit'] = out


def align_helmet(g, rep):
    """Helmets are rigid, and Hunyuan delivers them as closed solids. Fit = the smallest uniform scale, and the lowest
    seat at that scale, at which the skull cap (face-mesh points 11 cm or more above the head joint) lies inside the
    helmet while the eyes stay outside it (the open face). Centred over the scalp. No conform: the metal keeps its
    shape. Inside/outside is the side of the nearest helmet face (Hunyuan normals point outward)."""
    if FACE is None:
        rep['helmet'] = 'no face mesh: left as delivered'
        return
    me = g.data
    fm = FACE.matrix_world
    hz = J['head'].z
    fpts = [fm @ v.co for v in FACE.data.vertices]
    scalp = [p for p in fpts if p.z > hz + 0.11]
    crown = max(p.z for p in fpts)
    band = [p for p in fpts if hz + 0.06 < p.z < hz + 0.10]
    if len(scalp) < 20 or not band:
        rep['helmet'] = 'too few head points'
        return
    yfront = min(p.y for p in band)
    eyes = [p for p in band if p.y < yfront + 0.02]
    temples = [p for p in fpts if hz + 0.12 < p.z < hz + 0.14]
    head_w = (max(p.x for p in temples) - min(p.x for p in temples)) if temples else 0.16
    orig = [v.co.copy() for v in me.vertices]
    polys = [list(p.vertices) for p in me.polygons]
    cx = (max(c.x for c in orig) + min(c.x for c in orig)) / 2
    cy = (max(c.y for c in orig) + min(c.y for c in orig)) / 2
    top = max(c.z for c in orig)
    helm_w = max(c.x for c in orig) - min(c.x for c in orig)
    sx = (max(p.x for p in scalp) + min(p.x for p in scalp)) / 2
    sy = (max(p.y for p in scalp) + min(p.y for p in scalp)) / 2
    guess = (head_w + 0.04) / helm_w if helm_w > 0 else 1.0

    def placed(sc, dz):
        return [Vector((sx + (c.x - cx) * sc, sy + (c.y - cy) * sc, crown + dz + (c.z - top) * sc)) for c in orig]

    def inside(bvh, pts):
        n = 0
        for q in pts:
            loc, nrm, fi, d = bvh.find_nearest(q, 1.0)
            if loc is not None and (q - loc).dot(nrm) < 0:
                n += 1
        return n / max(1, len(pts))

    best = None
    for k in range(14):
        sc = guess * (0.88 + 0.03 * k)
        low = None
        for step in range(45):
            dz = 0.06 - 0.004 * step            # helmet top from 6 cm above the crown to 12 cm below
            bvh = BVHTree.FromPolygons(placed(sc, dz), polys, all_triangles=False)
            if inside(bvh, scalp) >= 0.97 and inside(bvh, eyes) <= 0.05:
                low = dz
            elif low is not None:
                break
        if low is not None:
            best = (sc, low)
            break
    if best is None:
        best = (guess, float(CFG.get('helmet_top_over_crown_cm', 6.0)) / 100.0)   # brow clear of the eyes (checked in UE)
        rep['helmet_note'] = 'no scale/seat kept the skull in and the eyes out; placed by width guess'
    for v, c in zip(me.vertices, placed(*best)):
        v.co = c
    me.update()
    # Open the face. Image-to-3D closes a helmet's face opening and only paints it dark; like the neck and cuff caps,
    # that cap is trimmed: forward-facing helmet faces lying in front of the eyes, nose and mouth (within 4 cm).
    face_front = [p for p in fpts if hz - 0.04 < p.z < hz + 0.095 and p.y < yfront + 0.05 and abs(p.x) < 0.065]
    if face_front:
        kd = kdtree.KDTree(len(face_front))
        for i, q in enumerate(face_front):
            kd.insert(q, i)
        kd.balance()
        bm = bmesh.new()
        bm.from_mesh(me)
        cut = [f for f in bm.faces if f.normal.y < -0.3 and kd.find(f.calc_center_median())[2] < 0.04
               and f.calc_center_median().z < hz + 0.095]
        bmesh.ops.delete(bm, geom=cut, context='FACES')
        bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
        bm.to_mesh(me)
        bm.free()
        me.update()
        rep['helmet_face_opening_faces'] = len(cut)
        polys = [list(p.vertices) for p in me.polygons]
    bvh = BVHTree.FromPolygons([v.co.copy() for v in me.vertices], polys, all_triangles=False)
    rep['helmet'] = {'scale': round(best[0], 3), 'width_guess': round(guess, 3), 'top_over_crown_cm': round(best[1] * 100, 1),
                     'skull_inside_pct': round(inside(bvh, scalp) * 100, 1), 'eyes_inside_pct': round(inside(bvh, eyes) * 100, 1),
                     'z_cm': [round(min(v.co.z for v in me.vertices) * 100, 1), round(max(v.co.z for v in me.vertices) * 100, 1)]}


def contain_legs(g, rep):
    """A straight pencil skirt is narrower at the ankle than this body's stance, so the legs pass through it. Below the
    crotch, each height band of the skirt is scaled in X about its centre to the legs' width there + 2 cm (bands are
    smoothed so the hem line stays clean). Only ever widens."""
    me = g.data
    mw = BODY.matrix_world
    crotch = J['thigh_l'].z - 0.10
    legs = {}
    for i, v in enumerate(BODY.data.vertices):
        p = mw @ v.co
        if p.z < crotch and not is_arm(BODY_DOM[i]):
            k = int(p.z * 50)
            lo, hi = legs.get(k, (1e9, -1e9))
            legs[k] = (min(lo, p.x), max(hi, p.x))
    bands = {}
    for v in me.vertices:
        if v.co.z < crotch:
            k = int(v.co.z * 50)
            lo, hi = bands.get(k, (1e9, -1e9))
            bands[k] = (min(lo, v.co.x), max(hi, v.co.x))
    scale = {}
    for k, (lo, hi) in bands.items():
        need = None
        for dk in (0, -1, 1, -2, 2):
            if k + dk in legs:
                need = legs[k + dk]
                break
        if need is None or hi - lo < 1e-3:
            continue
        want = (need[1] - need[0]) + 0.04
        scale[k] = max(1.0, want / (hi - lo))
    if not scale:
        return
    ks = sorted(scale)
    smooth = {k: sum(scale.get(k + d, scale[k]) for d in range(-2, 3)) / 5.0 for k in ks}
    for v in me.vertices:
        if v.co.z < crotch:
            k = int(v.co.z * 50)
            sc = smooth.get(k)
            if sc and sc > 1.0:
                lo, hi = bands[k]
                cx = (lo + hi) / 2
                w = smoothstep(crotch, crotch - 0.08, v.co.z)     # blend in below the crotch
                v.co.x = cx + (v.co.x - cx) * (1.0 + (sc - 1.0) * w)
    me.update()
    rep['skirt_widened'] = {'max_scale': round(max(smooth.values()), 3), 'bands': len(smooth)}


def pca_axis(points):
    n = len(points)
    c = sum(points, Vector()) / n
    cov = [[0.0] * 3 for _ in range(3)]
    for p in points:
        d = p - c
        for a in range(3):
            for b in range(3):
                cov[a][b] += d[a] * d[b]
    m = Matrix(cov)
    v = Vector((1, 1, 1)).normalized()
    for _ in range(60):     # power iteration for the main axis
        v = (m @ v).normalized()
    return c, v


def align_sleeves(g, rep):
    """Re-pose the sleeves to the body's bind pose by skinning, not by hand-rotating vertices:
      1. pose the body's own upperarm and lowerarm bones so each matches the garment's sleeve (upper sleeve from the
         shoulder, then forearm sleeve from the posed elbow): the body now stands in the garment's arm pose;
      2. bind every garment vertex to that posed body (weights interpolated from the nearest posed body triangle, then
         smoothed over the garment);
      3. apply the inverse of that skinning, which brings the garment back to the bind pose with a smooth bend through
         elbow and shoulder (per-vertex rotations about guessed pivots tore and folded sleeves).
    Then the forearm part of each sleeve is hemmed so the cuff ends 1 cm past the wrist."""
    me = g.data
    out = {}
    mw = BODY.matrix_world
    # Sleeve vertices (geometric): outside the torso width at that height and within 20 cm of that arm.
    bins = {}
    for i, v in enumerate(BODY.data.vertices):
        if is_arm(BODY_DOM[i]):
            continue
        p = mw @ v.co
        k = int(p.z * 50)
        bins[k] = max(bins.get(k, 0.0), abs(p.x))
    top_k = int((min(J['upperarm_l'].z, J['upperarm_r'].z) - 0.06) * 50)

    def half_width(z):
        k = min(int(z * 50), top_k)
        for dk in range(6):
            for kk in (k - dk, k + dk):
                if kk in bins:
                    return bins[kk]
        return 0.18

    def seg_dist(p, a, b):
        ab = b - a
        t = max(0.0, min(1.0, (p - a).dot(ab) / max(ab.length_squared, 1e-9)))
        return (p - (a + ab * t)).length

    owner = []
    for v in me.vertices:
        o = ''
        if abs(v.co.x) > half_width(v.co.z) + 0.015:
            sd = 'l' if (v.co.x > 0) == (J['upperarm_l'].x > 0) else 'r'
            sh, el, hd = J['upperarm_' + sd], J['lowerarm_' + sd], J['hand_' + sd]
            if v.co.z < sh.z + 0.06 and min(seg_dist(v.co, sh, el), seg_dist(v.co, el, hd)) < 0.20:
                o = sd
        owner.append(o)

    # 1) Pose the body's arms into the garment's arm pose.
    select_only(RIG)
    bpy.ops.object.mode_set(mode='POSE')
    for pb in RIG.pose.bones:
        pb.matrix_basis = Matrix()
    bpy.context.view_layer.update()
    rw = RIG.matrix_world
    rwi = rw.inverted()

    def bone_head(name):
        return rw @ RIG.pose.bones[name].head

    def turn_bone(name, pivot, frm, to):
        pb = RIG.pose.bones[name]
        q = frm.rotation_difference(to)
        m_world = rw @ pb.matrix
        m_world = Matrix.Translation(pivot) @ q.to_matrix().to_4x4() @ Matrix.Translation(-pivot) @ m_world
        pb.matrix = rwi @ m_world
        bpy.context.view_layer.update()

    for sd in ('l', 'r'):
        mine = [me.vertices[i].co.copy() for i, o in enumerate(owner) if o == sd]
        if len(mine) < 40:
            continue
        sh = bone_head('upperarm_' + sd)
        el = bone_head('lowerarm_' + sd)
        ua_len = (el - sh).length
        upper = [c for c in mine if 0.08 < (c - sh).length < ua_len * 0.85]
        if len(upper) < 15:
            continue
        ag = (sum(upper, Vector()) / len(upper) - sh).normalized()
        out[sd + '_upper_deg'] = round(math.degrees((el - sh).normalized().angle(ag)), 1)
        turn_bone('upperarm_' + sd, sh, (el - sh).normalized(), ag)
        el2 = bone_head('lowerarm_' + sd)
        hd2 = bone_head('hand_' + sd)
        fore = [c for c in mine if (c - sh).dot(ag) > ua_len * 0.95]
        if len(fore) < 15:
            continue
        af = (sum(fore, Vector()) / len(fore) - el2).normalized()
        out[sd + '_fore_deg'] = round(math.degrees((hd2 - el2).normalized().angle(af)), 1)
        turn_bone('lowerarm_' + sd, el2, (hd2 - el2).normalized(), af)

    # 2) Bind the garment to the posed body: weights from the nearest posed body triangle, smoothed on the garment.
    dg = bpy.context.evaluated_depsgraph_get()
    ev = BODY.evaluated_get(dg)
    bme = ev.to_mesh()
    P = [mw @ v.co for v in bme.vertices]
    F = [list(f.vertices) for f in bme.polygons]
    ev.to_mesh_clear()
    bvh = BVHTree.FromPolygons(P, F, all_triangles=False)
    gname = {gg.index: gg.name for gg in BODY.vertex_groups}
    VW = [{gname[x.group]: x.weight for x in v.groups} for v in BODY.data.vertices]
    W = []
    for v in me.vertices:
        loc, nrm, fi, d = bvh.find_nearest(v.co, 2.0)
        poly = F[fi]
        ws = [1.0 / max((P[j] - loc).length, 1e-4) for j in poly]
        tot = sum(ws)
        acc = {}
        for j, w in zip(poly, ws):
            for b, x in VW[j].items():
                acc[b] = acc.get(b, 0.0) + x * w / tot
        W.append(acc)
    nb = mesh_neighbours(me)
    for _ in range(3):
        W = [{b: 0.5 * W[i].get(b, 0.0) + 0.5 * sum(W[j].get(b, 0.0) for j in n) / len(n)
              for b in set(W[i]).union(*[W[j] for j in n])} if n else W[i] for i, n in enumerate(nb)]

    # 3) Inverse skinning: posed -> rest for every vertex (bones that did not move contribute identity).
    M = {}
    for pb in RIG.pose.bones:
        rest = pb.bone.matrix_local
        M[pb.name] = rw @ rest @ pb.matrix.inverted() @ rwi
    moved = 0
    for i, v in enumerate(me.vertices):
        w = W[i]
        tot = sum(w.values())
        if tot <= 0:
            continue
        acc = Vector()
        for b, x in w.items():
            m = M.get(b)
            acc += (m @ v.co if m is not None else v.co) * (x / tot)
        if (acc - v.co).length > 1e-5:
            moved += 1
        v.co = acc
    me.update()
    for pb in RIG.pose.bones:
        pb.matrix_basis = Matrix()
    bpy.context.view_layer.update()
    bpy.ops.object.mode_set(mode='OBJECT')
    out['moved_verts'] = moved

    # 4) Hem: cuffs end 1 cm past the wrist.
    hem = {}
    for sd in ('l', 'r'):
        el, hd = J['lowerarm_' + sd], J['hand_' + sd]
        axis = (hd - el).normalized()
        wrist = (hd - el).length
        idx = [i for i, o in enumerate(owner) if o == sd and (me.vertices[i].co - el).dot(axis) > 0.0]
        if not idx:
            continue
        reach = max((me.vertices[i].co - el).dot(axis) for i in idx)
        if reach > wrist + 0.015:
            k = (wrist + 0.01) / reach
            for i in idx:
                v = me.vertices[i]
                t = (v.co - el).dot(axis)
                v.co = v.co - axis * (t * (1.0 - k))
            hem[sd] = {'cuff_past_wrist_cm': round((reach - wrist) * 100, 1), 'forearm_scale': round(k, 3)}
    me.update()
    rep['sleeve_angle_deg'] = out
    rep['sleeve_hem'] = hem


# ------------------------------------------------------------------ 2. trim caps
def trim_caps(g, kind, rep):
    bvh, _ = world_bvh([BODY] + ([FACE] if FACE else []))
    me = g.data
    depth = []
    for v in me.vertices:
        loc, nrm, d = signed(bvh, v.co, 0.5)
        depth.append(d if d is not None else 1.0)
    zmin = min(v.co.z for v in me.vertices)
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.faces.ensure_lookup_table()
    kill = []
    crotch = J['thigh_l'].z - 0.10
    for f in bm.faces:
        if kind == 'skirt' and f.calc_center_median().z < crotch:
            if abs(f.normal.z) > 0.9 and all(v.co.z < zmin + 0.03 for v in f.verts):
                kill.append(f)
            continue                # legs pass through a pencil skirt below the crotch; that is not a cap
        if all(depth[v.index] < -TRIM_CM / 100 for v in f.verts):
            # A cap runs ACROSS the limb or neck (its normal is roughly perpendicular to the skin's normal there).
            # Garment surface that only sank into a bigger body runs ALONG the skin; that is pushed out later, never cut.
            loc, nrm, d = signed(bvh, f.calc_center_median(), 0.5)
            if nrm is None or abs(f.normal.dot(nrm)) < 0.5:
                kill.append(f)
        elif kind == 'skirt' and abs(f.normal.z) > 0.9 and all(v.co.z < zmin + 0.03 for v in f.verts):
            kill.append(f)
    bmesh.ops.delete(bm, geom=kill, context='FACES')
    loose = [v for v in bm.verts if not v.link_faces]
    bmesh.ops.delete(bm, geom=loose, context='VERTS')
    bm.to_mesh(me)
    bm.free()
    me.update()
    rep['trimmed_faces'] = len(kill)


# ------------------------------------------------------------------ 3. conform
def skin_domain():
    """Body + face (the neck above the body's top edge) as one surface: positions, smooth normals, polygons and
    adjacency, with the body/face neck seam stitched so the correction field is continuous across it."""
    dg = bpy.context.evaluated_depsgraph_get()
    P, N, F = [], [], []
    owner = []
    for o in [BODY] + ([FACE] if FACE else []):
        ev = o.evaluated_get(dg)
        me = ev.to_mesh()
        base = len(P)
        mw = o.matrix_world
        rot = mw.to_3x3().normalized()
        for v in me.vertices:
            P.append(mw @ v.co)
            N.append((rot @ v.normal).normalized())
            owner.append(o.name)
        F += [[base + i for i in p.vertices] for p in me.polygons]
        ev.to_mesh_clear()
    nb = [set() for _ in P]
    for f in F:
        for a, b in zip(f, f[1:] + f[:1]):
            nb[a].add(b)
            nb[b].add(a)
    if FACE:
        kd = kdtree.KDTree(len(P))
        for i, p in enumerate(P):
            kd.insert(p, i)
        kd.balance()
        for i, p in enumerate(P):
            if owner[i] != BODY.name:
                continue
            for _, j, d in kd.find_range(p, 0.012):
                if owner[j] != BODY.name:
                    nb[i].add(j)
                    nb[j].add(i)
    return P, N, F, [list(s) for s in nb], BVHTree.FromPolygons(P, F, all_triangles=False)


def skin_depths(P, N, skin_bvh):
    """How far inside the skin a ray may start at each point: under half the local limb thickness, 1..8 cm."""
    out = []
    for p, n in zip(P, N):
        hit = skin_bvh.ray_cast(p - n * 1e-4, -n, 0.4)
        t = hit[3] if hit[0] is not None else 0.16
        out.append(max(0.01, min(0.08, 0.45 * t)))
    return out


def surface_heights(P, N, bvh, depths, reach=REACH):
    """Height of a surface's INNERMOST sheet above each skin point (ray from inside the skin outward)."""
    out = []
    for p, n, depth in zip(P, N, depths):
        hit = bvh.ray_cast(p - n * depth, n, depth + reach)
        out.append(None if hit[0] is None else hit[3] - depth)
    return out


def outer_heights(P, N, bvh, reach=0.08, skin_bvh=None):
    """Height of a surface's OUTERMOST sheet above each skin point (ray from outside inward), within 8 cm. A hit only
    counts if it belongs over this skin point (its nearest skin point is within 5 cm): between the legs, a ray from
    one calf starts inside the other leg's trousers or boot, and must not push this leg's garment across the gap."""
    out = []
    for p, n in zip(P, N):
        hit = bvh.ray_cast(p + n * reach, -n, reach + 0.02)
        if hit[0] is None:
            out.append(None)
            continue
        if skin_bvh is not None:
            near = skin_bvh.find_nearest(hit[0], 0.3)
            if near[0] is None or (near[0] - p).length > 0.05:
                out.append(None)
                continue
        out.append(reach - hit[3])
    return out


def smooth_field(val, nb, iters, keep_max=False):
    """Normalised smoothing over the skin: covered points carry values, uncovered ones only pass them along."""
    v = [x if x is not None else 0.0 for x in val]
    w = [1.0 if x is not None else 0.0 for x in val]
    for _ in range(iters):
        nv, nw = [], []
        for i, n in enumerate(nb):
            sv, sw = v[i] * w[i], w[i]
            for j in n:
                sv += 0.5 * v[j] * w[j]
                sw += 0.5 * w[j]
            k = 1.0 + 0.5 * len(n)
            nw.append(sw / k)
            nv.append(sv / sw if sw > 1e-9 else 0.0)
        v, w = nv, nw
    if keep_max:
        v = [max(a, b) if b is not None else a for a, b in zip(v, val)]
    return v, w


def conform(g, kind, layers, rep):
    """Move the garment by a smooth correction field defined on the skin, so every sheet of the garment above a
    skin point (inner face, outer face, buttons, piping, a waistcoat over a shirt) moves by the same amount there.
    Thickness and surface detail are kept; only the garment's low-frequency distance to the body changes."""
    me = g.data
    P, N, F, NB, skin_bvh = skin_domain()
    depths = skin_depths(P, N, skin_bvh)
    skip_pts = set()
    if kind == 'feet' and CFG.get('hide_body', True):
        # Feet inside boots are hidden: pushing the boot off them would only bow the sole into the floor.
        skip_pts = {i for i in range(min(len(P), len(BODY_DOM))) if any(t in BODY_DOM[i] for t in ('foot', 'ball', 'toe'))}
    layer_bvh = world_bvh(layers)[0] if layers else None
    lay_h = outer_heights(P, N, layer_bvh, skin_bvh=skin_bvh) if layer_bvh else [None] * len(P)
    off = OFFSET[kind]
    pelvis_z = J['pelvis'].z
    crotch_z = J['thigh_l'].z - 0.10

    def tight_at(p):
        if kind == 'feet':
            return 0.0      # boots keep their last (toe box, heel): only pushed out where the foot pokes through
        if kind in ('skirt', 'coat') and p.z < crotch_z:
            return 0.0      # a fitted ankle skirt hugs waist and hips, then falls straight: only push out below
        if kind == 'upper' and p.z < pelvis_z - 0.04:
            return 0.8      # tight brief: hems below the waist only keep a little of their flare
        return 1.0

    # Map every garment vertex to its skin point once per round (face index + barycentric-ish weights).
    def apply(field, fw):
        moved = 0
        for v in me.vertices:
            loc, nrm, fi, d = skin_bvh.find_nearest(v.co, REACH * 2)
            if loc is None:
                continue
            poly = F[fi]
            ws = [1.0 / max((P[j] - loc).length, 1e-4) for j in poly]
            s = sum(ws)
            c = sum(field[j] * w for j, w in zip(poly, ws)) / s
            cov = sum(fw[j] * w for j, w in zip(poly, ws)) / s
            n = sum((N[j] * w for j, w in zip(poly, ws)), Vector()).normalized()
            a = (1.0 - smoothstep(REACH * 0.6, REACH, abs(d))) * min(1.0, cov * 4)
            if a > 0 and abs(c) > 1e-5:
                v.co += n * (c * a)
                moved += 1
        me.update()
        return moved

    history = []
    for rnd in range(7):
        gbvh = BVHTree.FromPolygons([v.co for v in me.vertices], [p.vertices[:] for p in me.polygons],
                                    all_triangles=False)
        h = surface_heights(P, N, gbvh, depths)
        val = []
        worst, n_low, outliers = 1.0, 0, 0
        for i, p in enumerate(P):
            if h[i] is None or (i in skip_pts):
                val.append(None)
                continue
            floor = MIN_CLEAR if lay_h[i] is None else lay_h[i] + LAYER_GAP
            want = max(off, floor) if rnd == 0 else floor
            c = want - h[i]
            if c < 0:
                c = c * tight_at(p) if rnd == 0 else 0.0
            if c > 0.04:
                # More than 4 cm under the skin is not a garment sheet over this point (a ray that crossed a
                # limb, a sleeve seen from the armpit): ignore it rather than inflate the garment here.
                val.append(None)
                outliers += 1
                continue
            if h[i] < floor - 0.0005:
                n_low += 1
            worst = min(worst, h[i] - floor)
            val.append(c)
        covered = sum(1 for x in val if x is not None)
        history.append({'round': rnd, 'skin_pts_covered': covered, 'below_floor': n_low,
                        'worst_cm': round(worst * 100, 2), 'ignored_deep': outliers})
        if rnd > 0 and n_low == 0:
            break
        field, fw = smooth_field(val, NB, SMOOTH_ITERS if rnd == 0 else 2, keep_max=rnd > 0)
        history[-1]['moved'] = apply(field, fw)
    # Last resort, per vertex: anything still under the skin (deeper than a field round could see) is pushed out
    # along the skin normal, with half of that push shared by its direct neighbours so no spike forms.
    nbv = mesh_neighbours(me)
    last = []
    for rnd in range(0 if (kind == 'feet' and CFG.get('hide_body', True)) else 4):
        push = {}
        for v in me.vertices:
            loc, nrm, fi, d = skin_bvh.find_nearest(v.co, 0.2)
            if loc is not None and (v.co - loc).dot(nrm) < MIN_CLEAR * 0.5:
                push[v.index] = nrm * (MIN_CLEAR - (v.co - loc).dot(nrm))
        last.append(len(push))
        if not push:
            break
        share = {}
        for i, pv in push.items():
            for j in nbv[i]:
                if j not in push:
                    share.setdefault(j, []).append(pv * 0.5)
        for i, pv in push.items():
            me.vertices[i].co += pv
        for j, lst in share.items():
            me.vertices[j].co += sum(lst, Vector()) / len(lst)
        me.update()
    history.append({'per_vertex_push_rounds': last})
    if kind != 'feet':
        floor_fix = 0
        for v in me.vertices:
            if v.co.z < 0.003:
                v.co.z = 0.003
                floor_fix += 1
        me.update()
        history.append({'clamped_to_floor': floor_fix})
    # Report: garment vertex distance to the skin after the fit.
    ds = []
    for v in me.vertices:
        loc, nrm, fi, d = skin_bvh.find_nearest(v.co, 0.5)
        if loc is not None:
            ds.append((v.co - loc).dot(nrm))
    ds.sort()
    rep['conform'] = {
        'offset_cm': round(off * 100, 2), 'layer_gap_cm': round(LAYER_GAP * 100, 2) if layers else None,
        'smooth_iters': SMOOTH_ITERS, 'rounds': history,
        'vertex_dist_cm': {'min': round(ds[0] * 100, 2), 'p05': round(ds[len(ds) // 20] * 100, 2),
                           'median': round(ds[len(ds) // 2] * 100, 2), 'p95': round(ds[len(ds) * 19 // 20] * 100, 2)},
    }


# ------------------------------------------------------------------ 4. weights
def skin(g, kind, rep):
    g.parent = RIG
    g.matrix_parent_inverse = RIG.matrix_world.inverted()
    for vg in list(g.vertex_groups):
        g.vertex_groups.remove(vg)
    dt = g.modifiers.new('weights', 'DATA_TRANSFER')
    dt.object = BODY
    dt.use_object_transform = True
    dt.use_vert_data = True
    dt.data_types_verts = {'VGROUP_WEIGHTS'}
    dt.vert_mapping = 'POLYINTERP_NEAREST'
    dt.layers_vgroup_select_src = 'ALL'
    dt.layers_vgroup_select_dst = 'NAME'
    select_only(g)
    bpy.ops.object.datalayout_transfer(modifier='weights')
    bpy.ops.object.modifier_apply(modifier='weights')
    me = g.data
    names = [vg.name for vg in g.vertex_groups]
    W = [{names[x.group]: x.weight for x in v.groups if x.weight > 0} for v in me.vertices]
    pelvis_z = J['pelvis'].z
    if kind in ('skirt', 'upper', 'coat'):
        # Hanging hems: blend toward pelvis + both thighs so the hem moves as one piece instead of splitting.
        top = pelvis_z - (0.02 if kind == 'upper' else 0.10)
        for i, v in enumerate(me.vertices):
            if v.co.z >= top:
                continue
            k = smoothstep(top, top - 0.18, v.co.z) * (0.7 if kind == 'upper' else 0.85)
            side = smoothstep(-0.10, 0.10, v.co.x)     # thigh_l is on +X
            tgt = {'pelvis': 0.5, 'thigh_l': 0.5 * side, 'thigh_r': 0.5 * (1 - side)}
            W[i] = {n: (1 - k) * W[i].get(n, 0.0) + k * tgt.get(n, 0.0) for n in set(W[i]) | set(tgt)}
    # Smooth over the garment's own topology (2 passes, half strength), keep the 8 strongest, normalise.
    nb = mesh_neighbours(me)
    for _ in range(2):
        nxt = []
        for i, n in enumerate(nb):
            acc = dict(W[i])
            if n:
                avg = {}
                for j in n:
                    for b, w in W[j].items():
                        avg[b] = avg.get(b, 0.0) + w / len(n)
                acc = {b: 0.5 * W[i].get(b, 0.0) + 0.5 * avg.get(b, 0.0) for b in set(W[i]) | set(avg)}
            nxt.append(acc)
        W = nxt
    unweighted = 0
    for vg in list(g.vertex_groups):
        g.vertex_groups.remove(vg)
    groups = {}
    for i, w in enumerate(W):
        top8 = sorted(((b, x) for b, x in w.items() if x > 1e-3), key=lambda t: -t[1])[:8]
        s = sum(x for _, x in top8)
        if s <= 0:
            unweighted += 1
            continue
        for b, x in top8:
            if b not in groups:
                groups[b] = g.vertex_groups.new(name=b)
            groups[b].add([i], x / s, 'REPLACE')
    arm = g.modifiers.new('MetaHuman body pose', 'ARMATURE')
    arm.object = RIG
    rep['weights'] = {'groups': len(groups), 'unweighted_verts': unweighted}


# ------------------------------------------------------------------ 5. pose checks
def rotate_world(pb, axis, deg):
    """Rotate a pose bone about a world axis through its head (armature space == world up to scale)."""
    m = pb.matrix.copy()
    head = m.to_translation()
    r = Matrix.Rotation(math.radians(deg), 4, axis)
    pb.matrix = Matrix.Translation(head) @ r @ Matrix.Translation(-head) @ m
    bpy.context.view_layer.update()


# Front is -Y. Rotating a leg about +X by a positive angle swings the foot toward -Y (forward).
POSES = {
    'walk': [('thigh_l', 'X', 28), ('thigh_r', 'X', -18), ('calf_r', 'X', -35), ('calf_l', 'X', -10),
             ('upperarm_l', 'X', -18), ('upperarm_r', 'X', 18), ('lowerarm_r', 'X', 25)],
    'run': [('thigh_l', 'X', 50), ('calf_l', 'X', -70), ('thigh_r', 'X', -30), ('calf_r', 'X', -95),
            ('upperarm_l', 'X', -35), ('lowerarm_l', 'X', 60), ('upperarm_r', 'X', 40), ('lowerarm_r', 'X', 75),
            ('spine_03', 'X', 10)],
    'cast': [('upperarm_r', 'X', 80), ('upperarm_l', 'X', 60), ('lowerarm_l', 'X', 40), ('spine_03', 'Z', 15)],
    'crouch': [('thigh_l', 'X', 95), ('thigh_r', 'X', 95), ('calf_l', 'X', -120), ('calf_r', 'X', -120),
               ('spine_01', 'X', 25)],
    'arms_up': [('upperarm_l', 'Y', 110), ('upperarm_r', 'Y', -110)],
    'arms_across': [('upperarm_l', 'Z', -55), ('upperarm_r', 'Z', 55), ('lowerarm_l', 'Z', -40),
                    ('lowerarm_r', 'Z', 40)],
}


def covered_skin(garments, body_obj):
    """Per body vertex: is it under a garment? Either a garment sheet lies within COVER_REACH along the skin normal,
    or the point is inside a garment's volume (5 of 6 horizontal rays meet the garment within 35 cm: legs inside a
    skirt). Hands, neck and face are never counted as covered."""
    gbvh, _ = world_bvh(garments)
    dg = bpy.context.evaluated_depsgraph_get()
    ev = body_obj.evaluated_get(dg)
    me = ev.to_mesh()
    mw = body_obj.matrix_world
    rot = mw.to_3x3().normalized()
    dirs = [Vector((math.cos(a), math.sin(a), 0.0)) for a in [k * math.pi / 3 for k in range(6)]]
    out = []
    for v in me.vertices:
        p = mw @ v.co
        if any(k in BODY_DOM[v.index] for k in PROTECT):
            out.append(False)       # hands (unless gloved); necks are kept by coverage, not by name
            continue
        n = (rot @ v.normal).normalized()
        if gbvh.ray_cast(p - n * 0.01, n, 0.01 + COVER_REACH)[0] is not None:
            out.append(True)
            continue
        out.append(sum(1 for d in dirs if gbvh.ray_cast(p, d, 0.35)[0] is not None) >= 5)
    ev.to_mesh_clear()
    return out


def hide_body(garments, rep):
    """A copy of the body without the skin the outfit covers, for this outfit's looks to wear in place of the body.
    Covered skin is eroded by HIDE_MARGIN_RINGS so skin stays under every cuff, collar and hem."""
    cov = covered_skin(garments, BODY)
    # Skin is hidden only if the garments still cover it in motion (walk and run as well as the rest pose): legs
    # leave a pencil skirt mid-stride, and a hidden leg there would show as a hole.
    moving = {}
    select_only(RIG)
    bpy.ops.object.mode_set(mode='POSE')
    for name in CFG.get('hide_poses', ['walk', 'run']):
        for pb in RIG.pose.bones:
            pb.matrix_basis = Matrix()
        bpy.context.view_layer.update()
        for bn, ax, deg in POSES[name]:
            pb = RIG.pose.bones.get(bn)
            if pb is not None:
                rotate_world(pb, ax, deg)
        posed = covered_skin(garments, BODY)
        moving[name] = sum(1 for a, b in zip(cov, posed) if a and not b)
        cov = [a and b for a, b in zip(cov, posed)]
    for pb in RIG.pose.bones:
        pb.matrix_basis = Matrix()
    bpy.context.view_layer.update()
    bpy.ops.object.mode_set(mode='OBJECT')
    me = BODY.data
    nb = mesh_neighbours(me)
    ok = cov[:]
    for _ in range(HIDE_MARGIN_RINGS):
        ok = [ok[i] and all(ok[j] for j in nb[i]) for i in range(len(ok))]
    hidden = {p.index for p in me.polygons if all(ok[i] for i in p.vertices)}
    hb = BODY.copy()
    hb.data = BODY.data.copy()
    BODY.users_collection[0].objects.link(hb)
    hb.name = CFG.get('body_hide_name', 'SKM_%s_BodyHidden_%s' % (CFG['body'], CFG['id']))
    hb.data.name = hb.name
    bm = bmesh.new()
    bm.from_mesh(hb.data)
    bm.faces.ensure_lookup_table()
    bmesh.ops.delete(bm, geom=[bm.faces[i] for i in sorted(hidden)], context='FACES')
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
    bm.to_mesh(hb.data)
    bm.free()
    hb.data.update()
    regions = {}
    for i in hidden:
        b = BODY_DOM[me.polygons[i].vertices[0]]
        key = b.split('_')[0] if b else '?'
        regions[key] = regions.get(key, 0) + 1
    rep['body_hide'] = {'name': hb.name, 'faces_hidden': len(hidden), 'faces_total': len(me.polygons),
                        'pct_hidden': round(100.0 * len(hidden) / len(me.polygons), 1),
                        'covered_verts': sum(cov), 'uncovered_in_motion': moving,
                        'by_region': dict(sorted(regions.items(), key=lambda x: -x[1]))}
    return hb, hidden


def pose_checks(garments, rep, hidden=frozenset()):
    """Per pose: garment vertices inside VISIBLE skin (skin hidden for the outfit can't show through), and hidden
    skin that the posed garments no longer cover (a hole someone could see)."""
    out = {}
    select_only(RIG)
    bpy.ops.object.mode_set(mode='POSE')
    for name, steps in POSES.items():
        for pb in RIG.pose.bones:
            pb.matrix_basis = Matrix()
        bpy.context.view_layer.update()
        for bn, ax, deg in steps:
            pb = RIG.pose.bones.get(bn)
            if pb is None:
                continue
            # Mirror the axis sense for right-side bones posed about Y or Z, handled in the table by sign.
            rotate_world(pb, ax, deg)
        bvh, _ = world_bvh([BODY])
        dg = bpy.context.evaluated_depsgraph_get()
        res = {}
        for g in garments:
            ev = g.evaluated_get(dg)
            me = ev.to_mesh()
            mw = g.matrix_world
            inside = 0
            where = {}
            for v in me.vertices:
                p = mw @ v.co
                loc, nrm, fi, dist = bvh.find_nearest(p, 0.08)
                if loc is None or fi in hidden:
                    continue
                if (p - loc).dot(nrm) < -0.005:
                    inside += 1
                    b = BODY_DOM[BODY_KD.find(loc)[1]]
                    where[b] = where.get(b, 0) + 1
            n = len(me.vertices)
            ev.to_mesh_clear()
            top = sorted(where.items(), key=lambda x: -x[1])[:5]
            res[g.name] = {'inside_visible_skin': inside, 'pct': round(100.0 * inside / max(1, n), 2), 'top_bones': top}
        if hidden:
            # Exposed holes: hidden faces whose posed centre has no garment over it.
            gbvh, _ = world_bvh(garments)
            bev = BODY.evaluated_get(dg)
            bme = bev.to_mesh()
            bmw = BODY.matrix_world
            brot = bmw.to_3x3().normalized()
            dirs = [Vector((math.cos(a), math.sin(a), 0.0)) for a in [k * math.pi / 3 for k in range(6)]]
            exposed = 0
            for i in hidden:
                poly = bme.polygons[i]
                c = bmw @ poly.center
                nrm = (brot @ poly.normal).normalized()
                if gbvh.ray_cast(c - nrm * 0.01, nrm, 0.01 + COVER_REACH * 1.5)[0] is None:
                    if sum(1 for d in dirs if gbvh.ray_cast(c, d, 0.35)[0] is not None) < 5:
                        exposed += 1
            bev.to_mesh_clear()
            res['hidden_skin_exposed'] = {'faces': exposed, 'pct_of_hidden': round(100.0 * exposed / len(hidden), 2)}
        out[name] = res
    for pb in RIG.pose.bones:
        pb.matrix_basis = Matrix()
    bpy.ops.object.mode_set(mode='OBJECT')
    rep['pose_checks'] = out


# ------------------------------------------------------------------ 6. export + preview
def export(g):
    # The armature OBJECT must be named "Armature": UE's FBX importer drops a root node of that name. Any other name
    # becomes an extra root bone, and importing onto an existing skeleton then REPLACES that skeleton's "root" bone
    # (this broke two shared MetaHuman skeletons on 2026-11-14). The bone tree itself starts at "root".
    select_only(g, RIG)
    path = OUT / (g.name + '.fbx')
    keep = RIG.name
    other = bpy.data.objects.get('Armature')
    if other is not None and other is not RIG:
        other.name = 'Armature_face'
    RIG.name = 'Armature'
    try:
        bpy.ops.export_scene.fbx(filepath=str(path), use_selection=True, object_types={'MESH', 'ARMATURE'},
                                 axis_forward='-Z', axis_up='Y', apply_unit_scale=True, add_leaf_bones=False,
                                 bake_anim=False, mesh_smooth_type='FACE', path_mode='COPY', embed_textures=False)
    finally:
        RIG.name = keep
    return rel(path)


def preview(garments, path):
    scn = bpy.context.scene
    for o in (BODY, FACE):
        for m in (o.data.materials if o else []):
            if m:
                m.diffuse_color = (0.80, 0.62, 0.52, 1.0)
    scn.render.engine = 'BLENDER_WORKBENCH'
    scn.display.shading.light = 'STUDIO'
    scn.display.shading.color_type = 'TEXTURE'
    scn.render.resolution_x, scn.render.resolution_y = 1000, 1500
    scn.render.film_transparent = False
    cam_data = bpy.data.cameras.new('cam')
    cam_data.type = 'ORTHO'
    cam_data.ortho_scale = 1.95
    cam = bpy.data.objects.new('cam', cam_data)
    scn.collection.objects.link(cam)
    scn.camera = cam
    shots = []
    for tag, ang in (('front', 0), ('side', 90), ('back', 180)):
        a = math.radians(ang)
        cam.location = (4 * math.sin(a), -4 * math.cos(a), 0.95)
        cam.rotation_euler = (math.radians(90), 0, a)
        p = str(path).replace('.png', '_%s.png' % tag)
        scn.render.filepath = p
        bpy.ops.render.render(write_still=True)
        shots.append(p)
    return shots


# ------------------------------------------------------------------ run
fitted = []
for piece in CFG['pieces']:
    rep = {'kind': piece['kind'], 'source': piece['fbx']}
    g = load_piece(piece)
    rep['verts_in'] = len(g.data.vertices)
    rep['tris_in'] = sum(len(p.vertices) - 2 for p in g.data.polygons)
    rep['materials'] = [m.name for m in g.data.materials if m]
    slots = {}
    for m in g.data.materials:
        if not m:
            continue
        tex, col = None, None
        if m.use_nodes:
            for n in m.node_tree.nodes:
                if n.type == 'TEX_IMAGE' and n.image and n.image.filepath:
                    tex = bpy.path.abspath(n.image.filepath).replace('\\', '/')
                if n.type == 'BSDF_PRINCIPLED':
                    col = [round(x, 4) for x in n.inputs['Base Color'].default_value[:3]]
        slots[m.name] = {'texture': tex, 'color': col or [round(x, 4) for x in m.diffuse_color[:3]]}
    rep['slots'] = slots
    if piece['kind'] == 'helmet':
        align_helmet(g, rep)
        g.parent = RIG
        g.matrix_parent_inverse = RIG.matrix_world.inverted()
        g.vertex_groups.new(name='head').add(list(range(len(g.data.vertices))), 1.0, 'REPLACE')
        g.modifiers.new('MetaHuman body pose', 'ARMATURE').object = RIG
        rep['weights'] = {'groups': 1, 'rigid': 'head'}
        rep['verts_out'] = len(g.data.vertices)
        fitted.append(g)
        REPORT['pieces'][g.name] = rep
        continue
    bvh, _ = world_bvh([BODY] + ([FACE] if FACE else []))
    if piece.get('coarse', True):
        coarse_fit(g, piece['kind'], rep)
    icp_align(g, bvh, piece['kind'], rep)
    if piece['kind'] in ('upper', 'coat'):
        align_sleeves(g, rep)
        if os.environ.get('FIT_DEBUG_STOP') == 'after_sleeves':
            bpy.ops.wm.save_as_mainfile(filepath=str(OUT / 'debug_after_sleeves.blend'))
            raise SystemExit(0)
    if piece['kind'] == 'feet':
        align_feet(g, rep)
    if piece['kind'] == 'skirt':
        contain_legs(g, rep)
    trim_caps(g, piece['kind'], rep)
    if piece['kind'] == 'feet' and CFG.get('hide_body', True):
        # Rigid boots: the leg inside is hidden, and conforming a shaft to the leg traces the boot's uneven inside.
        rep['conform'] = {'skipped': 'rigid boot (body hiding on)'}
    else:
        conform(g, piece['kind'], [f for f in fitted if REPORT['pieces'][f.name]['kind'] != 'helmet'], rep)
    skin(g, piece['kind'], rep)
    rep['verts_out'] = len(g.data.vertices)
    fitted.append(g)
    REPORT['pieces'][g.name] = rep

wearables = [f for f in fitted if REPORT['pieces'][f.name]['kind'] != 'helmet']
hidden_body, hidden_faces = hide_body(wearables, REPORT) if CFG.get('hide_body', True) and wearables else (None, frozenset())
pose_checks(fitted, REPORT, hidden_faces)
REPORT['fbx'] = [export(g) for g in fitted]
if hidden_body is not None:
    REPORT['body_hide']['fbx'] = export(hidden_body)
    BODY.hide_render = True     # previews show the body each look will actually wear
bpy.context.preferences.filepaths.save_version = 0
blend = OUT / (CFG['id'] + '_Fit.blend')
bpy.ops.wm.save_as_mainfile(filepath=str(blend))
REPORT['blend'] = rel(blend)
try:
    REPORT['previews'] = preview(fitted, OUT / (CFG['id'] + '_preview.png'))
except Exception as e:   # previews are a convenience; never fail the fit on them
    REPORT['preview_error'] = str(e)
(OUT / (CFG['id'] + '_report.json')).write_text(json.dumps(REPORT, indent=2))
print('FIT_REPORT=' + json.dumps(REPORT))
